"""核心: 平台抽象接口。

真实平台(论坛/App/PT站/校园打卡)通过实现 Platform 接入系统。
每个平台需要实现四个动作: 校验登录态 / 登录(刷新Cookie) / 执行签到 / 解析响应。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, Tuple

from ..models import Platform as PlatformConfig


class CheckinPlatform(Protocol):
    """签到平台接口。"""

    config: PlatformConfig

    def validate_login(self, cookie: Dict[str, str]) -> bool:
        """校验 Cookie 是否仍有效(状态码+页面语义)。"""

    def relogin(self) -> Dict[str, str]:
        """重新登录/扫码, 返回新 Cookie。"""

    def do_checkin(self, cookie: Dict[str, str], sign_fn=None) -> Tuple[int, str]:
        """执行签到, 返回 (status_code, body)。"""

    def solve_captcha(self, captcha: Dict[str, Any], sign_fn=None) -> Dict[str, Any]:
        """识别验证码并返回可提交的表单字段。"""

    def analyze_page(self, body: str) -> Dict[str, Any]:
        """页面语义分析(可选扩展)。"""
