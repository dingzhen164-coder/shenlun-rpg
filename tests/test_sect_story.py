"""青衡宗剧情的旧档兼容、真实进度、重复阅读与两科隔离；全用内存假数据。"""
import copy
import datetime as dt
import unittest
from types import SimpleNamespace
from rpg import sect_story


class SectStoryTest(unittest.TestCase):
    def game(self, **state):
        return SimpleNamespace(subject='行测', today=dt.date(2026, 10, 11), state=state)

    def test_empty_and_initialized_items_do_not_unlock_learning(self):
        g = self.game(items={'x': {'level': 0, 'last': None}}, xp=17)
        d = {'plan': {'tasks': [{'done': False}]}}
        r = sect_story.view(g, d)
        self.assertEqual(g.state['sect_story']['unlocked'], ['arrival'])
        self.assertEqual(r['unread'], 1)
        self.assertEqual(g.state['xp'], 17)
        self.assertIsNone(r['remaining'])

    def test_old_history_unlocks_and_read_is_idempotent(self):
        g = self.game(seconds={'2026-10-01': 10}, xp=19,
                      study_schedule={'exam': '2026-10-20'})
        d = {'tower': {'completed': 2}, 'boss_all': [{'score': 65}]}
        original = copy.deepcopy(g.state)
        r = sect_story.view(g, d)
        self.assertTrue(all(c['unlocked'] for c in r['chapters']))
        sect_story.mark_read(g, d, 'arrival')
        sect_story.mark_read(g, d, 'arrival')
        self.assertEqual(g.state['sect_story']['read'], ['arrival'])
        for k, v in original.items(): self.assertEqual(g.state[k], v)
        g.state['study_schedule']['exam'] = '2027-01-01'
        self.assertTrue(sect_story.view(g, {})['chapters'][-1]['unlocked'])

    def test_locked_unknown_and_other_subject(self):
        g = self.game()
        for chapter in ('tower', 'unknown', ['arrival']):
            with self.assertRaises(ValueError): sect_story.mark_read(g, {}, chapter)
        g = self.game(); g.subject = '申论'
        self.assertIsNone(sect_story.view(g, {}))
        with self.assertRaises(ValueError): sect_story.mark_read(g, {}, 'arrival')
        self.assertEqual(g.state, {})

    def test_invalid_story_field_and_past_exam(self):
        g = self.game(sect_story={'read': ['bad', {}, 'arrival'], 'unlocked': None},
                      seconds={'2026-10-01': 1}, study_schedule={'exam': '2026-10-10'})
        r = sect_story.view(g, {})
        self.assertFalse(r['chapters'][-1]['unlocked'])
        self.assertEqual(g.state['sect_story']['read'], ['arrival'])
        self.assertEqual(r['remaining'], -1)


if __name__ == '__main__': unittest.main()
