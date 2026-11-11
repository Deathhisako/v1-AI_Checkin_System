"""应用层: 结果通知(webhook/console)。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from ..models import CheckinResult

logger = logging.getLogger("aicheckin.app.notifier")


class Notifier:
    def __init__(self, enabled: bool = False, channel: str = "console", webhook_url: str = "") -> None:
        self.enabled = enabled
        self.channel = channel
        self.webhook_url = webhook_url

    def notify(self, result: CheckinResult) -> None:
        if not self.enabled:
            return
        payload = {
            "event": "checkin_result",
            "platform": result.platform_key,
            "ok": result.ok,
            "status": result.status.value,
            "attempts": result.attempts,
            "duration": round(result.duration, 2),
            "message": result.message,
            "heal_events": result.heal_events,
        }
        if self.channel == "webhook" and self.webhook_url:
            try:
                import requests
                requests.post(self.webhook_url, json=payload, timeout=10)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Webhook 通知失败: %s", exc)
        else:
            logger.info("通知: %s", json.dumps(payload, ensure_ascii=False))
