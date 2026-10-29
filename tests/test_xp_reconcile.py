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


class XpRulesTest(unittest.TestCase):
    """修为只看学习时间：自练按分钟、做题不再按题数额外发；旧规则文件里仍是旧默认值的行自动迁移。"""

    def test_manual_practice_pays_minutes_not_questions(self):
        import datetime as dt
        from rpg import config, engine, store
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        p = paths.Paths(Path(tmp.name)); p.ensure_train_dir()
        day = dt.date(2026, 10, 22)
        g = engine.Game(p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)
        x0 = g.state["xp"]
        g.add_practice("论证逻辑", 40, 30, 30)                       # 40 题、30 分钟
        self.assertEqual(g.state["xp"] - x0, 30)                    # 只按 30 分钟，不按题数
        g.add_practice("论证逻辑", 0, 0, 20)                        # 只记分钟也算
        self.assertEqual(g.state["xp"] - x0, 50)

    def test_old_explicit_rules_migrate_custom_kept(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        p = paths.Paths(Path(tmp.name)); p.ensure_train_dir()
        f = p.rules
        # 自己写一份只含相关行的规则文本：不依赖默认规则文件的当前内容。
        f.write_text("\n".join("- %s: %s" % kv for kv in (
            ("经验.实战答对", 5), ("经验.实战答错", 1), ("经验.实战通关", 30), ("经验.自练每题", 2), ("经验.听道每分钟", 0.5),
            ("经验.静修每分钟", 0.5), ("经验.自练每分钟", 3))) + "\n", encoding="utf-8")        # 自练每分钟：自己改过的值不动
        p._migrate_rules()
        from rpg import config
        r = config.Rules(f.read_text(encoding="utf-8"))
        self.assertEqual([r.xp(k) for k in ("实战答对", "实战答错", "实战通关", "自练每题")], [0, 0, 0, 0])
        self.assertEqual([r.xp(k) for k in ("听道每分钟", "静修每分钟", "自练每分钟")], [1, 1, 3])
