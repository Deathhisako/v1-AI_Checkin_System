"""核心: 自愈引擎 —— 监控-诊断-决策-自愈 闭环。

对应 PPT 四大痛点的第(4)点"长期稳定运行与自愈":
  传统: 单点定时任务, 无异常处理, 一崩就停、无人知晓。
  AI:   对响应/日志做语义分类, 识别"可重试/需人工/已升级", 自动重试、降级、报警。

每次签到执行流程(单平台):
  感知 -> 决策(诊断) -> 执行 -> 若失败 -> 自愈循环:
      语义分类 -> 选择动作(重试/重登/重析/验证码/降级/等待/报警)
      按 max_attempts 上限退避重试, 最终产出结果。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from ..decision import Diagnostician
from ..models import (
    CheckinResult,
    Diagnosis,
    ErrorKind,
    HealAction,
    HealOutcome,
    TaskStatus,
)
from .platform import CheckinPlatform


class SelfHealEngine:
    def __init__(self, diagnoser: Diagnostician, max_attempts: int = 5,
                 retry_delay: float = 2.0, max_backoff: float = 60.0,
                 allow_relogin: bool = True, allow_reanalyze: bool = True,
                 allow_browser_fallback: bool = True, alert_on_failure: bool = True,
                 logger: Optional[logging.Logger] = None) -> None:
        self.diagnoser = diagnoser
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.max_backoff = max_backoff
        self.allow_relogin = allow_relogin
        self.allow_reanalyze = allow_reanalyze
        self.allow_browser_fallback = allow_browser_fallback
        self.alert_on_failure = alert_on_failure
        self.log = logger or logging.getLogger("aicheckin.self_heal")

    # ---------------- 主入口 ----------------
    def run(self, platform: CheckinPlatform, context: Dict[str, Any] | None = None) -> CheckinResult:
        """对一个平台执行带自愈的完整签到流程。"""
        result = CheckinResult(platform_key=platform.config.key)
        context = context or {}
        start = time.time()
        attempt = 0
        backoff = self.retry_delay
        final_diag: Optional[Diagnosis] = None

        while attempt < self.max_attempts:
            attempt += 1
            result.attempts = attempt
            self.log.info("[%s] 第 %d/%d 次尝试", platform.config.key, attempt, self.max_attempts)

            status, body = self._safe_checkin(platform, context)
            signal = self.diagnoser.parse_page(status, body or "", context.get("headers"))
            self.log.debug("[%s] status=%s 需登录=%s 验证码=%s 成功=%s",
                           platform.config.key, status, signal.requires_login,
                           signal.requires_captcha, signal.sign_success)

            # 成功判定
            if signal.sign_success or (status in (200, 201) and not signal.requires_login and not signal.requires_captcha):
                result.ok = True
                result.status = TaskStatus.RECOVERED if attempt > 1 else TaskStatus.SUCCESS
                result.message = "签到成功" + (f"(第{attempt}次, 已自愈)" if attempt > 1 else "")
                break

            # 诊断: 把完整响应体 + 状态码一起交给 LLM 做语义分类
            raw = f"{signal.error_text} {body or ''}".strip()
            diag = self.diagnoser.diagnose(signal, {"raw_error": raw or signal.page_hint, **context})
            final_diag = diag
            result.heal_events.append(f"诊断: {diag.kind.value}/{diag.action.value} ({diag.reason})")
            self.log.warning("[%s] 诊断: kind=%s action=%s reason=%s",
                             platform.config.key, diag.kind.value, diag.action.value, diag.reason)

            # 执行自愈动作
            outcome = self._heal(platform, diag, context, result)
            if outcome == HealOutcome.NEED_HUMAN:
                break
            if outcome == HealOutcome.EXHAUSTED:
                break
            # 否则继续下一轮尝试
            if diag.action in (HealAction.WAIT, HealAction.RETRY):
                self._sleep(backoff)
                backoff = min(backoff * 2, self.max_backoff)

        result.duration = time.time() - start
        if not result.ok:
            result.status = TaskStatus.FAILED
            result.message = "最终失败: " + (final_diag.reason if final_diag else "未知异常")
            if self.alert_on_failure:
                result.heal_events.append("报警: 已通知人工介入")
                self.log.error("[%s] 最终失败并报警: %s", platform.config.key, result.message)
        self.log.info("[%s] 完成: ok=%s 尝试=%d 耗时=%.2fs", platform.config.key,
                      result.ok, result.attempts, result.duration)
        return result

    # ---------------- 内部 ----------------
    def _safe_checkin(self, platform: CheckinPlatform, context: Dict[str, Any]) -> Tuple[int, str]:
        try:
            return platform.do_checkin(platform.config.cookie, context.get("sign_fn"))
        except Exception as exc:  # noqa: BLE001
            self.log.error("[%s] 执行异常: %s", platform.config.key, exc)
            return 500, f"execution_error: {exc}"

    def _heal(self, platform: CheckinPlatform, diag: Diagnosis,
              context: Dict[str, Any], result: CheckinResult) -> HealOutcome:
        """根据诊断决策执行自愈动作, 返回是否应停止。"""
        action = diag.action
        # 降级到浏览器自动化
        if action == HealAction.FALLBACK_BROWSER or (
                action == HealAction.RE_ANALYZE and not self.allow_reanalyze and self.allow_browser_fallback):
            result.heal_events.append("动作: 降级浏览器自动化")
            return HealOutcome.RETRYING

        if action == HealAction.SOLVE_CAPTCHA:
            result.heal_events.append("动作: 语义验证码识别")
            return HealOutcome.RETRYING

        if action == HealAction.RELOGIN and self.allow_relogin:
            result.heal_events.append("动作: 自动重登刷新Cookie")
            new_cookie = self._safe_relogin(platform)
            if new_cookie:
                platform.config.cookie.update(new_cookie)
                return HealOutcome.RETRYING
            return HealOutcome.EXHAUSTED

        if action == HealAction.RE_ANALYZE and self.allow_reanalyze:
            result.heal_events.append("动作: 重新分析加密/页面逻辑")
            ok = self._safe_reanalyze(platform, context)
            return HealOutcome.RETRYING if ok else HealOutcome.EXHAUSTED

        if action == HealAction.WAIT:
            result.heal_events.append("动作: 风控等待")
            return HealOutcome.RETRYING

        if action in (HealAction.RETRY, HealAction.NONE):
            return HealOutcome.RETRYING

        # ALERT / NEED_HUMAN
        result.heal_events.append("动作: 报警人工介入")
        return HealOutcome.NEED_HUMAN

    def _safe_relogin(self, platform: CheckinPlatform) -> Dict[str, str]:
        try:
            return platform.relogin() or {}
        except Exception as exc:  # noqa: BLE001
            self.log.error("[%s] 重登失败: %s", platform.config.key, exc)
            return {}

    def _safe_reanalyze(self, platform: CheckinPlatform, context: Dict[str, Any]) -> bool:
        try:
            reanalyzer = context.get("reanalyze_fn")
            if reanalyzer:
                return bool(reanalyzer())
            return False
        except Exception as exc:  # noqa: BLE001
            self.log.error("[%s] 重分析失败: %s", platform.config.key, exc)
            return False

    @staticmethod
    def _sleep(seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
