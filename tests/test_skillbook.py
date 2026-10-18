"""藏经阁·心法：每板块专属目录、读取顺序与透明度、随时修改（保存即生效）、历史回滚、版本冲突。
全程隔离假 HOME / 假库 / 自编 skill，不碰真实资料。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import api, paths, skillbook, trainer, vault

BOARD = "论证逻辑"                       # 行测默认板块表里的板块
SOURCE = "xue-rui-argument-logic"        # 它默认对应的库内 skill


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
        self.p.ensure_train_dir()
        src = self.p.vault / "copilot/skills" / SOURCE
        (src / "chapters").mkdir(parents=True)
        (src / "scripts").mkdir()
        (src / "SKILL.md").write_text("# 原入口\n先识别，再排除。", encoding="utf-8")
        (src / "cheatsheet.md").write_text("口诀：自编速查", encoding="utf-8")
        (src / "chapters/01.md").write_text("第一章：自编方法", encoding="utf-8")
        (src / "scripts/run.md").write_text("脚本说明不读", encoding="utf-8")
        (src / ".hidden.md").write_text("隐藏文件不读", encoding="utf-8")
        paths.save_settings({"subject": "行测", "vaults": {"行测": str(self.p.vault)}})
        self.p = paths.Paths(self.p.vault, "行测")
        self.source_bytes = {str(f): f.read_bytes() for f in src.rglob("*") if f.is_file()}

    def source_unchanged(self):
        src = self.p.vault / "copilot/skills" / SOURCE
        return {str(f): f.read_bytes() for f in src.rglob("*") if f.is_file()} == self.source_bytes

    def own(self):
        skillbook.create_from_source(self.p, BOARD, SOURCE)

    # ---- 读取顺序与旧行为
    def test_without_own_version_old_behavior_is_unchanged(self):
        self.assertEqual(skillbook.mode(self.p, BOARD, SOURCE), "source")
        self.assertIsNone(skillbook.tutor_material(self.p, BOARD, SOURCE))      # 调用方走原逻辑
        old_text, old_used = vault.skill_for_tutor(self.p, SOURCE)
        plan = skillbook.reading_plan(self.p, BOARD, SOURCE)
        self.assertEqual(plan["text"], old_text)
        self.assertEqual([i["rel"] for i in plan["items"] if i["read"]], old_used)
        self.assertNotIn("脚本说明不读", old_text)

    def test_no_skill_at_all(self):
        self.assertEqual(skillbook.mode(self.p, BOARD, "不存在的skill"), "none")
        plan = skillbook.reading_plan(self.p, BOARD, "不存在的skill")
        self.assertEqual((plan["items"], plan["text"]), ([], ""))

    def test_copy_makes_own_version_and_never_touches_source(self):
        r = skillbook.create_from_source(self.p, BOARD, SOURCE)
        self.assertEqual(r["files"], ["SKILL.md", "chapters/01.md", "cheatsheet.md"])
        self.assertEqual(skillbook.mode(self.p, BOARD, SOURCE), "mine")
        self.assertTrue(self.source_unchanged())
        with self.assertRaises(skillbook.SkillError):
            skillbook.create_from_source(self.p, BOARD, SOURCE)               # 不覆盖已有版本

    def test_template_has_standard_files(self):
        skillbook.create_template(self.p, "没有原skill的板块")
        self.assertEqual(skillbook.own_files(self.p, "没有原skill的板块"),
                         ["SKILL.md", "01-识别.md", "02-方法.md", "03-陷阱.md", "04-例题.md", "05-速查.md"])
        self.assertIn("没有原skill的板块", skillbook.read_file(self.p, "没有原skill的板块", "", "SKILL.md")["text"])

    def test_edit_takes_effect_for_the_next_tutoring(self):
        self.own()
        f = skillbook.read_file(self.p, BOARD, SOURCE, "chapters/01.md")
        self.assertTrue(f["editable"])
        skillbook.save(self.p, BOARD, "chapters/01.md", "第一章：我新写的方法", f["rev"])
        text, used = skillbook.tutor_material(self.p, BOARD, SOURCE)
        self.assertIn("我新写的方法", text)
        self.assertNotIn("自编方法", text)
        self.assertEqual(used[0], "SKILL.md")
        self.assertTrue(self.source_unchanged())                                # 原 skill 始终没被改

    # ---- 保存、冲突、历史
    def test_conflict_does_not_overwrite(self):
        self.own()
        rev = skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["rev"]
        skillbook.save(self.p, BOARD, "SKILL.md", "甲改", rev)
        with self.assertRaises(skillbook.SkillError) as c:
            skillbook.save(self.p, BOARD, "SKILL.md", "乙改（还拿着旧版本号）", rev)
        self.assertTrue(c.exception.conflict)
        self.assertEqual(skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["text"], "甲改")

    def test_history_and_restore(self):
        self.own()
        rev = skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["rev"]
        r = skillbook.save(self.p, BOARD, "SKILL.md", "第二版", rev)
        self.assertTrue(r["changed"])
        self.assertFalse(skillbook.save(self.p, BOARD, "SKILL.md", "第二版", r["rev"])["changed"])   # 没变化不留历史
        versions = skillbook.history(self.p, BOARD, "SKILL.md")
        self.assertEqual(len(versions), 1)
        self.assertEqual(skillbook.history_text(self.p, BOARD, "SKILL.md", versions[0]["id"]), "# 原入口\n先识别，再排除。")
        skillbook.restore(self.p, BOARD, "SKILL.md", versions[0]["id"], r["rev"])
        self.assertIn("先识别", skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["text"])
        self.assertEqual(len(skillbook.history(self.p, BOARD, "SKILL.md")), 2)          # 回滚前的“第二版”也留着

    def test_delete_and_rename_keep_history(self):
        self.own()
        rev = skillbook.read_file(self.p, BOARD, SOURCE, "cheatsheet.md")["rev"]
        r = skillbook.rename(self.p, BOARD, "cheatsheet.md", "05-速查.md", rev)
        self.assertEqual(r["path"], "05-速查.md")
        self.assertNotIn("cheatsheet.md", skillbook.own_files(self.p, BOARD))
        self.assertEqual(len(skillbook.history(self.p, BOARD, "cheatsheet.md")), 1)       # 改名前的内容在历史里
        skillbook.delete(self.p, BOARD, "05-速查.md", r["rev"])
        self.assertEqual(len(skillbook.history(self.p, BOARD, "05-速查.md")), 1)         # 删除的文件还能找回
        vid = skillbook.history(self.p, BOARD, "05-速查.md")[0]["id"]
        skillbook.restore(self.p, BOARD, "05-速查.md", vid, "")
        self.assertIn("05-速查.md", skillbook.own_files(self.p, BOARD))
        with self.assertRaises(skillbook.SkillError):
            skillbook.rename(self.p, BOARD, "SKILL.md", "入口.md", skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["rev"])

    def test_history_folder_is_never_read_as_skill_text(self):
        self.own()
        rev = skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["rev"]
        skillbook.save(self.p, BOARD, "SKILL.md", "新入口", rev)
        self.assertNotIn("先识别，再排除", skillbook.tutor_material(self.p, BOARD, SOURCE)[0])
        self.assertTrue(all(not f.startswith(".") for f in skillbook.own_files(self.p, BOARD)))

    # ---- 安全
    def test_bad_paths_are_rejected(self):
        self.own()
        for bad in ("../x.md", "/etc/passwd.md", "a/../../b.md", "SKILL.txt", ".hidden.md", "a/b/c/d.md", "", "a//b.md", "x:y.md"):
            with self.assertRaises(skillbook.SkillError, msg=bad):
                skillbook.save(self.p, BOARD, bad, "x", "")
        for bad in ("", "..", ".历史", "a/b", "a\\b"):
            with self.assertRaises(skillbook.SkillError, msg=bad):
                skillbook.own_files(self.p, bad) or skillbook.board_dir(self.p, bad)

    def test_size_limits(self):
        self.own()
        with self.assertRaises(skillbook.SkillError):
            skillbook.save(self.p, BOARD, "big.md", "字" * (skillbook.MAX_FILE + 1), "")
        with patch.object(skillbook, "MAX_FILES", 3):
            with self.assertRaises(skillbook.SkillError):
                skillbook.save(self.p, BOARD, "n1.md", "x", "")

    def test_over_budget_files_are_listed_as_not_read(self):
        self.own()
        with patch.object(skillbook, "TUTOR_LIMIT", 20):
            plan = skillbook.reading_plan(self.p, BOARD, SOURCE)
            text, used = skillbook.tutor_material(self.p, BOARD, SOURCE)
        self.assertTrue(plan["total"] <= 20)
        self.assertTrue(any(not i["read"] for i in plan["items"]))
        self.assertTrue(any(u.endswith("（未读入：超出上限）") for u in used))
        self.assertEqual(len(text), len(plan["text"]))

    # ---- 接口 + 实际讲题读取
    def test_api_edit_then_tutor_reads_new_content(self):
        view = api.skillbook_view({})["boards"]
        row = next(b for b in view if b["board"] == BOARD)
        self.assertEqual((row["mode"], row["source_exists"]), ("source", True))
        self.assertEqual(api.skillbook_plan({"board": BOARD})["limit"], skillbook.TUTOR_LIMIT)
        self.assertEqual(api.skillbook_file({"board": BOARD, "path": "SKILL.md"})["editable"], False)
        with self.assertRaises(api.ApiError):
            api.skillbook_save({"board": BOARD, "path": "SKILL.md", "text": "x", "base": ""})   # 没有我的版本不能直接保存
        api.skillbook_create({"board": BOARD, "how": "copy"})
        f = api.skillbook_file({"board": BOARD, "path": "SKILL.md"})
        self.assertTrue(f["editable"])
        api.skillbook_save({"board": BOARD, "path": "SKILL.md", "text": "# 我的入口\n新的识别法", "base": f["rev"]})
        with api.open_game(save=False) as g:
            text, used = trainer._tutor_material(g, BOARD)
            self.assertIn("新的识别法", text)
            self.assertIn("SKILL.md", used)
            self.assertIn("新的识别法", trainer._plain_digest(g, BOARD))
            self.assertTrue(g.has_skill(BOARD))
        with self.assertRaises(api.ApiError):
            api.skillbook_save({"board": BOARD, "path": "SKILL.md", "text": "旧版本号再保存", "base": f["rev"]})
        with self.assertRaises(api.ApiError):
            api.skillbook_file({"board": "不存在的板块", "path": "SKILL.md"})
        self.assertTrue(self.source_unchanged())

    def test_other_boards_unaffected_by_one_boards_own_version(self):
        api.skillbook_create({"board": BOARD, "how": "copy"})
        others = [b for b in api.skillbook_view({})["boards"] if b["board"] != BOARD]
        self.assertTrue(others and all(b["mode"] != "mine" for b in others))


if __name__ == "__main__":
    unittest.main()
