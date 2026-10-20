"""师傅解惑的提示词要求分段、加粗、选项用表格（界面会渲染 Markdown），而不是一大段文字。"""
import unittest

from rpg import prompts


PERSONA = {"导师名": "导师", "导师人设": "严厉", "称呼": "弟子", "吐槽尺度": "中"}


class ExplainFormatTest(unittest.TestCase):
    def test_bank_explain_asks_for_structured_format(self):
        q = {"board": "逻辑填空", "stem": "题干", "options": {"A": "甲", "B": "乙"}, "answer": "B", "analysis": ""}
        msgs = prompts.bank_explain(PERSONA, q, "A", "资料", "skill")
        text = msgs[-1]["content"]
        for need in ("**结论：选 X**", "| 选项 | 判断 | 理由 |", "一招", "不要写成一整大段"):
            self.assertIn(need, text)
        self.assertNotIn("不用 Markdown 标题。", text)

    def test_group_and_discuss_prompts_ask_for_paragraphs_and_tables(self):
        g = prompts.group_explain(PERSONA, "条件", [{"label": "第1题", "stem": "题", "answer": "A", "mine": "B"}], "资料", "skill")
        self.assertIn("| 选项 | 判断 | 理由 |", g[-1]["content"])
        d = prompts.discuss(PERSONA, {"question": "题", "answer": "A"}, "资料", "为什么")
        self.assertIn("表格", d[0]["content"])


if __name__ == "__main__":
    unittest.main()
