"""结构化日志 + 事件总线。决策层依赖它做语义分类与诊断。"""
from __future__ import annotations

import json
import logging
import sys
from collections import deque
from pathlib import Path
from typing import Callable, Deque, List, Optional

from .models import Event

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class EventBus:
    """事件总线: 供监控/通知/实验数据采集订阅。"""

    def __init__(self) -> None:
        self._subscribers: List[Callable[[Event], None]] = []
        self._buffer: Deque[Event] = deque(maxlen=2000)

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        self._subscribers.append(fn)

    def publish(self, event: Event) -> None:
        self._buffer.append(event)
        for fn in list(self._subscribers):
            try:
                fn(event)
            except Exception:  # noqa: BLE001
                pass

    def drain(self) -> List[Event]:
        return list(self._buffer)


def build_logger(name: str, log_dir: Optional[str] = None) -> tuple[logging.Logger, EventBus]:
    """构造带文件输出的 logger 与全局事件总线。"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FMT))
    logger.addHandler(console)

    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(Path(log_dir) / "aicheckin.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT))
        logger.addHandler(fh)

    bus = EventBus()

    def _bridge(record: logging.LogRecord) -> None:
        bus.publish(Event(level=record.levelname.lower(), source=name, message=record.getMessage()))

    # 桥接日志 -> 事件总线
    logger.addFilter(_make_filter(_bridge))
    return logger, bus


class _make_filter:
    def __init__(self, fn: Callable[[logging.LogRecord], None]) -> None:
        self._fn = fn

    def filter(self, record: logging.LogRecord) -> bool:
        self._fn(record)
        return True


def json_line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
