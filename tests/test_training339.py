"""3.3.9：隔离自编题验证二十题、旧组续做、资料抽题及日程边界/安全保存。"""
import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import config, contest_calendar as calendar, engine, paths, question_bank as bank, store, task_board


class Training339Test(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        home = patch.object(Path, 'home', return_value=Path(temp.name)/'fake-home')
        home.start()
        self.addCleanup(home.stop)
        self.p = paths.Paths(Path(temp.name)/'vault', '行测') if hasattr(config, 'canon_key') else paths.Paths(Path(temp.name)/'vault')
        self.p.ensure_train_dir()
        self.day = dt.date(2026, 10, 17)
        self.g = engine.Game(self.p, task_board._rules(type('G', (), {'subject':'行测'})(), self.p.rules.read_text(encoding='utf-8')),
                             config.Persona(), config.Lines(), store.new_state(self.day), self.day)

    def questions(self, board):
        text = ''.join('\n## 题目 自编-%02d\n### 知识点\n自编考点\n### 题干\n自编材料%02d：甲乙丙丁的统计结果待核对。\n\n哪一项符合条件？\n### 选项\nA. 是\nB. 否\nC. 无关\nD. 未说明\n### 答案\nA\n### 解析\n核对条件。\n' % (i, i//5) for i in range(30))
        (self.p.train/'题库'/(board+'真题.md')).write_text(text, encoding='utf-8')
        return bank.read(self.p, board)[0]

    def test_twenty_and_existing_snapshot(self):
        board = bank.boards(self.g)[0]
        self.questions(board)
        self.g.rules.raw['实战每组题数'] = '20'
        run = bank.begin(self.g, board, 'new')
        self.assertEqual(len(run['questions']), 20)
        self.g.rules.raw['实战每组题数'] = '10'
        snapshot = copy.deepcopy(run)
        self.assertEqual(bank.begin(self.g, board, 'new'), snapshot)
        bank.close(self.g, run)
        self.assertEqual(len(bank.begin(self.g, board, 'new')['questions']), 10)

    @unittest.skipUnless(hasattr(config, 'canon_key'), '资料分析为行测板块')
    def test_data_review_random_ten_without_padding_material_siblings(self):
        questions = self.questions('资料分析')
        data = bank.state(self.g)
        for q in questions:
            data['records'][q['key']] = dict(question=q, wrong=True, history=[], streak=0)
        data['records'][questions[0]['key']]['wrong'] = False
        self.g.rules.raw['实战每组题数'] = '20'
        with patch.object(bank.random, 'sample', side_effect=lambda xs,n:list(reversed(xs))[:n]) as sample:
            run = bank.begin(self.g, '资料分析', 'review')
            self.assertEqual(len(run['questions']), 10)
            self.assertEqual(len({q['key'] for q in run['questions']}), 10)
            self.assertEqual(run['questions'][0]['id'], questions[-1]['id'])
            self.assertNotIn(questions[0], run['questions'])
            snapshot = copy.deepcopy(run)
            self.assertEqual(bank.begin(self.g, '资料分析', 'review'), snapshot)
            self.assertEqual(sample.call_count, 1)

    def test_weekly_anchor_sunday_and_rollover_without_scores(self):
        if getattr(self.g, 'subject', '法考') != '行测':
            self.assertIsNone(calendar.view(self.g)['mock'])
            return
        for date, season, days in [('2026-10-17',39,1),('2026-10-18',39,0),('2026-10-19',40,6),('2027-01-03',50,0)]:
            self.g.today = dt.date.fromisoformat(date)
            result = calendar.view(self.g)['mock']
            self.assertEqual((result['season'], result['remaining']), (season, days))

    def test_calendar_preserves_rules_state_and_rejects_conflicts(self):
        with self.p.rules.open('a', encoding='utf-8') as f:
            f.write('\n# 自编备注\n- 外部设置: 保留\n')
        before = copy.deepcopy(self.g.state)
        current = calendar.view(self.g)
        result = calendar.save(self.g, dict(current, name='自编考试', exam='2026-10-18'))
        self.assertEqual(result['remaining'], 1)
        self.assertIn('- 外部设置: 保留', self.p.rules.read_text(encoding='utf-8'))
        self.assertEqual(self.g.state, before)
        with self.assertRaises(ValueError):
            calendar.save(self.g, dict(current, name='不覆盖', exam='2026-10-18'))
        saved = self.p.rules.read_bytes()
        for extra in (dict(name='注入\n- 目标日: 2000-01-01'), dict(exam='坏日期')):
            with self.assertRaises(ValueError):
                calendar.save(self.g, dict(result, **extra))
        with patch.object(calendar.os, 'replace', side_effect=OSError('模拟磁盘失败')), self.assertRaises(OSError):
            calendar.save(self.g, dict(result, name='写入失败'))
        self.assertEqual(self.p.rules.read_bytes(), saved)
        self.g.today = dt.date(2026, 10, 19)
        self.assertEqual(calendar.view(self.g)['remaining'], -1)

    def test_external_edit_during_preparation_is_not_overwritten(self):
        current = calendar.view(self.g)
        def external_edit(_):
            with self.p.rules.open('a', encoding='utf-8') as f:
                f.write('\n- 外部并发编辑: 保留\n')
        with patch.object(calendar.os, 'fsync', side_effect=external_edit), self.assertRaises(ValueError):
            calendar.save(self.g, dict(current, name='不覆盖外部编辑'))
        self.assertIn('- 外部并发编辑: 保留', self.p.rules.read_text(encoding='utf-8'))
        self.assertFalse(list(self.p.rules.parent.glob('.exam-calendar-*.tmp')))
