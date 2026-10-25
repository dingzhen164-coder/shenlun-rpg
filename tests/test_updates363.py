"""3.6.3隔离回归：历史复盘不重发奖、考试日期统一、排布备份与奖励比例。"""
import copy
import datetime as dt
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rpg import config, engine, mock, mock_rewards, paths, question_bank as bank, scene_layout, store, trainer
from tests.test_bank import question


class Updates363Test(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, {'SHENLUN_SUBJECT': '行测'}); env.start(); self.addCleanup(env.stop)
        self.p = paths.Paths(Path(tmp.name), '行测'); self.p.ensure_train_dir()
        self.day = dt.date(2026, 10, 21)
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(self.day), self.day)
        self.addCleanup(trainer.SESSIONS.clear)

    def complete(self):
        (self.p.train/'题库/论证逻辑真题.md').write_text(question('自编1')+question('自编2'), encoding='utf-8')
        r = trainer.start(self.g, dict(type='bank', board='论证逻辑', title='自编练习'))
        sid = r['session']
        for i, answer in enumerate(('B', 'A')):
            trainer.action(self.g, sid, 'exam_pick:%s:%s' % (i, answer))
        trainer.action(self.g, sid, 'exam_submit')
        return sid

    def test_history_reopens_exact_snapshot_after_reload_without_rewards(self):
        sid = self.complete()
        run = bank.state(self.g)['runs']['论证逻辑']
        run['explain'] = {'0': '保存的自编解惑'}
        trainer.action(self.g, sid, 'exam_close')
        state = copy.deepcopy(self.g.state)
        (self.p.train/'题库/论证逻辑真题.md').write_text('', encoding='utf-8')
        data = bank.summary(self.g)['groups'][0]
        self.assertNotIn('review', data); self.assertEqual(data['group'], 0)
        self.g.state = copy.deepcopy(self.g.state)  # 模拟存档往返后对象身份不相连
        r = trainer.start(self.g, dict(type='bank_review', board='论证逻辑', group=0, title='历史复盘'))
        self.assertIn('保存的自编解惑', str(r)); self.assertIn('你的答案：B', str(r))
        self.assertTrue(any(m.get('fold') for m in r['messages']))
        trainer.action(self.g, r['session'], 'exam_rnext')
        trainer.action(self.g, r['session'], 'exam_close')
        for k in ('xp', 'events', 'practice', 'boss'):
            self.assertEqual(state.get(k), self.g.state.get(k))
        self.assertEqual(len(bank.state(self.g)['groups']), 1)

    def test_history_does_not_overwrite_unfinished_practice(self):
        self.complete()
        current = copy.deepcopy(bank.state(self.g)['runs']['论证逻辑'])
        replay = bank.reopen(self.g, 0); bank.close(self.g, replay)
        self.assertEqual(bank.state(self.g)['runs']['论证逻辑'], current)
        with self.assertRaises(bank.BankError): bank.reopen(self.g, -1)
        with self.assertRaises(bank.BankError): bank.reopen(self.g, True)

    def test_old_group_restores_from_history_and_preserves_score(self):
        self.complete(); group = bank.state(self.g)['groups'][0]; group.pop('review')
        r = bank.reopen(self.g, 0)
        self.assertEqual([x['answer'] for x in r['results']], ['B', 'A'])
        bank.state(self.g)['groups'][0].pop('review', None)
        bank.state(self.g)['records'].clear()
        with self.assertRaises(bank.BankError): bank.reopen(self.g, 0)
        self.assertEqual(group['correct'], 1)

    def test_reward_full_sixth_twelfth_and_existing_claim_preserved(self):
        for score, divisor in ((52, 1), (60, 6), (62, 6), (65, 12), (70, 12), (80, 12)):
            self.g.state.update(gates=self.g.gates(), xp=math.ceil(self.g.xp_at(score))+1, claimed=score)
            amount = mock_rewards.amount(self.g)
            info = self.g.realm_info()
            self.assertEqual(amount['amount'], min(math.ceil(amount['cost']/divisor), info['next_xp'] - self.g.state['xp']))   # 3.7.5：最多补满本阶段
        self.g.rules.raw['模考悟道.筑基分母'] = 3
        self.g.state.update(xp=math.ceil(self.g.xp_at(60))+1, claimed=60)
        self.assertEqual(mock_rewards.amount(self.g)['divisor'], 3)
        mock_rewards.offer(self.g, '自编', 80, 50); key = mock_rewards.exam_key('自编')
        mock_rewards.claim(self.g, key); before = copy.deepcopy(self.g.state)
        mock_rewards.claim(self.g, key); self.assertEqual(self.g.state, before)

    def test_dates_sort_score_accuracy_latest_and_analysis_together(self):
        for n in (38, 39, 40):
            folder = self.p.train/('模考复盘/第%d季' % n); folder.mkdir(parents=True)
            (folder/'01-政治理论.md').write_text('### 1. ✅\n自编题。\n> 正确答案：**A**　我的答案：**A**\n> [!note] 复盘\n> 自编解析。\n---\n', encoding='utf-8')
        mock.save(self.g, dict(season=39, score=70, date='2026-10-18'))
        mock.save(self.g, dict(season=38, score=75, date='2026-10-20'))
        mock.save(self.g, dict(season=40, score=80, date='2026-10-21'))
        d = mock.summary(self.g)
        self.assertEqual([s['season'] for s in d['seasons']], [39, 38, 40])
        self.assertEqual(d['overall']['latest'], 80)
        before = copy.deepcopy(self.g.state['events'])
        mock.save(self.g, dict(season=38, score=75, date='2026-10-22'))
        self.assertEqual([s['season'] for s in mock.summary(self.g)['seasons']], [39, 40, 38])
        self.assertEqual(mock.summary(self.g)['overall']['latest'], 75)
        self.assertEqual(self.g.state['events'], before)
        import json
        facts = json.loads(mock._facts(self.g, 38)); self.assertEqual(facts['上一季']['季'], 40)
        for bad in ('2026-02-30', 'wrong', '2026-1-2', '2026-10-21xxx'):
            with self.assertRaises(mock.MockError): mock.save(self.g, dict(season=38, date=bad))

    def test_scene_backup_seed_does_not_override_saved_positions(self):
        layout = dict(desktop={'peak-shu': {'x': 62, 'y': 17}}, narrow={'peak-zi': {'x': 52, 'y': 25}}, names={})
        result = scene_layout.save(self.g.state, dict(map='xingce', layout=layout, seed=True))
        changed = copy.deepcopy(layout); changed['narrow']['peak-zi']['x'] = 70
        self.assertEqual(scene_layout.save(self.g.state, dict(map='xingce', layout=changed, seed=True)), result)
        self.assertEqual(scene_layout.save(self.g.state, dict(map='xingce', layout=changed)), changed)
        old = copy.deepcopy(self.g.state)
        changed['desktop']['peak-shu']['x'] = float('nan')
        with self.assertRaises(ValueError): scene_layout.save(self.g.state, dict(map='xingce', layout=changed))
        self.assertEqual(self.g.state, old)
