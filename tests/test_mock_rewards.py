"""3.0.6阶段奖励与旧存档修正：仅使用临时库，不读用户存档、不调用AI。"""
import copy
import datetime as dt
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import config, engine, mock_rewards as rewards, paths, store, themes


class MockRewardTest(unittest.TestCase):
    def make(self):
        today = dt.date(2026, 10, 13)
        p = paths.Paths(None)
        state = store.new_state(today, p.subject) if hasattr(p, "subject") else store.new_state(today)
        return engine.Game(p, config.Rules(), config.Persona(), config.Lines(), state, today)

    def test_score_offers_manual_reward_without_topup(self):
        g = self.make()
        start = g.state['xp']
        g.add_boss('自编一', g.raw_score() + 20)
        g.add_boss('自编二', g.raw_score() + 21)
        self.assertEqual(g.state['xp'] - start, 2 * g.rules.xp('模考录分'))
        self.assertEqual(len(rewards.view(g)), 2)
        before = g.state['xp']
        amount = rewards.amount(g)
        key = rewards.exam_key('自编二')
        rewards.claim(g, key)
        self.assertEqual(g.state['xp'], before + amount['amount'])
        self.assertFalse(g.state.get('claimed', 0) > int(g.rules.num('起始分数')))
        self.assertEqual(rewards.claim(g, key), [])
        self.assertEqual(g.state['xp'], before + amount['amount'])

    def test_low_or_equal_score_ineligible_and_same_exam_once(self):
        g = self.make()
        rewards.offer(g, '低分', 50, 50)
        self.assertEqual(rewards.view(g), [])
        with self.assertRaises(ValueError):
            rewards.claim(g, rewards.exam_key('低分'))
        rewards.offer(g, '高分', 70, 50)
        rewards.offer(g, '高分', 80, 50)
        self.assertEqual(len(rewards.view(g)), 1)

    def test_current_stage_full_then_half_in_all_themes(self):
        g = self.make()
        for theme in themes.THEMES:
            g.state['theme'] = theme
            for score in (int(g.rules.num('起始分数')) + 2, g.gates()[0]):
                g.state['gates'] = g.gates()
                g.state['xp'] = math.ceil(g.xp_at(score)) + 1
                g.state['claimed'] = score
                info = g.realm_info()
                amount = rewards.amount(g)
                expected = (1 if info['big'] < 2 else 1/6 if info['big'] == 2 else 1/12) if getattr(g, 'subject', '法考') == '行测' else (1 if info['big'] < 2 else .5)
                self.assertEqual(amount['rate'], expected)
                self.assertEqual(amount['amount'], min(math.ceil(info['need'] * expected), info['next_xp'] - g.state['xp']))   # 3.7.5：最多补满本阶段

    def test_reward_only_fills_current_stage_without_overflow_or_auto_breakthrough(self):
        """用户场景：练气七层 1080/3500，领取只补 2320，修为刚好圆满，不溢出、不自己突破。"""
        g = self.make()
        start = int(g.rules.num('起始分数')) + 6          # 练气七层的起点（起始分+6）
        g.state.update(gates=g.gates(), claimed=start, xp=math.ceil(g.xp_at(start)) + 1080)
        info = g.realm_info()
        self.assertFalse(info['ready'])
        rewards.offer(g, '补满测试', start + 20, start)
        preview = rewards.amount(g)
        self.assertIn(preview['amount'], (info['need'] - info['into'], info['need'] - info['into'] + 1), '补的就是本阶段还差的修为')
        self.assertTrue(preview['capped'] and preview['amount'] < info['need'])
        rewards.claim(g, rewards.exam_key('补满测试'))
        after = g.realm_info()
        self.assertEqual((after['into'], after['need']), (after['need'], after['need']), '刚好补满本阶段')
        self.assertTrue(after['ready'], '圆满，等自己点突破')
        self.assertEqual(g.state['claimed'], start, '领取不会自己突破')
        self.assertLessEqual(g.state['xp'], math.ceil(g.xp_at(after['ready_to'])) + 1, '没有溢出到下一阶段')
        # 已圆满：再领一份新的奖励不可领，提示先突破
        rewards.offer(g, '圆满后', start + 30, start)
        self.assertFalse(rewards.amount(g)['available'])
        with self.assertRaisesRegex(ValueError, '突破'):
            rewards.claim(g, rewards.exam_key('圆满后'))
        g.break_through()
        self.assertTrue(rewards.amount(g)['available'], '突破进入下一阶段后可以领')

    def test_claim_uses_stage_at_claim_time_and_max_stage_unavailable(self):
        g = self.make()
        rewards.offer(g, '变更阶段', 80, 50)
        score = g.gates()[0]
        g.state.update(gates=g.gates(), xp=math.ceil(g.xp_at(score)) + 1, claimed=score)
        before = g.state['xp']
        amount = rewards.amount(g)
        rewards.claim(g, rewards.exam_key('变更阶段'))
        self.assertEqual(g.state['xp'] - before, amount['amount'])
        maximum = int(g.rules.num('最高分数'))
        g.state.update(xp=math.ceil(g.xp_at(maximum)), claimed=maximum)
        self.assertFalse(rewards.amount(g)['available'])

    def test_legacy_40082_rollback_preserves_learning_and_is_once(self):
        g = self.make()
        g.state.update(xp=43417, claimed=int(g.rules.num('起始分数')) + 1)
        g.state['boss'] = [dict(d=g.t, name='自编38', score=71.6, kind='大比')]
        g.state['events'] = [dict(d=g.t, type='boss', xp=100, note='宗门大比「自编38」71.6分'),
                             dict(d=g.t, type='insight', xp=40082, note='旧悟道')]
        g.state['seconds'] = {g.t: 163 * 60}
        before = copy.deepcopy(g.state)
        rewards.migrate(g)
        self.assertEqual(g.state['xp'], 3335)
        self.assertEqual(g.state['seconds'], before['seconds'])
        self.assertEqual(g.state['boss'], before['boss'])
        self.assertEqual(g.state['events'][:2], before['events'])
        self.assertEqual(g.insight_xp(), 0)
        self.assertEqual(rewards.view(g)[0]['status'], 'pending')
        corrected = copy.deepcopy(g.state)
        self.assertEqual(rewards.migrate(g), [])
        self.assertEqual(g.state, corrected)

    def test_api_concurrent_claim_persists_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from rpg import api
        with tempfile.TemporaryDirectory() as tmp:
            p = paths.Paths(Path(tmp))
            p.ensure_train_dir()
            rules, persona, lines = config.load_all(p, themes.DEFAULT_THEME)
            state = store.new_state(dt.date.today(), p.subject) if hasattr(p, 'subject') else store.new_state(dt.date.today())
            g = engine.Game(p, rules, persona, lines, state)
            rewards.offer(g, '并发测试', 99, 50)
            amount = rewards.amount(g)['amount']
            st = store.Store(p)
            st.save(state, g.today)
            with patch.object(api, 'Paths', return_value=p), patch.object(api, 'find_vault', return_value=Path(tmp)):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    list(pool.map(lambda _: api.mock_reward_claim({'key': rewards.exam_key('并发测试')}), range(2)))
            saved = st.load(g.today)
            self.assertEqual(saved['xp'], amount)
            self.assertEqual(len([e for e in saved['events'] if e.get('reward_model') == rewards.MODEL]), 1)

    def test_historical_scores_not_reissued_and_named_backup_preserved(self):
        g = self.make()
        g.state['boss'] = [dict(d=g.t, name='旧成绩', score=70)]
        rewards.migrate(g)
        rewards.offer(g, '旧成绩', 80, 50)
        self.assertEqual(rewards.view(g), [])
        with tempfile.TemporaryDirectory() as tmp:
            p = paths.Paths(Path(tmp))
            p.ensure_train_dir()
            st = store.Store(p)
            st.save(g.state, g.today)
            original = p.save_file.read_bytes()
            st.backup_named('3.0.6悟道修正前')
            for day in range(20):
                st.save(g.state, g.today + dt.timedelta(days=day))
            backup = p.save_dir / '备份/规则修正-3.0.6悟道修正前.json'
            self.assertEqual(backup.read_bytes(), original)
            self.assertTrue(st.load(g.today)['mock_rewards']['legacy_corrected'])


if __name__ == '__main__':
    unittest.main()
