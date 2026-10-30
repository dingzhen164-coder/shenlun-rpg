"""2026-10-30：删除导入的套卷（整份删）、藏经阁「清除」广告文字（查找/清除/撤销/广告词库自动清除）。隔离假库，不碰用户数据。"""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import ad_clean, config, engine, exam_room, paths, store
from tests.test_exam_room import blank_paper

AD = "一手最全公考资源加微信 biguo368"


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "行测"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class Base(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.root = Path(t.name)
        for ctx in (patch.object(Path, "home", return_value=self.root / "home"), patch.dict(os.environ, {"SHENLUN_SUBJECT": "行测"}),
                    patch.object(paths, "SETTINGS_DIR", self.root / "settings"), patch.object(paths, "SETTINGS_FILE", self.root / "settings" / "settings.json")):
            ctx.start(); self.addCleanup(ctx.stop)
        self.p = paths.Paths(self.root / "vault", "行测"); self.p.ensure_train_dir()
        (self.p.vault / "copilot/skills/test").mkdir(parents=True)
        paths.save_settings({"subject": "行测", "vaults": {"行测": str(self.p.vault)}})
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(dt.date(2026, 10, 25)), dt.date(2026, 10, 25))
        self.folder = self.p.train / "模考复盘/第1001季"
        blank_paper(self.folder)
        self.g.state.setdefault("mocks", {})["1001"] = {"name": "花生26下模拟卷第一套"}
        self.files = sorted(self.folder.glob("[0-9][0-9]-*.md"))
        self.first = self.files[0]

    def put_ads(self):
        text = self.first.read_text(encoding="utf-8")
        text = text.replace("### 1. ⚪\n自编条件题，仅用于隔离测试。", "### 1. ⚪\n自编条件题，仅用于隔离测试。\n" + AD, 1)                     # 整行广告
        text = text.replace("### 2. ⚪\n自编条件题，仅用于隔离测试。", "### 2. ⚪\n自编条件题，仅用于隔离测试。一手最全 公考资源加微信biguo368 继续正文", 1)   # 夹在句中
        self.first.write_text(text, encoding="utf-8")


class DeletePaperTest(Base):
    def test_delete_removes_everything_of_the_paper(self):
        bank = self.p.train / "题库"; bank.mkdir(exist_ok=True)
        (bank / "政治理论真题.md").write_text("# 政治理论真题\n\n## 题目 粉笔1001季-001\n### 知识点\n甲\n### 题干\n甲\n\n## 题目 粉笔36季-001\n### 知识点\n乙\n### 题干\n乙\n", encoding="utf-8")
        exam_room.begin(self.g, 1001)
        exam_room.save_run(self.g, 1001, {"answers": {"1": "A"}, "elapsed": 30})
        self.assertIn("1001", self.g.state["exam_runs"])
        self.assertTrue(exam_room.papers(self.g)["papers"][0]["deletable"])
        r = exam_room.delete_paper(self.g, 1001)
        self.assertEqual(r["season"], 1001)
        self.assertFalse(self.folder.exists())
        self.assertNotIn("1001", self.g.state.get("mocks", {}))
        self.assertNotIn("1001", self.g.state.get("exam_runs", {}))
        self.assertEqual(exam_room.papers(self.g)["papers"], [])
        left = (bank / "政治理论真题.md").read_text(encoding="utf-8")
        self.assertNotIn("粉笔1001季", left)
        self.assertIn("粉笔36季-001", left)                    # 别的季的题不动

    def test_original_vault_review_is_never_deleted(self):
        orig = self.p.vault / "FB模考试卷复盘" / "板块复盘" / "第36季"
        blank_paper(orig)
        self.p.seasons = self.p.vault / "FB模考试卷复盘" / "板块复盘"
        with self.assertRaises(exam_room.ExamError):
            exam_room.delete_paper(self.g, 36)
        self.assertTrue(orig.exists())


class AdCleanTest(Base):
    def test_find_ignores_spaces_and_reports_question(self):
        self.put_ads()
        r = ad_clean.find(self.g, {"text": "一手最全公考资源加微信biguo368"})
        self.assertEqual(r["total"], 2)
        whole = next(h for h in r["hits"] if h["whole_line"])
        mid = next(h for h in r["hits"] if not h["whole_line"])
        self.assertTrue(whole["question"].startswith("1."))
        self.assertTrue(mid["check"])                          # 夹在句中：提示请核对
        self.assertIn("套卷/复盘", whole["where"])

    def test_clean_undo_and_backup(self):
        self.put_ads()
        before = self.first.read_text(encoding="utf-8")
        r = ad_clean.clean(self.g, {"text": AD})
        self.assertEqual((r["cleaned"], r["files"]), (2, 1))
        after = self.first.read_text(encoding="utf-8")
        self.assertNotIn("biguo368", after)
        self.assertNotIn("\n\n\n", after.split("### 2.")[0][-40:])        # 整行广告连行一起删，不留空行
        self.assertIn("继续正文", after)                                    # 夹在句中的只删广告，两边的字接起来
        self.assertEqual(ad_clean.find(self.g, {"text": AD})["total"], 0)
        u = ad_clean.undo(self.g)
        self.assertEqual((u["restored"], u["skipped"]), (1, []))
        self.assertEqual(self.first.read_text(encoding="utf-8"), before)

    def test_clean_only_selected_and_undo_skips_edited_files(self):
        self.put_ads()
        hits = ad_clean.find(self.g, {"text": AD})["hits"]
        ad_clean.clean(self.g, {"text": AD, "ids": [hits[0]["id"]]})
        self.assertEqual(ad_clean.find(self.g, {"text": AD})["total"], 1)
        with open(self.first, "a", encoding="utf-8") as f:
            f.write("\n我后来记的笔记\n")
        u = ad_clean.undo(self.g)
        self.assertEqual(u["restored"], 0)
        self.assertEqual(len(u["skipped"]), 1)                   # 清除后你改过的文件不覆盖
        self.assertIn("我后来记的笔记", self.first.read_text(encoding="utf-8"))

    def test_too_short_text_is_refused_and_scope(self):
        with self.assertRaises(ad_clean.AdError):
            ad_clean.find(self.g, {"text": "加微"})
        self.put_ads()
        self.assertEqual(ad_clean.find(self.g, {"text": AD, "scopes": ["bank"]})["total"], 0)       # 只查板块题库时不看套卷
        outside = self.p.vault / "FB模考试卷复盘"; outside.mkdir(parents=True)
        (outside / "x.md").write_text(AD, encoding="utf-8")
        self.assertEqual(ad_clean.find(self.g, {"text": AD})["total"], 2)                          # 库里原有的文件不查、不动

    def test_word_list_cleans_future_imports(self):
        ad_clean.edit_words(self.g, {"act": "add", "text": AD})
        self.assertEqual(ad_clean.status(self.g)["words"][0]["text"], AD)
        self.assertTrue(ad_clean.edit_words(self.g, {"act": "add", "text": "一手最全公考资源 加微信biguo368"}).get("again"))   # 同一条不重复
        self.assertEqual(ad_clean.strip_text(self.p, "第一行\n%s\n第三行" % AD), "第一行\n第三行")
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + AD + "继续"), "正文继续")
        ad_clean.edit_words(self.g, {"act": "remove", "text": AD})
        self.assertEqual(ad_clean.status(self.g)["words"], [])
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + AD), "正文" + AD)

    def test_import_finish_applies_word_list(self):
        self.put_ads()
        ad_clean.edit_words(self.g, {"act": "add", "text": AD})
        self.assertGreaterEqual(ad_clean.strip_files(self.p, self.folder), 1)
        self.assertEqual(ad_clean.find(self.g, {"text": AD})["total"], 0)

    def test_bank_import_applies_word_list(self):
        from rpg import importer
        ad_clean.edit_words(self.g, {"act": "add", "text": AD})
        q = {"id": "自编-001", "board": "逻辑填空", "topic": "x", "stem": "题干正文" + AD, "options": {k: "选项" + k for k in "ABCD"}, "answer": "A"}
        importer._append(self.p, [q])
        text = (self.p.train / "题库" / "逻辑填空真题.md").read_text(encoding="utf-8")
        self.assertIn("题干正文", text)
        self.assertNotIn("biguo368", text)
