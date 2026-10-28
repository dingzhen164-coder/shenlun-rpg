"""模考悟道：近3次均分基准、退步不罚只提醒、境界保留与首次录分幂等；隔离自编数据。"""
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

    def test_regression_never_penalizes_xp_or_realm(self):
        for gap in [5.01, 6, 7, 9.99, 10, 20, 60]:
            with self.subTest(gap=gap):
                g, base = self.make(); old_realm = g.realm_info()['name']; claimed = g.claimed(); before = g.state['xp']
                ev = reward.offer(g, '新场', 80-gap, g.raw_score())
                rec = reward.ledger(g)['records'][reward.exam_key('新场')]
                self.assertEqual(rec['status'], 'neutral')
                self.assertNotIn('penalty', rec)
                self.assertEqual(g.state['xp'], before)          # 修为一分不扣
                self.assertEqual((g.claimed(), g.realm_info()['name']), (claimed, old_realm))
                self.assertTrue(any('道心' in e.get('msg', '') for e in ev))
                self.assertFalse([e for e in g.state['events'] if e.get('reward_model') == 'best-score-penalty-v1'])

    def test_reference_is_recent_three_by_date_not_peak(self):
        g, _ = self.make()
        g.state['boss'] = [{'name': 'A', 'd': '2026-09-01', 'score': 90, 'kind': '大比'},   # 很久以前的高峰
                           {'name': 'B', 'd': '2026-10-01', 'score': 60, 'kind': '大比'},
                           {'name': 'C', 'd': '2026-10-05', 'score': 64, 'kind': '大比'},
                           {'name': 'D', 'd': '2026-10-10', 'score': 62, 'kind': '大比'},
                           {'name': '补录旧卷', 'd': '2026-08-01', 'score': 30, 'kind': '大比'}]  # 补录的旧卷不算最近
        self.assertEqual(reward.reference(g, '新场'), 62)
        self.assertEqual(reward.prior_best(g, '新场'), 90)
        self.assertEqual([b['name'] for b in g.contests()][-2:], ['C', 'D'])        # 按日期而不是录入顺序

    def test_edited_history_and_current_exam_excluded(self):
        g, _ = self.make()
        g.state['boss'] = [{'name':'第33季','score':90},{'name':'第133季','score':80},{'name':'正式考试','score':99,'kind':'飞升'}]
        g.state['mocks'] = {'33':{'score':70},'133':{'score':72},'134':{'score':99}}
        self.assertEqual(reward.prior_best(g,'第134季'), 72)
        reward.offer(g,'第134季',70,g.raw_score())
        self.assertEqual(reward.ledger(g)['records'][reward.exam_key('第134季')]['status'],'pending')

    def test_report_first_score_only_and_dates_do_not_repeat(self):
        g, base = self.make(); before = g.state['xp']
        mock.save(g, {'season':41,'score':69,'date':'2026-10-22'})
        key = reward.exam_key('第41季'); r = reward.ledger(g)['records'][key]
        self.assertEqual(r['status'],'neutral'); self.assertGreaterEqual(g.state['xp'], before)
        state = copy.deepcopy(g.state)
        mock.save(g, {'season':41,'score':99,'date':'2026-10-10'})
        self.assertEqual(g.state['xp'], state['xp'])
        self.assertEqual(reward.ledger(g),state['mock_rewards'])

    def test_historical_migration_never_punishes(self):
        g, _ = self.make(); g.state.pop('mock_rewards'); g.state['boss'].append({'name':'旧低分','score':50,'d':g.t})
        before = g.state['xp']; reward.migrate(g); reward.offer(g,'旧低分',50,90)
        self.assertEqual(g.state['xp'],before)
        self.assertEqual(reward.view(g),[])

    def test_other_subject_unchanged(self):
        g, _ = self.make('申论'); before=g.state['xp'];reward.offer(g,'申论不罚',55,54)
        self.assertEqual(g.state['xp'],before)
        self.assertEqual(reward.ledger(g)['records'][reward.exam_key('申论不罚')]['status'],'pending')


if __name__ == '__main__':
    unittest.main()
