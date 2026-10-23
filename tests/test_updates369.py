"""3.6.9：整卷板块完整题量/来源/奖励、PDF原始行、联网出处及旧批注升级。仅自编资料。"""
import json
import os
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from rpg import question_bank as bank, politics, politics_import, policy_search
from tests import test_bank as bank_tests, test_politics as politics_tests
from tests.test_tianji import fitz


question = bank_tests.question


def setUpModule():
    os.environ['SHENLUN_SUBJECT'] = '行测'


def tearDownModule():
    os.environ.pop('SHENLUN_SUBJECT', None)


class BlockPaperTests(unittest.TestCase):
    setUp = bank_tests.BankTest.setUp
    tearDown = bank_tests.BankTest.tearDown

    def test_complete_board_includes_done_and_ignores_count_order(self):
        for board, total in [('资料分析', 20), ('图形推理', 6)]:
            text = ''.join(question('原卷-%02d' % i).replace('### 知识点', '### 试卷\n自编甲省卷\n### 题号\n%d\n### 知识点' % i)
                           for i in range(total, 0, -1))
            (self.paths.train/'题库'/(board+'真题.md')).write_text(text, encoding='utf-8')
        qs = bank.read(self.paths, '资料分析')[0]
        data = bank.state(self.g)
        data['order'] = 'shuffle'
        data['records'][qs[0]['key']] = {'question': qs[0], 'history': [{'ok': True}], 'wrong': False, 'streak': 1}
        slot = '卷块:资料分析:自编甲省卷'
        run = bank.begin(self.g, slot, 'new')
        self.assertEqual(len(run['questions']), 20)
        self.assertEqual([q['nums'][0] for q in run['questions']], list(range(1, 21)))
        self.assertIs(bank.begin(self.g, slot, 'new'), run)
        self.assertIn('来源：自编甲省卷', bank.label(slot))
        self.assertTrue(bank.is_set(slot))
        other = bank.begin(self.g, '卷块:图形推理:自编甲省卷', 'new')
        self.assertEqual(len(other['questions']), 6)
        self.assertTrue(all(q['board'] == '图形推理' for q in other['questions']))

    def test_provincial_counts_and_catalog_do_not_expose_answers(self):
        for total in (15, 20):
            text = ''.join(question('自编-%02d-%02d' % (total, i)) for i in range(1, total+1))
            (self.paths.train/'题库/资料分析真题.md').write_text(text, encoding='utf-8')
            result = bank.summary(self.g)
            entry = next(b for b in result['boards'] if b['board'] == '资料分析')['papers'][0]
            self.assertEqual(entry['total'], total)
            self.assertNotIn('秘密解析', json.dumps(entry))
            self.assertEqual(len(bank.begin(self.g, entry['slot'], 'new')['questions']), total)
        with self.assertRaises(bank.BankError):
            bank.begin(self.g, '卷块:图形推理:不存在', 'new')

    def test_repeat_full_board_does_not_award_first_question_twice(self):
        self.file.write_text(question('自编-01-01'), encoding='utf-8')
        slot = '卷块:论证逻辑:自编-01'
        run = bank.begin(self.g, slot, 'new')
        bank.record(self.g, run, 'A')
        group = bank.finish(self.g, run)
        self.assertEqual(group['first_count'], 1)
        xp = self.g.state['xp']
        repeat = bank.begin(self.g, slot, 'new')
        self.assertEqual(bank.record(self.g, repeat, 'A'), [])
        self.assertEqual(bank.finish(self.g, repeat)['first_count'], 0)
        self.assertEqual(self.g.state['xp'], xp)

    def test_existing_mock_import_ids_provide_paper_source(self):
        self.file.write_text(question('粉笔36季-080')+question('粉笔36季-079')+question('粉笔37季-079'), encoding='utf-8')
        run = bank.begin(self.g, '卷块:论证逻辑:粉笔第36季模考', 'new')
        self.assertEqual([q['id'] for q in run['questions']], ['粉笔36季-079', '粉笔36季-080'])


class Annotation369Tests(unittest.TestCase):
    setUp = politics_tests.PoliticsTests.setUp
    def test_network_research_is_saved_grounded_and_cached(self):
        research = {'status': 'ok', 'sources': [{'title': '自编政府政策说明', 'url': 'https://www.gov.cn/test.htm', 'summary': '自编政策依据'}]}
        with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.policy_search.search', return_value=research) as search, patch('rpg.politics.ai.chat', return_value=json.dumps(self.answer)) as chat:
            result = politics.explain(self.pp, self.src, self.body)
            self.assertEqual(result['note']['research'], research)
            self.assertEqual(result['note']['version'], politics.NOTE_VERSION)
            request = json.loads(chat.call_args[0][0][1]['content'])
            self.assertEqual(request['background_research'], research)
            self.assertTrue(politics.explain(self.pp, self.src, self.body)['cached'])
            self.assertEqual(search.call_count, 1)

    def test_v2_explicit_upgrade_and_failure_preserve_old_note(self):
        anchor = politics.validate_anchor(self.src, self.body)
        key = politics.digest(anchor)
        old = dict(anchor, key=key, version=2, explanation=dict(self.answer, role='旧语境', example='旧例子', plain='旧摘要'))
        file = self.pp.train/'词义批注'/(politics.identity(self.src)+'.json')
        politics.atomic_json(file, {key: old})
        with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value='bad'):
            self.assertEqual(politics.explain(self.pp, self.src, self.body)['note'], old)
            with self.assertRaises(politics.PoliticsError):
                politics.explain(self.pp, self.src, dict(self.body, refresh=True))
        self.assertEqual(politics.list_notes(self.pp, self.src)[key], old)


class LayoutSearchTests(unittest.TestCase):
    def test_tower_real_rgb_4k_and_native_sources(self):
        from PIL import Image
        root = Path(__file__).resolve().parents[1]/'web/assets/beauty/trial/hd/369'
        data = json.loads((root/'provenance.json').read_text(encoding='utf-8'))
        file = root/'hall-day.webp'
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), data['sha256'])
        with Image.open(file) as im:
            self.assertEqual(im.size, (3840, 2880))
            r, g, b = im.getpixel((500, 250))
            self.assertGreater(max(r,g,b)-min(r,g,b), 20, '合成不能变成灰度图')
        self.assertEqual(len(data['tiles']), 8)
        for tile in data['tiles']:
            self.assertGreaterEqual(tile['native'][0], tile['w'])
            self.assertGreaterEqual(tile['native'][1], tile['h'])
    @unittest.skipIf(fitz is None, '需要PDF组件')
    def test_pdf_actual_lines_keep_same_line_options_and_continuations(self):
        with fitz.open() as doc:
            p = doc.new_page()
            p.insert_text((60, 80), '1. First line')
            p.insert_text((60, 100), 'continuation?')
            p.insert_text((60, 120), 'A. One  B. Two')
            p.insert_text((60, 140), 'C. Three  D. Four')
            q = {'text': 'First linecontinuation?\nA.One\nB.Two\nC.Three\nD.Four'}
            politics_import._layout_text(doc, [q])
            self.assertEqual(q['layout_text'].splitlines(), ['1. First line', 'continuation?', 'A. One  B. Two', 'C. Three  D. Four'])

    def test_search_accepts_only_authoritative_https_and_handles_failure(self):
        for url in ['http://www.gov.cn/a', 'https://gov.cn.evil.test/a', 'https://evilgov.cn/a', 'https://user@www.gov.cn/a', 'https://www.gov.cn:444/a']:
            self.assertFalse(policy_search.trusted_url(url))
        self.assertTrue(policy_search.trusted_url('https://www.gov.cn/a'))
        with patch('rpg.policy_search.net.urlopen', side_effect=OSError('offline')):
            result = policy_search.search('严控一般性支出', '自编文件')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['sources'], [])

    def test_search_validates_live_response_sources_and_relevance(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (
            '<rss><channel><item><title>严控一般性支出政策说明</title><link>https://www.gov.cn/policy.htm</link>'
            '<description>压减非必要开支，保障民生。</description></item>'
            '<item><title>严控一般性支出</title><link>https://gov.cn.evil.test/a</link><description>伪造结果</description></item>'
            '<item><title>无关新闻</title><link>https://www.gov.cn/other.htm</link><description>无关内容</description></item>'
            '</channel></rss>').encode('utf-8')
        with patch('rpg.policy_search.net.urlopen', return_value=response):
            result = policy_search.search('严控一般性支出', '自编讲义')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual([s['url'] for s in result['sources']], ['https://www.gov.cn/policy.htm'])

    @unittest.skipIf(fitz is None, '需要PDF组件')
    def test_legacy_pdf_layout_recovers_without_reimport_or_rewrite(self):
        from rpg import paths
        with tempfile.TemporaryDirectory() as tmp, fitz.open() as doc:
            pp = paths.Paths(Path(tmp), '行测')
            p = doc.new_page()
            for index, text in enumerate(['1. A test?', 'A. One B. Two', 'C. Three D. Four']):
                p.insert_text((60, 80+index*20), text)
            content = doc.tobytes()
            ident = hashlib.sha256(content).hexdigest()
            folder = pp.train/'时政知识地图/原文'
            folder.mkdir(parents=True)
            file = folder/(ident+'.pdf')
            file.write_bytes(content)
            q = {'id': 20, 'text': 'A test?\nA.One\nB.Two\nC.Three\nD.Four', 'answer': 'A'}
            politics_import.restore_layout(pp, [q], [ident])
            self.assertEqual(q['layout_text'], '1. A test?\nA. One B. Two\nC. Three D. Four')
            self.assertEqual(q['id'], 20)
            self.assertEqual(file.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
