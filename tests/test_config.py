"""单元测试: 环境变量注入平台(GitHub Secrets)。"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aicheckin.config import load_platforms_from_env


class TestEnvPlatforms(unittest.TestCase):
    def test_load_from_platforms_config_json(self):
        data = {"platforms": [{"key": "a", "name": "A", "type": "forum"}]}
        os.environ["PLATFORMS_CONFIG"] = json.dumps(data)
        try:
            pf = load_platforms_from_env()
            self.assertEqual(len(pf), 1)
            self.assertEqual(pf[0].key, "a")
            self.assertEqual(pf[0].type.value, "forum")
        finally:
            os.environ.pop("PLATFORMS_CONFIG", None)

    def test_load_from_individual_vars(self):
        os.environ["PLATFORM_B_KEY"] = "b"
        os.environ["PLATFORM_B_TYPE"] = "pt"
        os.environ["PLATFORM_B_USERNAME"] = "u"
        os.environ["PLATFORM_B_PASSWORD"] = "p"
        os.environ["PLATFORM_B_EXTRA"] = '{"cookie_ttl": 8}'
        try:
            pf = load_platforms_from_env()
            self.assertEqual(len(pf), 1)
            self.assertEqual(pf[0].key, "b")
            self.assertEqual(pf[0].type.value, "pt")
            self.assertEqual(pf[0].username, "u")
            self.assertEqual(pf[0].extra["cookie_ttl"], 8)
        finally:
            for k in list(os.environ):
                if k.startswith("PLATFORM_B"):
                    os.environ.pop(k, None)

    def test_empty_returns_empty(self):
        for k in list(os.environ):
            if k.startswith("PLATFORM"):
                os.environ.pop(k, None)
        self.assertEqual(load_platforms_from_env(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
