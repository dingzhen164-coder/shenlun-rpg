"""2026-11-11 申论实操训练中心：答题卡按右栏高度排行（rows 随笔迹保存）、材料勾画按字号分开存的数据校验。"""
import unittest
from rpg import shenlun_bank as bank, shenlun_handwriting as hw, shenlun_materials as marks

KEY = 'a' * 64


def stroke(y):
    return {'points': [[100, y], [120, y]], 'width': 3}


class CardRowsTest(unittest.TestCase):
    def test_rows_saved_and_bound_height(self):
        c = hw.card({'layout': 2, 'rows': 25, 'pages': [{'strokes': [stroke(80 + 25 * 64 - 1)]}]})
        self.assertEqual(c['rows'], 25)
        with self.assertRaises(bank.BankError):            # 超出这一页的高度
            hw.card({'layout': 2, 'rows': 10, 'pages': [{'strokes': [stroke(80 + 10 * 64 + 5)]}]})
        for bad in (4, 31, 12.5, '12'):
            with self.assertRaises(bank.BankError):
                hw.card({'layout': 2, 'rows': bad, 'pages': []})
        with self.assertRaises(bank.BankError):            # 旧 25 格卡不带 rows
            hw.card({'rows': 12, 'pages': []})

    def test_old_cards_unchanged(self):
        self.assertEqual(hw.card({'layout': 2, 'pages': [{'strokes': [stroke(1300)]}]}), {'layout': 2, 'pages': [{'strokes': [{'points': [[100, 1300], [120, 1300]], 'erase': False, 'width': 3}]}]})
        self.assertNotIn('rows', hw.card({'pages': []}))


class MarksBySizeTest(unittest.TestCase):
    def sheet(self):
        return {'width': 800, 'height': 500, 'strokes': [{'tool': 'pen', 'width': 3, 'points': [[1, 1]]}]}

    def test_size_suffix_keys(self):
        out = marks.validate({KEY: self.sheet(), KEY + '@120': self.sheet(), KEY + '@200': self.sheet()})
        self.assertEqual(sorted(out), [KEY, KEY + '@120', KEY + '@200'])
        for bad in (KEY + '@100', KEY + '@210', KEY + '@125', KEY + '@', 'x' * 64):
            with self.assertRaises(bank.BankError):
                marks.validate({bad: self.sheet()})


if __name__ == '__main__':
    unittest.main()
