"""演示平台实现: 可控地制造四大痛点, 验证 AI 自愈。"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import Any, Callable, Dict, Optional, Tuple

from ..execution import BrowserFallback, CookieManager, CryptoAdapter
from ..models import Platform as PlatformConfig
from ..registry import register

logger = logging.getLogger("aicheckin.demo")


@register("demo")
class DemoPlatform:
    """一个模拟的真实签到平台。

    场景参数(extra):
        cookie_ttl:      Cookie 有效签到次数(过期后触发重登)
        encrypt_ttl:     加密算法稳定签到次数(过后升级)
        captcha_rate:    出现验证码概率 [0,1]
        transient_rate:  瞬时故障概率 [0,1]
        risk_rate:       风控概率 [0,1]
    """

    def __init__(self, config: PlatformConfig, runner=None) -> None:
        self.config = config
        self.runner = runner
        # 用平台 key 作种子, 保证实验可复现(论文数据可追溯)
        self._rng = random.Random(f"aicheckin::{config.key}")
        # 内部状态
        self._sign_count = 0
        self._cookie_ttl = int(config.extra.get("cookie_ttl", 5))
        self._encrypt_ttl = int(config.extra.get("encrypt_ttl", 7))
        self._captcha_rate = float(config.extra.get("captcha_rate", 0.3))
        self._transient_rate = float(config.extra.get("transient_rate", 0.15))
        self._risk_rate = float(config.extra.get("risk_rate", 0.05))
        self._cookie_remaining = self._cookie_ttl
        self._encrypt_remaining = self._encrypt_ttl
        self._cookie_secret = "cookie-secret-v1"
        self._sign_key = "aicheckin-demo-v1"

        self.cookie_mgr = CookieManager(config, login_fn=self.relogin, validate_fn=self.validate_login)
        self.crypto = CryptoAdapter(algorithm="md5", seed=self._sign_key)
        self.crypto.set_builder(self._make_sign_fn(self._sign_key))
        self.crypto.set_reanalyzer(self._reanalyze)
        self.browser = BrowserFallback()

    # ---------- 签名(模拟加密) ----------
    def _make_sign_fn(self, key: str) -> Callable[[Dict], str]:
        def fn(params: Dict) -> str:
            raw = "&".join(f"{k}={params[k]}" for k in sorted(params)) + key
            return hashlib.md5(raw.encode("utf-8")).hexdigest()
        return fn

    def _reanalyze(self, hint: str = "") -> Optional[Callable[[Dict], str]]:
        """模拟 LLM 辅助逆向: 识别到新算法后生成新逻辑。"""
        new_key = self._sign_key + "-rev" + str(self.crypto.version)
        self._sign_key = new_key
        self._encrypt_remaining = self._encrypt_ttl
        logger.info("[%s] 重新分析生成新签名逻辑(密钥轮换)", self.config.key)
        return self._make_sign_fn(new_key)

    def build_sign_fn(self) -> Callable[[Dict], str]:
        return self.crypto.sign

    def reanalyze(self) -> bool:
        return self.crypto.reanalyze("签名校验失败")

    # ---------- 登录态 ----------
    def validate_login(self, cookie: Dict[str, str]) -> bool:
        return bool(cookie) and self._cookie_remaining > 0

    def relogin(self) -> Dict[str, str]:
        logger.info("[%s] 执行重新登录/扫码, 获取新Cookie", self.config.key)
        self._cookie_remaining = self._cookie_ttl
        return {"session": f"new-session-{self._sign_count}", "uid": str(self._sign_count)}

    # ---------- 核心签到 ----------
    def do_checkin(self, cookie: Dict[str, str], sign_fn=None) -> Tuple[int, str]:
        self._sign_count += 1
        sign = sign_fn or self.crypto.sign

        # 1. 登录态失效
        if self._cookie_remaining <= 0 or not cookie:
            self._cookie_remaining = max(0, self._cookie_remaining - 1)
            return 401, "未登录: 会话已过期, 请重新登录"

        # 2. 动态加密升级
        self._encrypt_remaining -= 1
        if self._encrypt_remaining <= 0:
            # 平台升级签名算法 -> 旧逻辑产生的签名校验失败
            bad = self._make_sign_fn("platform-new-v2")({"action": "checkin", "uid": cookie.get("uid", "")})
            return 400, f"参数校验失败: 签名不正确(期望新算法), got={bad}"

        # 3. 验证码拦截
        if self._rng.random() < self._captcha_rate:
            ctype = "slider" if self._rng.random() < 0.5 else "semantic"
            return 200, f"需要{('滑块' if ctype == 'slider' else '点选语义')}验证码, 请完成验证"

        # 4. 瞬时故障 / 风控
        if self._rng.random() < self._transient_rate:
            return 502, "网关超时: 上游服务暂时不可用"
        if self._rng.random() < self._risk_rate:
            return 403, "风控拦截: 操作过于频繁, 请稍后再试"

        # 5. 成功
        self._cookie_remaining -= 1
        return 200, "签到成功: 今日积分已到账"

    # ---------- 验证码识别(感知层注入) ----------
    def solve_captcha(self, captcha: Dict[str, Any], sign_fn=None) -> Dict[str, Any]:
        # 实际场景: 调用感知层 captcha solver + 视觉大模型
        return {"ok": True, "answer": "demo-captcha-ok"}

    def analyze_page(self, body: str) -> Dict[str, Any]:
        return {"text": body[:200]}

    # ---------- 便捷 ----------
    @property
    def state(self) -> Dict[str, Any]:
        return {
            "sign_count": self._sign_count,
            "cookie_remaining": self._cookie_remaining,
            "encrypt_remaining": self._encrypt_remaining,
            "crypto_version": self.crypto.version,
            "sign_key": self._sign_key,
        }
