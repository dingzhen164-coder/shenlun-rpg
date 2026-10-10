"""每日文章更新：抓取的总额/日期/历史检索及文章批注本的原文、笔迹和版本保护。"""
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path

from rpg import article_notes, articles, notes, paths


def setUpModule():
    os.environ['SHENLUN_SUBJECT'] = '申论'


def tearDownModule():
    os.environ.pop('SHENLUN_SUBJECT', None)


def page(title, date=None):
    meta = '<meta name="publishdate" content="%s">' % date if date else ''
    return '<h1>%s</h1>%s<p>%s</p>' % (title, meta, '基层治理让群众少跑腿，创新服务方式促进共同发展。' * 15)


class ArticleUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = paths.Paths(Path(self.tmp.name), '申论')
        articles.JOB.update(running=False, log=[], added=0, done=0, total=0)

    def tearDown(self):
        self.tmp.cleanup()

    def test_calendar_ranges_and_validation(self):
        today = dt.date(2026, 3, 31)
        self.assertEqual(articles.crawl_options({'range': '7d'}, today)['since'], '2026-03-25')
        self.assertEqual(articles.crawl_options({'range': '1m'}, today)['since'], '2026-02-28')
        self.assertEqual(articles.crawl_options({'range': '6m'}, today)['since'], '2025-09-30')
        for body in ({'count': 0}, {'count': 2.5}, {'count': True}, {'range': 'wrong'}, {'categories': '经济'}, {'categories': ['wrong']}, {'sources': 'x'}):
            with self.assertRaises(articles.ArticleError):
                articles.crawl_options(body, today)

    def test_date_from_url_compact_people_and_invalid(self):
        for url in ('http://x.test/20261009/a.html', 'http://x.test/n1/2026/1009/c1-99.html'):
            art = articles.parse_article(page('科技创新服务民生'), url)
            self.assertEqual(art['date'], '2026-10-09')
            self.assertTrue(art['date_known'])
        unknown = articles.parse_article(page('日期不明确的文章', '2026-99-99'), 'http://x.test/a.html')
        self.assertFalse(unknown['date_known'])

    def test_total_quota_newest_across_sources_and_history(self):
        pages = {
            'http://a.test/': '<a href="/art/1.html">基层治理改革好做法</a><a href="/page2.html">下一页</a>',
            'http://a.test/page2.html': '<a href="/art/2.html">改革治理创新好做法</a><a href="/">上一页</a>',
            'http://a.test/art/1.html': page('基层治理改革好做法', '2026-10-07'),
            'http://a.test/art/2.html': page('改革治理创新好做法', '2026-10-09'),
            'http://b.test/': '<a href="/art/3.html">服务基层群众好做法</a>',
            'http://b.test/art/3.html': page('服务基层群众好做法', '2026-10-10'),
        }
        srcs = [{'name': n, 'url': 'http://%s.test/' % n, 'pat': r'/art/\d+\.html', 'cat': ''} for n in ('a', 'b')]
        opts = articles.crawl_options({'count': 2, 'range': '7d'}, dt.date(2026, 10, 10))
        visited = []
        def fetch(url):
            visited.append(url)
            return pages[url]
        results = articles.crawl(self.p, srcs, fetcher=fetch, options=opts)
        self.assertEqual(sum(r['added'] for r in results), 2)
        self.assertEqual({articles._read_file(f)['date'] for f in articles.all_files(self.p)}, {'2026-10-09', '2026-10-10'})
        self.assertEqual(visited.count('http://a.test/'), 1)
        # 已抓的两篇不占额度，再抓会补进尚未抓的那篇。
        again = articles.crawl(self.p, srcs, fetcher=fetch, options=opts)
        self.assertEqual(sum(r['added'] for r in again), 1)
        self.assertIn('不足', articles.JOB['log'][-1])

    def test_categories_future_old_and_unknown_dates_are_filtered(self):
        titles = [('科技创新的治理文章', '2026-10-09'), ('生态治理的绿色文章', '2026-10-09'),
                  ('科技创新的未来文章', '2026-10-11'), ('科技创新的旧文章', '2026-09-01'), ('科技创新无日期文章', None)]
        pages = {'http://x.test/': ''.join('<a href="/art/%d.html">%s</a>' % (i, t) for i, (t, _) in enumerate(titles))}
        pages.update({'http://x.test/art/%d.html' % i: page(t, d) for i, (t, d) in enumerate(titles)})
        opts = articles.crawl_options({'count': 10, 'range': '7d', 'categories': ['科技']}, dt.date(2026, 10, 10))
        results = articles.crawl(self.p, [{'name': 'x', 'url': 'http://x.test/', 'pat': r'/art/\d+\.html', 'cat': '党政治理'}], fetcher=pages.__getitem__, options=opts)
        self.assertEqual(results[0]['added'], 1)
        self.assertEqual(results[0]['unknown_date'], 1)
        self.assertEqual(articles._read_file(articles.all_files(self.p)[0])['category'], '科技')

    def test_history_navigation_stays_on_source(self):
        html = '<a href="http://evil.test/page2.html">下一页</a><a href="/page2.html">下一页</a><a href="/art/2.html">更多</a>'
        self.assertEqual(articles.history_links(html, 'http://x.test/', r'/art/\d+\.html'), ['http://x.test/page2.html'])

    def test_article_wrap_preserves_punctuation_and_avoids_hanging(self):
        text = '一' * 21 + '，继续阅读。' + '甲' * 15 + '（括号内的说明）'
        lines = article_notes.wrap(text)
        self.assertEqual(''.join(lines), text)
        self.assertTrue(all(not line.startswith(('，', '。', '）')) for line in lines))
        self.assertTrue(all(not line.endswith('（') for line in lines))

    def seed(self):
        art = {'id': 'abc12345', 'title': '科技服务基层', 'date': '2026-10-09', 'source': '自编测试', 'url': 'http://a.test/x',
               'category': '科技', 'paras': ['完整原文不截断，中英文 mixed text。' * 100, '尾段完整保留。']}
        articles.save_article(self.p, art)
        return art

    def test_snapshot_roundtrip_reopen_and_delete_preserves_notebook(self):
        art = self.seed()
        nid = article_notes.open_book(self.p, art['id'])['id']
        book = notes.get(self.p, nid)
        self.assertEqual(''.join(''.join(p['article_lines']) for p in book['pages']).replace('　', ''), ''.join(art['paras']))
        self.assertGreater(len(book['pages']), 1)
        self.assertEqual(notes.listing(self.p)[0]['article'], True)
        book['pages'][0]['strokes'] = [{'t': 'hl', 'c': '#ffff00', 'w': 22, 'p': [[70, 270], [700, 270]]}]
        notes.save(self.p, dict(book, text='我自己的心得'))
        self.assertEqual(article_notes.open_book(self.p, art['id'])['id'], nid)
        saved = notes.get(self.p, nid)
        self.assertEqual(saved['pages'][0]['strokes'][0]['t'], 'hl')
        self.assertEqual(saved['text'], '我自己的心得')
        self.assertEqual(saved['article']['paras'], art['paras'])
        articles.find(self.p, art['id'])['file'].unlink()
        self.assertEqual(notes.get(self.p, nid)['article']['paras'], art['paras'])

    def test_revision_prevents_stale_overwrite_and_layout_is_server_owned(self):
        art = self.seed()
        nid = article_notes.open_book(self.p, art['id'])['id']
        old = notes.get(self.p, nid)
        reply = notes.save(self.p, dict(old, text='新内容', pages=[{'strokes': [], 'article_lines': ['篡改原文'] }]))
        self.assertEqual(reply['revision'], 1)
        with self.assertRaisesRegex(notes.NotesError, '另一处更新'):
            notes.save(self.p, dict(old, text='过期覆盖'))
        saved = notes.get(self.p, nid)
        self.assertEqual(saved['text'], '新内容')
        self.assertEqual(saved['pages'][0]['article_lines'], old['pages'][0]['article_lines'])
        self.assertEqual(len(saved['pages']), len(old['pages']))
        self.assertEqual(saved['paper'], 'article')


if __name__ == '__main__':
    unittest.main()
