"""应用层: 编排器 —— 把感知/决策/执行/自愈串成流水线。

流水线: 对每个平台 -> 感知(页面/验证码) -> 决策(诊断) -> 执行(签到) -> 自愈。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..config import AppConfig
from ..core import SelfHealEngine
from ..decision import Diagnostician
from ..models import CheckinResult, Platform
from ..perception import MockCaptchaSolver, MockOCR, MockVision, build_captcha, build_ocr, build_vision
from .notifier import Notifier


class Runner:
    """系统编排器。"""

    def __init__(self, config: AppConfig, platforms: List[Platform],
                 diagnoser: Optional[Diagnostician] = None,
                 self_heal: Optional[SelfHealEngine] = None,
                 logger: Optional[logging.Logger] = None,
                 platform_adapters: Optional[Dict[str, Any]] = None) -> None:
        self.config = config
        self.platforms = platforms
        self.log = logger or logging.getLogger("aicheckin.runner")

        # 组装三层
        self.diagnoser = diagnoser or Diagnostician(logger=self.log)
        sh = config.self_heal
        self.self_heal = self_heal or SelfHealEngine(
            diagnoser=self.diagnoser,
            max_attempts=sh["max_attempts"],
            retry_delay=sh["retry_delay"],
            max_backoff=sh["max_backoff"],
            allow_relogin=sh["relogin_on_cookie"],
            allow_reanalyze=sh["reanalyze_on_encryption"],
            allow_browser_fallback=sh["fallback_browser"],
            alert_on_failure=sh["alert_on_failure"],
            logger=self.log,
        )
        n = config.notification
        self.notifier = Notifier(enabled=n["enabled"], channel=n["channel"], webhook_url=n["webhook_url"])

        # 感知层 provider
        ai = config.ai
        self.ocr = build_ocr(ai["ocr_provider"])
        self.vision = build_vision(ai["vision_provider"])
        self.captcha = build_captcha(ai["vision_provider"] or "mock")

        # 平台适配器注册表(真实平台实现); 默认使用注册到 Registry 的实现
        from ..registry import Registry
        self.registry = Registry
        self.platform_adapters = platform_adapters or {}
        self._adapter_cache: Dict[str, Any] = {}  # 适配器单例缓存(状态跨轮持久)

    def run_once(self) -> List[CheckinResult]:
        """执行一轮: 遍历所有启用的平台。"""
        results: List[CheckinResult] = []
        for pf in self.platforms:
            if not pf.enabled:
                continue
            adapter = self._get_adapter(pf)
            if adapter is None:
                self.log.warning("平台 %s 无适配器, 跳过", pf.key)
                continue
            ctx: Dict[str, Any] = {
                "sign_fn": adapter.build_sign_fn() if hasattr(adapter, "build_sign_fn") else None,
                "reanalyze_fn": adapter.reanalyze if hasattr(adapter, "reanalyze") else None,
            }
            result = self.self_heal.run(adapter, ctx)
            self.notifier.notify(result)
            results.append(result)
        return results

    def _get_adapter(self, pf: Platform):
        # 1. 显式注入的适配器
        if pf.key in self.platform_adapters:
            return self.platform_adapters[pf.key]
        # 2. 缓存单例(保证 Cookie/加密状态跨轮持久, 模拟真实长期运行)
        if pf.key in self._adapter_cache:
            return self._adapter_cache[pf.key]
        # 3. 从 Registry 按平台 key 构造
        factory = (self.registry.get(pf.key)
                   or self.registry.get(pf.type.value)
                   or self.registry.get("demo"))
        if factory is None:
            return None
        adapter = factory(pf, self)
        self._adapter_cache[pf.key] = adapter
        return adapter
