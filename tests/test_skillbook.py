"""藏经阁·心法（3.5.3）：每板块一份初始为空的专属心法；随时修改（保存即生效）、历史回滚、版本冲突；
导入 .skill / .zip / .md；心法总诀；讲题读取（SKILL.md 在前、references 仅查阅、调度节不读、总量上限）。
全程隔离假 HOME / 假库，不碰真实资料。"""
import base64
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from rpg import api, paths, skillbook, trainer

BOARD = "论证逻辑"                       # 行测默认板块表里的板块
OTHER = "逻辑填空"


def package(files, top="pkg", extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for rel, text in files.items():
            z.writestr((top + "/" if top else "") + rel, text)
        for rel, data in (extra or {}).items():
            z.writestr(rel, data)
    return buf.getvalue()


class SkillbookTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for ctx in (patch.object(Path, "home", return_value=self.root / "home"),
                    patch.dict(os.environ, {"SHENLUN_SUBJECT": "行测"}),
                    patch.object(paths, "SETTINGS_DIR", self.root / "home" / ".shenlun-rpg"),
                    patch.object(paths, "SETTINGS_FILE", self.root / "home" / ".shenlun-rpg" / "settings.json")):
            ctx.start()
            self.addCleanup(ctx.stop)
        self.p = paths.Paths(self.root / "vault", "行测")
        (self.p.vault / "copilot/skills").mkdir(parents=True)
        self.p.ensure_train_dir()
        paths.save_settings({"subject": "行测", "vaults": {"行测": str(self.p.vault)}})
        self.p = paths.Paths(self.p.vault, "行测")

    def put(self, rel="SKILL.md", text="# 入口\n先识别，再排除。", board=BOARD):
        return skillbook.save(self.p, board, rel, text, "")

    # ---- 初始为空
    def test_every_board_starts_empty_and_old_vault_skill_is_not_read(self):
        src = self.p.vault / "copilot/skills" / "xue-rui-argument-logic"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# 库里的老 skill", encoding="utf-8")
        view = api.skillbook_view({})["boards"]
        self.assertTrue(len(view) >= 10)
        self.assertTrue(all(b["n_files"] == 0 and b["files"] == [] for b in view))
        self.assertEqual(set(view[0]), {"board", "n_files", "files"})             # 没有 mode / source / pending 之类
        self.assertIsNone(skillbook.tutor_material(self.p, BOARD))
        with api.open_game(save=False) as g:
            self.assertEqual(trainer._tutor_material(g, BOARD), ("", []))          # 库里的原 skill 不再自动读取

    def test_other_boards_unaffected_by_one_boards_edit(self):
        self.put()
        self.assertEqual(skillbook.own_files(self.p, OTHER), [])
        self.assertIsNone(skillbook.tutor_material(self.p, OTHER))

    # ---- 读取
    def test_reading_order_skill_first_references_only_for_lookup_and_dispatch_hidden(self):
        self.put("SKILL.md", "# 入口\n先识别。\n\n## 被 xingce-jiexi-all 调度时\n运行 jiexi.py\n### 流程\n步骤\n\n## 后记\n保留这段")
        self.put("心法/01-分类.md", "分类内容")
        self.put("cheatsheet.md", "速查内容")
        self.put("references/大资料.md", "资料内容" * 50)
        self.put("学习版/01-建立联系.md", "学习版内容")
        self.put("学习版/例题精讲/01-电梯.md", "精讲内容")
        text, used = skillbook.tutor_material(self.p, BOARD)
        self.assertEqual(used, ["SKILL.md", "cheatsheet.md", "心法/01-分类.md"])
        self.assertTrue(text.index("先识别") < text.index("速查内容") < text.index("分类内容"))
        self.assertIn("保留这段", text)
        self.assertNotIn("jiexi.py", text)
        self.assertNotIn("资料内容", text)
        self.assertNotIn("学习版内容", text)                                              # 学习版只供阅读，不自动读入讲题
        self.assertNotIn("精讲内容", text)
        plan = skillbook.plan(self.p, BOARD)
        ref = next(i for i in plan["items"] if i["rel"] == "references/大资料.md")
        self.assertEqual((ref["kind"], ref["read"]), ("ref", False))
        study = {i["rel"]: i for i in plan["items"] if i["rel"].startswith("学习版/")}
        self.assertEqual({v["kind"] for v in study.values()}, {"ref"})
        self.assertEqual(len(study), 2)

    def test_history_folder_and_hidden_files_are_never_read(self):
        f = self.put()
        skillbook.save(self.p, BOARD, "SKILL.md", "新入口", f["rev"])
        self.assertNotIn("先识别，再排除", skillbook.tutor_material(self.p, BOARD)[0])
        (skillbook.board_dir(self.p, BOARD) / ".隐藏.md").write_text("不读", encoding="utf-8")
        self.assertTrue(all(not x.startswith(".") for x in skillbook.own_files(self.p, BOARD)))

    def test_over_budget_files_are_listed_as_not_read(self):
        self.put("SKILL.md", "入口" * 5)
        self.put("a.md", "字" * 30)
        with patch.object(skillbook, "TUTOR_LIMIT", 20):
            plan = skillbook.reading_plan(self.p, BOARD)
            text, used = skillbook.tutor_material(self.p, BOARD)
        self.assertTrue(plan["total"] <= 20)
        self.assertTrue(any(u.endswith("（未读入：超出上限）") for u in used))
        self.assertEqual(len(text), len(plan["text"]))

    # ---- 保存、冲突、历史
    def test_edit_takes_effect_for_the_next_tutoring(self):
        self.put()
        f = skillbook.read_file(self.p, BOARD, "SKILL.md")
        self.assertTrue(f["editable"])
        skillbook.save(self.p, BOARD, "SKILL.md", "# 入口\n我新写的方法", f["rev"])
        text, used = skillbook.tutor_material(self.p, BOARD)
        self.assertIn("我新写的方法", text)
        self.assertNotIn("先识别", text)

    def test_conflict_does_not_overwrite(self):
        rev = self.put()["rev"]
        skillbook.save(self.p, BOARD, "SKILL.md", "甲改", rev)
        with self.assertRaises(skillbook.SkillError) as c:
            skillbook.save(self.p, BOARD, "SKILL.md", "乙改（还拿着旧版本号）", rev)
        self.assertTrue(c.exception.conflict)
        self.assertEqual(skillbook.read_file(self.p, BOARD, "SKILL.md")["text"], "甲改")
        with self.assertRaises(skillbook.SkillError):
            skillbook.save(self.p, BOARD, "新文件.md", "x", "带着版本号新建")

    def test_history_and_restore(self):
        rev = self.put()["rev"]
        r = skillbook.save(self.p, BOARD, "SKILL.md", "第二版", rev)
        self.assertTrue(r["changed"])
        self.assertFalse(skillbook.save(self.p, BOARD, "SKILL.md", "第二版", r["rev"])["changed"])   # 没变化不留历史
        versions = skillbook.history(self.p, BOARD, "SKILL.md")
        self.assertEqual(len(versions), 1)
        self.assertEqual(skillbook.history_text(self.p, BOARD, "SKILL.md", versions[0]["id"]), "# 入口\n先识别，再排除。")
        skillbook.restore(self.p, BOARD, "SKILL.md", versions[0]["id"], r["rev"])
        self.assertIn("先识别", skillbook.read_file(self.p, BOARD, "SKILL.md")["text"])
        self.assertEqual(len(skillbook.history(self.p, BOARD, "SKILL.md")), 2)          # 回滚前的“第二版”也留着

    def test_delete_and_rename_keep_history(self):
        rev = self.put("cheatsheet.md", "口诀")["rev"]
        r = skillbook.rename(self.p, BOARD, "cheatsheet.md", "05-速查.md", rev)
        self.assertEqual(r["path"], "05-速查.md")
        self.assertNotIn("cheatsheet.md", skillbook.own_files(self.p, BOARD))
        self.assertEqual(len(skillbook.history(self.p, BOARD, "cheatsheet.md")), 1)
        skillbook.delete(self.p, BOARD, "05-速查.md", r["rev"])
        vid = skillbook.history(self.p, BOARD, "05-速查.md")[0]["id"]
        skillbook.restore(self.p, BOARD, "05-速查.md", vid, "")
        self.assertIn("05-速查.md", skillbook.own_files(self.p, BOARD))
        s = self.put()
        with self.assertRaises(skillbook.SkillError):
            skillbook.rename(self.p, BOARD, "SKILL.md", "入口.md", s["rev"])

    # ---- 安全与上限
    def test_bad_paths_are_rejected(self):
        for bad in ("../x.md", "/etc/passwd.md", "a/../../b.md", "SKILL.txt", ".hidden.md", "a/b/c/d.md", "", "a//b.md", "x:y.md"):
            with self.assertRaises(skillbook.SkillError, msg=bad):
                skillbook.save(self.p, BOARD, bad, "x", "")
        for bad in ("", "..", ".历史", "a/b", "a\\b"):
            with self.assertRaises(skillbook.SkillError, msg=bad):
                skillbook.board_dir(self.p, bad)

    def test_size_limits(self):
        with self.assertRaises(skillbook.SkillError):
            skillbook.save(self.p, BOARD, "big.md", "字" * (skillbook.MAX_FILE + 1), "")
        with patch.object(skillbook, "MAX_FILES", 2):
            self.put("a.md", "x"); self.put("b.md", "x")
            with self.assertRaises(skillbook.SkillError):
                skillbook.save(self.p, BOARD, "n1.md", "x", "")

    def test_word_count_is_like_a_word_processor(self):
        self.assertEqual(skillbook.words("形式逻辑 A→B, $\\neg$ ab12 **粗**"), 9)
        self.assertEqual(skillbook.title_of("---\nx: y\n---\n# 第一章 基础\n正文"), "第一章 基础")
        self.assertEqual(skillbook.title_of("没有标题"), "")

    # ---- 导入
    def test_import_skill_package_strips_top_folder_skips_non_md_and_macos_junk(self):
        raw = package({"SKILL.md": "# 入口\n先看流程", "心法/00-总流程.md": "# 总流程", "references/a.md": "# 资料",
                       "agents/openai.yaml": "x: 1", "references/回测.json": "{}"},
                      extra={"__MACOSX/pkg/._SKILL.md": b"junk", "pkg/.DS_Store": b"x"})
        r = skillbook.import_package(self.p, BOARD, "xuerui.skill", raw)
        self.assertEqual(r["added"], ["SKILL.md", "references/a.md", "心法/00-总流程.md"])
        self.assertEqual((r["overwritten"], r["same"]), ([], []))
        self.assertEqual(sorted(x[0] for x in r["skipped"]), ["agents/openai.yaml", "references/回测.json"])
        self.assertEqual(skillbook.own_files(self.p, BOARD), ["SKILL.md", "references/a.md", "心法/00-总流程.md"])
        self.assertIn("先看流程", skillbook.tutor_material(self.p, BOARD)[0])

    def test_import_without_top_folder_and_overwrite_keeps_history_and_other_files(self):
        self.put("SKILL.md", "旧入口")
        self.put("我自己的.md", "自己写的")
        raw = package({"SKILL.md": "新入口", "新.md": "新文件"}, top="")
        r = skillbook.import_package(self.p, BOARD, "x.zip", raw)
        self.assertEqual((r["added"], r["overwritten"]), (["新.md"], ["SKILL.md"]))
        self.assertEqual(skillbook.read_file(self.p, BOARD, "SKILL.md")["text"], "新入口")
        self.assertEqual(skillbook.read_file(self.p, BOARD, "我自己的.md")["text"], "自己写的")      # 其余文件不动
        vid = skillbook.history(self.p, BOARD, "SKILL.md")[0]["id"]
        self.assertEqual(skillbook.history_text(self.p, BOARD, "SKILL.md", vid), "旧入口")          # 覆盖前的内容在历史里
        again = skillbook.import_package(self.p, BOARD, "x.zip", raw)
        self.assertEqual((again["added"], again["overwritten"], sorted(again["same"])), ([], [], ["SKILL.md", "新.md"]))

    def test_import_single_md_and_rejections(self):
        r = skillbook.import_package(self.p, BOARD, "我的方法.md", "# 方法\n正文".encode("utf-8"))
        self.assertEqual(r["added"], ["我的方法.md"])
        for name, raw, why in (("a.skill", b"not a zip", "压缩包"), ("a.zip", b"PK\x03\x04broken", "损坏"),
                               ("a.skill", package({"x.json": "{}"}), "没有可以导入"),
                               ("a.exe", b"MZ", "压缩包")):
            with self.assertRaises(skillbook.SkillError, msg=name) as c:
                skillbook.import_package(self.p, BOARD, name, raw)
            self.assertIn(why, str(c.exception))

    def test_import_blocks_path_escape_too_deep_too_long_and_too_many(self):
        raw = package({"../escape.md": "x", "a/b/c/d.md": "太深", "ok.md": "好", "长.md": "字" * (skillbook.MAX_FILE + 1)}, top="")
        r = skillbook.import_package(self.p, BOARD, "x.skill", raw)
        self.assertEqual(r["added"], ["ok.md"])
        self.assertEqual(len(r["skipped"]), 3)
        self.assertFalse((self.p.train / "技能" / "escape.md").exists())
        with patch.object(skillbook, "MAX_FILES", 2):
            with self.assertRaises(skillbook.SkillError):
                skillbook.import_package(self.p, BOARD, "y.skill", package({"1.md": "x", "2.md": "x"}, top=""))

    def test_api_import_base64_and_unknown_board(self):
        raw = package({"SKILL.md": "# 入口\n导入的内容"})
        r = api.skillbook_import({"board": BOARD, "name": "a.skill", "data": "data:application/zip;base64," + base64.b64encode(raw).decode()})
        self.assertEqual(r["added"], ["SKILL.md"])
        with api.open_game(save=False) as g:
            self.assertIn("导入的内容", trainer._tutor_material(g, BOARD)[0])
            self.assertTrue(g.has_skill(BOARD))
        with self.assertRaises(api.ApiError):
            api.skillbook_import({"board": "不存在的板块", "name": "a.skill", "data": base64.b64encode(raw).decode()})
        with self.assertRaises(api.ApiError):
            api.skillbook_import({"board": BOARD, "name": "a.skill", "data": "%%%不是base64"})

    # ---- 接口：直接修改、没有旧功能
    def test_api_create_save_history_and_removed_features(self):
        api.skillbook_create({"board": BOARD, "path": "SKILL.md", "text": "# 入口\n新的识别法"})
        f = api.skillbook_file({"board": BOARD, "path": "SKILL.md"})
        api.skillbook_save({"board": BOARD, "path": "SKILL.md", "text": "# 入口\n改过了", "base": f["rev"]})
        self.assertEqual(len(api.skillbook_history({"board": BOARD, "path": "SKILL.md"})["versions"]), 1)
        with self.assertRaises(api.ApiError):
            api.skillbook_save({"board": BOARD, "path": "SKILL.md", "text": "旧版本号再保存", "base": f["rev"]})
        with self.assertRaises(api.ApiError):
            api.skillbook_file({"board": "不存在的板块", "path": "SKILL.md"})
        plan = api.skillbook_plan({"board": BOARD})
        self.assertEqual(plan["limit"], skillbook.TUTOR_LIMIT)
        for gone in ("skillbook_organize", "skillbook_accept", "skillbook_dismiss", "skillbook_proposals", "distill_state", "distill_step"):
            self.assertFalse(hasattr(api, gone), gone)
        routes = {p for _, p in api.ROUTES}
        self.assertFalse(any(r.startswith("/api/distill/") or r in ("/api/skillbook/organize", "/api/skillbook/accept") for r in routes))
        for needed in ("/api/skillbook/import", "/api/skillbook/zongjue"):
            self.assertIn(needed, routes)

    # ---- 心法总诀
    def test_zongjue_has_the_five_files_readable_and_in_sync(self):
        lst = api.skillbook_zongjue({})["files"]
        self.assertEqual([x["file"] for x in lst], ["蒸馏-第一步-提取例题.md", "蒸馏-第二步-归纳心法.md", "蒸馏-第三步-生成学习版.md", "配置-空白模板.md", "使用流程.md"])
        for x in lst:
            t = api.skillbook_zongjue({"file": x["file"]})["text"]
            self.assertTrue(len(t) > 300, x["file"])
        flow = api.skillbook_zongjue({"file": "使用流程.md"})["text"]
        self.assertIn("导入 skill", flow)
        self.assertIn("固定清单", api.skillbook_zongjue({"file": "配置-空白模板.md"})["text"])
        self.assertIn("references/", api.skillbook_zongjue({"file": "蒸馏-第二步-归纳心法.md"})["text"])
        cfg = api.skillbook_zongjue({"file": "配置-空白模板.md"})["text"]
        self.assertIn("混合型", cfg)
        self.assertIn("方法 / 技巧清单", cfg)
        self.assertIn("混合型文件格式", api.skillbook_zongjue({"file": "蒸馏-第二步-归纳心法.md"})["text"])
        self.assertIn("用到的技巧", api.skillbook_zongjue({"file": "蒸馏-第一步-提取例题.md"})["text"])
        step3 = api.skillbook_zongjue({"file": "蒸馏-第三步-生成学习版.md"})["text"]
        self.assertIn("老师是怎么讲的", step3)
        self.assertIn("学习版/", step3)
        self.assertIn("老师的讲解", api.skillbook_zongjue({"file": "蒸馏-第一步-提取例题.md"})["text"])       # 第一步要把概念讲解记详细
        for bad in ("../x.md", "不存在.md"):
            with self.assertRaises(api.ApiError):
                api.skillbook_zongjue({"file": bad})


if __name__ == "__main__":
    unittest.main()
