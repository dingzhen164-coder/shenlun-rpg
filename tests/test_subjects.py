"""2.0.0：一个程序两个科目（行测 / 申论）——设置、找库、路径、规则别名、存档隔离、网页措辞改写。
全部在临时目录里跑，不碰真实数据和 ~/.shenlun-rpg、~/.xingce-rpg。"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import api, cards, config, mindmap, paths, store, subjects, wording  # noqa: E402


def make_vault(root, name, season=False):
    v = Path(root) / name
    (v / "copilot/skills/x").mkdir(parents=True)
    if season:
        (v / "FB模考试卷复盘/板块复盘/第1季").mkdir(parents=True)
    return v


class SubjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._keep = (paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR, paths.LEGACY_SETTINGS)
        paths.SETTINGS_DIR = paths._DEFAULT_SETTINGS_DIR = self.tmp / "home" / ".shenlun-rpg"      # 假的“本机设置”目录
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.LEGACY_SETTINGS = self.tmp / "home" / ".xingce-rpg" / "settings.json"
        self.xc = make_vault(self.tmp, "行测库", season=True)
        self.sl = make_vault(self.tmp, "申论库")
        for k in ("SHENLUN_SUBJECT", "XINGCE_VAULT", "SHENLUN_VAULT"):
            os.environ.pop(k, None)

    def tearDown(self):
        paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR, paths.LEGACY_SETTINGS = self._keep
        os.environ.pop("SHENLUN_SUBJECT", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------------------------------------------------------- 设置与找库
    def test_default_subject_and_switch(self):
        self.assertEqual(subjects.active(), "申论")
        paths.save_settings({"subject": "行测"})
        self.assertEqual(subjects.active(), "行测")
        paths.save_settings({"subject": "乱写"})
        self.assertEqual(subjects.active(), "申论")
        os.environ["SHENLUN_SUBJECT"] = "行测"        # 环境变量优先（测试用）
        self.assertEqual(subjects.active(), "行测")

    def test_old_single_vault_key_is_shenlun(self):
        paths.SETTINGS_DIR.mkdir(parents=True)
        paths.SETTINGS_FILE.write_text(json.dumps({"vault": str(self.sl), "api_key": "k"}), encoding="utf-8")
        self.assertEqual(paths.find_vault("申论"), self.sl.resolve())
        self.assertIsNone(paths.find_vault("行测"))
        paths.save_settings(paths.load_settings())     # 存回去：旧键并进 vaults，不再写 vault
        raw = json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))
        self.assertNotIn("vault", raw)
        self.assertEqual(raw["vaults"]["申论"], str(self.sl))

    def test_each_subject_has_own_vault(self):
        paths.save_settings({"vaults": {"行测": str(self.xc), "申论": str(self.sl)}})
        self.assertEqual(paths.find_vault("行测"), self.xc.resolve())
        self.assertEqual(paths.find_vault("申论"), self.sl.resolve())
        os.environ["SHENLUN_SUBJECT"] = "行测"
        self.assertEqual(paths.find_vault(), self.xc.resolve())
        os.environ["XINGCE_VAULT"] = str(self.tmp)       # 不像库的路径被忽略，回退到设置
        self.assertEqual(paths.find_vault(), self.xc.resolve())

    def test_guess_distinguishes_subjects(self):
        home = self.tmp / "h"
        shutil.copytree(self.xc, home / "Desktop" / "行测库")
        shutil.copytree(self.sl, home / "Desktop" / "申论库")
        self.assertEqual(paths.guess_vault(home, subject="行测").name, "行测库")
        self.assertEqual(paths.guess_vault(home, subject="申论").name, "申论库")

    def test_borrow_old_xingce_settings_once(self):
        paths.LEGACY_SETTINGS.parent.mkdir(parents=True)
        paths.LEGACY_SETTINGS.write_text(json.dumps({"api_key": "old-key", "model": "m1", "vault": str(self.xc)}), encoding="utf-8")
        s = paths.load_settings()
        self.assertEqual((s["api_key"], s["model"], s["vaults"]["行测"]), ("old-key", "m1", str(self.xc)))
        paths.save_settings({"api_key": "new-key", "vaults": {"申论": str(self.sl)}})
        s = paths.load_settings()
        self.assertEqual(s["api_key"], "new-key")             # 自己填过的优先
        self.assertEqual(s["vaults"]["行测"], str(self.xc))      # 缺的行测库仍借旧设置

    # ---------------------------------------------------------- 路径与默认文件
    def test_paths_per_subject(self):
        os.environ["SHENLUN_SUBJECT"] = "申论"
        ps = paths.Paths(self.sl)
        ps.ensure_train_dir()
        self.assertTrue((self.sl / "训练/采分点").is_dir() and (self.sl / "训练/作答").is_dir())
        self.assertFalse((self.sl / "训练/题库").exists())
        self.assertIn("晋升分数线", (self.sl / "训练/规则.md").read_text(encoding="utf-8"))
        self.assertFalse((self.sl / "训练/台词库·玄幻.md").exists())
        px = paths.Paths(self.xc, "行测")
        px.ensure_train_dir()
        self.assertTrue((self.xc / "训练/题库").is_dir())
        self.assertFalse((self.xc / "训练/采分点").exists())
        self.assertIn("渡劫分数线", (self.xc / "训练/规则.md").read_text(encoding="utf-8"))
        self.assertTrue((self.xc / "训练/台词库·玄幻.md").exists())
        self.assertEqual(px.ensure_train_dir(), [])         # 各自的文件版本互不干扰，第二次不升级
        self.assertEqual(ps.ensure_train_dir(), [])

    def test_shenlun_rule_names_map_to_standard_keys(self):
        r = config.Rules("- 晋升分数线: 61, 66\n- 专长得分率.归纳概括: 50, 55, 60, 65, 70, 75, 80, 85\n- 题型.测试: shenlun-xiaoti | 测试\n- 周例会.整改销号: 7", "申论")
        self.assertEqual(r.nums("渡劫分数线"), [61.0, 66.0])
        self.assertEqual(r.root_thresholds("归纳概括")[0], 0.5)
        self.assertIn("测试", r.boards)
        self.assertEqual(r.num("周常.斩心魔"), 7)
        rx = config.Rules("- 渡劫分数线: 62, 67", "行测")      # 行测的叫法照旧
        self.assertEqual(rx.nums("渡劫分数线"), [62.0, 67.0])
        self.assertEqual(list(config.Rules("", "申论").boards), ["归纳概括", "综合分析", "提出对策", "贯彻执行", "大作文"])
        self.assertIn("论证逻辑", config.Rules("", "行测").boards)

    def test_shipped_shenlun_rules_file_parses_to_known_keys(self):
        """随程序发的申论 规则.md 里每个键翻回标准键后都认识（不会因为写错名字被悄悄忽略）"""
        text = (paths.DEFAULTS_DIR / "申论" / "规则.md").read_text(encoding="utf-8")
        r = config.Rules(text, "申论")
        known = set(config.DEFAULT_RULES)
        bad = [k for k in r.raw if k not in known and not k.startswith(("板块.", "副线.", "灵根正确率.", "渡劫灵根.", "周常.")) and k != "配置版本"
               and not (k.startswith("第") and k.endswith("批"))]
        self.assertEqual(bad, [])

    # ---------------------------------------------------------- 存档隔离与迁移
    def test_old_shenlun_save_backed_up_but_xingce_save_kept(self):
        s_old = {"version": 1, "created": "2026-09-29", "xp": 500, "gates": [30]}
        for sub, vault, keep in (("申论", self.sl, False), ("行测", self.xc, True)):
            ps = paths.Paths(vault, sub)
            ps.ensure_train_dir()
            ps.save_file.write_text(json.dumps(s_old), encoding="utf-8")
            st = store.Store(ps).load(dt.date(2026, 10, 1))
            self.assertEqual(st["xp"], 500 if keep else 0, sub)
            self.assertEqual(st["theme"], "修仙" if sub == "行测" else "官场")
            self.assertEqual((vault / "训练/存档/存档-旧版.json").exists(), not keep)

    def test_saves_are_separate(self):
        paths.save_settings({"vaults": {"行测": str(self.xc), "申论": str(self.sl)}})
        os.environ["SHENLUN_SUBJECT"] = "行测"
        with api.open_game() as g:
            g.state["xp"] = 123
        os.environ["SHENLUN_SUBJECT"] = "申论"
        with api.open_game() as g:
            self.assertEqual(g.state["xp"], 0)
            self.assertEqual(g.subject, "申论")
            g.state["xp"] = 7
        os.environ["SHENLUN_SUBJECT"] = "行测"
        with api.open_game() as g:
            self.assertEqual((g.state["xp"], g.subject, g.theme), (123, "行测", "修仙"))

    def test_default_decks_and_mindmap_boards_per_subject(self):
        paths.save_settings({"vaults": {"行测": str(self.xc), "申论": str(self.sl)}})
        os.environ["SHENLUN_SUBJECT"] = "申论"
        with api.open_game() as g:
            c = cards.data(g)
            self.assertEqual(sorted(c["decks"]), sorted(cards.DEFAULT_DECKS_SHENLUN))
            # 1.0.0 的申论存档误建了行测的 12 个空便笺夹：清掉空的，不动已经有设置的
            c2 = g.state["cards"]
            c2["sl_clean"] = False
            for b in cards.DEFAULT_DECKS:
                c2["decks"].setdefault(b, {})
            c2["decks"]["常识判断"] = {"new_per_day": 5}
            cards.data(g)
            self.assertNotIn("论证逻辑", c2["decks"])
            self.assertIn("常识判断", c2["decks"])
        self.assertEqual(mindmap.default_boards()[0], "归纳概括")
        os.environ["SHENLUN_SUBJECT"] = "行测"
        with api.open_game() as g:
            self.assertEqual(sorted(cards.data(g)["decks"]), sorted(cards.DEFAULT_DECKS))
        self.assertEqual(mindmap.default_boards()[0], "政治理论")

    # ---------------------------------------------------------- 接口
    def test_api_subject_and_theme_rules(self):
        paths.save_settings({"vaults": {"行测": str(self.xc), "申论": str(self.sl)}})
        r = api.subject_get({})
        self.assertEqual(r["subject"], "申论")
        self.assertEqual([x["name"] for x in r["subjects"]], ["行测", "申论"])
        api.subject_set({"subject": "行测"})
        self.assertEqual(subjects.active(), "行测")
        with self.assertRaises(api.ApiError):
            api.subject_set({"subject": "不存在"})
        d = api.dashboard({})
        self.assertEqual((d["subject"], d["features"]["bank"], d["theme"]["name"]), ("行测", True, "修仙"))
        self.assertIsNotNone(d["tower"])
        api.theme_set({"theme": "玄幻"})                      # 行测可以切玄幻
        os.environ["SHENLUN_SUBJECT"] = "申论"
        with self.assertRaises(api.ApiError):
            api.theme_set({"theme": "玄幻"})                  # 申论只有官场
        d = api.dashboard({})
        self.assertEqual((d["subject"], d["features"]["grading"], d["theme"]["name"], d["tower"]), ("申论", True, "官场", None))
        self.assertEqual(d["theme"]["terms"]["brand"], "🏛 申论官途")

    def test_settings_vault_per_subject(self):
        os.environ["SHENLUN_SUBJECT"] = "申论"
        api.settings_set({"vault": str(self.xc), "vault_subject": "行测"})
        api.settings_set({"vault": str(self.sl)})                # 不写 vault_subject = 当前科目
        s = api.settings_get({})
        self.assertEqual(s["vaults"], {"行测": str(self.xc.resolve()), "申论": str(self.sl.resolve())})
        with self.assertRaises(api.ApiError):
            api.settings_set({"vault": str(self.tmp / "不是库")})

    def test_settings_shows_whether_each_vault_has_a_save(self):
        paths.save_settings({"vaults": {"行测": str(self.xc), "申论": str(self.sl)}})
        saves = api.settings_get({})["saves"]
        self.assertEqual((saves["行测"]["has"], saves["申论"]["has"]), (False, False))
        os.environ["SHENLUN_SUBJECT"] = "行测"
        with api.open_game() as g:
            g.state["xp"] = 1
        saves = api.settings_get({})["saves"]
        self.assertTrue(saves["行测"]["has"])
        self.assertEqual(saves["行测"]["date"], dt.date.today().isoformat())
        self.assertFalse(saves["申论"]["has"])

    def test_index_tells_page_its_subject_and_theme_class(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def get(name):
                return urllib.request.urlopen("http://127.0.0.1:%d/%s" % (srv.server_address[1], name)).read().decode("utf-8")
            paths.save_settings({"subject": "申论"})
            html = get("index.html")
            self.assertIn('window.SUBJECT0="申论"', html)
            self.assertIn("theme-gc", html)
            self.assertIn('<body class="guantu">', html)
            self.assertNotIn("三才时辰", get("app.js"))
            paths.save_settings({"subject": "行测"})
            html = get("index.html")
            self.assertIn('window.SUBJECT0="行测"', html)
            self.assertNotIn("theme-gc", html)
            self.assertIn("三才时辰", get("app.js"))          # 行测的页面一个字不改
        finally:
            srv.shutdown()
            srv.server_close()

    def test_guanchang_page_color_does_not_cover_background_image(self):
        """回归：申论的页面底色规则优先级高过“选了背景图时 body 透明”，背景图就看不见了（2.2.2 修）"""
        css = (paths.WEB_DIR / "style.css").read_text(encoding="utf-8")
        self.assertIn("html.theme-gc body.has-bg { background: transparent; }", css)
        self.assertLess(css.index("html.theme-gc, html.theme-gc body { background: var(--bg); }"),
                        css.index("html.theme-gc body.has-bg { background: transparent; }"))

    # ---------------------------------------------------------- 措辞改写
    def test_wording_only_in_shenlun_web_files(self):
        raw = "每日修炼 · 斩心魔 · 玉简 · 行测板块".encode("utf-8")
        self.assertEqual(wording.web("app.js", raw, "行测"), raw)
        self.assertEqual(wording.web("app.js", raw, "申论").decode("utf-8"), "每日办理 · 整改销号 · 便笺 · 申论题型")
        self.assertEqual(wording.web("vendor/big.js", raw, "申论"), raw)      # 第三方库不动
        self.assertEqual(wording.web("icons/a.png", raw, "申论"), raw)
        self.assertEqual(wording.web("app.js", "[\"review\", \"温\", \"复习\", \"温养\"".encode("utf-8"), "申论").decode("utf-8"),
                         "[\"review\", \"复\", \"复习\", \"复核\"")


if __name__ == "__main__":
    unittest.main()
