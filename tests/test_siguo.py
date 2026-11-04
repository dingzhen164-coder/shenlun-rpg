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


if __name__ == "__main__":
    unittest.main()
