"""决策层: 异常诊断与处置决策。

核心闭环: 感知(信号) -> LLM语义分类 -> 决策(处置动作)。
对应 PPT 的"监控-诊断-决策-自愈"中的 诊断+决策。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ..models import Diagnosis, ErrorKind, HealAction
from .llm import LLMClient, MockLLM
from .parser import PageSignal, ResponseParser


class Diagnostician:
    """根据平台返回的信号 + LLM 语义理解产出处置决策。"""

    def __init__(self, llm: Optional[LLMClient] = None, logger: Optional[logging.Logger] = None) -> None:
        self.llm = llm or MockLLM()
        self.parser = ResponseParser()
        self.log = logger or logging.getLogger("aicheckin.decision")

    def parse_page(self, status_code: int, body: str = "", headers: Dict | None = None) -> PageSignal:
        return self.parser.parse(status_code, body, headers)

    def diagnose(self, signal: PageSignal, context: Dict[str, Any] | None = None) -> Diagnosis:
        """对页面信号做语义分类, 产出处置决策。"""
        context = context or {}

        # 1. 直接用结构化信号做高置信度判定
        if signal.requires_captcha:
            return Diagnosis(
                kind=ErrorKind.CAPTCHA_REQUIRED, action=HealAction.SOLVE_CAPTCHA,
                confidence=0.95, reason="检测到验证码", suggestion=f"识别并提交{signal.captcha_type}验证码")
        if signal.requires_login:
            return Diagnosis(
                kind=ErrorKind.COOKIE_EXPIRED, action=HealAction.RELOGIN,
                confidence=0.93, reason="登录态失效", suggestion="重新登录刷新Cookie")

        # 2. 其余交给 LLM 做语义分类
        #    优先使用完整响应体(raw_error), 再回退到精简状态码文本
        text = (context.get("raw_error") or signal.error_text or signal.page_hint) or "未知异常"
        try:
            raw = self.llm.chat("分类", text)
            data = json.loads(raw) if isinstance(raw, str) else raw
            return Diagnosis(
                kind=ErrorKind(data.get("kind", "unknown")),
                action=HealAction(data.get("action", "alert")),
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reason", ""),
                suggestion=data.get("suggestion", ""),
            )
        except Exception as exc:  # noqa: BLE001
            self.log.warning("LLM 分类失败, 回退启发式: %s", exc)
            return self._fallback(text)

    def _fallback(self, text: str) -> Diagnosis:
        low = text.lower()
        if any(k in text for k in ("验证码", "captcha")):
            return Diagnosis(ErrorKind.CAPTCHA_REQUIRED, HealAction.SOLVE_CAPTCHA, 0.8, "验证码", "识别验证码")
        if any(k in text for k in ("登录", "cookie", "401", "403")):
            return Diagnosis(ErrorKind.COOKIE_EXPIRED, HealAction.RELOGIN, 0.85, "登录态", "重新登录")
        if any(k in text for k in ("加密", "签名", "校验失败")):
            return Diagnosis(ErrorKind.DYNAMIC_ENCRYPTION, HealAction.RE_ANALYZE, 0.8, "加密", "重新分析")
        if any(k in low for k in ("timeout", "500", "502", "503", "超时", "网关", "暂时不可用")):
            return Diagnosis(ErrorKind.TRANSIENT, HealAction.RETRY, 0.8, "瞬时", "重试")
        if any(k in text for k in ("风控", "限制", "封禁")):
            return Diagnosis(ErrorKind.RISK_CONTROL, HealAction.WAIT, 0.75, "风控", "等待/降级")
        return Diagnosis(ErrorKind.UNKNOWN, HealAction.ALERT, 0.4, "未知", "报警人工")

    def summarize_patterns(self, log_lines: List[str]) -> List[Dict[str, Any]]:
        """从日志归纳失败模式(用于持续优化策略)。"""
        try:
            raw = self.llm.chat("归纳", "\n".join(log_lines[-200:]))
            data = json.loads(raw) if isinstance(raw, str) else raw
            return data.get("dominant_patterns", [])
        except Exception:  # noqa: BLE001
            return []
