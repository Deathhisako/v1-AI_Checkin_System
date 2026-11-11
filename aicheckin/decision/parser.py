"""决策层: 页面/响应语义解析。

从 HTTP 响应与页面 DOM 语义中提取关键信号:
  - 是否要求登录
  - 是否出现验证码
  - 签到结果/是否成功
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict


@dataclass
class PageSignal:
    requires_login: bool = False
    requires_captcha: bool = False
    sign_success: bool = False
    sign_done_already: bool = False
    error_text: str = ""
    captcha_type: str = "text"
    page_hint: str = ""


class ResponseParser:
    """基于响应状态码 + 文本特征的语义解析(可对接真实页面解析库)。"""

    def parse(self, status_code: int, body: str = "", headers: Dict | None = None) -> PageSignal:
        sig = PageSignal()
        low = (body or "").lower()

        # 登录态判断: 状态码 + 页面语义
        if status_code in (401, 403):
            sig.requires_login = True
            sig.error_text = f"HTTP {status_code} 未授权/禁止"
        elif any(k in low for k in ("未登录", "请先登录", "login.php", "signin", "登录后才能", "登录后")):
            sig.requires_login = True
            sig.page_hint = "页面包含登录提示"

        # 验证码判断
        if any(k in low for k in ("验证码", "captcha", "滑块", "滑动", "点选")):
            sig.requires_captcha = True
            if "滑块" in low or "滑动" in low:
                sig.captcha_type = "slider"
            elif "点选" in low or "点击" in low:
                sig.captcha_type = "semantic"
            else:
                sig.captcha_type = "text"

        # 签到结果判断
        if any(k in low for k in ("签到成功", "已签到", "打卡成功", "连续签到", "奖励已领取")):
            sig.sign_success = True
        if any(k in low for k in ("已签到", "今日已签", "重复签到", "已经签到")):
            sig.sign_done_already = True

        if not sig.error_text and status_code >= 400:
            sig.error_text = f"HTTP {status_code}"
        return sig
