"""执行层: 浏览器自动化降级(Playwright/Selenium 封装)。

当请求直签被风控/加密阻断时, 回退到真实浏览器自动化执行, 保证任务不中断。
默认提供接口与 mock; 真实接入时注入 playwright 引擎。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Protocol

logger = logging.getLogger("aicheckin.execution.browser")


class BrowserEngine(Protocol):
    def goto(self, url: str) -> None: ...
    def click(self, selector: str) -> None: ...
    def fill(self, selector: str, value: str) -> None: ...
    def screenshot(self) -> Any: ...
    def close(self) -> None: ...


class MockBrowser:
    """无真实浏览器时的模拟引擎(演示用)。"""

    def __init__(self) -> None:
        self.page_text = "模拟页面: 签到成功"

    def goto(self, url: str) -> None:
        logger.info("[browser-mock] goto %s", url)

    def click(self, selector: str) -> None:
        logger.info("[browser-mock] click %s", selector)

    def fill(self, selector: str, value: str) -> None:
        logger.info("[browser-mock] fill %s=%s", selector, value)

    def screenshot(self) -> Any:
        return {"type": "text", "text": "签到成功"}

    def close(self) -> None:
        logger.info("[browser-mock] closed")


class BrowserFallback:
    """降级执行器: 请求直签失败时切换到浏览器自动化。"""

    def __init__(self, engine_factory: Callable[[], BrowserEngine] | None = None) -> None:
        self._factory = engine_factory or MockBrowser

    def execute(self, task: Callable[[BrowserEngine], Any]) -> Any:
        engine = self._factory()
        try:
            return task(engine)
        finally:
            engine.close()
