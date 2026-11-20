"""老师题本：七字段目录按原套序排列，混合板块的作答、续做、复盘沿用试炼记录。"""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import config, engine, library, paths, question_bank as bank, store, trainer


def question(ident, topic, paper, num, answer='A'):
    return ('## 题目 %s\n### 知识点\n%s\n### 题干\n测试题干%s\n### 选项\n'
            'A. 甲\nB. 乙\nC. 丙\nD. 丁\n### 答案\n%s\n### 解析\n测试解析\n'
            '### 试卷\n%s\n### 题号\n%d\n\n' % (ident, topic, ident, answer, paper, num))


class WorkbooksTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict('os.environ', {'SHENLUN_SUBJECT': '行测'})
        env.start()
        self.addCleanup(env.stop)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        p = paths.Paths(Path(folder.name))
        p.ensure_train_dir()
        self.day = dt.date(2026, 11, 19)
        self.g = engine.Game(p, config.Rules(), config.Persona(), config.Lines(),
                             store.new_state(self.day), self.day)
        self.folder = p.train / '题库'
        self.doc = self.folder / '言语理解.md'
        base = '【张老师】26下-专项1期-言语理解题本·'
        self.first = base + '选词10'
        self.second = base + '片段2'
        self.raw = (question('A02', '语句排序', self.first, 2)
                    + question('A01', '逻辑填空', self.first, 1)
                    + question('B01', '语句表达', self.second, 1)
                    + question('B02', '片段阅读', self.second, 2, '（待补）')
                    + question('C01', '逻辑填空', self.first.replace('1期', '2期'), 1))
        self.doc.write_text(self.raw, encoding='utf-8')
        self.addCleanup(trainer.SESSIONS.clear)

    def test_catalog_order_copies_and_ordinary_bank(self):
        (self.folder / '逻辑填空真题-张老师.md').write_text(self.raw, encoding='utf-8')
        (self.folder / '数量关系真题.md').write_text(
            question('普通题', '工程', '2025年模拟卷', 1), encoding='utf-8')
        info = bank.summary(self.g)
        books = info['workbooks']
        self.assertEqual([b['name'] for b in books], ['【张老师】专项 · 言语理解题本'])
        periods = books[0]['periods']
        self.assertEqual([p['name'] for p in periods], ['26下-专项1期', '26下-专项2期'])
        self.assertEqual([(s['name'], s['total']) for s in periods[0]['sets']], [('选词10', 2), ('片段2', 1)])
        for board, ids in [('片段阅读', ['A02', 'B01', 'B02']), ('逻辑填空', ['A01', 'C01'])]:
            qs, errors = bank.read_all(self.g.paths, board)
            self.assertEqual([q['id'] for q in qs], ids)
            self.assertEqual(errors, [])
        self.assertEqual(bank.reload(self.g)['total'], 5)
        self.assertEqual(self.doc.read_text(encoding='utf-8'), self.raw)

    def test_skill_titles_and_validation(self):
        self.doc.write_text(
            question('A', '逻辑填空', '林老师-周练第1期·基础练习1', 1, '（待补）')
            + question('B', '片段阅读', '林老师-周练第2期·基础练习1', 1)
            + question('C', '逻辑填空', '林老师-周练题本第1期·基础练习1', 1), encoding='utf-8')
        books = bank.summary(self.g)['workbooks']
        self.assertEqual([b['name'] for b in books], ['林老师 · 周练', '林老师 · 周练题本'])
        self.assertEqual([p['name'] for p in books[0]['periods']], ['第1期', '第2期'])
        first = books[0]['periods'][0]['sets'][0]
        self.assertEqual((first['name'], first['pending'], first['total']), ('基础练习1', 1, 0))
        with self.assertRaises(bank.BankError):
            bank.begin(self.g, first['slot'], 'new')

    def test_legacy_filename_identity_survives_mixed_board_and_duplicate_copy(self):
        file = self.folder / '逻辑填空真题-老师.md'
        file.write_text(self.raw, encoding='utf-8')
        old_key = '逻辑填空::A02'
        q = dict(bank.read(self.g.paths, '片段阅读')[0][0], key=old_key, board='逻辑填空', source=file.name)
        self.g.state['bank']['records'][old_key] = {
            'question': q, 'history': [{'answer': 'B', 'ok': False, 'mode': 'new', 'date': self.g.t}],
            'wrong': True, 'streak': 0}
        slot = bank.summary(self.g)['workbooks'][0]['periods'][0]['sets'][0]['slot']
        run = bank.begin(self.g, slot, 'new')
        self.assertEqual([q['key'] for q in run['questions']], [old_key, '逻辑填空::A01'])
        bank.record(self.g, run, 'A')
        self.assertFalse(run['results'][0]['first'])
        self.assertEqual(set(bank.state(self.g)['records']), {old_key})
        self.assertEqual(library.detail(self.g, old_key)['board'], '片段阅读')
        self.assertEqual(len(library.detail(self.g, old_key)['history']), 2)
        self.assertEqual(bank.save_tutor_to_bank(self.g.paths, run['questions'][0], '讲解', self.g.t), '')
        self.assertEqual(file.read_text(encoding='utf-8'), self.raw)

    def test_bad_set_leaves_other_sets_available_and_template_updates_only_if_unedited(self):
        self.doc.write_text(question('A', '逻辑填空', self.first, 1, 'Z')
                            + question('B', '片段阅读', self.second, 1), encoding='utf-8')
        entries = bank.summary(self.g)['workbooks'][0]['periods'][0]['sets']
        self.assertTrue(entries[0]['errors'])
        self.assertEqual(entries[1]['errors'], [])
        self.assertEqual(bank.begin(self.g, entries[1]['slot'], 'new')['questions'][0]['id'], 'B')
        template = self.folder / bank.TEMPLATE
        template.write_text(bank.OLD_TEMPLATE_TEXT, encoding='utf-8')
        bank.reload(self.g)
        self.assertIn('林老师-周练第1期', template.read_text(encoding='utf-8'))
        template.write_text('我的模板', encoding='utf-8')
        bank.reload(self.g)
        self.assertEqual(template.read_text(encoding='utf-8'), '我的模板')

    def test_legacy_run_after_renaming_file_uses_existing_history_and_snapshot(self):
        original = dict(bank.read(self.g.paths, '片段阅读')[0][0], board='逻辑填空',
                        key='逻辑填空::A02', source='逻辑填空真题-老师.md', stem='旧题干快照')
        data = self.g.state['bank']
        data['records'][original['key']] = {
            'question': dict(original), 'history': [{'answer': 'A', 'ok': True, 'mode': 'new', 'date': self.g.t}],
            'wrong': False, 'streak': 1}
        slot = bank.BLOCK_PAPER_PREFIX + '逻辑填空:' + self.first
        data['runs'][slot] = {'questions': [dict(original)], 'results': [], 'board': slot, 'mode': 'new',
                              'pos': 0, 'phase': 'answer', 'token': 'old'}
        sid = trainer.start(self.g, {'type': 'bank', 'board': slot})['session']
        trainer.action(self.g, sid, 'exam_pick:0:A')
        trainer.action(self.g, sid, 'exam_submit')
        self.assertEqual(set(data['records']), {'片段阅读::A02'})
        self.assertEqual(data['groups'][-1]['first_count'], 0)
        rec = data['records']['片段阅读::A02']
        self.assertEqual(len(rec['history']), 2)
        self.assertEqual(rec['question']['stem'], '旧题干快照')

    def test_resume_settle_review_repeat_and_wrong_board(self):
        slot = bank.summary(self.g)['workbooks'][0]['periods'][0]['sets'][0]['slot']
        task = {'type': 'bank', 'board': slot}
        sid = trainer.start(self.g, task)['session']
        run = bank.state(self.g)['runs'][slot]
        self.assertEqual([q['id'] for q in run['questions']], ['A02', 'A01'])
        self.assertEqual(trainer.study_board(self.g, sid), '片段阅读')
        trainer.action(self.g, sid, 'exam_pick:0:B')
        self.assertEqual(trainer.study_board(self.g, sid), '逻辑填空')
        trainer.action(self.g, sid, 'bank_pause')
        store.Store(self.g.paths).save(self.g.state, self.day)
        trainer.SESSIONS.clear()
        self.g.state = store.Store(self.g.paths).load(self.day)
        entry = bank.summary(self.g)['workbooks'][0]['periods'][0]['sets'][0]
        self.assertEqual((entry['active'], entry['done'], entry['completed']), (True, 1, False))
        self.doc.unlink()
        sid = trainer.start(self.g, task)['session']
        self.assertEqual(bank.state(self.g)['runs'][slot]['picks'], {'0': 'B'})
        trainer.action(self.g, sid, 'exam_pick:1:A')
        result = trainer.action(self.g, sid, 'exam_submit')
        self.assertEqual(trainer.study_board(self.g, sid), '片段阅读')
        self.assertIn('测试解析', str(result))
        trainer.action(self.g, sid, 'exam_close')
        self.doc.write_text(self.raw, encoding='utf-8')
        d = bank.summary(self.g)
        first, second = d['workbooks'][0]['periods'][0]['sets']
        self.assertTrue(first['completed'])
        self.assertEqual(first['completed_count'], 1)
        self.assertFalse(second['completed'])
        self.assertEqual(first['done'], 2)
        self.assertEqual(d['groups'][0]['boards'], ['片段阅读', '逻辑填空'])
        self.assertEqual(d['groups'][0]['correct'], 1)
        self.assertTrue(bank.state(self.g)['records']['片段阅读::A02']['wrong'])
        self.assertEqual([q['id'] for q in bank.begin(self.g, slot, 'new')['questions']], ['A02', 'A01'])
        self.assertEqual(self.doc.read_text(encoding='utf-8'), self.raw)

    def test_workbook_without_subdivided_board_practices_by_period_and_set(self):
        judge_doc = self.folder / '海海刷-判断推理.md'
        p1 = '【四海】26下-海海刷1期-判断推理题本·逻辑刷题1'
        p2 = '【四海】26下-海海刷1期-判断推理题本·判断套题1'
        judge_doc.write_text(
            question('海海刷1期-判断-逻辑刷题1-01', '逻辑判断', p1, 1)
            + question('海海刷1期-判断-判断套题1-26', '判断推理', p2, 26)
            + question('海海刷1期-判断-判断套题1-27', '', p2, 27),
            encoding='utf-8',
        )
        books = {b['name']: b for b in bank.summary(self.g)['workbooks']}
        self.assertIn('【四海】海海刷 · 判断推理题本', books)
        sets = {s['name']: s for s in books['【四海】海海刷 · 判断推理题本']['periods'][0]['sets']}
        self.assertEqual(sets['逻辑刷题1']['errors'], [])
        self.assertEqual(sets['判断套题1']['errors'], [])
        self.assertEqual(sets['逻辑刷题1']['total'], 1)
        self.assertEqual(sets['判断套题1']['total'], 2)
        run1 = bank.begin(self.g, sets['逻辑刷题1']['slot'], 'new')
        self.assertEqual([q['id'] for q in run1['questions']], ['海海刷1期-判断-逻辑刷题1-01'])
        run2 = bank.begin(self.g, sets['判断套题1']['slot'], 'new')
        self.assertEqual([q['id'] for q in run2['questions']], ['海海刷1期-判断-判断套题1-26', '海海刷1期-判断-判断套题1-27'])
