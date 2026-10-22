"""两项目共用心跳预算：多来源/并发重试不超服务端实时时长，所有路径均为假库。"""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rpg import study_clock


class StudyClockTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.p=SimpleNamespace(vault=Path(temp.name),subject='行测'); self.now=1000.0
        clock=patch.object(study_clock,'_now',side_effect=lambda:self.now);clock.start();self.addCleanup(clock.stop)
        study_clock.seconds(self.p)

    def test_concurrent_retries_share_elapsed_seconds(self):
        self.now+=30
        with ThreadPoolExecutor(max_workers=8) as pool:
            paid=list(pool.map(lambda _:study_clock.seconds(self.p,30),range(20)))
        self.assertEqual(sum(paid),30);self.assertEqual(study_clock.seconds(self.p,90),0)

    def test_refresh_does_not_reset_budget_and_fractions_carry(self):
        self.now+=.7;self.assertEqual(study_clock.seconds(self.p,90),0)
        study_clock.seconds(self.p);self.now+=.4;self.assertEqual(study_clock.seconds(self.p,90),1)
        self.assertEqual(study_clock.seconds(self.p,90),0)

    def test_idle_cap_and_subject_isolation(self):
        self.now+=1000;self.assertEqual(study_clock.seconds(self.p,999),90)
        other=SimpleNamespace(vault=self.p.vault,subject='申论');self.assertEqual(study_clock.seconds(other,30),0)
        self.assertEqual(study_clock.seconds(SimpleNamespace(vault=None),90),0)
