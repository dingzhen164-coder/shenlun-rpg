"""网页导入解析文档（import/draft）与设置（settings）。设置测试把 ~/.shenlun-rpg 重定向到临时目录，不碰真实配置。"""
import base64
import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import paths as core_paths  # noqa: E402
from core import settings  # noqa: E402
from core.paths import Paths  # noqa: E402
from subjects.shenlun import routes  # noqa: E402
from test_rubric import DOC, fake_ai  # noqa: E402

TODAY = dt.date(2026, 10, 2)


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = Paths(self.tmp.name)
        self.paths.ensure_train_dir()

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, path, body):
        return routes.handle("POST", path, "", body, self.paths, TODAY, fake_ai)

    def upload(self, name="样例卷.txt", text=DOC):
        return self.call("/api/shenlun/import", {"name": name, "data": base64.b64encode(text.encode("utf-8")).decode()})

    def test_import_recognizes_questions(self):
        j = self.upload()
        self.assertEqual(j["questions"][0]["score"], 10)
        self.assertTrue((self.paths.train / "资料" / "样例卷.txt").exists())

    def test_import_rejects_bad_type_and_unrecognized(self):
        with self.assertRaises(routes.ApiError):
            self.upload("a.docx")
        with self.assertRaises(routes.ApiError) as cm:
            self.upload("空.txt", "没有题号的文字")
        self.assertEqual(cm.exception.code, 422)

    def test_draft_does_not_overwrite_by_default(self):
        self.upload()
        r1 = self.call("/api/shenlun/draft", {"file": "样例卷.txt", "prefix": "样例", "no": 1})
        self.assertFalse(r1["skipped"])
        f = self.paths.rubric_dir / "样例-01.md"
        f.write_text(f.read_text(encoding="utf-8") + "\n用户手改的内容\n", encoding="utf-8")
        r2 = self.call("/api/shenlun/draft", {"file": "样例卷.txt", "prefix": "样例", "no": 1})
        self.assertTrue(r2["skipped"])
        self.assertIn("用户手改的内容", f.read_text(encoding="utf-8"))
        r3 = self.call("/api/shenlun/draft", {"file": "样例卷.txt", "prefix": "样例", "no": 1, "overwrite": True})
        self.assertFalse(r3["skipped"])
        self.assertNotIn("用户手改的内容", f.read_text(encoding="utf-8"))

    def test_draft_unsafe_names(self):
        with self.assertRaises(routes.ApiError):
            self.call("/api/shenlun/draft", {"file": "../x.txt", "prefix": "a", "no": 1})
        with self.assertRaises(routes.ApiError):
            self.call("/api/shenlun/draft", {"file": "样例卷.txt", "prefix": "../a", "no": 1})


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = (core_paths.SETTINGS_DIR, core_paths.SETTINGS_FILE)
        core_paths.SETTINGS_DIR = Path(self.tmp.name) / "cfg"
        core_paths.SETTINGS_FILE = core_paths.SETTINGS_DIR / "settings.json"
        for k in ("DEEPSEEK_API_KEY", "SHENLUN_VAULT", "SHENLUN_AI_BASE_URL"):
            os.environ.pop(k, None)

    def tearDown(self):
        core_paths.SETTINGS_DIR, core_paths.SETTINGS_FILE = self._old
        self.tmp.cleanup()

    def test_roundtrip_and_mask(self):
        self.assertFalse(settings.get()["has_key"])
        settings.put({"api_key": "sk-abcdefghijklmnop", "model": "deepseek-chat"})
        g = settings.get()
        self.assertTrue(g["has_key"])
        self.assertNotIn("abcdefghij", g["key_mask"])
        settings.put({"api_key": "", "model": "x"})       # 留空 = 不改 key
        self.assertTrue(settings.get()["has_key"])
        self.assertEqual(settings.get()["model"], "x")

    def test_vault_validation(self):
        with self.assertRaises(ValueError):
            settings.put({"vault": str(Path(self.tmp.name) / "不存在")})
        self.assertTrue(settings.put({"vault": self.tmp.name})["vault_changed"])
        self.assertFalse(settings.put({"vault": self.tmp.name})["vault_changed"])
        self.assertEqual(core_paths.find_vault(), Path(self.tmp.name))


if __name__ == "__main__":
    unittest.main()
