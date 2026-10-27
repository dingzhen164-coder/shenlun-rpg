"""研读红标记区间运算：subtract必须是线性的（取消全部标红后，cuts和ranges一样多，曾因O(n×m)让标红卡顿）。"""
import random
import time
import unittest

from rpg import politics_reading as pr


def slow(ranges, cuts):
    result = pr.merge(ranges)
    for a, b in pr.merge(cuts):
        result = [part for x, y in result for part in ([x, min(y, a)], [max(x, b), y]) if part[0] < part[1]]
    return pr.merge(result)


class SubtractTest(unittest.TestCase):
    def test_same_result_as_the_simple_version(self):
        random.seed(7)
        for _ in range(2000):
            ranges = [[a, a+random.randint(1, 30)] for a in [random.randint(0, 200) for _ in range(random.randint(0, 12))]]
            cuts = [[a, a+random.randint(1, 40)] for a in [random.randint(0, 200) for _ in range(random.randint(0, 12))]]
            self.assertEqual(pr.subtract(ranges, cuts), slow(ranges, cuts), (ranges, cuts))

    def test_clearing_everything_then_marking_stays_fast(self):
        ranges, p = [], 0
        while p < 120000:
            a = p+5; b = a+12; ranges.append([a, b]); p = b
        start = time.perf_counter()
        for _ in range(20):
            self.assertEqual(pr.subtract(ranges+[[ranges[3][0]+1, ranges[3][1]-1]], ranges), [])
        self.assertLess((time.perf_counter()-start)/20, .05, '上万个区间互相扣除也要在几十毫秒内')


if __name__ == '__main__':
    unittest.main()
