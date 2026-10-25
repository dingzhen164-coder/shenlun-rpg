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

    def test_quantitative_explain_skips_option_table_and_forbids_latex(self):
        q = {"board": "数量关系", "stem": "某数加3等于5，求该数", "options": {"A": "1", "B": "2"}, "answer": "B", "analysis": ""}
        text = prompts.bank_explain(PERSONA, q, None, "资料", "数量关系")[-1]["content"]
        self.assertIn("不要逐项分析选项，不要画表格", text)
        self.assertNotIn("| 选项 | 判断 | 理由 |", text)
        self.assertIn("不要用 LaTeX", text)
        logic = prompts.bank_explain(PERSONA, dict(q, board="论证逻辑"), None, "资料", "论证逻辑")[-1]["content"]
        self.assertIn("| 选项 | 判断 | 理由 |", logic)           # 其他板块仍逐项用表格
        self.assertIn("不要用 LaTeX", logic)
        # 板块只在 skill 名里时也认（试炼复盘走这条）
        self.assertIn("不要画表格", prompts.bank_explain(PERSONA, {"stem": "题", "options": {}}, None, "资料", "数量关系")[-1]["content"])

    def test_plain_math_turns_latex_into_readable_text(self):
        raw = r"设总人数为 \(100a+10b+c\)。得 \(90(a-b)=270\)，所以 \(b=a-3\)；\(x\equiv3\pmod4\)，\(x\le12\)，\(\frac{5x+4y}{2}\)，\(x^2\times y^{10}\)；价格$5和$6不变"
        out = prompts.plain_math(raw)
        self.assertEqual(out, "设总人数为 100a+10b+c。得 90(a-b)=270，所以 b=a-3；x≡3（mod 4），x≤12，(5x+4y)/2，x²×y¹⁰；价格$5和$6不变")
        self.assertEqual(prompts.plain_math("没有公式 1+1=2"), "没有公式 1+1=2")


if __name__ == "__main__":
    unittest.main()
