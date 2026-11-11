"""应用层: 任务编排/定时调度。

支持: 单次执行 / 循环执行(间隔) / 固定次数。
真实部署可对接 GitHub Actions cron 或系统任务计划程序(无人值守)。
"""
from __future__ import annotations

import logging
import time
from typing import Callable, List, Optional

logger = logging.getLogger("aicheckin.app.scheduler")


class Scheduler:
    def __init__(self, interval_seconds: float = 60.0, once: bool = False, run_count: int = 0) -> None:
        self.interval = interval_seconds
        self.once = once
        self.run_count = run_count
        self._running = False

    def run(self, job: Callable[[], List], stop_event=None) -> List:
        """运行任务循环, 返回所有结果。"""
        self._running = True
        all_results = []
        runs = 0
        while self._running:
            runs += 1
            logger.info("===== 第 %d 轮任务编排 =====", runs)
            results = job()
            all_results.extend(results)
            if self.once:
                break
            if self.run_count and runs >= self.run_count:
                break
            # 等待下一轮(支持外部停止)
            for _ in range(int(self.interval)):
                if stop_event is not None and stop_event.is_set():
                    self._running = False
                    break
                time.sleep(1)
        return all_results

    def stop(self) -> None:
        self._running = False
