"""备考HUD的平均值/日期口径与只读保证，避免自练分钟重复计入。"""
import copy
import datetime as dt
import unittest
from types import SimpleNamespace
from rpg import study_status

class StudyStatusTest(unittest.TestCase):
    def game(self, start=dt.date(2026,10,10)):
        dates={'开始日期':start,'目标日':dt.date(2026,11,1)}
        return SimpleNamespace(today=dt.date(2026,10,12),t='2026-10-12',rules=SimpleNamespace(date=dates.__getitem__),
            state={'seconds':{'2026-10-09':60000,'2026-10-10':3600,'2026-10-12':7200,'2026-10-13':9999},
                   'lectures':[{'d':'2026-10-11','minutes':90}], 'practice':[{'d':'2026-10-10','minutes':60}], 'xp':1000})
    def test_inclusive_calendar_average_and_no_duplicate_practice(self):
        g=self.game();before=copy.deepcopy(g.state);s=study_status.view(g)
        self.assertEqual(s['day'],3);self.assertEqual(s['remaining'],20);self.assertEqual(s['average_minutes'],90)
        self.assertEqual(g.state,before)
    def test_future_start_is_zero_not_day_one(self):
        s=study_status.view(self.game(dt.date(2026,12,1)));self.assertEqual(s['day'],0);self.assertEqual(s['average_minutes'],0)
    def test_zero_days_and_bad_values(self):
        g=self.game();g.state['seconds']={'2026-10-10':-60,'2026-10-11':float('nan'),'2026-10-12':'bad'}
        g.state['lectures']=[];self.assertEqual(study_status.view(g)['average_minutes'],0)
