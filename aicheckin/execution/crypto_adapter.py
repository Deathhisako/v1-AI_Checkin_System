"""执行层: 动态加密对抗(参数加密适配)。

传统做法: 静态逆向参数加密并写死, 平台一升级即失效。
本方案: 检测到校验失败 -> 重新分析混淆JS/参数算法 -> 生成新逻辑 -> 验证通过。
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger("aicheckin.execution.crypto")


class CryptoAdapter:
    """参数签名/加密适配器, 支持在算法变化后动态重建。"""

    def __init__(self, algorithm: str = "md5", seed: str = "aicheckin") -> None:
        self.algorithm = algorithm
        self.seed = seed
        self.version = 1
        self._build_fn: Optional[Callable[[Dict], str]] = None
        self._reanalyzer = None
        self.last_reanalyze = 0.0

    def set_builder(self, fn: Callable[[Dict], str]) -> None:
        self._build_fn = fn

    def set_reanalyzer(self, fn: Callable[[str], Callable[[Dict], str]]) -> None:
        """fn: (failed_payload_or_hint) -> 新的签名函数"""
        self._reanalyzer = fn

    def sign(self, params: Dict) -> str:
        """对参数做签名。若平台算法升级, 此函数会被重建。"""
        if self._build_fn is not None:
            return self._build_fn(params)
        # 默认: 简单拼接哈希(演示)
        raw = "&".join(f"{k}={params[k]}" for k in sorted(params)) + self.seed
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def verify(self, params: Dict, expected: str) -> bool:
        return self.sign(params) == expected

    def reanalyze(self, hint: str = "") -> bool:
        """识别到算法变化后, 重新分析并生成新逻辑。"""
        if self._reanalyzer is None:
            logger.warning("未配置加密重分析器, 无法重建")
            return False
        try:
            new_fn = self._reanalyzer(hint)
            if new_fn is None:
                return False
            self._build_fn = new_fn
            self.version += 1
            self.last_reanalyze = time.time()
            logger.info("加密适配器已重建(v%d)", self.version)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("加密重分析失败: %s", exc)
            return False
