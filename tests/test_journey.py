"""委托的学习证据、幂等、冲突、撤销、跨日和旧档兼容；所有库隔离。"""
import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from rpg import journey, narrative, cards, config, engine, paths, store, question_bank as bank


class JourneyTest(unittest.TestCase):
    def game(self, wid=None, **state):
        wid = wid or next(iter(narrative.DEFINITIONS))
        return SimpleNamespace(subject={'mage': '法考', 'xingce': '行测', 'office': '申论'}[wid],
            state=state, today=dt.date(2026, 10, 12), persona={'导师名': '周静宜'})

    def act(self, g, action, ident, **extra):
        data = journey.view(g, {})
        return journey.act(g, {}, dict(world=data['world'], revision=data['revision'], action=action, id=ident, **extra))

    def test_old_records_and_client_assertions_do_not_complete(self):
        g = self.game(xp=500, seconds={'d': 999}, events=[{'type': 'grade'}], grades=[{'score': 20}])
        self.act(g, 'claim', 'main:study')
        old = copy.deepcopy(g.state)
        for extra in ({'completed': True}, {'proof': {'id': 'fake'}}, {'score': 100}):
            with self.assertRaises(ValueError): self.act(g, 'deliver', 'main:study', **extra)
        self.assertEqual(g.state, old)
        for kind in ('boss', 'lecture', 'selfstudy', 'study', 'practice'):
            self.assertIsNone(journey.record(g, kind))
        self.assertEqual(journey.view(g, {})['tasks'][0]['status'], 'active')

    def test_complete_loop_is_idempotent_and_preserves_learning(self):
        for wid in narrative.DEFINITIONS:
            g = self.game(wid, xp=19, seconds={}, bank={'records': {}}, sect_story={'read': ['arrival']})
            learn = copy.deepcopy(g.state)
            initial = journey.view(g, {})
            with self.assertRaises(ValueError): self.act(g, 'claim', 'main:review')
            self.act(g, 'claim', 'main:study', approach='practice')
            journey.record(g, 'grade' if wid == 'office' else 'bank', token='first')
            complete = self.act(g, 'deliver', 'main:study')
            stale = dict(world=wid, revision=0, action='deliver', id='main:study')
            self.assertEqual(journey.act(g, {}, stale), complete)
            self.assertEqual(len(complete['collection']), 1)
            clone = self.game(wid, **copy.deepcopy(g.state))
            self.assertEqual(journey.view(clone, {}), complete)
            self.act(clone, 'claim', 'main:review')
            journey.record(clone, 'bank', token='new-question')
            journey.record(clone, 'bank_review', token='first')  # 已消费事件不能给下一段
            with self.assertRaises(ValueError): self.act(clone, 'deliver', 'main:review')
            journey.record(clone, 'card', token='second')
            end = self.act(clone, 'deliver', 'main:review')
            self.assertEqual(end['stage'], 2)
            self.assertEqual(len(end['collection']), 3)
            self.assertNotEqual(initial['text'], end['text'])
            self.act(clone, 'place', 'main:study:reward', slot='desk')
            self.act(clone, 'place', 'main:ornament', slot='shelf')
            state = journey.view(clone, {})
            self.assertEqual(len(state['placements']), 2)
            self.assertIn('从题目检验', state['collection'][0]['text'])
            for key, value in learn.items(): self.assertEqual(clone.state[key], value)

    def test_cas_world_and_invalid_collections(self):
        g = self.game()
        r = journey.view(g, {})
        self.act(g, 'claim', 'main:study')
        before = copy.deepcopy(g.state)
        for payload in (dict(world=r['world'], revision=r['revision'], action='claim', id='main:review'),
                        dict(world='unknown', revision=0, action='claim', id='main:study')):
            with self.assertRaises(ValueError): journey.act(g, {}, payload)
        self.assertEqual(g.state, before)
        with self.assertRaises(ValueError): self.act(g, 'place', 'missing', slot='desk')
        journey.record(g, 'card', token='c')
        self.act(g, 'deliver', 'main:study')
        with self.assertRaises(ValueError): self.act(g, 'place', 'main:study:reward', slot='wall')

    def test_undo_revokes_pending_proof_but_preserves_earned_keepsake(self):
        g = self.game()
        self.act(g, 'claim', 'main:study')
        journey.record(g, 'card', token='undo')
        journey.revoke(g, 'undo')
        with self.assertRaises(ValueError): self.act(g, 'deliver', 'main:study')
        journey.record(g, 'card', token='keep')
        self.act(g, 'deliver', 'main:study')
        journey.revoke(g, 'keep')
        self.assertEqual(len(journey.view(g, {})['collection']), 1)

    def test_daily_needs_original_task_and_evidence_after_claim(self):
        g = self.game(plan={'date': '2026-10-12', 'tasks': [dict(id='bank:a', type='bank', title='一组题',
                            board='a', target='a', done=False)]})
        self.act(g, 'claim', 'daily:2026-10-12', task_id='bank:a')
        journey.record(g, 'bank', board='b', token='wrong-board')
        g.state['plan']['tasks'][0]['done'] = True
        self.assertEqual(journey.view(g, {})['tasks'][-1]['status'], 'active')
        journey.record(g, 'bank', board='a', token='right-board')
        self.assertEqual(journey.view(g, {})['tasks'][-1]['status'], 'completed')
        g.today += dt.timedelta(days=1)
        self.act(g, 'deliver', 'daily:2026-10-12')
        self.assertEqual(len(journey.view(g, {})['collection']), 1)

    def test_next_day_unfinished_daily_expires_and_main_continues(self):
        g = self.game(plan={'date': '2026-10-12', 'tasks': [dict(id='cards:all', type='cards', title='温习', done=False)]})
        self.act(g, 'claim', 'daily:2026-10-12', task_id='cards:all')
        self.act(g, 'claim', 'main:study')
        g.today += dt.timedelta(days=1)
        g.state['plan'] = {'date': '2026-10-13', 'tasks': [dict(id='cards:all', type='cards', title='温习', done=False)]}
        data = journey.view(g, {})
        self.assertIn('daily:2026-10-13', [t['id'] for t in data['tasks']])
        journey.record(g, 'card', token='later')
        self.act(g, 'deliver', 'main:study')
        with self.assertRaises(ValueError): self.act(g, 'deliver', 'daily:2026-10-12')

    def test_future_or_corrupt_state_is_preserved_and_learning_can_continue(self):
        for raw in ({'schema': 999, 'worlds': {}}, {'schema': 1, 'worlds': {next(iter(narrative.DEFINITIONS)): {'revision': 0}}}):
            g = self.game(journey=copy.deepcopy(raw))
            self.assertTrue(journey.safe_view(g, {})['error'])
            self.assertIsNone(journey.record(g, 'card'))
            self.assertEqual(g.state['journey'], raw)

    def test_card_and_grade_hooks_use_real_records_and_undo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            if 'xingce' in narrative.DEFINITIONS:
                p = paths.Paths(root, '行测')
            else:
                p = paths.Paths(root)
            p.ensure_train_dir()
            day = dt.date(2026, 10, 12)
            g = engine.Game(p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)
            self.act(g, 'claim', 'main:study')
            cards._CACHE['key'] = None
            note = cards.add(g, dict(deck=next(iter(g.boards)), type='问答', front='自编练习', back='自编解答'))
            key = note['id'] + '#1'
            cards.answer(g, key, 3)
            self.assertEqual(journey.view(g, {})['tasks'][0]['status'], 'completed')
            cards.undo(g)
            self.assertEqual(journey.view(g, {})['tasks'][0]['status'], 'active')
            if hasattr(g, 'on_grade'):
                g.on_grade('自编题', next(iter(g.boards)), 5, 10, draft=True)
                self.assertEqual(journey.view(g, {})['tasks'][0]['status'], 'active')
                g.on_grade('自编题', next(iter(g.boards)), 5, 10)
            else:
                cards.answer(g, key, 3)
            self.act(g, 'deliver', 'main:study')
            state = copy.deepcopy(g.state)
            store.Store(p).save(state, day)
            reloaded = store.Store(p).load(day)
            self.assertEqual(reloaded['journey'], state['journey'])

    def test_bank_hook_guards_duplicate_and_review_keeps_original_xp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = paths.Paths(root, '行测') if 'xingce' in narrative.DEFINITIONS else paths.Paths(root)
            p.ensure_train_dir()
            day = dt.date(2026, 10, 12)
            g = engine.Game(p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)
            board = next(iter(g.boards))
            (p.train / '题库' / (board + '真题.md')).write_text(
                '\n## 题目 自编-01\n### 知识点\n自编\n### 题干\n自编题干\n### 选项\nA. 甲\nB. 乙\nC. 丙\nD. 丁\n### 答案\nA\n### 解析\n自编解析\n', encoding='utf-8')
            self.act(g, 'claim', 'main:study')
            run = bank.begin(g, board, 'new')
            bank.record(g, run, 'B')
            self.act(g, 'deliver', 'main:study')
            self.act(g, 'claim', 'main:review')
            with self.assertRaises(bank.BankError): bank.record(g, run, 'B')
            self.assertEqual(journey.view(g, {})['tasks'][1]['status'], 'active')
            bank.finish(g, run)
            xp = g.state['xp']
            review = bank.begin(g, board, 'review')
            bank.record(g, review, 'A')
            self.act(g, 'deliver', 'main:review')
            self.assertEqual(g.state['xp'], xp)


if __name__ == '__main__':
    unittest.main()
