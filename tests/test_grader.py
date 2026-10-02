"""批改流程：用假 AI 服务（tests/fake_ai_server.py）端到端测试，包括重试、依据句核验、草稿标记、标定。"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import ai  # noqa: E402
from fake_ai_server import FakeAI  # noqa: E402
from subjects.shenlun import grader, rubric  # noqa: E402

RUBRIC = """---
题目: 样例-01
状态: 已定稿
总分: 10
字数: 200
题型: 归纳概括
---
## 采分点
- [5] 建立网格体系 | 关键词: 划分网格；配备网格员 | 依据: 第1段
- [5] 搭建数据平台 | 关键词: 整合部门数据；手机端上报；限时办结 | 依据: 第3段
## 加分点
- [+1] 核心理念 | 关键词: 小事不出网格
## 题干
请概括A社区网格化服务的做法。（10分）
"""
GOOD = "一、建立网格体系。划分网格，配备网格员。二、搭建数据平台。整合部门数据，手机端上报，限时办结。小事不出网格。" + "字" * 80
HALF = "一、建立网格体系。划分网格，配备网格员。二、搭建数据平台。手机端上报。" + "字" * 80


class GraderTest(unittest.TestCase):
    def setUp(self):
        self.r = rubric.parse(RUBRIC)
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

    def run_with(self, mode, answer, r=None, **kw):
        with FakeAI(mode) as srv:
            os.environ["SHENLUN_AI_BASE_URL"] = srv.url
            try:
                return grader.grade(r or self.r, answer, ai.chat_json, **kw), srv
            finally:
                pass

    def test_prompt_contains_rubric_and_answer(self):
        m = grader.build_messages(self.r, "我的作答")
        text = m[1]["content"]
        for s in ("划分网格；配备网格员", "加1", "我的作答", "A1 漏采分点", "请概括A社区"):
            self.assertIn(s, text)

    def test_full_marks_and_cap(self):
        res, _ = self.run_with("ok", GOOD)
        self.assertEqual(res["total"], 10)           # 满分 + 加分，封顶 10
        self.assertEqual(res["bonus"], 1)
        self.assertFalse(res["draft"])
        self.assertTrue(res["summary"])

    def test_half_credit_and_lost(self):
        res, _ = self.run_with("ok", HALF)
        self.assertEqual(res["content"], 7.5)        # 5 + 5×0.5
        self.assertEqual(res["lost"][0]["code"], "A1")
        self.assertEqual(res["points"][1]["hit"], "half")
        self.assertEqual(res["points"][1]["reason"], "关键词命中 1/3")

    def test_retry_once_then_ok(self):
        res, srv = self.run_with("bad_once", GOOD)
        self.assertEqual(srv.calls, 2)
        self.assertEqual(res["total"], 10)

    def test_gives_up_after_two_bad_replies(self):
        with self.assertRaises(grader.GradeError):
            self.run_with("always_bad", GOOD)

    def test_fake_evidence_is_rejected(self):
        res, _ = self.run_with("fake_evidence", GOOD)
        self.assertEqual(res["content"], 0)
        self.assertTrue(all(p["flag"] for p in res["points"] if not p["bonus"]))

    def test_draft_flag_and_block(self):
        d = rubric.parse(RUBRIC.replace("已定稿", "草稿"))
        res, _ = self.run_with("ok", GOOD, d)
        self.assertTrue(res["draft"])
        with self.assertRaises(grader.GradeError):
            self.run_with("ok", GOOD, d, allow_draft=False)

    def test_empty_answer(self):
        with self.assertRaises(grader.GradeError):
            grader.grade(self.r, "  ", lambda m: {})

    def test_calibrate(self):
        with FakeAI("ok") as srv:
            os.environ["SHENLUN_AI_BASE_URL"] = srv.url
            rows = grader.calibrate(self.r, [GOOD, HALF], ai.chat_json)
        self.assertEqual([x["ok"] for x in rows], [True, False])
        self.assertEqual(rows[1]["missed"], ["搭建数据平台"])


if __name__ == "__main__":
    unittest.main()
