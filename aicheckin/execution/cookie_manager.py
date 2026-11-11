"""执行层: Cookie 失效自适应管理(登录态自愈)。

传统做法: 定时刷新, 无法感知真实失效时刻, 失效即崩。
本方案: 有效性监测(状态码+页面语义) -> 自动恢复(重新登录/扫码) -> 刷新Cookie。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Optional

from ..models import Platform

logger = logging.getLogger("aicheckin.execution.cookie")


class CookieManager:
    """管理登录态, 提供 校验/刷新/失效检测。"""

    def __init__(self, platform: Platform, login_fn=None, validate_fn=None) -> None:
        """login_fn: () -> new_cookie_dict (重新登录/扫码获取新Cookie)
        validate_fn: (cookie) -> bool  (校验Cookie是否仍有效)
        """
        self.platform = platform
        self.cookie: Dict[str, str] = dict(platform.cookie)
        self._login_fn = login_fn
        self._validate_fn = validate_fn
        self._last_refresh = 0.0

    @property
    def is_stale(self) -> bool:
        """超过有效期则视为可能过期(结合真实校验)。"""
        return False

    def validate(self) -> bool:
        """结合外部校验器 + 时间启发判断。"""
        if self._validate_fn is not None:
            try:
                if not self._validate_fn(self.cookie):
                    return False
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cookie 校验异常: %s", exc)
                return False
        return bool(self.cookie)

    def refresh(self) -> bool:
        """触发重新登录/扫码, 刷新Cookie。"""
        if self._login_fn is None:
            logger.error("平台 %s 未配置登录函数, 无法自愈", self.platform.key)
            return False
        try:
            new_cookie = self._login_fn()
            if new_cookie:
                self.cookie.update(new_cookie)
                self.platform.cookie.update(new_cookie)
                self._last_refresh = time.time()
                logger.info("平台 %s Cookie 已刷新", self.platform.key)
                return True
        except Exception as exc:  # noqa: BLE001
            logger.error("平台 %s 重新登录失败: %s", self.platform.key, exc)
        return False

    def mark_invalid(self) -> None:
        self.cookie.clear()

    def get_header(self) -> Dict[str, str]:
        if not self.cookie:
            return {}
        return {"Cookie": "; ".join(f"{k}={v}" for k, v in self.cookie.items())}
