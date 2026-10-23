"""独立解惑的数据边界与折叠：仅题面与本地skill，不发送标准答案/解析/作答/历史。"""
import copy
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpg import config, engine, paths, prompts, store, trainer


def setUpModule():
    os.environ['SHENLUN_SUBJECT']='行测'


def tearDownModule():
    os.environ.pop('SHENLUN_SUBJECT',None)


class IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.pp=paths.Paths(Path(self.tmp.name),'行测');self.pp.ensure_train_dir()
        day=dt.date(2026,10,21)
        self.g=engine.Game(self.pp,config.Rules(),config.Persona(),config.Lines(),store.new_state(day),day)
        self.q={'board':'类比推理','id':'自编1','stem':'自编题干：甲与乙的关系？','options':{'A':'选项甲','B':'选项乙'},'answer':'A','analysis':'原解析_CANARY','tutor':'旧讲解_CANARY','topic':'标签_CANARY'}

    def test_single_wire_payload_ignores_existing_explanations_and_attempt(self):
        with patch.object(trainer,'_tutor_material',return_value=('自编心法_LOCAL',['SKILL.md'])) as material,patch.object(trainer.ai,'chat',return_value='自编讲解') as chat,patch.object(trainer.idioms,'from_explanation'):
            trainer._explain(self.g,self.q,{'answer':'作答_CANARY'})
        payload=str(chat.call_args.args[0])
        material.assert_called_once_with(self.g, '类比推理')
        for text in ('自编题干','选项甲','选项乙','自编心法_LOCAL','禁止搜索正确答案'):
            self.assertIn(text,payload)
        for text in ('原解析_CANARY','旧讲解_CANARY','作答_CANARY','标签_CANARY','正确答案：A'):
            self.assertNotIn(text,payload)
        p=self.g.persona
        a=prompts.bank_explain(p,self.q,'作答_CANARY','资料_CANARY','skill_CANARY')
        changed=dict(self.q,analysis='另一解析',tutor='另一旧讲解')
        self.assertEqual(a,prompts.bank_explain(p,changed,'另一作答','资料_CANARY','skill_CANARY'))
        self.assertIn('资料_CANARY',str(a))

    def test_group_wire_payload_does_not_include_members_attempts_or_references(self):
        items=[{'label':'第1题','stem':'自编条件与选项A.甲 B.乙','answer':'A','mine':'组作答_CANARY','analysis':'组解析_CANARY'}]
        with patch.object(trainer,'_tutor_material',return_value=('自编组心法',['SKILL.md'])),patch.object(trainer.ai,'chat',return_value='自编整组讲解') as chat:
            trainer._explain_group(self.g,'一拖五','自编共用材料',items)
        payload=str(chat.call_args.args[0]);self.assertIn('自编共用材料',payload)
        self.assertIn('自编组心法',payload);self.assertNotIn('正确答案：A',payload);self.assertNotIn('组作答_CANARY',payload);self.assertNotIn('组解析_CANARY',payload)

    def test_wrong_question_explain_button_ignores_discussion_history(self):
        session={'discuss':{'board':'类比推理','question':'自编题干及A甲B乙','answer':'A','mine':'错题作答_CANARY','reference':'错题解析_CANARY','previous':'前次_CANARY','history':[{'role':'assistant','content':'历史_CANARY'}]}}
        with patch.object(trainer.ai,'available',return_value=True),patch.object(trainer,'_skill_digest',return_value='自编错题心法'),patch.object(trainer.ai,'chat',return_value='自编解释') as chat:
            result=trainer._discuss_ask(self.g,session,'请独立讲解',independent=True)
        payload=str(chat.call_args.args[0]);self.assertIn('自编题干及A甲B乙',payload)
        self.assertNotIn('_CANARY',payload)
        self.assertIn('自编错题心法',payload)
        self.assertEqual(result[0]['fold'],'🧙 师傅解惑')
        self.assertEqual(session['discuss']['history'][-1]['content'],'自编解释')

    def test_bank_review_keeps_blocks_in_fold_and_reopens_saved_tutor_closed(self):
        q=dict(self.q,topic='类比',analysis='自编原解析',stem='自编题干')
        run={'questions':[q],'results':[{'answer':'B','ok':False,'seconds':2}], 'settled':{'correct':0,'total':1,'rank':0},'explain':{'0':'自编已保存讲解'},'rpos':0,'chat':{},'board':'类比推理'}
        session={'id':'自编session','type':'bank','title':'自编复盘','task':{}}
        with patch.object(trainer,'_bank_resp',side_effect=lambda g,s,r,msgs,ev,inp:{'messages':msgs}),patch.object(trainer,'_say',return_value=''),patch.object(trainer,'_bank_blocks',return_value=[{'t':'text','v':'自编原解析'},{'t':'img','v':'自编图.png'}]):
            first=trainer._review_show(self.g,session,run)
            again=trainer._review_show(self.g,session,run)
        folds=[m for m in first['messages'] if m.get('fold')]
        self.assertTrue(any(m.get('blocks') and m['blocks'][-1]['t']=='img' for m in folds))
        self.assertTrue(any(m['text']=='自编已保存讲解' for m in folds))
        self.assertEqual(first,again)
        self.assertTrue(all(not m.get('open') for m in folds))

    def test_explain_still_saves_when_discussion_history_reaches_limit(self):
        session={'id':'mock-session','type':'wrong','title':'自编错题','task':{},'key':'38|类比推理|1',
                 'discuss':{'board':'类比推理','question':'自编题干A甲B乙','answer':'A','reference':'原解析_CANARY',
                            'history':[{'role':'assistant','content':'历史_CANARY'} for _ in range(10)]}}
        with patch.object(trainer.ai,'available',return_value=True),patch.object(trainer.ai,'chat',return_value='自编最新讲解') as chat,patch.object(trainer.vault,'save_tutor_note',return_value='自编资料') as save:
            result=trainer._discuss_action(self.g,session,'ask_explain')
        self.assertEqual(len(session['discuss']['history']),10)
        self.assertEqual(save.call_args.args[2],'自编最新讲解')
        self.assertIn('已存入复盘解析',str(result))
        self.assertNotIn('_CANARY',str(chat.call_args.args[0]))
