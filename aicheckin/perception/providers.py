"""感知层 Provider: OCR / 视觉大模型 / 验证码识别。

设计: 提供 mock 实现(可离线运行演示)与真实实现接口。
真实接入时: 实现对应 Protocol 并注入, 或配置 ai.ocr_provider / vision_provider。
"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, Tuple


class OCRProvider(Protocol):
    def recognize(self, image: Any) -> List[str]: ...


class VisionProvider(Protocol):
    """视觉语言模型: 语义匹配(如"点击所有红绿灯")。"""

    def match_semantic(self, instruction: str, candidates: List[Any]) -> List[int]:
        """根据语义指令从候选图片中选出匹配的索引列表。"""


class CaptchaSolver(Protocol):
    def solve(self, image: Any, instruction: str = "") -> Dict[str, Any]:
        """返回 {type, answer, target_indices, confidence}。"""


class MockOCR:
    """内置启发式 OCR: 无真实依赖时可用的降级实现。"""

    def recognize(self, image: Any) -> List[str]:
        # mock: 假设图片是 dict 中带 text 字段
        if isinstance(image, dict) and "text" in image:
            return [str(image["text"])]
        return []


class MockVision:
    """内置启发式语义匹配: 基于标签相似度(演示用)。

    真实接入: 替换为 CLIP / Qwen-VL / InternVL 等视觉语言模型。
    """

    def match_semantic(self, instruction: str, candidates: List[Any]) -> List[int]:
        keywords = _extract_keywords(instruction)
        hits: List[int] = []
        for idx, cand in enumerate(candidates):
            tags = cand.get("tags", []) if isinstance(cand, dict) else []
            labels = " ".join(str(t) for t in tags)
            if any(k in labels for k in keywords):
                hits.append(idx)
        return hits


def _extract_keywords(instruction: str) -> List[str]:
    """从自然语言指令中提取关键名词(演示启发式)。

    真实方案: 交由 LLM 做语义解析, 而非关键词匹配。
    """
    drop = "点击所有包含的图片中请找出与的红色绿色蓝色灯路滑块的旋转角度"
    keep = []
    for ch in instruction:
        if ch not in drop and ch not in (" ", ",", "，", "、", "。"):
            keep.append(ch)
    return ["".join(keep)] if keep else []


class MockCaptchaSolver:
    """内置启发式验证码识别。

    模拟三类: text(文字)、slider(滑块)、semantic(语义点选)。
    """

    def solve(self, image: Any, instruction: str = "") -> Dict[str, Any]:
        if isinstance(image, dict):
            ctype = image.get("type", "text")
            if ctype == "slider":
                return {"type": "slider", "answer": image.get("gap", 42), "confidence": 0.9}
            if ctype == "semantic":
                indices = MockVision().match_semantic(instruction, image.get("candidates", []))
                return {"type": "semantic", "target_indices": indices, "confidence": 0.8}
            return {"type": "text", "answer": str(image.get("text", "")), "confidence": 0.9}
        return {"type": "text", "answer": "", "confidence": 0.0}


def build_ocr(kind: str) -> OCRProvider:
    if kind in ("mock", ""):
        return MockOCR()
    raise NotImplementedError(f"OCR provider '{kind}' 需自行实现")


def build_vision(kind: str) -> VisionProvider:
    if kind in ("mock", ""):
        return MockVision()
    raise NotImplementedError(f"Vision provider '{kind}' 需自行实现")


def build_captcha(kind: str) -> CaptchaSolver:
    if kind in ("mock", ""):
        return MockCaptchaSolver()
    raise NotImplementedError(f"Captcha provider '{kind}' 需自行实现")
