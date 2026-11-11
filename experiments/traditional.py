"""传统方案: 硬编码脚本(对照组)。

模拟 PPT 描述的现有方案痛点:
  - 固定Cookie, 过期即崩, 无法感知失效时刻
  - 固定加密逻辑写死, 平台升级即报废
  - 固定模板OCR/固定坐标, 验证码一变即失效
  - 无异常处理, 一崩就停, 无人知晓
"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import Any, Dict, Tuple

log = logging.getLogger("experiments.traditional")


class TraditionalScript:
    """无 AI 的硬编码签到脚本。与 DemoPlatform 使用相同干扰场景。"""

    def __init__(self, platform_key: str, cookie_ttl: int, encrypt_ttl: int,
                 captcha_rate: float, transient_rate: float, risk_rate: float,
                 fixed_key: str = "hardcoded-v1") -> None:
        self.platform_key = platform_key
        self.cookie = {"session": "hardcoded-session", "uid": "1"}
        self._cookie_ttl = cookie_ttl
        self._encrypt_ttl = encrypt_ttl
        self._captcha_rate = captcha_rate
        self._transient_rate = transient_rate
        self._risk_rate = risk_rate
        self._fixed_key = fixed_key
        self._cookie_remaining = cookie_ttl
        self._encrypt_remaining = encrypt_ttl
        self._rng = random.Random(42)
        self._sign_count = 0
        self.needs_human = 0   # 统计需要人工介入次数

    def _sign(self, params: Dict) -> str:
        # 写死的加密逻辑: 一旦平台升级, 此函数失效且无法感知
        raw = "&".join(f"{k}={params[k]}" for k in sorted(params)) + self._fixed_key
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def checkin(self) -> Tuple[bool, str]:
        self._sign_count += 1
        # 1. Cookie 过期(无法感知, 直接失败)
        if self._cookie_remaining <= 0:
            self.needs_human += 1
            return False, "未登录: 会话已过期(需人工重新登录)"

        # 2. 加密升级(写死逻辑失效, 无法重建)
        self._encrypt_remaining -= 1
        if self._encrypt_remaining <= 0:
            self.needs_human += 1
            return False, "参数校验失败: 平台加密算法已升级, 脚本报废"

        # 3. 验证码(固定OCR无法识别, 直接失败)
        if self._rng.random() < self._captcha_rate:
            self.needs_human += 1
            return False, "需要滑块/语义验证码(固定OCR无法应对)"

        # 4. 瞬时故障(无重试/自愈, 直接失败)
        if self._rng.random() < self._transient_rate:
            return False, "网关超时(无重试机制)"

        # 5. 风控(无应对)
        if self._rng.random() < self._risk_rate:
            self.needs_human += 1
            return False, "风控拦截(需人工处理)"

        self._cookie_remaining -= 1
        return True, "签到成功"

    @property
    def state(self) -> Dict[str, Any]:
        return {"sign_count": self._sign_count, "needs_human": self.needs_human}
