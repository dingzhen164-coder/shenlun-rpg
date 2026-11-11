"""2026-11-11 参阅室：新排版（tidy / 段间空 / 电头淡色 / 按高度分页、旧笔迹另存）、自己写的精读写回 .md、
导入文件夹读成文章、手写精读存摘编、批注本只存改动页。隔离临时库，不连网不连 AI。"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from rpg import article_notes as an, articles, notes, paths


class Base(unittest.TestCase):
    def setUp(self):
        os.environ["SHENLUN_SUBJECT"] = "申论"
        self.tmp = tempfile.TemporaryDirectory()
        self.p = paths.Paths(Path(self.tmp.name), '申论')
        self.art = {'id': 'abcd1234', 'title': '自编排版测试', 'source': '测试', 'date': '2026-10-10', 'url': '', 'category': '科技',
                    'paras': ['新华社北京10月29日电', '（2026年10月29日自编会议通过）', '自编会议于10月在北京举行，会议听取并讨论了自编工作报告，审议通过了自编决定', '。',
                              '·', '与会同志  一致认为 ，要  坚持  自编原则。'] + ['自编正文段落，用来把页面排满。' * 5] * 30}
        articles.save_article(self.p, self.art)

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("SHENLUN_SUBJECT", None)


class LayoutTest(Base):
    def test_tidy_keeps_text_and_cleans_noise(self):
        t = an.tidy(self.art['paras'][:6])
        self.assertEqual(t[0], '新华社北京10月29日电')
        self.assertTrue(t[2].endswith('自编决定。'), '单独断开的句号接回上一段')
        self.assertNotIn('·', t)
        self.assertEqual(t[3], '与会同志一致认为，要坚持自编原则。')

    def test_layout3_gaps_muted_and_height_pages(self):
        pages = an.layout3(self.art)
        first = pages[0]['article_lines']
        self.assertTrue(first[0].startswith('\x01'), '电头淡色单独成行')
        self.assertTrue(any(x.startswith('\x01（2026') for x in first), '括号副标题淡色')
        self.assertIn('', first, '段间空半行')
        self.assertTrue(any(x.startswith('　　自编会议') for x in first), '正文首行缩进两字')
        self.assertNotEqual(pages[0]['article_lines'][0], '')
        for pg in pages:
            y = pg['article_top']
            for line in pg['article_lines']:
                y += an.L3['gap'] if line == '' else an.L3['line']
            self.assertLessEqual(y - an.L3['line'], an.L3['bottom'] + an.L3['line'], '每页不超出正文区')
            self.assertNotEqual(pg['article_lines'][0], '', '页首不留空行')
        self.assertGreater(pages[1]['article_top'], 0)

    def test_old_layout_with_ink_archived_and_rebuilt(self):
        nid = an.open_book(self.p, 'abcd1234')['id']
        b = notes.get(self.p, nid)
        b['article']['layout'] = 2
        b['pages'][0]['strokes'] = [{'t': 'pen', 'c': '#000000', 'w': 3, 'p': [[60, 200], [90, 200]]}]
        notes._file(self.p, nid).write_text(json.dumps(b, ensure_ascii=False), encoding='utf-8')
        r = an.open_book(self.p, 'abcd1234')
        self.assertEqual(r['archived'], nid + '-v2')
        self.assertTrue(notes.get(self.p, r['archived'])['pages'][0]['strokes'])
        new = notes.get(self.p, nid)
        self.assertEqual(new['article']['layout'], 3)
        self.assertFalse(any(p['strokes'] for p in new['pages']))


class ManualJdTest(Base):
    def test_jd_section_roundtrip_and_body_untouched(self):
        articles.save_jd_md(self.p, 'abcd1234', '## 第三步 · 挖万能对策\n- 上门代办\n\n## 金句\n- 群众少跑腿')
        a = articles.find(self.p, 'abcd1234')
        self.assertIn('上门代办', a['jd_md'])
        self.assertEqual(a['paras'], [x for x in self.art['paras'] if x.strip()], '正文不受精读段影响')
        self.assertIn('\n## 精读\n', a['file'].read_text(encoding='utf-8'))
        articles.save_jd_md(self.p, 'abcd1234', '')
        self.assertNotIn('## 精读', articles.find(self.p, 'abcd1234')['file'].read_text(encoding='utf-8'))

    def test_manual_digest_sections_or_whole(self):
        articles.save_jd_md(self.p, 'abcd1234', '## 对策\n1. 上门代办\n- 一次办好\n\n## 黄金句式\n- 群众少跑腿')
        g = type('G', (), {'paths': self.p})()
        r = articles.digest_save(g, 'abcd1234')
        self.assertEqual((r['countermeasures'], r['quotes']), (2, 1))
        d = json.loads(articles.digest_file(self.p, 'abcd1234').read_text(encoding='utf-8'))
        self.assertEqual([x['direction'] for x in d['countermeasures']], ['上门代办', '一次办好'])
        articles.save_jd_md(self.p, 'abcd1234', '只有一段自己的体会')
        r = articles.digest_save(g, 'abcd1234')
        self.assertTrue(r['whole'])
        self.assertEqual(json.loads(articles.digest_file(self.p, 'abcd1234').read_text(encoding='utf-8'))['text'], '只有一段自己的体会')


class ImportTest(Base):
    def test_absorb_template_files(self):
        out = articles.absorb(self.p)
        root = articles.folder(self.p)
        self.assertTrue((root / '导入模板.md').is_file())
        self.assertEqual(out, {'added': [], 'problems': []})
        (root / '导入' / '好文.md').write_text('# 自编导入文章\n来源：自编来源\n日期：2026-11-01\n栏目：民生社会\n\n第一段正文。\n\n第二段正文。\n\n## 精读\n\n（这一段可以不写。）\n\n### 对策\n- 自编对策\n', encoding='utf-8')
        (root / '导入' / '坏.md').write_text('没有标题的文件\n正文', encoding='utf-8')
        out = articles.absorb(self.p)
        self.assertEqual(out['added'], ['自编导入文章'])
        self.assertEqual(len(out['problems']), 1)
        self.assertIn('标题', out['problems'][0])
        self.assertTrue((root / '导入' / '已导入' / '好文.md').is_file())
        self.assertTrue((root / '导入' / '坏.md').is_file(), '读不懂的留在原处')
        a = next(x for x in (articles._read_file(f) for f in articles.all_files(self.p)) if x and x['title'] == '自编导入文章')
        self.assertEqual((a['source'], a['category'], a['date'], a['paras']), ('自编来源', '民生社会', '2026-11-01', ['第一段正文。', '第二段正文。']))
        self.assertEqual(a['jd_md'], '### 对策\n- 自编对策')
        (root / '导入' / '再来.md').write_text('# 自编导入文章\n日期：2026-11-01\n\n正文。', encoding='utf-8')
        self.assertTrue(any('没有重复导入' in x for x in articles.absorb(self.p)['problems']))


class PagePatchTest(Base):
    def test_patch_saves_only_changed_pages(self):
        nid = an.open_book(self.p, 'abcd1234')['id']
        b = notes.get(self.p, nid)
        stroke = {'t': 'pen', 'c': '#222222', 'w': 3, 'p': [[100, 300], [140, 300]]}
        notes.save(self.p, {'id': nid, 'revision': b['revision'], 'page_patch': {'1': {'strokes': [stroke]}}})
        after = notes.get(self.p, nid)
        self.assertEqual(len(after['pages'][1]['strokes']), 1)
        self.assertEqual(after['pages'][0]['strokes'], [])
        self.assertEqual([p['article_lines'] for p in after['pages']], [p['article_lines'] for p in b['pages']])
        self.assertEqual([p.get('article_top') for p in after['pages']], [p.get('article_top') for p in b['pages']])
        with self.assertRaises(notes.NotesError):
            notes.save(self.p, {'id': nid, 'revision': after['revision'], 'page_patch': {'99': {'strokes': []}}})
        # 普通手札：可以接着加一页
        nb = '20261111-120000-001'
        notes.save(self.p, {'id': nb, 'title': '自编手札', 'pages': [{'strokes': []}]})
        notes.save(self.p, {'id': nb, 'page_patch': {'1': {'strokes': [stroke]}}})
        self.assertEqual(len(notes.get(self.p, nb)['pages']), 2)


if __name__ == '__main__':
    unittest.main()
