"""单元测试: 自愈引擎核心逻辑。"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aicheckin.core import SelfHealEngine
from aicheckin.decision import Diagnostician
from aicheckin.demo import DemoPlatform
from aicheckin.models import Platform as PlatformConfig
from aicheckin.models import ErrorKind, HealAction, PlatformType


def _make_platform(**extra) -> DemoPlatform:
    cfg = PlatformConfig(
        key="t", name="test", type=PlatformType.DEMO,
        extra={"cookie_ttl": 2, "encrypt_ttl": 3,
               "captcha_rate": 0.0, "transient_rate": 0.0, "risk_rate": 0.0, **extra},
    )
    return DemoPlatform(cfg)


class TestSelfHeal(unittest.TestCase):
    def setUp(self):
        self.d = Diagnostician()
        self.sh = SelfHealEngine(self.d, max_attempts=5, retry_delay=0.0, max_backoff=0.0)

    def test_cookie_expiry_self_heal(self):
        """Cookie 过期后应自动重登并恢复。"""
        pf = _make_platform(cookie_ttl=2, encrypt_ttl=100)
        ctx = {"sign_fn": pf.build_sign_fn(), "reanalyze_fn": pf.reanalyze}
        events = []
        for _ in range(4):
            r = self.sh.run(pf, ctx)
            self.assertTrue(r.ok, f"Cookie 过期自愈应持续成功: {r.message}")
            events.extend(r.heal_events)
        self.assertTrue(any("relogin" in e for e in events), "应触发重新登录自愈")

    def test_encryption_upgrade_self_heal(self):
        """加密升级后应自动重析并恢复。"""
        pf = _make_platform(cookie_ttl=100, encrypt_ttl=3)
        ctx = {"sign_fn": pf.build_sign_fn(), "reanalyze_fn": pf.reanalyze}
        diag_kinds = set()
        for _ in range(5):
            r = self.sh.run(pf, ctx)
            self.assertTrue(r.ok, f"加密升级自愈应成功: {r.message}")
            for ev in r.heal_events:
                if ev.startswith("诊断"):
                    diag_kinds.add(ev.split(": ")[1].split("/")[0])
        self.assertIn("dynamic_encryption", diag_kinds)

    def test_all_success_without_interference(self):
        """无干扰场景应全部一次成功。"""
        pf = _make_platform(cookie_ttl=100, encrypt_ttl=100, captcha_rate=0.0,
                            transient_rate=0.0, risk_rate=0.0)
        # 预先登录, 填充Cookie
        pf.config.cookie = {"session": "s", "uid": "1"}
        ctx = {"sign_fn": pf.build_sign_fn(), "reanalyze_fn": pf.reanalyze}
        for _ in range(5):
            r = self.sh.run(pf, ctx)
            self.assertTrue(r.ok)
            self.assertEqual(r.attempts, 1)

    def test_diagnosis_mapping(self):
        """LLM语义分类映射正确。"""
        cases = [
            ("需要验证码", ErrorKind.CAPTCHA_REQUIRED, HealAction.SOLVE_CAPTCHA),
            ("未登录: 会话已过期", ErrorKind.COOKIE_EXPIRED, HealAction.RELOGIN),
            ("参数校验失败: 签名不正确", ErrorKind.DYNAMIC_ENCRYPTION, HealAction.RE_ANALYZE),
            ("网关超时", ErrorKind.TRANSIENT, HealAction.RETRY),
            ("风控拦截", ErrorKind.RISK_CONTROL, HealAction.WAIT),
        ]
        for text, kind, action in cases:
            signal = self.d.parse_page(400, text)
            diag = self.d.diagnose(signal, {"raw_error": text})
            self.assertEqual(diag.kind, kind, f"文本: {text}")
            self.assertEqual(diag.action, action, f"文本: {text}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
