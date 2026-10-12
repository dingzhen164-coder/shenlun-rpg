"""三主题阶段/同伴：真实来源、时间线、重读、旧档、跨主题与收藏幂等。"""
import copy
import datetime as dt
import unittest
from types import SimpleNamespace
from rpg import narrative, journey, world, config


class WorldTest(unittest.TestCase):
    def game(self, wid=None, **state):
        wid = wid or next(iter(narrative.DEFINITIONS))
        return SimpleNamespace(subject={'mage': '法考', 'xingce': '行测', 'office': '申论'}[wid],
            state=state, today=dt.date(2026, 10, 12), persona={'导师名': '周静宜'}, rules=config.Rules())

    def story(self, g, action, choice=None):
        result = narrative.act(g, {}, dict(world=narrative.world_id(g), chapter='peer_method', action='open'))
        return narrative.act(g, {}, dict(world=result['world'], chapter='peer_method', action=action,
            node=result['scene']['node'], revision=result['revision'], choice=choice))

    def task(self, g, action, ident):
        result = journey.view(g, {})
        return journey.act(g, {}, dict(world=result['world'], revision=result['revision'], action=action, id=ident))

    def test_empty_and_fake_totals_cannot_open_regions_or_award_keepsakes(self):
        g = self.game(xp=9999, items={'empty': {'level': 0}}, seconds={}, boss=[])
        result = narrative.view(g, {})
        self.assertEqual(result['world_progress']['stage'], 0)
        self.assertTrue(all(not r['unlocked'] for r in result['world_progress']['regions']))
        self.story(g, 'skip')
        self.assertEqual(journey.view(g, {})['collection'], [])
        self.assertEqual(g.state['xp'], 9999)

    def test_companion_first_choice_feedback_and_collection_need_learning(self):
        for wid in narrative.DEFINITIONS:
            g = self.game(wid, xp=12, seconds={})
            self.story(g, 'choose', 'practice')
            self.story(g, 'choose', 'continue')
            self.story(g, 'finish')
            first = copy.deepcopy(g.state['narrative'])
            self.assertEqual(journey.view(g, {})['collection'], [])
            self.task(g, 'claim', 'main:study')
            journey.record(g, 'card', token='actual-card')
            self.task(g, 'deliver', 'main:study')
            result = narrative.view(g, {})
            self.assertEqual(result['world_progress']['stage'], 1)
            self.assertEqual(len(result['journey']['collection']), 2)
            companion = result['companions'][0]
            self.assertEqual(companion['feedback'], companion['echo_practice'])
            scene = narrative.act(g, {}, dict(world=wid, chapter='peer_method', action='open'))
            self.assertEqual(scene['profile']['character'], companion['name'])
            self.story(g, 'replay')
            self.story(g, 'choose', 'method')
            self.story(g, 'skip')
            result = narrative.view(g, {})
            self.assertEqual(result['companions'][0]['feedback'], companion['echo_practice'])
            self.assertEqual(len(result['journey']['collection']), 2)
            self.assertEqual(g.state['narrative']['worlds'][wid]['chapters']['peer_method']['record'],
                             first['worlds'][wid]['chapters']['peer_method']['record'])
            self.assertEqual(g.state['xp'], 12)
            self.assertEqual(g.state['seconds'], {})

    def test_date_change_and_restarting_preserve_unlocks_and_scores(self):
        g = self.game(seconds={'day': 60}, xp=8, study_schedule={'exam': '2026-10-20'}, boss=[])
        before = copy.deepcopy(g.state)
        result = narrative.view(g, {})
        self.assertEqual(result['world_progress']['stage'], 4)
        g.state['study_schedule']['exam'] = '2028-01-01'
        g.state['seconds'] = {}
        clone = self.game(**copy.deepcopy(g.state))
        result = narrative.view(clone, {})
        self.assertTrue(result['world_progress']['milestones'][-1]['unlocked'])
        self.assertEqual(result['world_progress']['remaining'], (dt.date(2028,1,1)-g.today).days)
        self.assertEqual(clone.state['xp'], before['xp'])
        self.assertEqual(clone.state['boss'], before['boss'])

    def test_configurable_calendar_and_valid_boss_source(self):
        g = self.game(seconds={'day': 60}, study_schedule={'exam': '2026-10-20'}, boss=[{'score': float('nan')}])
        g.rules = config.Rules('- 世界考前提醒天数: 3')
        self.assertEqual(narrative.view(g, {})['world_progress']['stage'], 0)
        g.state['boss'].append(dict(d='2026-10-12', name='自编模拟测验', score=62))
        result = narrative.view(g, {})['world_progress']
        self.assertEqual(result['stage'], 3)
        self.assertIn('原模考', result['regions'][2]['reason'])

    def test_old_title_migration_and_future_world_module_are_preserved(self):
        g = self.game()
        self.task(g, 'claim', 'main:study')
        journey.record(g, 'card', token='a')
        self.task(g, 'deliver', 'main:study')
        self.task(g, 'claim', 'main:review')
        journey.record(g, 'card', token='b')
        self.task(g, 'deliver', 'main:review')
        st = g.state['journey']['worlds'][narrative.world_id(g)]
        del st['collection']['main:title']
        first = journey.view(g, {})
        self.assertEqual(first, journey.view(g, {}))
        self.assertEqual(len(first['collection']), 4)
        g.state['world_progress'] = {'schema': 999, 'worlds': {}}
        before = copy.deepcopy(g.state['world_progress'])
        self.assertTrue(narrative.view(g, {})['world_progress']['error'])
        self.assertEqual(g.state['world_progress'], before)

    def test_companions_do_not_rewrite_other_world_or_original_five_chapters(self):
        g = self.game(sect_story={'schema':1, 'unlocked':['arrival'], 'read':['arrival']})
        original = copy.deepcopy(g.state['sect_story'])
        self.story(g, 'skip')
        self.assertEqual(g.state['sect_story'], original)
        first = copy.deepcopy(g.state['narrative']['worlds'])
        for wid in narrative.DEFINITIONS:
            if wid != narrative.world_id(g):
                g.subject = {'mage':'法考', 'xingce':'行测', 'office':'申论'}[wid]
                narrative.view(g, {})
                for key in first: self.assertEqual(g.state['narrative']['worlds'][key], first[key])
                break

if __name__ == '__main__': unittest.main()
