"""整卷模拟考试：导入试卷/答案、倒计时作答、交卷批改、按试卷名记入宗门大比；自编130题，隔离临时库，不连AI。"""
import base64
import copy
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import api, config, engine, exam_room, importer, mock, paths, store, vault
from tests.test_mock_score import paper

NAME = '花生26下模拟卷第一套'


def blank_paper(folder, unknown=()):
    """130题的试卷：第N题的标准答案按 ABCD 轮换；unknown 里的题没有答案（正确答案：**?**）"""
    paper(folder)
    for f in folder.glob('[0-9][0-9]-*.md'):
        text = f.read_text(encoding='utf-8')
        for num in range(1, 131):
            letter = 'ABCD'[num % 4]
            text = text.replace('### %d. ✅\n自编条件题，仅用于隔离测试。\n> [!check]- 答案\n> 正确答案：**A**　我的答案：**A**' % num,
                                '### %d. ⚪\n自编条件题，仅用于隔离测试。\n- **A.** 甲\n- **B.** 乙\n- **C.** 丙\n- **D.** 丁\n> [!check]- 答案\n> 正确答案：**%s**　我的答案：**—**　未作答' % (num, '?' if num in unknown else letter))
        f.write_text(text, encoding='utf-8')


def key_of(num):
    return 'ABCD'[num % 4]


class ExamRoomTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); self.root = Path(t.name)
        for ctx in (patch.object(Path, 'home', return_value=self.root / 'home'), patch.dict(os.environ, {'SHENLUN_SUBJECT': '行测'}),
                    patch.object(paths, 'SETTINGS_DIR', self.root / 'settings'), patch.object(paths, 'SETTINGS_FILE', self.root / 'settings' / 'settings.json')):
            ctx.start(); self.addCleanup(ctx.stop)
        self.p = paths.Paths(self.root / 'vault', '行测'); self.p.ensure_train_dir()
        (self.p.vault / 'copilot/skills/test').mkdir(parents=True)
        paths.save_settings({'subject': '行测', 'vaults': {'行测': str(self.p.vault)}})
        self.g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(dt.date(2026, 10, 25)), dt.date(2026, 10, 25))
        self.n = 1001
        self.folder = self.p.train / ('模考复盘/第%d季' % self.n)

    def install(self, unknown=()):
        blank_paper(self.folder, unknown)
        self.g.state.setdefault('mocks', {})[str(self.n)] = {'name': NAME}

    def answers(self, wrong=(), blank=()):
        return {str(i): ('' if i in blank else 'ABCD'[(i + 1) % 4] if i in wrong else key_of(i)) for i in range(1, 131)}

    def take(self, answers, elapsed=5400):
        exam_room.begin(self.g, self.n)
        exam_room.save_run(self.g, self.n, {'answers': answers, 'elapsed': elapsed})
        return exam_room.submit(self.g, self.n, {'answers': answers, 'elapsed': elapsed})

    def test_papers_listed_by_name_and_questions_hide_answers(self):
        self.install()
        listing = exam_room.papers(self.g)
        item = listing['papers'][0]
        self.assertEqual((item['season'], item['name'], item['total'], item['keyed']), (1001, NAME, 130, 130))
        self.assertEqual([m['display'] for m in item['modules']], ['政治理论', '常识判断', '言语理解与表达', '数量关系', '判断推理', '资料分析'])
        self.assertEqual(listing['minutes'], 120)
        data = exam_room.begin(self.g, self.n)
        self.assertEqual(len(data['questions']), 130)
        self.assertEqual(data['run']['limit'], 7200)
        self.assertEqual(data['questions'][0]['choices'], ['A', 'B', 'C', 'D'])
        self.assertNotIn('正确答案', str(data)); self.assertNotIn('correct', data['questions'][0])
        again = exam_room.begin(self.g, self.n)
        self.assertEqual(again['run']['started'], data['run']['started'], '再进来是继续同一场')

    def test_submit_grades_writes_review_and_records_contest_by_paper_name(self):
        self.install()
        result = self.take(self.answers(wrong={1, 2, 3}, blank={130}))
        self.assertEqual((result['ok'], result['bad'], result['blank'], result['nokey']), (126, 3, 1, 0))
        self.assertFalse(result['partial'])
        self.assertTrue(result['basis'].startswith('按规则里的参考分值表'))
        self.assertGreater(result['score'], 90)
        self.assertEqual(result['minutes'], 90)
        icons = {q['num']: q['icon'] for f in sorted(self.folder.glob('[0-9][0-9]-*.md')) for q in vault.parse_board_file(f)}
        self.assertEqual((icons[1], icons[4], icons[130]), ('❌', '✅', '⚪'))
        s = next(x for x in mock.summary(self.g)['seasons'] if x['season'] == self.n)
        self.assertEqual((s['name'], s['score'], s['date']), (NAME, result['score'], self.g.t))
        self.assertEqual([b['name'] for b in self.g.state['boss']], [NAME])
        self.assertTrue(any(p.get('source') == NAME and p['minutes'] == 90 for p in self.g.state['practice']))
        self.assertNotIn(str(self.n), g_runs(self.g))
        text = (self.folder / '01-政治理论.md').read_text(encoding='utf-8')
        self.assertIn('我的答案：**%s**　错误' % 'ABCD'[2], text)
        again = exam_room.result(self.g, self.n)
        self.assertEqual((again['score'], again['attempts']), (result['score'], 1))

    def test_reward_once_and_retake_updates_score(self):
        self.install()
        first = self.take(self.answers(wrong=set(range(1, 21))))
        boss_count = len(self.g.state['boss']); xp = self.g.state['xp']
        second = self.take(self.answers())
        self.assertEqual(len(self.g.state['boss']), boss_count, '同一张试卷录分奖励只结算一次')
        self.assertGreater(second['score'], first['score'])
        self.assertEqual(self.g.state['mocks'][str(self.n)]['score'], second['score'])
        self.assertEqual(second['attempts'], 2)
        self.assertGreater(self.g.state['xp'], xp)          # 自练按题给的修为仍记

    def test_questions_without_key_are_not_graded_and_answers_import_regrades(self):
        self.install(unknown={1, 2, 3})
        result = self.take(self.answers())
        self.assertEqual((result['nokey'], result['partial']), (3, True))
        self.assertEqual(result['ok'], 127)
        before = self.g.state['mocks'][str(self.n)]['score']
        out = exam_room.import_answers(self.g, {'season': self.n, 'text': '1.%s 2.%s 3.%s' % (key_of(1), key_of(2), key_of(3))})
        self.assertEqual((out['filled'], out['keyed'], out['missing']), (3, 130, []))
        self.assertEqual(out['regraded']['nokey'], 0)
        rec = self.g.state['mocks'][str(self.n)]
        self.assertFalse(rec['exam']['partial'])
        self.assertGreaterEqual(rec['score'] if rec['score'] is not None else 0, 0)
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_answers(self.g, {'season': self.n, 'text': '没有答案'})

    def test_answers_from_pdf_text_layer(self):
        import pymupdf
        self.install(unknown={1, 2, 3})
        doc = pymupdf.open(); page = doc.new_page()
        page.insert_text((72, 72), '1.%s 2.%s 3.%s' % (key_of(1), key_of(2), key_of(3)))
        out = exam_room.import_answers(self.g, {'season': self.n, 'pdf': base64.b64encode(doc.tobytes()).decode()})
        self.assertEqual((out['filled'], out['keyed']), (3, 130))
        blank = pymupdf.open(); blank.new_page()
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_answers(self.g, {'season': self.n, 'pdf': base64.b64encode(blank.tobytes()).decode()})
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_answers(self.g, {'season': self.n, 'pdf': 'not a pdf'})

    def test_save_run_validates_and_pauses(self):
        self.install()
        exam_room.begin(self.g, self.n)
        r = exam_room.save_run(self.g, self.n, {'answers': {'1': 'a', '999': 'A', 'x': 'B', '2': 'Z'}, 'marks': [3, 'z', 999], 'elapsed': 61})
        self.assertEqual((r['elapsed'], r['answered']), (61, 1))
        run = self.g.state['exam_runs'][str(self.n)]
        self.assertEqual((run['answers'], run['marks']), ({'1': 'A'}, [3]))
        exam_room.save_run(self.g, self.n, {'elapsed': 30})
        self.assertEqual(run['elapsed'], 61, '用时只增不减')
        exam_room.discard(self.g, self.n)
        with self.assertRaises(exam_room.ExamError):
            exam_room.save_run(self.g, self.n, {'elapsed': 1})

    def test_overtime_and_rules_minutes(self):
        self.install()
        self.g.rules.raw['整卷考试.分钟'] = '90'
        data = exam_room.begin(self.g, self.n)
        self.assertEqual(data['run']['limit'], 5400)
        result = self.take(self.answers(), elapsed=6000)
        self.assertTrue(result['overtime']); self.assertEqual(result['minutes'], 90)

    def test_import_paper_names_it_and_skips_the_import_credit(self):
        from rpg import exam_scan
        calls = []
        def fake_split(paths_, pdf, number, engine=None, part_sizes=None):
            calls.append((number, Path(pdf).name))
            blank_paper(paths_.train / ('模考复盘/第%d季' % number))
            return {'found': 130, 'total': 130, 'missing': [], 'modules': {'政治理论': 20}, 'split_log': '按版面拆分：认出 130/130 题'}
        with patch.object(exam_scan, 'split', side_effect=fake_split):
            r = exam_room.import_paper(self.g, {'name': NAME, 'data': base64.b64encode(b'%PDF-1.4 fake').decode()})
        self.assertEqual((r['season'], r['name'], r['total'], r['keyed']), (1001, NAME, 130, 130))
        self.assertEqual(calls[0][0], 1001)
        self.assertTrue((self.p.train.parent / 'FB模考试卷复盘' / '模考试卷' / ('第1001季-%s.pdf' % NAME)).is_file() or any(self.p.vault.rglob('第1001季-*.pdf')))
        self.assertIn('1001', self.g.state['mock_practice'], '导入不另记120分钟')
        self.assertEqual(self.g.state['practice'], [])
        self.assertEqual(mock.season_name(self.g, 1001), NAME)
        self.assertEqual(exam_room._PENDING, set(), '导入完成后编号不再占用')
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_paper(self.g, {'name': NAME, 'data': 'x'})            # 重名
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_paper(self.g, {'name': '', 'data': 'x'})

    def test_scanned_paper_goes_through_the_whole_exam_flow_with_images(self):
        """扫描卷（没有文字层）：版面拆分 → 开始考试拿到的是图片块 → 补答案 → 交卷批改。"""
        import re
        from rpg import exam_scan
        from tests import test_exam_scan as ts
        pdf = self.root / 'scan.pdf'
        ts.make_pdf(pdf, ts.PAGES + ts.PAGES_C)
        pages = ts.PAGES + ts.PAGES_C
        engine = lambda f: pages[int(re.search(r'p(\d+)\.png', f).group(1))]
        plan = exam_room.plan_import(self.g, {'name': NAME, 'data': base64.b64encode(pdf.read_bytes()).decode()})
        report = exam_scan.split(self.g.paths, pdf, plan['season'], engine=engine)
        done = exam_room.finish_import(self.g, plan, report)
        self.assertEqual((done['total'], done['keyed'], done['missing']), (9, 0, []))
        data = exam_room.begin(self.g, 1001)
        self.assertEqual([q['num'] for q in data['questions']], list(range(1, 10)))
        self.assertTrue(all(any(b['t'] == 'img' for b in q['blocks']) for q in data['questions']), '每题都是图片')
        self.assertTrue(data['materials'], '资料分析的材料图')
        self.assertIn('没有标准答案', data['warning'])
        exam_room.import_answers(self.g, {'season': 1001, 'text': '1-9 ABCDABCDA'})
        result = exam_room.submit(self.g, 1001, {'answers': {str(i): 'ABCDABCDA'[i - 1] for i in range(1, 10)}, 'elapsed': 600})
        self.assertEqual((result['ok'], result['bad'], result['nokey']), (9, 0, 0))

    def test_split_failure_releases_the_season_number_and_reports_the_reason(self):
        from rpg import exam_scan
        with patch.object(exam_scan, 'split', side_effect=exam_scan.ScanError('这份试卷PDF是扫描图片，需要系统自带OCR')):
            with self.assertRaises(exam_room.ExamError) as ctx:
                exam_room.import_paper(self.g, {'name': NAME, 'data': base64.b64encode(b'%PDF-1.4 fake').decode()})
        self.assertIn('扫描图片', str(ctx.exception))
        self.assertEqual(exam_room._PENDING, set())
        self.assertEqual(exam_room.next_season(self.g), 1001, '失败后编号还能用')

    def test_old_split_script_is_tried_first_for_text_pdfs_and_scan_is_the_fallback(self):
        from rpg import exam_scan
        order = []
        def old(paths_, body):
            order.append('old')
            raise exam_room.importer.ImportError_('拆分完成但没找到第1001季的板块复盘')
        def new(paths_, pdf, number, engine=None, part_sizes=None):
            order.append('scan')
            blank_paper(paths_.train / ('模考复盘/第%d季' % number))
            return {'found': 130, 'total': 130, 'missing': [], 'modules': {}, 'split_log': '按版面拆分'}
        with patch.object(exam_room.importer, 'split_script', return_value=Path('x.py')), patch.object(exam_room, '_has_text_layer', return_value=True), \
                patch.object(exam_room.importer, 'split_pdf', side_effect=old), patch.object(exam_scan, 'split', side_effect=new):
            r = exam_room.import_paper(self.g, {'name': NAME, 'data': base64.b64encode(b'%PDF-1.4 fake').decode()})
        self.assertEqual(order, ['old', 'scan'])
        self.assertIn('旧拆分脚本没认出', r['split_log'])

    def test_legacy_seasons_keep_their_names(self):
        blank_paper(self.p.train / '模考复盘/第39季')
        self.assertEqual(mock.season_name(self.g, 39), '第39季')
        self.assertEqual(exam_room.papers(self.g)['papers'][0]['name'], '第39季')
        self.assertEqual(exam_room.next_season(self.g), 1001)


def g_runs(g):
    return g.state.get('exam_runs', {})


if __name__ == '__main__':
    unittest.main()
