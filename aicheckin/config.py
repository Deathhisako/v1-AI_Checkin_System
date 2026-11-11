"""配置加载: 应用配置 + 平台配置。支持 YAML / JSON / dict。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from .models import Platform, PlatformType

DEFAULTS: Dict[str, Any] = {
    "log_dir": "logs",
    "scheduler": {"interval_seconds": 60, "once": False, "run_count": 0},
    "self_heal": {
        "max_attempts": 5,          # 单次签到最大尝试次数
        "retry_delay": 2.0,         # 基础退避(秒)
        "max_backoff": 60.0,        # 最大退避
        "relogin_on_cookie": True,
        "reanalyze_on_encryption": True,
        "fallback_browser": True,
        "alert_on_failure": True,
    },
    "ai": {
        # 真实接入时填写; 为空则使用内置"规则+启发式"模拟语义决策
        "llm_provider": "mock",      # mock | openai | dashscope | custom
        "llm_api_key": "",
        "llm_model": "",
        "ocr_provider": "mock",      # mock | paddleocr | custom
        "vision_provider": "mock",   # mock | clip | custom
    },
    "notification": {
        "enabled": False,
        "channel": "webhook",        # webhook | email | console
        "webhook_url": "",
    },
}


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class AppConfig:
    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = _merge(DEFAULTS, data or {})

    @property
    def log_dir(self) -> str:
        return self.data["log_dir"]

    @property
    def scheduler(self) -> Dict[str, Any]:
        return self.data["scheduler"]

    @property
    def self_heal(self) -> Dict[str, Any]:
        return self.data["self_heal"]

    @property
    def ai(self) -> Dict[str, Any]:
        return self.data["ai"]

    @property
    def notification(self) -> Dict[str, Any]:
        return self.data["notification"]

    @classmethod
    def load(cls, path: str | Path) -> "AppConfig":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() in (".yaml", ".yml"):
            if yaml is None:
                raise RuntimeError("需要安装 PyYAML 才能读取 YAML 配置")
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
        return cls(data)


def _parse_platforms(data: Dict[str, Any]) -> List[Platform]:
    platforms: List[Platform] = []
    for item in data.get("platforms", []):
        platforms.append(
            Platform(
                key=item["key"],
                name=item.get("name", item["key"]),
                type=PlatformType(item.get("type", "custom")),
                enabled=item.get("enabled", True),
                username=item.get("username", ""),
                password=item.get("password", ""),
                cookie=item.get("cookie", {}),
                extra=item.get("extra", {}),
            )
        )
    return platforms


def load_platforms(config_path: str | Path) -> List[Platform]:
    """从配置文件加载平台列表。"""
    p = Path(config_path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    return _parse_platforms(data)


def load_platforms_from_env() -> List[Platform]:
    """从环境变量加载平台(用于 GitHub Actions Secrets 注入, 凭据不落地磁盘)。

    支持两种方式:
      1. PLATFORMS_CONFIG=<JSON字符串>  # 一次性注入完整配置
      2. 逐平台独立变量:
         PLATFORM_<KEY>_TYPE / _USERNAME / _PASSWORD / _EXTRA(JSON)
    """
    import os
    raw = os.environ.get("PLATFORMS_CONFIG", "")
    if raw.strip():
        data = json.loads(raw)
        return _parse_platforms(data)

    # 从独立变量组装
    platforms: List[Platform] = []
    seen = set()
    for k, v in os.environ.items():
        if k.startswith("PLATFORM_") and k.endswith("_KEY"):
            key = v
            if key in seen:
                continue
            seen.add(key)
            prefix = f"PLATFORM_{key.upper()}"
            extra_raw = os.environ.get(f"{prefix}_EXTRA", "{}")
            try:
                extra = json.loads(extra_raw)
            except Exception:  # noqa: BLE001
                extra = {}
            platforms.append(
                Platform(
                    key=key,
                    name=os.environ.get(f"{prefix}_NAME", key),
                    type=PlatformType(os.environ.get(f"{prefix}_TYPE", "custom")),
                    enabled=os.environ.get(f"{prefix}_ENABLED", "1") not in ("0", "false", "False"),
                    username=os.environ.get(f"{prefix}_USERNAME", ""),
                    password=os.environ.get(f"{prefix}_PASSWORD", ""),
                    extra=extra,
                )
            )
    return platforms
