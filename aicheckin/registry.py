"""平台适配器注册表。真实平台实现后在此注册。"""
from __future__ import annotations

from typing import Callable, Dict

Registry: Dict[str, Callable] = {}


def register(key: str):
    def deco(cls):
        Registry[key] = cls
        return cls
    return deco
