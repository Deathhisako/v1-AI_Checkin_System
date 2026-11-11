"""真实平台适配器目录。

接入新平台: 参考 template.py 实现 CheckinPlatform, 用 @register 注册。
"""
from .template import TemplatePlatform

__all__ = ["TemplatePlatform"]
