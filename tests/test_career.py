"""2.2.0 申论仕途：职务履历（单位 / 岗位 / 职级 / 直属领导）、导师随阶段切换、选调生加成、便笺只留五个题型。"""
import datetime as dt
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import api, career, cards, config, engine, paths, store, themes  # noqa: E402


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "申论"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


def make_game(state=None, rules_text="", career_text=None):
    p = paths.Paths(None, "申论")
    st = state or store.new_state(dt.date(2026, 10, 9), "申论")
    rules, persona, lines = config.load_all(p, "官场")
    rules = config.Rules(rules_text, "申论")
    g = engine.Game(p, rules, persona, lines, st, dt.date(2026, 10, 9))
    if career_text is not None:
        g.career = career.Career(career_text)
        g._apply_career()
    return g


class CareerFileTest(unittest.TestCase):
    def test_default_file_has_eight_bands_with_three_posts(self):
        c = career.Career("")
        self.assertEqual(len(c.bands), 8)
        self.assertTrue(all(len(b["stages"]) == 3 for b in c.bands[:-1]))
        self.assertEqual(len(c.bands[-1]["stages"]), 1)
        self.assertEqual(c.bands[0]["stages"][0]["rank"], "四级主任科员")          # 研究生选调生的起点
        self.assertEqual(c.describe(80)["level"], "副国级")
        self.assertEqual(c.describe(85)["level"], "正国级")

    def test_stage_by_score(self):
        c = career.Career("")
        self.assertEqual([c.stage(s) for s in (50, 51, 52, 53, 54, 55, 59, 60)], [(0, 0), (0, 0), (0, 1), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0)])
        self.assertEqual(c.stage(200), (7, 0))                         # 最后一段只有一个岗位
        d = c.describe(54)
        self.assertEqual((d["post"], d["rank"], d["level"]), ("镇党政办主任", "二级主任科员", "正科级"))
        self.assertEqual(c.describe(70)["leader"]["title"], "部长")

    def test_no_rank_above_vice_minister(self):
        d = career.Career("").describe(72)                             # 副部长：没有职级，只写领导职务层次
        self.assertEqual(d["rank"], "")
        self.assertEqual(d["label"], "副部长（副部级）")

    def test_broken_file_falls_back_to_default(self):
        self.assertEqual(len(career.Career("乱写一通").bands), 8)
        self.assertEqual(len(career.Career("## 只有一段 | 50-54\n单位: 某地\n- 岗位 | 职级 | 层次").bands), 8)

    def test_user_can_edit_file(self):
        text = "".join(f"## 段{i} | {50 + 5 * i}-{54 + 5 * i}\n单位: 单位{i}\n背景: 故事{i}\n领导: 王{i}长 | 局长 | 正处级 | 简称: 王局 | 称呼: 小李 | 性格: 严格。\n"
                       f"- 岗A{i} | 一级科员 | 科员级\n- 岗B{i} | 二级科员 | 科员级\n- 岗C{i} | 办事员 | 科员级\n" for i in range(3))
        c = career.Career(text)
        self.assertEqual(len(c.bands), 3)
        self.assertEqual(c.describe(52)["post"], "岗B0")
        patch = career.persona_patch(c.describe(52))
        self.assertEqual((patch["导师名"], patch["称呼"]), ("王局", "小李"))
        self.assertIn("严格", patch["导师人设"])


class CareerEngineTest(unittest.TestCase):
    def test_start_is_town_government_with_party_secretary_as_tutor(self):
        g = make_game()
        info = g.realm_info()
        self.assertEqual(info["name"], "镇长助理（四级主任科员）")
        self.assertEqual(info["big_name"], "乡镇政府")
        self.assertEqual(g.persona["导师名"], "周书记")
        d = g.dashboard()
        self.assertEqual(d["career"]["leader"]["name"], "周静宜")
        self.assertEqual(d["career"]["level"], "副科级")

    def test_tutor_changes_with_stage(self):
        st = store.new_state(dt.date(2026, 10, 9), "申论")
        st.update(claimed=60, xp=10 ** 6, gates=[60])          # 政绩够了、60 分那道晋升考核也过了、已经点了晋升
        g = make_game(st)
        self.assertEqual(g.persona["导师名"], "林书记")
        self.assertIn("检察", g.persona["导师人设"])
        self.assertEqual(g.career_info()["post"], "副检察长")

    def test_gate_labels_use_unit_names(self):
        g = make_game()
        self.assertEqual([g.gate_label(x) for x in g.gates()], ["地市检察院", "省公安厅", "国家部委", "正部级岗位", "副国级岗位", "正国级岗位"])

    def test_bands_only_change_for_guanchang(self):
        self.assertEqual(themes.sub_stage(52, "官场")[2:], (52, 54))
        self.assertEqual(themes.sub_stage(52)[2:], (52, 53))            # 行测（修仙）：炼气每分一层，一点没变
        self.assertEqual(themes.band_of(55, "官场")[0], 1)
        self.assertEqual(themes.band_of(55)[0], 1)

    def test_xuandiao_bonus_only_before_threshold(self):
        # 点拨概率设成 0：领导点拨（随机额外政绩）会让数目不确定
        g = make_game(rules_text="- 点拨概率: 0\n- 选调生加成: 0.5\n- 选调生加成分数线: 60")
        gain = g._award(100, "grade", "归纳概括", "q1", True, "x", bonus=True)
        self.assertEqual(g.state["xp"], 150)
        g2 = make_game(rules_text="- 点拨概率: 0\n- 选调生加成: 0")
        g2._award(100, "grade", "归纳概括", "q1", True, "x", bonus=True)
        self.assertEqual(g2.state["xp"], 100)
        g3 = make_game(rules_text="- 点拨概率: 0\n- 选调生加成: 0.5\n- 选调生加成分数线: 40")
        g3._award(100, "grade", "归纳概括", "q1", True, "x", bonus=True)
        self.assertEqual(g3.state["xp"], 100)                           # 综合评价已经不低于分数线

    def test_xingce_is_untouched(self):
        p = paths.Paths(None, "行测")
        st = store.new_state(dt.date(2026, 10, 9), "行测")
        rules, persona, lines = config.load_all(p, "修仙")
        g = engine.Game(p, rules, persona, lines, st, dt.date(2026, 10, 9))
        self.assertIsNone(g.career)
        self.assertEqual(g.realm_info()["name"], "凡人 · 未入道")
        self.assertEqual(g.persona["导师名"], "劭神韵")
        self.assertIsNone(g.dashboard()["career"])


class FilesAndDecksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._keep = (paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR)
        paths.SETTINGS_DIR = paths._DEFAULT_SETTINGS_DIR = self.tmp / "h"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        v = self.tmp / "申论库"
        (v / "copilot/skills/x").mkdir(parents=True)
        paths.save_settings({"vaults": {"申论": str(v)}})
        self.vault = v

    def tearDown(self):
        paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths._DEFAULT_SETTINGS_DIR = self._keep
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_career_file_is_installed_and_edits_apply(self):
        with api.open_game() as g:
            self.assertEqual(g.career_info()["post"], "镇长助理")
        f = self.vault / "训练/职务履历.md"
        self.assertTrue(f.exists())
        f.write_text(f.read_text(encoding="utf-8").replace("镇长助理 | 四级主任科员", "选调生 | 四级主任科员"), encoding="utf-8")
        with api.open_game() as g:
            self.assertEqual(g.career_info()["post"], "选调生")
        self.assertEqual(api.dashboard({})["career"]["post"], "选调生")

    def test_only_five_decks_and_news_goes_to_comprehensive_analysis(self):
        with api.open_game() as g:
            self.assertEqual(sorted(cards.data(g)["decks"]), sorted(["归纳概括", "综合分析", "提出对策", "贯彻执行", "大作文"]))
            self.assertEqual(g.news_board(), "综合分析")
            c = g.state["cards"]
            c["sl_clean"] = 1
            c["decks"]["政治理论"] = {}                                   # 旧存档里空的政治理论夹子：清掉
            c["decks"]["提出对策"] = {"new_per_day": 3}
            cards.data(g)
            self.assertNotIn("政治理论", c["decks"])
            self.assertEqual(c["decks"]["提出对策"], {"new_per_day": 3})


if __name__ == "__main__":
    unittest.main()
