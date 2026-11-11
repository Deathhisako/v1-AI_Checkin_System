"""领域实体: 平台、任务、结果、事件。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import ErrorKind, HealAction, PlatformType, TaskStatus


def _now() -> float:
    return time.time()


@dataclass
class Platform:
    """一个签到平台的抽象描述(用户配置)。"""
    key: str
    name: str
    type: PlatformType = PlatformType.CUSTOM
    enabled: bool = True
    # 登录凭据(敏感信息建议由密钥环管理)
    username: str = ""
    password: str = ""
    cookie: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckinResult:
    """单次签到执行结果。"""
    platform_key: str
    ok: bool = False
    status: TaskStatus = TaskStatus.FAILED
    message: str = ""
    attempts: int = 0
    heal_events: List[str] = field(default_factory=list)
    duration: float = 0.0
    timestamp: float = field(default_factory=_now)
    detail: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.ok


@dataclass
class Diagnosis:
    """决策层对一次异常的诊断结果。"""
    kind: ErrorKind = ErrorKind.UNKNOWN
    action: HealAction = HealAction.NONE
    confidence: float = 0.0
    reason: str = ""
    suggestion: str = ""


@dataclass
class Event:
    """系统事件: 用于日志/监控/通知。"""
    ts: float = field(default_factory=_now)
    level: str = "info"          # debug/info/warning/error
    source: str = ""             # 哪个模块
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
