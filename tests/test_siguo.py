"""行测·思过崖（rpg/siguo.py）：板块文档解析（多题文档、单题旧写法、答案写法）、重做判分记录与每日一次奖励。"""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from rpg import config, engine, paths, siguo, store

MULTI = """# 中心理解错题记录

> 说明

## 题目索引

| 题号 | 题目 |
|---|---|
| 一 | 土瓜冲村 |

## 错题一：土瓜冲村标题题

### 原题干

曲靖市土瓜冲村……

最适合该段落的标题是：

- A. 因地制宜
- B. 闲置资源的再利用
- C. 旅居村：乡村旅游发展的新路径
- D. 政府引领

### 答案

| 正确答案 | 我的选择 |
|---|---|
| **C** | **B**（错选） |

### 错因分析（重点）

手段当结果。

**5. 我当时的真实想法（待补充）：** _不显示这一行_

### 我当时的真实想法

这一节不显示

### 一句话教训

> 标题题先问落脚点。

---

## 错因分类（待积累）

| 标签 | 描述 |
|---|---|
| 取手段不取结果 | … |
"""

SINGLE = """# 001 · 月牙儿（力透纸背）

## 区别（先看这里）

参照物不同。

## 原题

这篇小说之所以能__，掷地有声。

- A. 不落窠臼
- B. 洛阳纸贵
- C. 力透纸背　**← 答案**
- D. 巧夺天工

## 解析

同义并列。
"""


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "行测"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class SiguoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        vault = Path(self.tmp.name)
        (vault / "FB模考试卷复盘/板块复盘").mkdir(parents=True)
        self.p = paths.Paths(vault)
        self.p.ensure_train_dir()
        day = dt.date(2026, 11, 4)
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)

    def tearDown(self):
        self.tmp.cleanup()

    def test_multi_question_document(self):
        d = siguo.parse(MULTI)
        self.assertEqual(len(d["questions"]), 1)                       # “错因分类”不算题
        q = d["questions"][0]
        self.assertEqual((q["answer"], q["mine"]), ("C", "B"))
        self.assertEqual(list(q["options"]), list("ABCD"))
        self.assertTrue(q["stem"].startswith("曲靖市"))
        titles = [s["title"] for s in q["sections"]]
        self.assertEqual(titles, ["错因分析（重点）", "一句话教训"])     # “我当时的真实想法”不显示
        self.assertNotIn("真实想法", q["sections"][0]["md"])

    def test_single_question_legacy_file(self):
        d = siguo.parse(SINGLE)
        q = d["questions"][0]
        self.assertEqual((q["title"], q["answer"], q["options"]["C"]), ("001 · 月牙儿（力透纸背）", "C", "力透纸背"))
        self.assertEqual([s["title"] for s in q["sections"]], ["区别（先看这里）", "解析"])

    def test_legacy_correct_record_keeps_award_after_wrong_attempt(self):
        siguo.boards(self.g)
        (self.p.train / "思过崖/中心理解.md").write_text(MULTI, encoding="utf-8")
        key = siguo.board(self.g, "中心理解")["questions"][0]["key"]
        siguo.answer(self.g, "中心理解", key, "C")
        self.g.state["siguo"]["中心理解|" + key].pop("reward_date")
        xp = self.g.state["xp"]
        siguo.answer(self.g, "中心理解", key, "B")
        siguo.answer(self.g, "中心理解", key, "C")
        self.assertEqual(self.g.state["xp"], xp, "旧格式已领奖记录不能被答错重置")

    def test_correct_wrong_correct_cannot_repeat_daily_award(self):
        siguo.boards(self.g)
        (self.p.train / "思过崖/中心理解.md").write_text(MULTI, encoding="utf-8")
        key = siguo.board(self.g, "中心理解")["questions"][0]["key"]
        siguo.answer(self.g, "中心理解", key, "C")
        awarded = self.g.state["xp"]
        siguo.answer(self.g, "中心理解", key, "B")
        result = siguo.answer(self.g, "中心理解", key, "C")
        self.assertEqual(self.g.state["xp"], awarded, "错误尝试不能重置当天的领奖资格")
        self.assertEqual(result["events"], [])
        tomorrow = dt.date(2026, 11, 5)
        self.g = engine.Game(self.p, self.g.rules, config.Persona(), config.Lines(), self.g.state, tomorrow)
        siguo.answer(self.g, "中心理解", key, "B")
        siguo.answer(self.g, "中心理解", key, "C")
        self.assertEqual(self.g.state["xp"] - awarded, config.DEFAULT_RULES["经验.思过崖答对"])

    def test_boards_and_redo_award_once_a_day(self):
        r = siguo.boards(self.g)
        self.assertEqual([b["name"] for b in r["boards"]], [n for n, _ in siguo.BOARDS])
        self.assertTrue((self.p.train / "思过崖/_模板.md").is_file())
        self.assertEqual(siguo.parse((self.p.train / "思过崖/_模板.md").read_text(encoding="utf-8"))["questions"][0]["answer"], "C")
        (self.p.train / "思过崖/中心理解.md").write_text(MULTI, encoding="utf-8")
        b = siguo.board(self.g, "中心理解")
        self.assertEqual(b["board"], "片段阅读")
        q = b["questions"][0]
        self.assertNotIn("answer", q)                                  # 重做前不给答案
        bad = siguo.answer(self.g, "中心理解", q["key"], "B")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["events"], [])
        xp = self.g.state["xp"]
        ok = siguo.answer(self.g, "中心理解", q["key"], "C")
        self.assertTrue(ok["ok"])
        self.assertEqual(self.g.state["xp"] - xp, config.DEFAULT_RULES["经验.思过崖答对"])
        siguo.answer(self.g, "中心理解", q["key"], "C")                 # 同一天再答对不重复给
        self.assertEqual(self.g.state["xp"] - xp, config.DEFAULT_RULES["经验.思过崖答对"])
        rec = self.g.state["siguo"]["中心理解|" + q["key"]]
        self.assertEqual((rec["tries"], rec["ok"], rec["last"]), (3, 2, "ok"))
        self.assertEqual(siguo.boards(self.g)["boards"][0]["ok"], 1)
        with self.assertRaises(ValueError):
            siguo.answer(self.g, "中心理解", "nope", "A")
        with self.assertRaises(ValueError):
            siguo.board(self.g, "资料分析")

    def test_sync_from_vault_gk_skill_and_wordbook(self):
        from rpg import vault as vault_mod
        old_sdir, old_sfile = paths.SETTINGS_DIR, paths.SETTINGS_FILE
        try:
            paths.SETTINGS_DIR = Path(self.tmp.name) / ".settings"
            paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"

            gk = self.p.vault / "gk-skill"
            (gk / "错题集" / "assets").mkdir(parents=True)
            (gk / "笔记与题集" / "成语实词录").mkdir(parents=True)
            (gk / "skill" / "言语").mkdir(parents=True)

            (gk / "错题集" / "中心理解.md").write_text(MULTI, encoding="utf-8")
            (gk / "错题集" / "数量关系.md").write_text(
                "# 数量关系\n\n## 001 · 图形题\n\n### 原题\n\n如图 ![配图](assets/q01.png)\n\n- A. 1\n- B. 2\n\n### 答案\n\n正确答案：A\n",
                encoding="utf-8",
            )
            (gk / "错题集" / "assets" / "q01.png").write_bytes(b"\x89PNG\r\n\x1a\nfakepng")
            (gk / "笔记与题集" / "成语实词录" / "成语区别汇总.md").write_text("# 成语\n\n## 1. 测试组\n", encoding="utf-8")
            (gk / "笔记与题集" / "成语实词录" / "实词区别汇总.md").write_text("# 实词\n\n## 1. 测试组\n", encoding="utf-8")
            (gk / "skill" / "言语" / "大宝-言语.md").write_text("# 心法不应同步\n", encoding="utf-8")

            meta = siguo.boards(self.g)["sync"]
            self.assertEqual(meta["mode"], "vault")
            self.assertEqual(Path(meta["source"]).resolve(), gk.resolve())

            r = siguo.sync_from_source(self.g)
            sr = r["sync_result"]
            self.assertEqual([x["name"] for x in sr["boards_updated"]], ["中心理解", "数量关系"])
            self.assertEqual(sr["assets_updated"], 1)
            self.assertEqual(set(sr["wordbook_updated"]), {"成语", "实词"})
            self.assertTrue((self.p.train / "思过崖" / "assets" / "q01.png").is_file())
            self.assertTrue((self.p.train / "成语实词录" / "成语区别汇总.md").is_file())
            self.assertTrue((self.p.train / "成语实词录" / "实词区别汇总.md").is_file())
            # 不同步心法
            self.assertFalse((self.p.vault / "copilot" / "skills").exists())
            self.assertFalse((self.p.train / "skill").exists())
            # vault._vault_find 跳过库内 gk-skill，避免串台
            self.assertIsNone(vault_mod._vault_find(self.p, "大宝-言语.md"))
            # /vault-file 可安全读取同步后的思过崖配图
            self.assertIsNotNone(vault_mod.safe_vault_file(self.p, "训练/思过崖/assets/q01.png"))

            # 再次同步无变化
            r2 = siguo.sync_from_source(self.g)
            self.assertEqual(r2["sync_result"]["boards_updated"], [])
            self.assertEqual(r2["sync_result"]["assets_updated"], 0)
            self.assertEqual(r2["sync_result"]["wordbook_updated"], [])
            self.assertIn("已是最新", r2["sync_result"]["summary"])
        finally:
            paths.SETTINGS_DIR, paths.SETTINGS_FILE = old_sdir, old_sfile

    def test_sync_from_custom_external_dir_and_legacy_wordbook(self):
        old_sdir, old_sfile = paths.SETTINGS_DIR, paths.SETTINGS_FILE
        try:
            paths.SETTINGS_DIR = Path(self.tmp.name) / ".settings2"
            paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
            with tempfile.TemporaryDirectory() as ext:
                ext_p = Path(ext)
                (ext_p / "错题集").mkdir()
                (ext_p / "言语" / "成语实词录").mkdir(parents=True)
                (ext_p / "错题集" / "逻辑填空.md").write_text(SINGLE, encoding="utf-8")
                (ext_p / "言语" / "成语实词录" / "成语区别汇总.md").write_text("# 旧路径成语\n", encoding="utf-8")

                paths.save_settings({"gk_skill_dir": str(ext_p)})
                r = siguo.sync_from_source(self.g)
                self.assertEqual(r["sync_result"]["mode"], "custom")
                self.assertEqual([x["name"] for x in r["sync_result"]["boards_updated"]], ["逻辑填空"])
                self.assertEqual(r["sync_result"]["wordbook_updated"], ["成语"])
                self.assertEqual((self.p.train / "成语实词录" / "成语区别汇总.md").read_text(encoding="utf-8"), "# 旧路径成语\n")
        finally:
            paths.SETTINGS_DIR, paths.SETTINGS_FILE = old_sdir, old_sfile


if __name__ == "__main__":
    unittest.main()
