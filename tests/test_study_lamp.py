"""学习蜡烛凭据：服务端实时时长、防重复、过期及科目/资料库隔离；无用户数据。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rpg import study_lamp as lamp


class StudyLampTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.paths = SimpleNamespace(vault=Path(self.tmp.name)/'自编', subject='行测')
        self.now = 1000.0
        self.clock = patch.object(lamp.time, 'monotonic', side_effect=lambda:self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)
        lamp._READERS.clear()

    def test_elapsed_budget_and_duplicate_claim(self):
        token = lamp.start(self.paths, '政治理论')
        self.assertEqual(lamp.seconds(self.paths, token, 90), (0, '政治理论'))
        self.now += 4.7
        self.assertEqual(lamp.seconds(self.paths, token, 90), (4, '政治理论'))
        self.assertEqual(lamp.seconds(self.paths, token, 90), (0, '政治理论'))
        self.now += .4
        self.assertEqual(lamp.seconds(self.paths, token, 90), (1, '政治理论'))
        self.now += 100
        self.assertEqual(lamp.seconds(self.paths, token, 999), (90, '政治理论'))

    def test_idle_touch_and_stop(self):
        token = lamp.start(self.paths)
        self.now += 100; self.assertTrue(lamp.touch(self.paths, token))
        self.now += 100; self.assertIsNotNone(lamp.seconds(self.paths, token, 30))
        self.now += lamp.IDLE_SECONDS+1
        self.assertIsNone(lamp.seconds(self.paths, token, 30)); self.assertFalse(lamp.touch(self.paths, token))
        fresh = lamp.start(self.paths); lamp.stop(self.paths, fresh)
        self.assertIsNone(lamp.seconds(self.paths, fresh, 30))

    def test_scope_and_missing_token(self):
        token = lamp.start(self.paths)
        other = SimpleNamespace(vault=self.paths.vault, subject='申论')
        alien = SimpleNamespace(vault=self.paths.vault/'另一个库', subject='行测')
        self.now += 30
        for p in (other, alien):
            self.assertIsNone(lamp.seconds(p, token, 30)); self.assertFalse(lamp.touch(p, token)); lamp.stop(p, token)
        self.assertEqual(lamp.seconds(self.paths, token, 30), (30, ''))
        self.assertIsNone(lamp.seconds(self.paths, '', 30))
        with self.assertRaises(ValueError):lamp.start(SimpleNamespace(vault=None,subject='行测'))

    def test_registry_bounded(self):
        for _ in range(300):lamp.start(self.paths)
        self.assertEqual(len(lamp._READERS),256)
        self.now += lamp.IDLE_SECONDS+1;lamp.start(self.paths)
        self.assertEqual(len(lamp._READERS),1)


if __name__ == '__main__':unittest.main()
