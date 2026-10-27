"""解惑完整输出：不再压成固定短文，保留心法资料与来源，长回复不被本地截断。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from rpg import trainer, prompts


class CompleteExplanationTest(unittest.TestCase):
    def test_long_explanation_is_returned_whole_with_room_to_finish(self):
        persona={'导师名':'导师','导师人设':'严谨','称呼':'学员','吐槽尺度':'低'}
        game=SimpleNamespace(persona=persona,boards={'论证逻辑':{'skill':'方法资料'}})
        question={'board':'论证逻辑','stem':'自编题干','options':{'A':'甲','B':'乙'},'answer':'A','analysis':''}
        material=('心法来源标记',['心法.md'])
        if hasattr(trainer,'KNOW'):
            material=material+('skill',)
        long_text='\n'.join('第%d项推理依据与条件。'%i for i in range(200))
        with patch.object(trainer,'_tutor_material',return_value=material), patch.object(trainer.ai,'chat',return_value=long_text) as chat:
            with patch.object(trainer.idioms,'from_explanation',create=True):
                result,skill,used=trainer._explain(game,question,{'answer':'B'})
        self.assertEqual(result,long_text)
        self.assertEqual(used,['心法.md'])
        self.assertGreaterEqual(chat.call_args.kwargs['max_tokens'],8000)
        prompt='\n'.join(m['content'] for m in chat.call_args.args[0])
        self.assertIn('心法来源标记',prompt)
        self.assertIn('完整、不重复',prompt)
        self.assertNotRegex(prompt,r'\d+\s*字以内|必须用表格|每段.{0,8}句')

    def test_single_group_and_followup_keep_method_without_fixed_word_cap(self):
        p={'导师名':'导师','导师人设':'严谨','称呼':'学员','吐槽尺度':'低'}
        q={'board':'论证逻辑','stem':'题干','options':{},'answer':'A','analysis':''}
        messages=[prompts.bank_explain(p,q,'B','心法来源标记','方法资料'),
                  prompts.group_explain(p,'条件',[dict(q,label='第1题',mine='B')],'心法来源标记','方法资料'),
                  prompts.discuss(p,{'question':'题干'},'心法来源标记','为什么')]
        if hasattr(prompts,'law_explain'):
            messages.append(prompts.law_explain(p,q,'B','心法来源标记'))
        for msgs in messages:
            text='\n'.join(m['content'] for m in msgs)
            self.assertIn('心法来源标记',text)
            self.assertIn('完整、不重复',text)
            self.assertNotRegex(text,r'\d+\s*字以内|必须用表格|每段.{0,8}句')
