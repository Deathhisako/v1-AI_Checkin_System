"""真实平台接入模板。

以某个论坛/PT站为例, 展示如何把一个真实签到平台接入本系统。
接入步骤:
  1. 复制本文件为 my_forum.py, 实现四个方法;
  2. @register("my_forum") 注册, 类型与 config 中 platforms[].type 对应;
  3. 配置 config/config.yaml 添加平台;
  4. 真实 LLM/OCR/视觉: 配置 ai.llm_provider 等, 并在 build_* 工厂注入。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

from ..execution import BrowserFallback, CookieManager, CryptoAdapter
from ..models import Platform as PlatformConfig
from ..registry import register

logger = logging.getLogger("aicheckin.platforms.template")


@register("template")
class TemplatePlatform:
    """真实平台模板。方法体为示意, 需按目标平台实现。"""

    BASE_URL = "https://example.com"

    def __init__(self, config: PlatformConfig, runner=None) -> None:
        self.config = config
        self.runner = runner
        # 1. Cookie 管理(自愈)
        self.cookie_mgr = CookieManager(config, login_fn=self.relogin,
                                        validate_fn=self.validate_login)
        # 2. 加密适配(自愈): 设置签名函数与重分析器
        self.crypto = CryptoAdapter(algorithm="md5", seed="platform-secret")
        self.crypto.set_builder(self._build_sign)
        self.crypto.set_reanalyzer(self._reanalyze)
        # 3. 浏览器降级
        self.browser = BrowserFallback()

    # ---------- 签名(加密) ----------
    def _build_sign(self, params: Dict) -> str:
        import hashlib
        raw = "&".join(f"{k}={params[k]}" for k in sorted(params)) + "platform-secret"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _reanalyze(self, hint: str = "") -> Optional[Callable[[Dict], str]]:
        """LLM辅助逆向: 平台升级后生成新签名逻辑。"""
        return self._build_sign

    def build_sign_fn(self) -> Callable[[Dict], str]:
        return self.crypto.sign

    def reanalyze(self) -> bool:
        return self.crypto.reanalyze("签名校验失败")

    # ---------- 登录态 ----------
    def validate_login(self, cookie: Dict[str, str]) -> bool:
        # 真实: 请求一个需要登录的接口, 看状态码/页面语义
        return bool(cookie)

    def relogin(self) -> Dict[str, str]:
        # 真实: 用账号密码/扫码/短信登录, 返回新Cookie
        # 可结合 LLM 解析登录页提示选择方式:
        #   self.runner.diagnoser.llm.chat("登录", "页面提示...") -> {"method": ...}
        return {"session": "new-session"}

    # ---------- 核心签到 ----------
    def do_checkin(self, cookie: Dict[str, str], sign_fn=None) -> Tuple[int, str]:
        # 真实: 构造带签名的请求调用签到接口
        #   参数用 sign_fn(params) 签名; 失败时把响应体交给系统语义分类
        sign = sign_fn or self.crypto.sign
        params = {"action": "checkin", "uid": cookie.get("uid", "")}
        params["sign"] = sign(params)
        # resp = requests.post(f"{self.BASE_URL}/api/checkin", params=params,
        #                      headers=self.cookie_mgr.get_header())
        # return resp.status_code, resp.text
        return 200, "签到成功"

    def solve_captcha(self, captcha: Dict[str, Any], sign_fn=None) -> Dict[str, Any]:
        # 真实: 调用感知层 self.runner.captcha.solve(image, instruction)
        return {"ok": True, "answer": "captcha-ok"}

    def analyze_page(self, body: str) -> Dict[str, Any]:
        return {"text": body[:500]}
