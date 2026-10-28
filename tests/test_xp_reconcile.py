"""学习时间对账：心跳给的修为必须等于“有效分钟 × 每分钟修为”，不多不少。
（模考结算、听道、静修各有各的测试；这里只对账心跳这一条路径。）"""
import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rpg import api, paths  # noqa: E402


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "行测"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class XpReconcileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        v = self.tmp / "行测"
        v.mkdir()
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.tmp / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.save_settings({"vaults": {"行测": str(v)}, "api_key": "test"})

    def tearDown(self):
        paths.SETTINGS_FILE, paths.SETTINGS_DIR = self._settings

    def _run(self, kind, beats, sec):
        with api.open_game() as g:
            rate = g.rules.xp("修炼每分钟")
            x0, s0 = g.state["xp"], g.state["seconds"].get(g.t, 0)
            for _ in range(beats):
                g.add_seconds(sec, kind)
            gained = g.state["xp"] - x0
            secs = g.state["seconds"][g.t] - s0
            return gained, secs, rate, g.state.get("xp_carry", 0)

    def test_heartbeat_xp_equals_minutes_times_rate(self):
        for kind in ("practice", "review"):
            gained, secs, rate, carry = self._run(kind, 412, 30)     # 206 分钟，每 30 秒一跳
            self.assertEqual(secs, 412 * 30)
            self.assertAlmostEqual(gained + carry, secs / 60 * rate, places=6, msg=kind)

    def test_long_session_not_lost_to_rest_or_event_trim(self):
        # 走火入魔休息、事件列表裁剪都不能让修为少发
        gained, secs, rate, carry = self._run("practice", 800, 30)   # 400 分钟，跨过走火入魔线
        self.assertAlmostEqual(gained + carry, secs / 60 * rate, places=6)


if __name__ == "__main__":
    unittest.main()
