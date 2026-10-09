"""申论接口端到端：题库、定稿、导入解析文档、起草采分点、作答批改计入政绩与专长、作答计时。
在临时申论库里跑，AI 用假服务 / 假函数，不碰真实数据和 ~/.shenlun-rpg。"""
import base64
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_grade_ai import FakeAI  # noqa: E402
from rpg import ai, api, paths, shenlun  # noqa: E402
from test_shenlun import DOC, GOOD, HALF, RUBRIC, fake_ai  # noqa: E402


class ShenlunApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        v = self.tmp / "申论"
        (v / "copilot/skills/shenlun-xiaoti").mkdir(parents=True)
        (v / "copilot/skills/shenlun-xiaoti/SKILL.md").write_text("---\nname: x\n---\n# 小题\n", encoding="utf-8")
        (v / "训练/采分点").mkdir(parents=True)
        (v / "训练/采分点/样例-01.md").write_text(RUBRIC.replace("题型: 归纳概括", "题型: 归纳概括"), encoding="utf-8")
        self.vault = v
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.tmp / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.save_settings({"vault": str(v), "api_key": "test"})
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

    # ------------------------------------------------------------ 题库与定稿
    def test_questions_and_finalize(self):
        qs = api.shenlun_questions({})["questions"]
        self.assertEqual((qs[0]["qid"], qs[0]["status"], qs[0]["points"]), ("样例-01", "已定稿", 2))
        f = self.vault / "训练/采分点/样例-01.md"
        f.write_text(f.read_text(encoding="utf-8").replace("状态: 已定稿", "状态: 草稿").replace("[5] 搭建", "[3] 搭建"), encoding="utf-8")
        with self.assertRaises(api.ApiError) as cm:
            api.shenlun_finalize({"qid": "样例-01"})
        self.assertIn("不等于总分", str(cm.exception))
        with self.assertRaises(api.ApiError):
            api.shenlun_question({"qid": "../x"})
        with self.assertRaises(api.ApiError):
            api.shenlun_question({"qid": "不存在"})

    # ------------------------------------------------------------ 批改计入政绩和专长
    def test_grade_awards_xp_and_builds_root(self):
        xp0 = self.state()["xp"]
        res = api.shenlun_grade({"qid": "样例-01", "answer": GOOD})
        self.assertEqual(res["total"], 10)
        self.assertTrue((self.vault / res["review_file"]).exists())
        st = self.state()
        self.assertGreater(st["xp"], xp0)
        self.assertEqual(st["grades"][-1]["qid"], "样例-01")
        self.assertEqual(st["practice"][-1]["source"], "批改")
        api.shenlun_grade({"qid": "样例-01", "answer": GOOD})
        with api.open_game() as g:
            g.housekeeping()
            acc = g.accuracy("归纳概括")
            self.assertAlmostEqual(acc["rate"], 1.0)
            self.assertEqual(len(acc["per"]), 2)
            roots = {r["board"]: r for r in g.roots()}
            self.assertTrue(roots["归纳概括"]["on"])          # 连续两次批改得分率达标 → 专长养成

    def test_draft_grade_is_trial(self):
        f = self.vault / "训练/采分点/样例-01.md"
        f.write_text(f.read_text(encoding="utf-8").replace("状态: 已定稿", "状态: 草稿"), encoding="utf-8")
        xp0 = self.state()["xp"]
        res = api.shenlun_grade({"qid": "样例-01", "answer": GOOD})
        self.assertTrue(res["draft"])
        st = self.state()
        self.assertEqual(st["xp"], xp0)                         # 试批不给政绩
        self.assertEqual([x for x in st["practice"] if x.get("source") == "批改"], [])
        self.assertTrue(st["grades"][-1]["draft"])

    def test_low_score_and_errors(self):
        res = api.shenlun_grade({"qid": "样例-01", "answer": HALF})
        self.assertLess(res["rate"], 0.9)
        with self.assertRaises(api.ApiError):
            api.shenlun_grade({"qid": "样例-01", "answer": "  "})
        n = len(self.state().get("grades", []))
        with self.assertRaises(api.ApiError):
            api.shenlun_grade({"qid": "不存在", "answer": GOOD})
        self.assertEqual(len(self.state().get("grades", [])), n)   # 失败不记录

    # ------------------------------------------------------------ 导入与起草
    def test_import_and_draft_never_overwrites(self):
        b64 = base64.b64encode(DOC.encode("utf-8")).decode()
        j = api.shenlun_import({"name": "样例卷.txt", "data": b64})
        self.assertEqual(j["questions"][0]["score"], 10)
        self.assertTrue((self.vault / "训练/资料/样例卷.txt").exists())
        with self.assertRaises(api.ApiError):
            api.shenlun_import({"name": "a.docx", "data": b64})
        with patch.object(ai, "chat_json", fake_ai):
            r1 = api.shenlun_draft({"file": "样例卷.txt", "prefix": "导入", "no": 1})
            self.assertFalse(r1["skipped"])
            f = self.vault / "训练/采分点/导入-01.md"
            f.write_text(f.read_text(encoding="utf-8") + "\n用户手改\n", encoding="utf-8")
            self.assertTrue(api.shenlun_draft({"file": "样例卷.txt", "prefix": "导入", "no": 1})["skipped"])
            self.assertIn("用户手改", f.read_text(encoding="utf-8"))
            self.assertFalse(api.shenlun_draft({"file": "样例卷.txt", "prefix": "导入", "no": 1, "overwrite": True})["skipped"])
            with self.assertRaises(api.ApiError):
                api.shenlun_draft({"file": "../x.txt", "prefix": "a", "no": 1})

    # ------------------------------------------------------------ 作答计时（服务端校验）
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
