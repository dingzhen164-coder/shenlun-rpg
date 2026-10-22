"""3.6.8功能回归：自编题/本地心法/假时钟，不调用真实AI或读取用户库。"""
import base64
import copy
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rpg import config, engine, html_mock, idioms, importer, paths, prompts, question_bank, skillbook, store, study_clock, trainer, vault
from test_html_mock import body, fixture


class Repairs368Test(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for ctx in (patch.object(Path, 'home', return_value=root/'home'), patch.dict(os.environ, {'SHENLUN_SUBJECT':'行测'})):
            ctx.start(); self.addCleanup(ctx.stop)
        self.p = paths.Paths(root/'vault', '行测'); self.p.ensure_train_dir()
        day = dt.date(2026,10,22)
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)

    def test_real_skill_plan_is_used_but_references_and_answers_are_not(self):
        skillbook.save(self.p, '类比推理', 'SKILL.md', '先比关系，再比方向。', '')
        skillbook.save(self.p, '类比推理', 'references/example.md', '禁止自动读取_REF', '')
        q = dict(board='类比推理', stem='自编关系', options={'A':'甲','B':'乙'}, answer='答案_CANARY', analysis='解析_CANARY')
        with patch.object(trainer.ai,'chat',return_value='自编解答') as chat:
            _, _, used = trainer._explain(self.g,q,{'answer':'作答_CANARY'})
        payload=str(chat.call_args.args[0]); self.assertIn('先比关系，再比方向',payload)
        self.assertEqual(used,['SKILL.md'])
        for value in ('禁止自动读取_REF','答案_CANARY','解析_CANARY','作答_CANARY'): self.assertNotIn(value,payload)

    def test_all_option_idioms_and_deduplicated_sources(self):
        q=dict(board='逻辑填空',topic='逻辑填空',stem='自编____。',options=dict(A='方兴未艾',B='如火如荼',C='蒸蒸日上',D='崭露头角'),answer='A',analysis='',key='逻辑填空::368',id='368')
        before={k:copy.deepcopy(self.g.state[k]) for k in ('xp','seconds','boss')}
        for _ in range(2): idioms.from_explanation(self.g,q,'“如火如荼”形容气势旺盛。')
        self.assertEqual(set(idioms.data(self.g)),set(q['options'].values()))
        for entry in idioms.data(self.g).values(): self.assertEqual(len(entry['sources']),1)
        src=idioms.data(self.g)['如火如荼']['sources'][0]
        self.assertEqual((src['option'],src['answer']),('B','A'))
        self.assertNotIn('正确答案是「如火如荼」',str(prompts.idiom_compare(self.g.persona,'如火如荼',src)))
        for k,v in before.items(): self.assertEqual(v,self.g.state[k])

    def test_accuracy_import_and_repeat_preserve_original_review(self):
        b=body(); b['data']=base64.b64encode(fixture().replace('</app-ti>','<div class="answer-accuracy">全站正确率：65.25%</div></app-ti>').encode()).decode()
        preview=html_mock.import_file(self.p,b)
        result=html_mock.import_file(self.p,dict(b,commit=True,digest=preview['digest']))
        self.assertEqual(set(result['html_meta']['question_accuracy'].values()),{65.25})
        qs,errors=question_bank.read(self.p,'资料分析'); self.assertEqual(errors,[])
        self.assertTrue(all(q['source_accuracy']==65.25 for q in qs))
        review=next(self.p.train.glob('模考复盘/第39季/*.md'))
        self.assertTrue(all(q['source_accuracy']==65.25 for q in vault.parse_board_file(review)))
        original=review.read_bytes(); html_mock.import_file(self.p,dict(b,commit=True,digest=preview['digest']))
        self.assertEqual(original,review.read_bytes())

    def test_missing_or_invalid_accuracy_is_not_invented(self):
        for text in ('正确率未知','正确率：101%','正确率：-1%','答对65题','65.25'):
            self.assertIsNone(vault.parse_accuracy(text),text)
        self.assertEqual(vault.parse_accuracy('全站正确率：０％'),0)
        self.assertEqual(vault.parse_accuracy('65.25%'),65.25)

    def test_old_lines_get_new_variants_without_overwriting_user_text(self):
        fallback=(Path(__file__).parents[1]/'defaults/台词库.md').read_text(encoding='utf-8')
        lines=config.Lines('## 试炼·复盘错题\n- 自定义句子\n',fallback)
        self.assertIn('自定义句子',lines.sec['试炼·复盘错题']); self.assertGreaterEqual(len(lines.sec['试炼·复盘错题']),10)
        values=[lines.pick('试炼·复盘错题',你的答案='B',正确答案='A') for _ in range(30)]
        self.assertTrue(all(a!=b for a,b in zip(values,values[1:])))

    def test_six_ten_second_awards_equal_one_minute(self):
        before=self.g.state['xp']; self.g.state['xp_carry']=0
        for _ in range(6): self.g.add_seconds(10)
        self.assertEqual(self.g.state['xp']-before,self.g.rules.xp('修炼每分钟'))
        self.assertGreaterEqual(self.g.state['xp_carry'],0)


class HeartbeatBudget368Test(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.p=SimpleNamespace(vault=Path(self.temp.name),subject='行测'); self.now=1000.0
        clock=patch.object(study_clock,'_now',side_effect=lambda:self.now); clock.start(); self.addCleanup(clock.stop)

    def test_retry_tabs_and_sources_share_one_elapsed_budget(self):
        self.assertEqual(study_clock.seconds(self.p,90),0)
        self.now+=30; self.assertEqual(study_clock.seconds(self.p,30),30)
        for _ in range(10): self.assertEqual(study_clock.seconds(self.p,90),0)
        study_clock.seconds(self.p)  # 刷新dashboard也不能恢复已经领取的预算。
        self.assertEqual(study_clock.seconds(self.p,30),0)
        self.now+=.7; self.assertEqual(study_clock.seconds(self.p,90),0)
        self.now+=.4; self.assertEqual(study_clock.seconds(self.p,90),1)

    def test_budget_caps_and_subject_isolation(self):
        study_clock.seconds(self.p); self.now+=1000
        self.assertEqual(study_clock.seconds(self.p,999),90)
        other=SimpleNamespace(vault=self.p.vault,subject='申论')
        self.assertEqual(study_clock.seconds(other,30),0)
        self.assertEqual(study_clock.seconds(SimpleNamespace(vault=None),30),0)
