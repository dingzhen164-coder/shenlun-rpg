"""3.6.5：最高分基准、奖惩边界、境界保留与首次录分幂等；隔离自编数据。"""
import copy
import datetime as dt
import math
import tempfile
import unittest
from pathlib import Path
from rpg import config, engine, mock, mock_rewards as reward, paths, store


class Updates365Test(unittest.TestCase):
    def make(self, subject='行测', progress=1000):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        p = paths.Paths(Path(tmp.name), subject); p.ensure_train_dir()
        day = dt.date(2026, 10, 22)
        g = engine.Game(p, config.Rules(subject=subject), config.Persona(), config.Lines(), store.new_state(day, subject), day)
        base = math.ceil(g.xp_at(52))
        g.state.update(xp=base+progress, claimed=52, mock_rewards={'schema':1, 'legacy_corrected':True, 'records':{}},
                       boss=[{'name':'自编高峰', 'd':g.t, 'score':80, 'kind':'大比'}])
        return g, base

    def test_keep_neutral_and_reward_stage_gate(self):
        for score, expected in [(81,'pending'), (80,'pending'), (78,'pending'), (77.99,'neutral'), (75,'neutral')]:
            with self.subTest(score=score):
                g, _ = self.make(); before = g.state['xp']
                reward.offer(g, '新场', score, g.raw_score())
                r = reward.ledger(g)['records'][reward.exam_key('新场')]
                self.assertEqual(r['status'], expected)
                self.assertEqual(r['best'], 80)
                self.assertEqual(g.state['xp'], before)
        g, _ = self.make(); g.state['boss'][0]['score'] = 53
        reward.offer(g, '未越线', 52, g.raw_score())
        self.assertEqual(reward.ledger(g)['records'][reward.exam_key('未越线')]['status'], 'neutral')

    def test_penalty_exact_boundaries_and_no_demotion(self):
        for gap, rate in [(5.01,.1),(5.99,.1),(6,.2),(6.99,.2),(7,.4),(8,.6),(9,.8),(9.99,.8),(10,1),(20,1)]:
            with self.subTest(gap=gap):
                g, base = self.make(); old_realm = g.realm_info()['name']; claimed = g.claimed()
                reward.offer(g, '新场', 80-gap, g.raw_score())
                rec = reward.ledger(g)['records'][reward.exam_key('新场')]
                self.assertEqual(rec['penalty_rate'], rate)
                self.assertEqual(rec['penalty'], math.ceil(1000*rate))
                self.assertEqual(g.state['xp'], base+1000-math.ceil(1000*rate))
                self.assertEqual(g.claimed(), claimed)
                self.assertEqual(g.realm_info()['name'], old_realm)
                state = copy.deepcopy(g.state)
                self.assertEqual(reward.offer(g, '新场', 10, 90), [])
                self.assertEqual(g.state, state)
        g, base = self.make(progress=0)
        reward.offer(g, '已无进度', 60, g.raw_score())
        self.assertEqual(g.state['xp'], base)

    def test_current_stage_clear_preserves_all_realms_and_overflow(self):
        for score in [51,52,59,60,62,64,65,70,80]:
            with self.subTest(stage=score):
                g, _ = self.make(); g.state.update(gates=g.gates(), claimed=score, xp=math.ceil(g.xp_at(score))+500)
                start = g.realm_info()['name']; claim = g.claimed()
                reward.offer(g, '清空', 60, g.raw_score())
                self.assertEqual(g.claimed(), claim)
                self.assertEqual(g.realm_info()['name'], start)
                self.assertEqual(reward.stage_progress(g)[2], 0)

    def test_edited_history_and_current_exam_excluded(self):
        g, _ = self.make()
        g.state['boss'] = [{'name':'第33季','score':90},{'name':'第133季','score':80},{'name':'正式考试','score':99,'kind':'飞升'}]
        g.state['mocks'] = {'33':{'score':70},'133':{'score':72},'134':{'score':99}}
        self.assertEqual(reward.prior_best(g,'第134季'), 72)
        reward.offer(g,'第134季',70,g.raw_score())
        self.assertEqual(reward.ledger(g)['records'][reward.exam_key('第134季')]['status'],'pending')

    def test_report_first_score_only_and_dates_do_not_repeat_penalty(self):
        g, base = self.make(); before = g.state['xp']
        mock.save(g, {'season':41,'score':69,'date':'2026-10-22'})
        key = reward.exam_key('第41季'); r = reward.ledger(g)['records'][key]
        self.assertEqual(r['status'],'penalized'); self.assertEqual(g.state['xp'],base)
        penalties = [e for e in g.state['events'] if e.get('reward_model')=='best-score-penalty-v1']
        self.assertEqual(len(penalties),1)
        state = copy.deepcopy(g.state)
        mock.save(g, {'season':41,'score':99,'date':'2026-10-10'})
        self.assertEqual(g.state['xp'], state['xp'])
        self.assertEqual(reward.ledger(g),state['mock_rewards'])
        self.assertEqual(len([e for e in g.state['events'] if e.get('reward_model')=='best-score-penalty-v1']),1)

    def test_penalty_removes_stale_ready_notification(self):
        g, _ = self.make()
        g.state['xp'] = math.ceil(g.xp_at(53))-1
        events = g.add_boss('新低分', 69)
        self.assertFalse(g.realm_info()['ready'])
        self.assertFalse(any(e.get('kind') == 'ready' for e in events))

    def test_historical_migration_never_punishes(self):
        g, _ = self.make(); g.state.pop('mock_rewards'); g.state['boss'].append({'name':'旧低分','score':50,'d':g.t})
        before = g.state['xp']; reward.migrate(g); reward.offer(g,'旧低分',50,90)
        self.assertEqual(g.state['xp'],before)
        self.assertEqual(reward.view(g),[])

    def test_rules_and_other_subject_unchanged(self):
        g, _ = self.make(); g.rules.raw['模考悟道.退步扣除比例']='0.05, 0.1, 0.2, 0.3, 0.4'
        reward.offer(g,'按配置',74,g.raw_score());self.assertEqual(reward.ledger(g)['records'][reward.exam_key('按配置')]['penalty'],100)
        g, _ = self.make('申论'); before=g.state['xp'];reward.offer(g,'申论不罚',55,54)
        self.assertEqual(g.state['xp'],before)
        self.assertEqual(reward.ledger(g)['records'][reward.exam_key('申论不罚')]['status'],'pending')


if __name__ == '__main__':
    unittest.main()
