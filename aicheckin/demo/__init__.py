"""演示平台: 模拟真实环境中的四大痛点, 用于离线验证自愈机制。

不依赖真实账号/API Key, 可通过场景参数复现:
  - Cookie过期        (cookie_ttl 次签到后过期)
  - 动态加密升级       (encrypt_ttl 次后算法变化)
  - 滑块/语义验证码     (captcha_rate 概率出现)
  - 瞬时故障/风控       (transient_rate 概率抖动)
"""
from .platform import DemoPlatform

__all__ = ["DemoPlatform"]
