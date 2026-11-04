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

    def add_word(self):
        f = self.p.train / "清除" / "广告词库.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(AD + "\n", encoding="utf-8")
        ad_clean._WORDS_CACHE.clear()

    def put_ads(self):
        text = self.first.read_text(encoding="utf-8")
        text = text.replace("### 1. ⚪\n自编条件题，仅用于隔离测试。", "### 1. ⚪\n自编条件题，仅用于隔离测试。\n" + AD, 1)                     # 整行广告
        text = text.replace("### 2. ⚪\n自编条件题，仅用于隔离测试。", "### 2. ⚪\n自编条件题，仅用于隔离测试。一手最全 公考资源加微信biguo368 继续正文", 1)   # 夹在句中
        self.first.write_text(text, encoding="utf-8")


class WordListTest(Base):
    """广告词库是本地文档 训练/清除/广告词库.txt（一行一条，# 注释）；旧 json 第一次读到时转成 txt"""
    def test_word_list_edit_with_unchanged_timestamp_takes_effect(self):
        self.add_word()
        f = self.p.train / "清除/广告词库.txt"
        before = f.stat()
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + AD), "正文")
        changed = AD.replace("368", "369")
        f.write_text(changed + "\n", encoding="utf-8")
        os.utime(f, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + AD), "正文" + AD)
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + changed), "正文")

    def test_migration_and_import_writes_support_python38(self):
        root = self.p.train / "清除"
        root.mkdir(parents=True, exist_ok=True)
        (root / "广告词库.json").write_text('[{"text": "%s"}]' % AD, encoding="utf-8")
        original = Path.write_text
        def legacy_write(path, data, encoding=None, errors=None):
            return original(path, data, encoding=encoding, errors=errors)
        self.put_ads()
        with patch.object(Path, "write_text", legacy_write):
            self.assertEqual(ad_clean.words(self.p), [{"text": AD}])
            self.assertGreaterEqual(ad_clean.strip_files(self.p, self.folder), 1)
        self.assertNotIn(AD, self.first.read_text(encoding="utf-8"))

    def test_text_word_list_and_json_migration(self):
        root = self.p.train / "清除"
        root.mkdir(parents=True, exist_ok=True)
        (root / "广告词库.json").write_text('[{"text": "%s", "added": "2026-10-30"}]' % AD, encoding="utf-8")
        self.assertEqual([w["text"] for w in ad_clean.words(self.p)], [AD])
        self.assertTrue((root / "广告词库.txt").is_file())
        self.assertEqual(ad_clean.strip_text(self.p, "第一行\n%s\n第三行" % AD), "第一行\n第三行")
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + AD + "继续"), "正文继续")
        (root / "广告词库.txt").write_text("# 注释\n短\n", encoding="utf-8")
        self.assertEqual(ad_clean.strip_text(self.p, "正文" + AD), "正文" + AD)          # 太短的跳过，不误删


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
    def test_import_finish_applies_word_list(self):
        self.put_ads()
        self.add_word()
        self.assertGreaterEqual(ad_clean.strip_files(self.p, self.folder), 1)
        self.assertNotIn("biguo368", "".join(f.read_text(encoding="utf-8") for f in self.folder.rglob("*.md")))

    def test_bank_import_applies_word_list(self):
        from rpg import importer
        self.add_word()
        q = {"id": "自编-001", "board": "逻辑填空", "topic": "x", "stem": "题干正文" + AD, "options": {k: "选项" + k for k in "ABCD"}, "answer": "A"}
        importer._append(self.p, [q])
        text = (self.p.train / "题库" / "逻辑填空真题.md").read_text(encoding="utf-8")
        self.assertIn("题干正文", text)
        self.assertNotIn("biguo368", text)
