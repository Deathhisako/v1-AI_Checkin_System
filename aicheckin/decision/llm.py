"""决策层 LLM 语义理解。

真实接入: 实现 LLMClient 协议并注入(可对接 OpenAI/DashScope/本地部署模型)。
默认 mock 使用规则+启发式模拟"语义理解", 保证无 Key 也能完整跑通演示。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Protocol


class LLMClient(Protocol):
    def chat(self, system: str, user: str) -> str: ...


class MockLLM:
    """内置启发式 LLM: 用于演示与离线运行。

    行为:
      - classify_error: 根据错误文本特征输出 {kind, action, confidence}
      - parse_login: 解析登录页语义, 输出登录方式建议
      - summarize: 从日志归纳失败模式
    """

    def chat(self, system: str, user: str) -> str:
        if "分类" in system or "classify" in system.lower():
            return self._classify(user)
        if "登录" in system or "login" in system.lower():
            return self._login(user)
        if "归纳" in system or "summarize" in system.lower():
            return self._summarize(user)
        return json.dumps({"text": "ok"}, ensure_ascii=False)

    # ---- 语义分类: 错误文本 -> 异常类型 + 处置动作 ----
    def _classify(self, user: str) -> str:
        text = user
        low = text.lower()
        if any(k in text for k in ("验证码", "captcha", "滑块", "滑动")):
            return json.dumps(
                {"kind": "captcha_required", "action": "solve_captcha",
                 "confidence": 0.92, "reason": "检测到验证码拦截", "suggestion": "调用语义验证码识别"}, ensure_ascii=False)
        if any(k in text for k in ("登录", "cookie", "未登录", "401", "403", "会话")):
            return json.dumps(
                {"kind": "cookie_expired", "action": "relogin",
                 "confidence": 0.9, "reason": "登录态失效", "suggestion": "重新登录刷新Cookie"}, ensure_ascii=False)
        if any(k in text for k in ("加密", "签名", "sign", "token", "校验失败", "参数错误")):
            return json.dumps(
                {"kind": "dynamic_encryption", "action": "re_analyze",
                 "confidence": 0.85, "reason": "参数加密规则变化", "suggestion": "重新分析生成新逻辑"}, ensure_ascii=False)
        if any(k in low for k in ("timeout", "connect", "connection", "500", "502", "503", "网络", "超时", "网关", "暂时不可用")):
            return json.dumps(
                {"kind": "transient", "action": "retry",
                 "confidence": 0.8, "reason": "瞬时网络/服务抖动", "suggestion": "退避后重试"}, ensure_ascii=False)
        if any(k in text for k in ("风控", "限制", "频繁", "block", "ban", "封禁")):
            return json.dumps(
                {"kind": "risk_control", "action": "wait",
                 "confidence": 0.75, "reason": "风控/频率限制", "suggestion": "等待或降级浏览器自动化"}, ensure_ascii=False)
        if any(k in text for k in ("版本", "升级", "改版", "接口变更")):
            return json.dumps(
                {"kind": "upgraded", "action": "re_analyze",
                 "confidence": 0.7, "reason": "平台升级/改版", "suggestion": "重新分析接口"}, ensure_ascii=False)
        return json.dumps(
            {"kind": "unknown", "action": "alert",
             "confidence": 0.5, "reason": "未能归类", "suggestion": "报警人工介入"}, ensure_ascii=False)

    # ---- 登录页语义解析 ----
    def _login(self, user: str) -> str:
        text = user
        method = "qrcode" if any(k in text for k in ("扫码", "二维码", "qr")) else "password"
        if any(k in text for k in ("短信", "验证码")):
            method = "sms"
        return json.dumps({"method": method, "confidence": 0.8}, ensure_ascii=False)

    # ---- 日志归纳 ----
    def _summarize(self, user: str) -> str:
        fails = re.findall(r"(?:失败|error|failed)[:：]?\s*([^;\n]+)", user)
        counter: Dict[str, int] = {}
        for f in fails:
            counter[f.strip()] = counter.get(f.strip(), 0) + 1
        top = sorted(counter.items(), key=lambda x: -x[1])[:3]
        return json.dumps(
            {"dominant_patterns": [{"pattern": k, "count": v} for k, v in top]},
            ensure_ascii=False)


def build_llm(kind: str) -> LLMClient:
    if kind in ("mock", ""):
        return MockLLM()
    # 真实接入: 在此返回你的 LLMClient 实现
    raise NotImplementedError(f"LLM provider '{kind}' 需自行实现")
