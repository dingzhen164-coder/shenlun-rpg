"""申论路由：题目列表、定稿、批改写记录与复盘文件、草稿不计入预估分。"""
import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import ai, api  # noqa: E402
from core.paths import Paths  # noqa: E402
from core.store import Store  # noqa: E402
from fake_ai_server import FakeAI  # noqa: E402
from subjects.shenlun import routes  # noqa: E402
from test_grader import GOOD, RUBRIC  # noqa: E402

TODAY = dt.date(2026, 10, 2)
NOW = dt.datetime(2026, 10, 2, 9, 30, 15)


class RoutesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paths = Paths(self.tmp.name)
        self.paths.ensure_train_dir()
        (self.paths.rubric_dir / "样例-01.md").write_text(RUBRIC.replace("已定稿", "草稿"), encoding="utf-8")
        os.environ["DEEPSEEK_API_KEY"] = "k"

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, method, path, body=None, query=""):
        with FakeAI("ok") as srv:
            os.environ["SHENLUN_AI_BASE_URL"] = srv.url
            return routes.handle(method, path, query, body or {}, self.paths, TODAY, ai.chat_json, NOW)

    def test_list_and_get(self):
        qs = self.call("GET", "/api/shenlun/questions")["questions"]
        self.assertEqual((qs[0]["qid"], qs[0]["status"], qs[0]["points"]), ("样例-01", "草稿", 2))
        q = self.call("GET", "/api/shenlun/question", query="qid=样例-01")
        self.assertIn("A社区", q["stem"])
        with self.assertRaises(routes.ApiError):
            self.call("GET", "/api/shenlun/question", query="qid=不存在")
        with self.assertRaises(routes.ApiError):
            self.call("GET", "/api/shenlun/question", query="qid=../x")

    def test_draft_grade_is_trial_and_not_counted(self):
        res = self.call("POST", "/api/shenlun/grade", {"qid": "样例-01", "answer": GOOD})
        self.assertTrue(res["draft"])
        self.assertTrue((self.paths.vault / res["review_file"]).exists())
        self.assertIn("得分：**10", (self.paths.vault / res["review_file"]).read_text(encoding="utf-8"))
        d = api.dashboard(TODAY, Store(self.paths))
        self.assertEqual(d["stats"]["total"], 1)
        self.assertEqual(d["stats"]["rated"], 0)          # 试批不进预估分
        self.assertIsNone(d["rank"]["score"])

    def test_finalize_then_counted(self):
        self.call("POST", "/api/shenlun/finalize", {"qid": "样例-01"})
        res = self.call("POST", "/api/shenlun/grade", {"qid": "样例-01", "answer": GOOD})
        self.assertFalse(res["draft"])
        d = api.dashboard(TODAY, Store(self.paths))
        self.assertEqual(d["stats"]["rated"], 1)
        self.assertEqual(d["rank"]["score"], 100.0)
        self.assertEqual(d["daily"]["question"]["id"], "样例-01")  # 有真题时每日一题取真题

    def test_finalize_rejects_bad_rubric(self):
        f = self.paths.rubric_dir / "样例-01.md"
        f.write_text(f.read_text(encoding="utf-8").replace("[5] 搭建", "[3] 搭建"), encoding="utf-8")
        with self.assertRaises(routes.ApiError) as cm:
            self.call("POST", "/api/shenlun/finalize", {"qid": "样例-01"})
        self.assertIn("不等于总分", cm.exception.msg)

    def test_grade_errors(self):
        with self.assertRaises(routes.ApiError) as cm:
            self.call("POST", "/api/shenlun/grade", {"qid": "样例-01", "answer": ""})
        self.assertEqual(cm.exception.code, 502)
        self.assertEqual(Store(self.paths).load(TODAY)["records"], [])  # 失败不记录


if __name__ == "__main__":
    unittest.main()
