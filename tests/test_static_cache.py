"""静态文件缓存：背景图/脚本带 ETag，浏览器再问时没变就回 304，不再每次重下几MB的4K背景。仅自编夹具，不碰用户数据。"""
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import unittest

from rpg import api, paths
from tests import test_subjects


class StaticCacheTests(unittest.TestCase):
    setUp = test_subjects.SubjectTest.setUp
    tearDown = test_subjects.SubjectTest.tearDown

    def get(self, name, etag=None):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request("http://127.0.0.1:%d/%s" % (srv.server_address[1], name))
            if etag:
                req.add_header("If-None-Match", etag)
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, r.headers, r.read()
            except urllib.error.HTTPError as e:
                with e:
                    return e.code, e.headers, e.read()
        finally:
            srv.shutdown()
            srv.server_close()

    def test_image_is_revalidated_with_304_instead_of_downloaded_again(self):
        paths.save_settings({"subject": "行测"})
        name = "assets/beauty/trial/hd/369/hall-day.webp"
        status, head, body = self.get(name)
        self.assertEqual(status, 200)
        self.assertGreater(len(body), 10000)
        self.assertEqual(head["Cache-Control"], "no-cache")
        tag = head["ETag"]
        self.assertTrue(tag)
        status, head2, body2 = self.get(name, tag)
        self.assertEqual((status, body2), (304, b""))
        self.assertEqual(head2["ETag"], tag)
        status, _, body3 = self.get(name, '"other-version"')
        self.assertEqual(status, 200)
        self.assertEqual(len(body3), len(body))

    def test_versioned_art_url_is_kept_by_the_browser_but_a_plain_one_is_asked_each_time(self):
        paths.save_settings({"subject": "行测"})
        name = "assets/beauty/trial/hd/369/hall-day.webp"
        self.assertEqual(self.get(name + "?v=123")[1]["Cache-Control"], "public, max-age=31536000, immutable")
        self.assertEqual(self.get(name)[1]["Cache-Control"], "no-cache")
        self.assertEqual(self.get("app.js?v=123")[1]["Cache-Control"], "no-cache", "脚本即使带版本号也每次问一下，更新后不会读到旧代码")

    def test_script_etag_follows_its_content_and_subject(self):
        paths.save_settings({"subject": "行测"})
        status, head, _ = self.get("app.js")
        self.assertEqual(status, 200)
        xc_tag = head["ETag"]
        self.assertEqual(self.get("app.js", xc_tag)[0], 304)
        paths.save_settings({"subject": "申论"})
        status, head, _ = self.get("app.js", xc_tag)
        self.assertEqual(status, 200, "申论换了措辞，行测的缓存不能拿来用")
        self.assertNotEqual(head["ETag"], xc_tag)

    def test_index_page_and_api_stay_uncached(self):
        paths.save_settings({"subject": "行测"})
        status, head, _ = self.get("index.html")
        tag = head["ETag"]
        self.assertEqual(self.get("index.html", tag)[0], 304)
        status, head, _ = self.get("api/dashboard")
        self.assertEqual(head["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
