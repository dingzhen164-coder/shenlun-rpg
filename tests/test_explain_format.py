"""师傅解惑的提示词要求分段、加粗、选项用表格（界面会渲染 Markdown），而不是一大段文字。"""
import unittest

from rpg import prompts


PERSONA = {"导师名": "导师", "导师人设": "严厉", "称呼": "弟子", "吐槽尺度": "中"}


class ExplainFormatTest(unittest.TestCase):
    def test_explanations_follow_skill_without_word_count_or_template(self):
        q={"board":"逻辑填空","stem":"题干独立标记","options":{"A":"甲","B":"乙"},"answer":"答案秘密标记","analysis":"旧解析秘密标记"}
        messages=[prompts.bank_explain(PERSONA,q,"学员秘密标记","心法专属标记","skill"),
                  prompts.group_explain(PERSONA,"条件",[{"label":"第1题","stem":"题"}],"心法专属标记","skill"),
                  prompts.discuss(PERSONA,{"question":"题"},"心法专属标记","为什么")]
        for msgs in messages:
            text='\n'.join(m['content'] for m in msgs)
            self.assertIn('心法专属标记',text)
            self.assertIn('完整、不重复',text)
            self.assertNotRegex(text,r'\d+\s*字以内|每段.{0,8}句|必须用表格')
            self.assertNotIn('**结论：选 X**',text)
        independent=str(messages[0])
        for secret in ['答案秘密标记','旧解析秘密标记','学员秘密标记']:
            self.assertNotIn(secret,independent)
        self.assertIn('禁止搜索正确答案',independent)
        self.assertIn('不要用 LaTeX',independent)

    def test_plain_math_turns_latex_into_readable_text(self):
        raw = r"设总人数为 \(100a+10b+c\)。得 \(90(a-b)=270\)，所以 \(b=a-3\)；\(x\equiv3\pmod4\)，\(x\le12\)，\(\frac{5x+4y}{2}\)，\(x^2\times y^{10}\)；价格$5和$6不变"
        out = prompts.plain_math(raw)
        self.assertEqual(out, "设总人数为 100a+10b+c。得 90(a-b)=270，所以 b=a-3；x≡3（mod 4），x≤12，(5x+4y)/2，x²×y¹⁰；价格$5和$6不变")
        self.assertEqual(prompts.plain_math("没有公式 1+1=2"), "没有公式 1+1=2")


if __name__ == "__main__":
    unittest.main()
