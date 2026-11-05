"""藏经阁·词录（rpg/wordbook.py）：按组读用户文档、组名“第N组—各词”、组卡同步保留进度、旧自动收录一次性备份清除。"""
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path

from rpg import cards, config, engine, paths, store, wordbook

DOC = """# 成语区别汇总

> 说明一行。

## 1. 夸文章、作品

**最深区别：拿什么当参照物。**

| 成语 | 回答的问题 | 一句话区别 | 出处与例句 |
|---|---|---|---|
| 力透纸背 | 文字有劲吗？ | **无外部参照**，夸力度〔推断〕 | 例句<br>**熟词僻义**：背，纸的背面 |
| 洛阳纸贵 | 抢着读吗？ | **参照读者** | — |

---

## 2. 事情走不动

**维度一：为什么走不下去。**

| 成语 | 回答的问题 | 一句话区别 | 出处与例句 |
|---|---|---|---|
| 步履维艰 | 还在走吗？ | 外部阻力 | — |
| （无关）短褐不全 | — | 与本组无关 | — |

**维度二（辅助）：进展还是心态。**

| 说的是 | 成语 |
|---|---|
| 事情的进展 | 步履维艰、止步不前 |

**易混**：看阻力在外还是在内。
"""


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "行测"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class WordbookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        vault = Path(self.tmp.name)
        (vault / "FB模考试卷复盘/板块复盘").mkdir(parents=True)
        self.p = paths.Paths(vault)
        self.p.ensure_train_dir()
        day = dt.date(2026, 11, 4)
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)
        cards._CACHE["key"] = None

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text=DOC, kind="成语"):
        f = self.p.train / wordbook.FOLDER / wordbook.KINDS[kind]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    def test_groups_named_by_number_and_words(self):
        d = wordbook.parse(DOC)
        self.assertEqual([g["name"] for g in d["groups"]], ["第一组—力透纸背、洛阳纸贵", "第二组—步履维艰"])
        g2 = d["groups"][1]
        self.assertNotIn("短褐不全", g2["words"])                       # 括号开头的“无关”项不进组名
        self.assertEqual([b["type"] for b in g2["blocks"]], ["axis", "table", "axis", "table", "tip"])
        self.assertEqual(d["groups"][0]["diffs"]["力透纸背"], "**无外部参照**，夸力度〔推断〕")
        self.assertEqual(d["problems"], [])
        self.assertEqual(wordbook.cn_num(12), "十二")
        self.assertEqual(wordbook.cn_num(20), "二十")

    def test_three_digit_group_numbers_do_not_break_document(self):
        self.write(DOC.split('## 2.')[0].replace('## 1.', '## 100.'))
        result = wordbook.listing(self.g, '成语')
        self.assertEqual(len(result['groups']), 1)
        self.assertEqual(result['groups'][0]['no'], 100)
        self.assertTrue(result['groups'][0]['name'].startswith('第100组'))

    def test_missing_file_writes_template_only(self):
        r = wordbook.listing(self.g, "实词")
        self.assertFalse(r["exists"])
        self.assertTrue((self.p.train / wordbook.FOLDER / wordbook.TEMPLATE).is_file())
        self.assertFalse((self.p.train / wordbook.FOLDER / wordbook.KINDS["实词"]).exists())
        with self.assertRaises(ValueError):
            wordbook.sync_cards(self.g, "实词")

    def test_group_cards_keep_progress_and_follow_document(self):
        self.write()
        r = wordbook.sync_cards(self.g, "成语")
        self.assertEqual((r["cards"], r["new"], r["removed"]), (2, 2, 0))
        links = dict(self.g.state["wordbook_cards"])
        note = next(n for n in cards.load(self.p)[0] if n["id"] == links["成语|夸文章、作品"])
        self.assertEqual(note["deck"], "逻辑填空::成语组")
        self.assertIn("第一组—力透纸背、洛阳纸贵", note["front"])
        self.assertIn("- **洛阳纸贵**：参照读者", note["back"])
        self.assertIn("最深区别", note["back"])
        # 改一组内容：同一张卡（编号不变）；删掉一组：对应卡删除
        self.write(DOC.replace("夸力度", "夸作品自身的力度").split("## 2.")[0])
        r = wordbook.sync_cards(self.g, "成语")
        self.assertEqual((r["cards"], r["kept"], r["removed"]), (1, 1, 1))
        self.assertEqual(self.g.state["wordbook_cards"]["成语|夸文章、作品"], links["成语|夸文章、作品"])
        self.assertNotIn(links["成语|事情走不动"], [n["id"] for n in cards.load(self.p)[0]])

    def test_multi_dimension_group_splits_into_subgroups(self):
        doc = DOC + """
## 3. 求快求功

**维度一：难处从哪来。**

| 成语 | 一句话区别 |
|---|---|
| 步履维艰 | 外部阻力 |
| 进退维谷 | 两难 |

**维度二：只重复前面的词，不单独成组。**

| 成语 | 一句话区别 |
|---|---|
| 进退维谷 | 两难 |

**维度三：做事盯着什么。**

| 成语 | 一句话区别 |
|---|---|
| 急功近利 | 盯眼前利益 |
"""
        gs = [g for g in wordbook.parse(doc)["groups"] if g["no"] == 3]
        self.assertEqual([g["name"] for g in gs], ["第三组一—步履维艰、进退维谷", "第三组二—急功近利"])
        self.assertEqual([g["id"] for g in gs], ["3-1", "3-2"])
        self.write(doc)
        wordbook.sync_cards(self.g, "成语")
        self.assertIn("成语|求快求功|2", self.g.state["wordbook_cards"])
        where = wordbook.listing(self.g, "成语")["where"]["步履维艰"]
        self.assertEqual([x["id"] for x in where], ["2-0", "3-1"])

    def test_retire_old_auto_book_backs_up_once(self):
        self.g.state["idioms"] = {"方兴未艾": {"word": "方兴未艾", "sources": []}}
        self.g.state["idiom_cards"] = {}
        (self.p.train / "成语实词录.md").write_text("# 旧", encoding="utf-8")
        self.assertTrue(wordbook.retire_old(self.g))
        self.assertNotIn("idioms", self.g.state)
        bak = list((self.p.train / "词录备份").glob("旧成语实词录-*.json"))
        self.assertEqual(json.loads(bak[0].read_text(encoding="utf-8"))["idioms"]["方兴未艾"]["word"], "方兴未艾")
        self.assertFalse((self.p.train / "成语实词录.md").exists())
        self.assertTrue(list((self.p.train / "词录备份").glob("旧成语实词录-*.md")))
        self.assertFalse(wordbook.retire_old(self.g))


if __name__ == "__main__":
    unittest.main()
