"""自考（纸质卷计时 + 预设分值录分）与宗门大比各板块用时求和测试。"""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import api, config, engine, mock, paper_exam, paths, store


class PaperExamAndBoardTimeTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        for ctx in (
            patch.object(Path, "home", return_value=self.root / "home"),
            patch.dict(os.environ, {"SHENLUN_SUBJECT": "行测"}),
            patch.object(paths, "SETTINGS_DIR", self.root / "settings"),
            patch.object(paths, "SETTINGS_FILE", self.root / "settings/settings.json"),
        ):
            ctx.start()
            self.addCleanup(ctx.stop)
        self.p = paths.Paths(self.root / "vault", "行测")
        self.p.ensure_train_dir()
        (self.p.vault / "copilot/skills/test").mkdir(parents=True)
        paths.save_settings({"subject": "行测", "vaults": {"行测": str(self.p.vault)}})
        self.g = engine.Game(
            self.p,
            config.Rules(),
            config.Persona(),
            config.Lines(),
            store.new_state(dt.date(2026, 10, 18)),
            dt.date(2026, 10, 18),
        )

    def test_builtin_and_custom_presets_reorder_and_validation(self):
        v = paper_exam.view(self.g)
        by_id = {p["id"]: p for p in v["presets"]}
        self.assertEqual(by_id["guokao_130"]["total_questions"], 130)
        self.assertEqual(by_id["guokao_130"]["full_score"], 100.0)
        self.assertEqual(by_id["sc_gz_100"]["total_questions"], 100)
        self.assertEqual(by_id["sc_gz_100"]["full_score"], 100.0)
        self.assertFalse(v["show_digital"])

        # 调整做题顺序（如先做资料分析）
        sc_secs = list(by_id["sc_gz_100"]["sections"])
        sc_secs = [sc_secs[-1]] + sc_secs[:-1]
        v2 = paper_exam.save_prefs(self.g, {"action": "reorder", "preset_id": "sc_gz_100", "sections": sc_secs})
        self.assertEqual(v2["active_preset"], "sc_gz_100")
        p_sc = next(p for p in v2["presets"] if p["id"] == "sc_gz_100")
        self.assertTrue(p_sc["overridden"])
        self.assertEqual(p_sc["sections"][0]["name"], "资料分析")

        # 另存为自定义 150 分省考预设
        v3 = paper_exam.save_prefs(
            self.g,
            {
                "action": "save_preset",
                "name": "贵州150分制自测",
                "as_new": True,
                "sections": [
                    {"name": "言语理解", "module": "言语理解", "total": 30, "points": "1.5", "target_minutes": 30},
                    {"name": "判断推理", "module": "判断推理", "total": 30, "points": "1.5", "target_minutes": 30},
                    {"name": "资料分析", "module": "资料分析", "total": 20, "points": "1.5", "target_minutes": 25},
                    {"name": "常识与政治", "module": "常识判断", "total": 20, "points": "1.5", "target_minutes": 15},
                ],
            },
        )
        custom_id = v3["active_preset"]
        self.assertTrue(custom_id.startswith("custom_"))
        p_gz = next(p for p in v3["presets"] if p["id"] == custom_id)
        self.assertEqual(p_gz["full_score"], 150.0)

        # 删除自定义预设
        v4 = paper_exam.save_prefs(self.g, {"action": "delete_preset", "preset_id": custom_id})
        self.assertFalse(any(p["id"] == custom_id for p in v4["presets"]))

    def test_save_edit_delete_paper_exam_and_mock_integration(self):
        v = paper_exam.view(self.g)
        guokao = next(p for p in v["presets"] if p["id"] == "guokao_130")
        # 构造对题、错题与每块用时：政治16对4错(8分)、常识10对5错(5分)、言语24对6错(19.2分)、
        # 图推8对2错(6.4分)、定义8对2错(6.4分)、类比4对1错(3.2分)、逻辑8对2错(6.8分)、数量5对3错2空(5分)、资料18对2错(18分)
        # 合计 = 8 + 5 + 19.2 + 6.4 + 6.4 + 3.2 + 6.8 + 5 + 18 = 78.0 分
        answers = {
            "政治理论": (16, 4, 720),
            "常识判断": (10, 5, 480),
            "言语理解": (24, 6, 1800),
            "图形推理": (8, 2, 540),
            "定义判断": (8, 2, 600),
            "类比推理": (4, 1, 240),
            "逻辑判断": (8, 2, 720),
            "数量关系": (5, 3, 600),
            "资料分析": (18, 2, 1500),
        }
        secs_payload = []
        for s in guokao["sections"]:
            ok, wrong, sec = answers[s["name"]]
            secs_payload.append(dict(s, ok=ok, wrong=wrong, seconds=sec))

        res = paper_exam.save_exam(
            self.g,
            {
                "name": "2025四川省考纸质卷一",
                "date": "2026-10-18",
                "preset_id": "guokao_130",
                "preset_name": guokao["name"],
                "sections": secs_payload,
            },
        )
        season = res["season"]
        self.assertGreater(season, 2000)
        self.assertEqual(res["score"], 78.0)

        # 验证已进入宗门大比考情与战绩，但不生成逐题复盘列表
        sm = res["summary"]
        self.assertEqual(sm["overall"]["count"], 1)
        self.assertEqual(sm["overall"]["latest"], 78.0)
        s_item = sm["seasons"][0]
        self.assertTrue(s_item["paper_exam"])
        self.assertEqual(s_item["review"], [])
        self.assertEqual(s_item["ok"], 101)
        self.assertEqual(s_item["total"], 130)
        self.assertEqual(s_item["minutes"], 120.0)
        judge_mod = next(m for m in s_item["modules"] if m["name"] == "判断推理")
        self.assertEqual(judge_mod["score"], 22.8)
        self.assertEqual(judge_mod["minutes"], 35.0)
        self.assertEqual(len(judge_mod["boards"]), 4)

        # 再次修改同一场自考：更新分数与名称，但不重复发放录分修为或历练时长
        xp_before = self.g.state["xp"]
        prac_count_before = len(self.g.state["practice"])
        secs_payload[-1]["ok"] = 19
        secs_payload[-1]["wrong"] = 1
        res2 = paper_exam.save_exam(
            self.g,
            {
                "season": season,
                "name": "2025四川省考纸质卷一（订正）",
                "date": "2026-10-18",
                "sections": secs_payload,
            },
        )
        self.assertEqual(res2["score"], 79.0)
        self.assertEqual(self.g.state["xp"], xp_before)
        self.assertEqual(len(self.g.state["practice"]), prac_count_before)
        self.assertEqual(self.g.state["boss"][-1]["score"], 79.0)
        self.assertEqual(self.g.state["boss"][-1]["name"], "2025四川省考纸质卷一（订正）")

        # 校验对题+错题超总题数报错
        bad_secs = [dict(x) for x in secs_payload]
        bad_secs[0]["ok"] = 18
        bad_secs[0]["wrong"] = 5
        with self.assertRaises(paper_exam.PaperExamError):
            paper_exam.save_exam(self.g, {"name": "错卷", "sections": bad_secs})

        # 删除自考记录：从考情与战绩移出
        del_res = paper_exam.delete_exam(self.g, {"season": season})
        self.assertEqual(del_res["summary"]["overall"]["count"], 0)
        self.assertEqual(self.g.state["boss"], [])

    def test_mock_summary_sums_per_question_seconds_by_board_and_module(self):
        folder = self.p.train / "模考复盘/第12季"
        folder.mkdir(parents=True, exist_ok=True)
        # 资料分析 2 题：写在 .md 里各 75 秒、45 秒 → 合计 120 秒 = 2.0 分钟
        (folder / "01-资料分析.md").write_text(
            "### 1. ✅\n题目一\n> 正确答案：**A**　我的答案：**A**\n> 用时：**75秒**\n---\n"
            "### 2. ❌\n题目二\n> 正确答案：**B**　我的答案：**C**\n> 用时：**45秒**\n---\n",
            encoding="utf-8",
        )
        # 图形推理 2 题 + 定义判断 1 题：来自 exam.qtimes 与 html_import.question_seconds → 合计 90+60+30 = 180 秒 = 3.0 分钟
        (folder / "02-图形推理.md").write_text(
            "### 3. ✅\n题目三\n> 正确答案：**A**　我的答案：**A**\n---\n"
            "### 4. ✅\n题目四\n> 正确答案：**D**　我的答案：**D**\n---\n",
            encoding="utf-8",
        )
        (folder / "03-定义判断.md").write_text(
            "### 5. ❌\n题目五\n> 正确答案：**C**　我的答案：**A**\n---\n",
            encoding="utf-8",
        )
        self.g.state.setdefault("mocks", {})["12"] = {
            "exam": {"qtimes": {"3": 90, "4": 60}},
            "html_import": {"question_seconds": {"5": 30}},
        }
        s = mock.summary(self.g)["seasons"][0]
        self.assertEqual(s["minutes"], 5.0)
        rv_by_board = {r["board"]: r for r in s["review"]}
        self.assertEqual(rv_by_board["资料分析"]["seconds"], 120)
        self.assertEqual(rv_by_board["资料分析"]["minutes"], 2.0)
        self.assertEqual(rv_by_board["图形推理"]["minutes"], 2.5)
        self.assertEqual(rv_by_board["定义判断"]["minutes"], 0.5)

        mod_by_name = {m["name"]: m for m in s["modules"]}
        self.assertEqual(mod_by_name["资料分析"]["minutes"], 2.0)
        self.assertTrue(mod_by_name["资料分析"]["minutes_auto"])
        self.assertEqual(mod_by_name["判断推理"]["minutes"], 3.0)
        sub_by_board = {b["board"]: b for b in mod_by_name["判断推理"]["boards"]}
        self.assertEqual(sub_by_board["图形推理"]["minutes"], 2.5)
        self.assertEqual(sub_by_board["定义判断"]["minutes"], 0.5)

    def test_api_endpoints_roundtrip(self):
        v = api.paper_exam_view({})
        self.assertEqual(v["active_preset"], "guokao_130")
        secs = [dict(s, ok=s["total"], wrong=0, seconds=300) for s in v["presets"][0]["sections"]]
        saved = api.paper_exam_save({"name": "API自测满分卷", "date": "2026-10-18", "sections": secs})
        self.assertEqual(saved["score"], 100.0)
        deleted = api.paper_exam_delete({"season": saved["season"]})
        self.assertTrue(deleted["ok"])


if __name__ == "__main__":
    unittest.main()
