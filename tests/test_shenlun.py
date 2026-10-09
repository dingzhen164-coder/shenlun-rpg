"""申论采分点与批改：解析/校验/分值分配/算分、从解析文档起草（自编小样本 + 假 AI，不含真题原文）、批改流程、成绩计入政绩与专长。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_grade_ai import FakeAI  # noqa: E402
from rpg import ai, paths  # noqa: E402
from rpg import shenlun_analysis as analysis, shenlun_grader as grader, shenlun_rubric as rubric  # noqa: E402

# 自编样本：模仿解析文档转文字后的样子——页眉页脚、水印碎字、被换行且中间夹着相邻列的单元格
DOC = """        ©2026 某机构。仅供学习                                                  页眉

样例卷 · 第1题

❓ 题干
请根据“给定资料1”，概括A社区网格化服务的做法。（10分）
要求：全面准确，有条理，不超过200字。

样例卷第1题 · 解题解析

一、题型判定
题型：归纳概括题

五、得分要点清单

 序号        前置提炼                核心采分点（关键词）
                         划分网格、配备网格员、
 ①      建立网格体系               每格不超过300户
                                                      /抖
                                          印
 ②      搭建数据平台      整合部门数据、手机端上报、
                           限时办结/
 ③                                             第3段
                           回访群众
                                     撤销项目
                                                       @某机构 第 4 页 / 共 19 页
【加分点】
 核心理念     "小事不出网格"

六、常见误区
参考答案1（👍 5）
一、建立网格体系。划分网格，配备网格员。
"""


def fake_ai(messages):
    return {
        "points": [
            {"name": "建立网格体系", "keywords": ["划分网格", "配备网格员", "每格不超过300户"], "source": "第1段"},
            {"name": "搭建数据平台", "keywords": ["整合部门数据", "手机端上报", "限时办结/回访群众", "凭空编的词"], "source": ""},
        ],
        "bonus": [{"name": "核心理念", "keywords": ["小事不出网格"], "source": ""}],
    }


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "申论"     # 本文件的测试跑在这个科目下（rpg/subjects.py）


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class AnalysisTest(unittest.TestCase):
    def test_split_and_clean(self):
        bs = analysis.split_questions(DOC)
        self.assertEqual(len(bs), 1)
        b = bs[0]
        self.assertEqual((b["no"], b["score"], b["words"], b["type"]), (1, 10, 200, "归纳概括题"))
        self.assertNotIn("某机构", b["table"])      # 页眉页脚已去掉
        self.assertNotIn("/抖", b["table"])         # 水印已去掉
        self.assertIn("撤销项目", b["table"])        # 纯中文 4 字的被换行单元格要保留
        self.assertEqual(len(b["answers"]), 1)

    def test_draft_validates_keywords_and_allocates(self):
        b = analysis.split_questions(DOC)[0]
        r, warns = analysis.draft(b, fake_ai, "样例-01")
        self.assertEqual([p["score"] for p in r["points"]], [5, 5])
        self.assertEqual(r["status"], rubric.STATUS_DRAFT)
        kws = r["points"][1]["keywords"]
        self.assertIn("限时办结/回访群众", kws)       # 被换行拆开的关键词，按片段核对通过
        self.assertNotIn("凭空编的词", kws)          # 原文里没有的关键词被丢弃
        self.assertEqual(len(warns), 1)
        self.assertEqual(rubric.validate(r, final=True), [])


class RubricTest(unittest.TestCase):
    def setUp(self):
        b = analysis.split_questions(DOC)[0]
        self.r, _ = analysis.draft(b, fake_ai, "样例-01")

    def test_roundtrip(self):
        r2 = rubric.parse(rubric.dumps(self.r))
        self.assertEqual(r2["total"], 10)
        self.assertEqual([p["keywords"] for p in r2["points"]], [p["keywords"] for p in self.r["points"]])
        self.assertEqual(r2["bonus"][0]["score"], 1)

    def test_allocate(self):
        self.assertEqual(rubric.allocate(10, 5), [2, 2, 2, 2, 2])
        self.assertEqual(rubric.allocate(10, 3), [3.5, 3.5, 3])
        self.assertEqual(sum(rubric.allocate(20, 7)), 20)
        self.assertEqual(rubric.allocate(10, 2, [3, 1]), [7.5, 2.5])

    def test_validate(self):
        r = rubric.parse(rubric.dumps(self.r))
        r["points"][0]["score"] = 9
        self.assertTrue(any("超过总分" in e for e in rubric.validate(r)))
        r["points"][0]["score"], r["points"][1]["score"] = 3, 3
        self.assertTrue(any("不等于总分" in e for e in rubric.validate(r, final=True)))
        self.assertEqual(rubric.validate(r), [])  # 草稿阶段只要不超过总分

    def test_score(self):
        ans = "划分网格，配备网格员。整合部门数据，手机端上报。小事不出网格。" + "字" * 100
        j = {1: {"hit": "full", "evidence": "划分网格，配备网格员"},
             2: {"hit": "half", "evidence": "整合部门数据"},
             "加1": {"hit": "full", "evidence": "小事不出网格"}}
        res = rubric.score(self.r, ans, j)
        self.assertEqual(res["content"], 7.5)
        self.assertEqual(res["bonus"], 1)
        self.assertEqual(res["total"], 8.5)
        self.assertAlmostEqual(res["rate"], 0.85)

    def test_score_rejects_fake_evidence_and_caps(self):
        ans = "划分网格。" + "字" * 100
        res = rubric.score(self.r, ans, {1: {"hit": "full", "evidence": "AI 编造的依据句"}})
        self.assertEqual(res["points"][0]["hit"], "none")
        self.assertTrue(res["points"][0]["flag"])
        j = {1: {"hit": "full", "evidence": "划分网格"}, 2: {"hit": "full", "evidence": "划分网格"}, "加1": {"hit": "full", "evidence": "划分网格"}}
        self.assertEqual(rubric.score(self.r, ans, j)["total"], 10)  # 加分后不超过总分

    def test_word_rules(self):
        j = {1: {"hit": "full", "evidence": "划分网格"}, 2: {"hit": "full", "evidence": "划分网格"}}
        over = rubric.score(self.r, "划分网格" + "字" * 300, j)           # 超 200 字上限 10% 以上
        self.assertEqual(over["deductions"][0]["points"], 1)
        self.assertEqual(over["total"], 9)
        short = rubric.score(self.r, "划分网格", j)                        # 不足上限一半
        self.assertEqual(short["deductions"][0]["points"], 2)
        ok = rubric.score(self.r, "划分网格" + "字" * 210, j)              # 超 5%，在宽限内
        self.assertEqual(ok["deductions"], [])


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
        self.tmp = tempfile.TemporaryDirectory()
        self._old = (paths.SETTINGS_DIR, paths.SETTINGS_FILE)       # 隔离本机设置，不碰真实的 ~/.shenlun-rpg
        paths.SETTINGS_DIR = Path(self.tmp.name)
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        os.environ["DEEPSEEK_API_KEY"] = "test-key"

    def tearDown(self):
        paths.SETTINGS_DIR, paths.SETTINGS_FILE = self._old
        self.tmp.cleanup()

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
