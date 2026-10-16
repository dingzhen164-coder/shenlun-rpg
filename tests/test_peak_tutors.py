"""五峰求助：临时人物资料/假HOME/假AI，验证身份路由、可编辑性格与原存档不改。"""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rpg import config, peak_tutors, trainer


class PeakTutorsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.home=patch.object(Path,'home',return_value=root/'home');self.home.start();self.addCleanup(self.home.stop)
        self.g=SimpleNamespace(subject='行测',persona=config.Persona(),paths=SimpleNamespace(vault=root,train=root/'训练'),state={},boards={})

    def test_all_boards_match_existing_five_peaks(self):
        for cid,name,role,boards in peak_tutors.PEAKS:
            for b in boards:
                self.assertEqual(peak_tutors.profile(self.g,b)['id'],cid)
                p=peak_tutors.persona(self.g,b)
                self.assertEqual(p['导师名'],name)
                self.assertNotEqual(p['导师人设'],self.g.persona['导师人设'])
        self.assertEqual(self.g.persona['导师名'],'劭神韵');self.assertEqual(self.g.state,{})

    def test_custom_personality_and_portrait_reused_without_private_chat(self):
        p=peak_tutors.profile(self.g,'资料分析');card=self.g.paths.train/'人物/行测/xc-chenhuaian/人物卡.md'
        card.write_text(card.read_text(encoding='utf-8').replace('陈怀安','自定义峰主')+'\n',encoding='utf-8')
        p=peak_tutors.persona(self.g,'资料分析')
        self.assertEqual(p['导师名'],'自定义峰主');self.assertIn('说话方式',p['导师人设'])
        self.assertTrue(peak_tutors.profile(self.g,'资料分析')['avatar'].startswith('/vault-file?'))
        self.assertEqual(self.g.state,{})

    def test_mixed_paper_uses_review_position_not_answer_position(self):
        self.g.state={'bank':{'runs':{'套:自编':{'questions':[{'board':'数量关系'},{'board':'片段阅读'}],'phase':'review','pos':1,'rpos':0}}}}
        s={'type':'bank','board':'套:自编'};before=copy.deepcopy(self.g.state)
        r={'session':'s','messages':[{'who':'npc','text':'讲解'}],'input':{'buttons':[{'id':'ask','label':'师傅解惑'}]}}
        peak_tutors.attach(self.g,r,{'s':s});self.assertEqual(r['mentor']['name'],'花生十三');self.assertEqual(r['messages'][0]['mentor'],r['mentor']);self.assertEqual(r['input']['buttons'][0]['label'],'花生十三解惑')
        self.assertEqual(self.g.state,before)
        self.g.state['bank']['runs']['套:自编']['phase']='answer'
        self.assertEqual(peak_tutors.session_board(self.g,s),'片段阅读')

    def test_mock_review_discussion_and_other_subjects(self):
        s={'type':'mock_review','board':'逻辑填空','source':'言语理解'}
        self.assertEqual(peak_tutors.session_board(self.g,s),'逻辑填空')
        s={'type':'wrong','board':'数量关系','discuss':{'board':'资料分析'}}
        r=peak_tutors.attach(self.g,{'session':'s','messages':[]},{'s':s})
        self.assertEqual(r['mentor']['name'],'陈怀安')
        for subject in ['申论','法考']:
            self.g.subject=subject;self.assertIs(peak_tutors.persona(self.g,'资料分析'),self.g.persona)
            r={'session':'s','messages':[]};self.assertEqual(peak_tutors.attach(self.g,r,{'s':s}),r);self.assertNotIn('mentor',r)

    def test_explanation_and_group_prompt_use_corresponding_personality(self):
        for board,name in [('片段阅读','张弓'),('一拖五','薛睿'),('数量关系','花生十三'),('资料分析','陈怀安'),('常识判断','小黑')]:
            q={'board':board,'stem':'自编题干','options':{'A':'甲'},'answer':'A','analysis':'自编解析'}
            with patch.object(trainer.vault,'skill_for_tutor',return_value=('自编方法',[])),patch.object(trainer.ai,'chat',return_value='自编讲解') as chat:
                trainer._explain(self.g,q,{'answer':'A'})
                self.assertIn('你是「'+name+'」',chat.call_args.args[0][0]['content'])
                trainer._explain_group(self.g,board,'自编材料',[dict(label='1',stem='自编题',answer='A',mine='B')])
                self.assertIn('你是「'+name+'」',chat.call_args.args[0][0]['content'])

    def test_bad_profile_falls_back_to_its_peak_and_unknown_board_keeps_tutor(self):
        peak_tutors.profile(self.g,'数量关系');p=self.g.paths.train/'人物/行测/xc-huasheng13/人物卡.md'
        p.write_text('- 人物ID：错误\n',encoding='utf-8')
        self.assertEqual(peak_tutors.profile(self.g,'数量关系')['name'],'花生十三')
        self.assertIs(peak_tutors.persona(self.g,'未知板块'),self.g.persona)
