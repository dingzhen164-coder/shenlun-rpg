"""📅 每日文章（rpg/articles.py）：用本地假网页测列表页挑链接、正文提取、去重、坏来源不拖累别的来源、精读校验、玉简、API"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import ai, api, articles, cards, paths  # noqa: E402


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "申论"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


BODY = "基层治理是国家治理的基石，要把服务送到群众家门口，让群众办事少跑腿、不添堵。" * 6


def article_html(title, date="2026-10-01", body=BODY):
    return ('<html><head><title>%s_某网</title><meta name="publishdate" content="%s"></head><body><nav><p>首页 导航 登录 注册 更多栏目</p></nav>'
            '<h1>%s</h1><p>%s</p><p>让群众少跑腿，是衡量治理水平的一把尺子，也是干部作风的试金石。</p><p>责任编辑：某某</p>'
            '<footer><p>版权所有 某某网站 未经许可不得转载 Copyright</p></footer></body></html>') % (title, date, title, body)


LIST = ('<html><body><a href="/n1/2026/1001/c1-1.html">基层治理要让群众少跑腿</a><a href="/n1/2026/1002/c1-2.html">绿色发展的生态账本怎么算</a>'
        '<a href="/about.html">关于我们的网站介绍</a><a href="/n1/2026/1003/c1-3.html">这一篇打不开会失败</a></body></html>')
PAT = r"/n1/\d{4}/\d{4}/c\d+-\d+\.html"
PAGES = {"http://a.test/": LIST,
         "http://a.test/n1/2026/1001/c1-1.html": article_html("基层治理要让群众少跑腿", "2026-10-01"),
         "http://a.test/n1/2026/1002/c1-2.html": article_html("绿色发展的生态账本怎么算", "2026-10-02")}


def fake_fetch(url, timeout=12):
    if url in PAGES:
        return PAGES[url]
    raise OSError("连不上 " + url)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._keep = (paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR)
        paths.SETTINGS_DIR = paths._DEFAULT_SETTINGS_DIR = self.tmp / "h"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        v = self.tmp / "申论库"
        (v / "copilot/skills/x").mkdir(parents=True)
        paths.save_settings({"vaults": {"申论": str(v)}})
        self.vault = v
        articles.JOB.update(running=False, log=[], added=0, done=0, total=0)

    def tearDown(self):
        paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR = self._keep
        shutil.rmtree(self.tmp, ignore_errors=True)


class ParseTest(unittest.TestCase):
    def test_links_pick_only_article_urls(self):
        links = articles.find_links(LIST, "http://a.test/", PAT)
        self.assertEqual([u for u, _ in links], ["http://a.test/n1/2026/1001/c1-1.html", "http://a.test/n1/2026/1002/c1-2.html", "http://a.test/n1/2026/1003/c1-3.html"])

    def test_parse_article_drops_nav_and_footer(self):
        a = articles.parse_article(article_html("基层治理要让群众少跑腿"), "http://a.test/x")
        self.assertEqual(a["title"], "基层治理要让群众少跑腿")
        self.assertEqual(a["date"], "2026-10-01")
        self.assertTrue(all("责任编辑" not in p and "版权所有" not in p and "导航" not in p for p in a["paras"]))
        self.assertGreaterEqual(len(a["paras"]), 2)

    def test_short_page_is_not_an_article(self):
        with self.assertRaises(articles.ArticleError):
            articles.parse_article("<html><h1>标题标题</h1><p>只有这么一点点字数而已。</p></html>", "http://a.test/x")

    def test_category_guess(self):
        self.assertEqual(articles.guess_category("发展绿色经济的生态账本"), "生态")
        self.assertEqual(articles.guess_category("随便", "党政治理"), "党政治理")
        self.assertEqual(articles.guess_category("某某时评"), "社论评论")

    def test_gbk_page_decoded(self):
        class R:
            headers = type("H", (), {"get_content_charset": lambda s: None})()
            def __enter__(s): return s
            def __exit__(s, *a): pass
            def read(s, n): return '<meta charset="gb2312"><p>人民时评</p>'.encode("gb18030")
        with patch("urllib.request.urlopen", return_value=R()):
            self.assertIn("人民时评", articles.fetch("http://x.test/"))


class CrawlTest(Base):
    def test_crawl_saves_files_dedupes_and_isolates_bad_source(self):
        p = paths.Paths(self.vault, "申论")
        srcs = [{"name": "好来源", "url": "http://a.test/", "pat": PAT, "cat": ""},
                {"name": "坏来源", "url": "http://dead.test/", "pat": PAT, "cat": ""},
                {"name": "改版来源", "url": "http://a.test/n1/2026/1001/c1-1.html", "pat": r"/never/", "cat": ""}]
        res = articles.crawl(p, srcs, fetcher=fake_fetch)
        self.assertEqual([r["added"] for r in res], [2, 0, 0])
        self.assertEqual(res[0]["failed"], 1)                       # 第三篇打不开，只算这一篇失败
        self.assertIn("打不开", res[1]["error"])
        self.assertIn("改版", res[2]["error"])
        files = articles.all_files(p)
        self.assertEqual(len(files), 2)
        self.assertTrue(all(f.parent.name == "2026-10" for f in files))
        again = articles.crawl(p, srcs[:1], fetcher=fake_fetch)       # 再抓：已有的不重复
        self.assertEqual((again[0]["added"], again[0]["skipped"]), (0, 2))
        self.assertEqual(len(articles.all_files(p)), 2)

    def test_import_url_and_roundtrip(self):
        p = paths.Paths(self.vault, "申论")
        r = articles.import_url(p, "http://a.test/n1/2026/1001/c1-1.html", fetcher=fake_fetch)
        self.assertTrue(r["new"])
        self.assertFalse(articles.import_url(p, "http://a.test/n1/2026/1001/c1-1.html", fetcher=fake_fetch)["new"])
        a = articles.find(p, r["id"])
        self.assertEqual((a["source"], a["category"]), ("手动导入", "民生社会"))
        with self.assertRaises(articles.ArticleError):
            articles.import_url(p, "不是网址", fetcher=fake_fetch)
        with self.assertRaises(articles.ArticleError):
            articles.import_url(p, "http://nope.test/x", fetcher=fake_fetch)


class StateAndJdTest(Base):
    def seed(self, g):
        art = articles.parse_article(article_html("基层治理要让群众少跑腿"), "u")
        art.update(id="abcd1234", source="人民网·观点", url="http://a.test/1", category="党政治理")
        articles.save_article(g.paths, art)
        return articles.find(g.paths, "abcd1234")

    def test_read_star_filter_data_and_delete(self):
        with api.open_game() as g:
            self.seed(g)
            it = articles.listing(g)["items"][0]
            self.assertEqual((it["read"], it["star"], it["jd"]), (False, False, False))
            articles.get(g, "abcd1234")
            articles.mark(g, "abcd1234", {"star": True})
        with api.open_game() as g:                                      # 存档里有
            it = articles.listing(g)["items"][0]
            self.assertEqual((it["read"], it["star"]), (True, True))
            articles.set_category(g, "abcd1234", "经济")
            self.assertEqual(articles.listing(g)["items"][0]["category"], "经济")
            self.assertEqual(len(articles.all_files(g.paths)), 1)          # 改分类不留旧文件的话，仍然只有一个文件
            articles.delete(g, "abcd1234")
            self.assertEqual(articles.listing(g)["items"], [])

    def test_sources_toggle_and_custom(self):
        with api.open_game() as g:
            on = {s["name"] for s in articles.sources(g) if s["on"]}
            self.assertIn("人民网·观点", on)
            self.assertNotIn("半月谈", on)                                  # 没实测的默认关
            articles.toggle_source(g, "半月谈", True)
            articles.toggle_source(g, "人民网·观点", False)
            on = {s["name"] for s in articles.sources(g) if s["on"]}
            self.assertEqual(("半月谈" in on, "人民网·观点" in on), (True, False))
            articles.add_source(g, "我的来源", "http://my.test/", "经济")
            with self.assertRaises(articles.ArticleError):
                articles.add_source(g, "我的来源", "http://my.test/", "")
            self.assertTrue(any(s["name"] == "我的来源" and not s["builtin"] for s in articles.sources(g)))
            articles.remove_source(g, "我的来源")
            self.assertFalse(any(s["name"] == "我的来源" for s in articles.sources(g)))

    def test_check_jd_drops_invented_quotes_and_bad_tixing(self):
        with api.open_game() as g:
            art = self.seed(g)
        real = "让群众少跑腿，是衡量治理水平的一把尺子"
        raw = {"theme": "基层治理要便民", "points": ["服务到家门口"], "structure": ["提出", "分析"],
               "quotes": [{"text": real, "use": "分析题"}, {"text": "这句话文章里根本没有过的内容啊", "use": "编的"}],
               "materials": [{"kind": "怪", "text": "一网通办"}], "tixing": ["提出对策", "不存在的题型"], "writing": "写法"}
        jd = articles.check_jd(raw, art, cards.DEFAULT_DECKS_SHENLUN)
        self.assertEqual([q["text"] for q in jd["quotes"]], [real])
        self.assertEqual(jd["tixing"], ["提出对策"])
        self.assertEqual(jd["materials"][0]["kind"], "表述")
        for bad in ({}, {"theme": "x", "points": []}):
            with self.assertRaises(articles.ArticleError):
                articles.check_jd(bad, art, [])

    def test_api_jd_retry_cache_and_cards(self):
        with api.open_game() as g:
            self.seed(g)
        good = {"theme": "主旨", "points": ["观点"], "structure": [], "quotes": [{"text": "让群众少跑腿，是衡量治理水平的一把尺子", "use": "用在对策"}],
                "materials": [{"kind": "表述", "text": "服务送到家门口"}], "tixing": ["提出对策"], "writing": ""}
        calls = []

        def fake(msgs, **kw):
            calls.append(1)
            return {"nope": 1} if len(calls) == 1 else good
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", side_effect=fake):
            r = api.ar_jd({"id": "abcd1234"})
            self.assertEqual(len(calls), 2)                                  # 第一次格式不对，重试一次
            self.assertFalse(r["cached"])
            r2 = api.ar_jd({"id": "abcd1234"})
            self.assertTrue(r2["cached"])
            self.assertEqual(len(calls), 2)                                  # 存过的不再花钱
        c = api.ar_cards({"id": "abcd1234"})
        self.assertEqual(c["added"], 2)
        self.assertEqual(api.ar_cards({"id": "abcd1234"})["added"], 0)       # 不重复刻
        with api.open_game() as g:
            self.assertIn("每日文章", cards.data(g)["decks"].get("综合分析", {}).get("children", {}) or str(cards.data(g)["decks"]))

    def test_jd_fails_cleanly_when_ai_keeps_bad(self):
        with api.open_game() as g:
            self.seed(g)
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value={"x": 1}):
            with self.assertRaises(api.ApiError):
                api.ar_jd({"id": "abcd1234"})
        with api.open_game() as g:
            self.assertFalse(articles.jd_file(g.paths, "abcd1234").exists())      # 不入记录

    def test_api_crawl_runs_in_background(self):
        with patch.object(articles, "fetch", side_effect=fake_fetch), patch.object(articles, "SOURCES", [{"name": "测试源", "url": "http://a.test/", "pat": PAT, "cat": ""}]):
            self.assertTrue(api.ar_crawl({})["started"])
            for _ in range(100):
                if not articles.JOB["running"]:
                    break
                import time
                time.sleep(0.05)
            self.assertFalse(articles.JOB["running"])
        r = api.ar_list({})
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(r["job"]["added"], 2)


class SubjectTest(unittest.TestCase):
    def test_xingce_has_no_articles(self):
        tmp = Path(tempfile.mkdtemp())
        keep = (paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR)
        os.environ["SHENLUN_SUBJECT"] = "行测"
        try:
            paths.SETTINGS_DIR = paths._DEFAULT_SETTINGS_DIR = tmp / "h"
            paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
            v = tmp / "行测库"
            (v / "copilot/skills/x").mkdir(parents=True)
            paths.save_settings({"vaults": {"行测": str(v)}})
            with self.assertRaises(api.ApiError):
                api.ar_list({})
        finally:
            os.environ["SHENLUN_SUBJECT"] = "申论"
            paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR = keep
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
