"""core 层的单元测试：Markdown 配置解析、存档读写与备份、职级换算、今日概览。"""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import api, mdconf, themes  # noqa: E402
from core.paths import Paths  # noqa: E402
from core.store import Store  # noqa: E402

TODAY = dt.date(2026, 10, 2)


class MdconfTest(unittest.TestCase):
    def test_parse(self):
        t = "# 标题\n- 目标试卷: 国考行政执法  # 注释\n- 题型: 归纳概括, 综合分析、公文写作\n```\n- 忽略: 代码块里\n```\n"
        d = mdconf.parse(t)
        self.assertEqual(d["目标试卷"], "国考行政执法")
        self.assertNotIn("忽略", d)
        self.assertEqual(mdconf.split_list(d["题型"]), ["归纳概括", "综合分析", "公文写作"])


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = Paths(self.tmp.name)
        self.paths.ensure_train_dir()
        self.store = Store(self.paths)

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_and_backup(self):
        s = self.store.load(TODAY)
        s["xp"] = 10
        self.store.save(s, TODAY)
        s["xp"] = 20
        self.store.save(s, TODAY)  # 第二次写入前应已有当天备份
        self.assertEqual(self.store.load(TODAY)["xp"], 20)
        self.assertTrue((self.paths.save_dir / "备份" / "存档-20261002.json").exists())

    def test_corrupt_save_is_kept(self):
        self.paths.save_file.write_text("{坏的", encoding="utf-8")
        s = self.store.load(TODAY)
        self.assertEqual(s["xp"], 0)
        self.assertTrue(list(self.paths.save_dir.glob("存档-损坏-*.json")))

    def test_old_save_gets_new_fields(self):
        self.paths.save_file.write_text('{"version": 1, "xp": 5}', encoding="utf-8")
        s = self.store.load(TODAY)
        self.assertEqual(s["xp"], 5)
        self.assertEqual(s["records"], [])


class ThemeTest(unittest.TestCase):
    def test_rank(self):
        self.assertEqual(themes.rank_of("官场", None)[0], "科员")
        self.assertEqual(themes.rank_of("官场", 62)[:2], ("正科", "副处"))
        self.assertEqual(themes.rank_of("官场", 99)[1], None)


class DashboardTest(unittest.TestCase):
    def test_empty_and_streak(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = Paths(tmp)
            paths.ensure_train_dir()
            store = Store(paths)
            d = api.dashboard(TODAY, store)
            self.assertEqual(d["stats"]["streak"], 0)
            self.assertIsNone(d["rank"]["score"])
            s = store.load(TODAY)
            s["records"] = [{"d": "2026-10-01", "rate": 0.6}, {"d": "2026-10-02", "rate": 0.7}]
            store.save(s, TODAY)
            d = api.dashboard(TODAY, store)
            self.assertEqual(d["stats"]["streak"], 2)
            self.assertEqual(d["rank"]["score"], 65.0)
            self.assertEqual(d["rank"]["name"], "副处")


if __name__ == "__main__":
    unittest.main()
