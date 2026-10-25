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
        calls = []
        def fake_split(paths_, body):
            number = int(body['file'].split('季')[0].lstrip('第'))
            calls.append((number, body['file']))
            blank_paper(paths_.train / ('模考复盘/第%d季' % number))
            return {'ready': 130, 'fix': 0, 'split_log': '共解析130题'}
        with patch.object(importer, 'split_pdf', side_effect=fake_split):
            r = exam_room.import_paper(self.g, {'name': NAME, 'data': base64.b64encode(b'%PDF-1.4 fake').decode()})
        self.assertEqual((r['season'], r['name'], r['total'], r['keyed']), (1001, NAME, 130, 130))
        self.assertEqual(calls[0][0], 1001)
        self.assertTrue((self.p.train / '模考试卷' / ('第1001季-%s.pdf' % NAME)).is_file())
        self.assertIn('1001', self.g.state['mock_practice'], '导入不另记120分钟')
        self.assertEqual(self.g.state['practice'], [])
        self.assertEqual(mock.season_name(self.g, 1001), NAME)
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_paper(self.g, {'name': NAME, 'data': 'x'})            # 重名
        with self.assertRaises(exam_room.ExamError):
            exam_room.import_paper(self.g, {'name': '', 'data': 'x'})

    def test_legacy_seasons_keep_their_names(self):
        blank_paper(self.p.train / '模考复盘/第39季')
        self.assertEqual(mock.season_name(self.g, 39), '第39季')
        self.assertEqual(exam_room.papers(self.g)['papers'][0]['name'], '第39季')
        self.assertEqual(exam_room.next_season(self.g), 1001)


def g_runs(g):
    return g.state.get('exam_runs', {})


if __name__ == '__main__':
    unittest.main()
