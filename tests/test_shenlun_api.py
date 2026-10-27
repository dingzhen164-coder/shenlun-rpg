"""申论作答计时：只有最近2分钟内敲过键盘才计时（服务端校验，防挂机）。
在临时申论库里跑，不碰真实数据和 ~/.shenlun-rpg。"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_grade_ai import FakeAI  # noqa: E402
from rpg import api, paths, shenlun  # noqa: E402
import study_clock_fixture  # noqa: E402


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "申论"     # 本文件的测试跑在这个科目下（rpg/subjects.py）


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class ShenlunApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        v = self.tmp / "申论"
        (v / "copilot/skills/shenlun-xiaoti").mkdir(parents=True)
        (v / "copilot/skills/shenlun-xiaoti/SKILL.md").write_text("---\nname: x\n---\n# 小题\n", encoding="utf-8")
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.tmp / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.save_settings({"vaults": {"申论": str(v)}, "api_key": "test"})
        self.srv = FakeAI("ok")
        self.srv.__enter__()
        os.environ["SHENLUN_AI_BASE_URL"] = self.srv.url
        shenlun._TOUCH["t"] = 0.0

    def tearDown(self):
        self.srv.__exit__()
        os.environ.pop("SHENLUN_AI_BASE_URL", None)
        paths.SETTINGS_FILE, paths.SETTINGS_DIR = self._settings
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self):
        with api.open_game(save=False) as g:
            return g.state

    @study_clock_fixture.elapsed_heartbeats
    def test_answering_time_needs_recent_typing(self):
        api.heartbeat({"seconds": 30, "answering": "归纳概括"})
        self.assertEqual(self.state()["seconds"].get(self.state()["created"], 0) if False else sum(self.state()["seconds"].values()), 0)   # 没敲过键盘 → 不计时
        api.shenlun_active({})
        r = api.heartbeat({"seconds": 30, "answering": "归纳概括"})
        self.assertTrue(r["studying"])
        self.assertEqual(sum(self.state()["seconds"].values()), 30)
        self.assertEqual(sum(v.get("practice", 0) for v in self.state().get("seconds_kind", {}).values()), 30)


if __name__ == "__main__":
    unittest.main()
