"""藏经阁·心法 3.4.2/3.4.3：待审建议（整理向导、记入心法）、采纳规则、发布回原 skill。
假 AI、假库、假 HOME；不碰真实资料。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import ai, api, paths, skillbook, skillbook_ai, trainer

BOARD = "论证逻辑"
SOURCE = "xue-rui-argument-logic"


class Base(unittest.TestCase):
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
        self.src = self.p.vault / "copilot/skills" / SOURCE
        (self.src / "scripts").mkdir(parents=True)
        (self.src / "SKILL.md").write_text("# 原入口\n先识别。", encoding="utf-8")
        (self.src / "cheatsheet.md").write_text("原速查", encoding="utf-8")
        (self.src / "scripts/run.md").write_text("脚本不读", encoding="utf-8")
        paths.save_settings({"subject": "行测", "vaults": {"行测": str(self.p.vault)}})
        self.p = paths.Paths(self.p.vault, "行测")
        self.src_bytes = {str(f): f.read_bytes() for f in self.src.rglob("*") if f.is_file()}

    def src_same(self):
        return {str(f): f.read_bytes() for f in self.src.rglob("*") if f.is_file()} == self.src_bytes

    def prop(self, edits, kind="note", key="k1", summary="补一条"):
        return skillbook.add_proposal(self.p, BOARD, kind, summary, edits, {"label": "试炼复盘 粉笔1-1"}, key)


class ProposalTest(Base):
    def test_only_safe_edits_are_kept(self):
        p = self.prop([{"path": "03-陷阱.md", "action": "append", "text": "新陷阱", "reason": "r"},
                       {"path": "../x.md", "action": "append", "text": "越界"}, {"path": "a.md", "action": "replace", "text": "覆盖"},
                       {"path": "b.md", "action": "new", "text": "  "}, "不是字典"])
        self.assertEqual([e["path"] for e in p["edits"]], ["03-陷阱.md"])
        with self.assertRaises(skillbook.SkillError):
            self.prop([{"path": "../x.md", "action": "append", "text": "x"}], key="k2")
        self.assertEqual(len(skillbook.proposals(self.p, BOARD)), 1)

    def test_same_key_is_not_saved_twice(self):
        a = self.prop([{"path": "03-陷阱.md", "action": "append", "text": "x"}])
        b = self.prop([{"path": "03-陷阱.md", "action": "append", "text": "y"}])
        self.assertEqual(a["id"], b["id"])

    def test_accept_note_creates_own_version_appends_and_logs(self):
        p = self.prop([{"path": "cheatsheet.md", "action": "append", "text": "## 新口诀\n看问法", "reason": "补"},
                       {"path": "03-陷阱.md", "action": "append", "text": "新陷阱：偷换概念"}])
        r = skillbook.accept(self.p, BOARD, SOURCE, p["id"], [0])
        self.assertEqual((r["applied"], r["left"]), (["cheatsheet.md"], 1))
        self.assertTrue(skillbook.has_own(self.p, BOARD))
        text = skillbook.read_file(self.p, BOARD, SOURCE, "cheatsheet.md")["text"]
        self.assertTrue(text.startswith("原速查") and "看问法" in text)
        self.assertIn("采纳「补一条」", skillbook.read_file(self.p, BOARD, SOURCE, "变更记录.md")["text"])
        self.assertTrue(self.src_same())                                          # 原 skill 不动
        self.assertEqual(len(skillbook.history(self.p, BOARD, "cheatsheet.md")), 1)
        r = skillbook.accept(self.p, BOARD, SOURCE, p["id"], [1])                     # 另一条：新建文件（原来没有）
        self.assertEqual(r["left"], 0)
        self.assertEqual(skillbook.proposals(self.p, BOARD), [])                       # 全部处理完自动移走

    def test_new_never_overwrites_and_picks_are_required(self):
        skillbook.create_from_source(self.p, BOARD, SOURCE)
        p = self.prop([{"path": "cheatsheet.md", "action": "new", "text": "覆盖？"}])
        r = skillbook.accept(self.p, BOARD, SOURCE, p["id"], [0])
        self.assertEqual(r["applied"], [])
        self.assertIn("没有覆盖", r["skipped"][0])
        self.assertEqual(skillbook.read_file(self.p, BOARD, SOURCE, "cheatsheet.md")["text"], "原速查")
        with self.assertRaises(skillbook.SkillError):
            skillbook.accept(self.p, BOARD, SOURCE, p["id"], [])
        with self.assertRaises(skillbook.SkillError):
            skillbook.accept(self.p, "形式逻辑", SOURCE, p["id"], [0])                 # 不能采纳到别的板块

    def test_dismiss(self):
        p = self.prop([{"path": "03-陷阱.md", "action": "append", "text": "x"}])
        skillbook.dismiss(self.p, p["id"])
        self.assertEqual(skillbook.proposals(self.p, BOARD), [])
        with self.assertRaises(skillbook.SkillError):
            skillbook.dismiss(self.p, p["id"])
        with self.assertRaises(skillbook.SkillError):
            skillbook.dismiss(self.p, "../../x")

    def test_organize_first_accept_needs_entry_file_and_keeps_source_files_out(self):
        edits = [{"path": "SKILL.md", "action": "new", "text": "# 入口\n整理后的入口"}, {"path": "02-方法.md", "action": "new", "text": "# 方法\n步骤"}]
        p = self.prop(edits, kind="organize", key="o1")
        with self.assertRaises(skillbook.SkillError):
            skillbook.accept(self.p, BOARD, SOURCE, p["id"], [1])
        self.assertFalse(skillbook.has_own(self.p, BOARD))
        skillbook.accept(self.p, BOARD, SOURCE, p["id"], [0, 1])
        self.assertEqual(skillbook.own_files(self.p, BOARD), ["SKILL.md", "02-方法.md", "变更记录.md"])   # 没有混入原 cheatsheet.md
        self.assertTrue(self.src_same())


class PublishTest(Base):
    def own(self):
        skillbook.create_from_source(self.p, BOARD, SOURCE)
        rev = skillbook.read_file(self.p, BOARD, SOURCE, "cheatsheet.md")["rev"]
        skillbook.save(self.p, BOARD, "cheatsheet.md", "我改过的速查", rev)
        skillbook.save(self.p, BOARD, "02-方法.md", "新方法", "")

    def test_preview_publish_backup_restore(self):
        self.own()
        pv = skillbook.publish_preview(self.p, BOARD, SOURCE, [BOARD, "形式逻辑"])
        st = {x["path"]: x["status"] for x in pv["files"]}
        self.assertEqual(st, {"SKILL.md": "same", "cheatsheet.md": "changed", "02-方法.md": "new"})
        self.assertEqual(pv["shared_with"], ["形式逻辑"])
        r = skillbook.publish(self.p, BOARD, SOURCE, pv["digest"])
        self.assertEqual(sorted(r["written"]), ["02-方法.md", "cheatsheet.md"])
        self.assertEqual((self.src / "cheatsheet.md").read_text(encoding="utf-8"), "我改过的速查")
        self.assertEqual((self.src / "scripts/run.md").read_text(encoding="utf-8"), "脚本不读")   # 不碰 scripts
        self.assertEqual(len(skillbook.publish_backups(self.p, BOARD)), 1)
        self.assertIn("发布回原 skill", skillbook.read_file(self.p, BOARD, SOURCE, "变更记录.md")["text"])
        skillbook.publish_restore(self.p, BOARD, SOURCE, r["backup"])
        self.assertTrue(self.src_same())                                                     # 一字不差还原，新建的也删掉
        self.assertEqual(skillbook.publish_backups(self.p, BOARD), [])
        with self.assertRaises(skillbook.SkillError):
            skillbook.publish_restore(self.p, BOARD, SOURCE, r["backup"])

    def test_changed_after_preview_is_refused_and_nothing_written(self):
        self.own()
        pv = skillbook.publish_preview(self.p, BOARD, SOURCE)
        (self.src / "cheatsheet.md").write_text("别处又改了原 skill", encoding="utf-8")
        with self.assertRaises(skillbook.SkillError) as c:
            skillbook.publish(self.p, BOARD, SOURCE, pv["digest"])
        self.assertTrue(c.exception.conflict)
        self.assertEqual((self.src / "cheatsheet.md").read_text(encoding="utf-8"), "别处又改了原 skill")
        self.assertFalse((self.src / "02-方法.md").exists())

    def test_needs_own_version_and_existing_source(self):
        with self.assertRaises(skillbook.SkillError):
            skillbook.publish_preview(self.p, BOARD, SOURCE)
        skillbook.create_template(self.p, "没有原skill的板块")
        with self.assertRaises(skillbook.SkillError):
            skillbook.publish_preview(self.p, "没有原skill的板块", "不存在")

    def test_api_switch_is_off_by_default(self):
        skillbook.create_from_source(self.p, BOARD, SOURCE)
        self.assertFalse(api.skillbook_view({})["publish_back"])
        with self.assertRaises(api.ApiError):
            api.skillbook_publish({"board": BOARD})
        self.assertTrue(api.skillbook_settings({"publish_back": True})["publish_back"])
        pv = api.skillbook_publish({"board": BOARD})
        self.assertIn("digest", pv)
        self.assertTrue(self.src_same())                                                     # 预览不写


class FakeAITest(Base):
    def fake(self, reply):
        return patch.object(ai, "chat_json", side_effect=reply if isinstance(reply, list) else None, return_value=None if isinstance(reply, list) else reply)

    def test_ai_unavailable_is_explained(self):
        with patch.object(ai, "available", return_value=False), self.assertRaises(skillbook.SkillError) as c:
            skillbook_ai.organize(self.p, BOARD, SOURCE)
        self.assertIn("API key", str(c.exception))

    def test_organize_saves_valid_files_only_and_reuses_result(self):
        reply = {"summary": "整理好了", "files": [{"path": "SKILL.md", "text": "# 入口"}, {"path": "02-方法.md", "text": "# 方法"},
                                                   {"path": "乱写.md", "text": "不在标准结构里"}]}
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value=reply) as call:
            a = skillbook_ai.organize(self.p, BOARD, SOURCE)
            b = skillbook_ai.organize(self.p, BOARD, SOURCE)
        self.assertEqual(call.call_count, 1)                                                 # 同样的资料不重复花钱
        self.assertEqual(a["id"], b["id"])
        self.assertEqual([e["path"] for e in a["edits"]], ["SKILL.md", "02-方法.md"])
        self.assertFalse(skillbook.has_own(self.p, BOARD))                                   # 只是建议，采纳前不写文件
        prompt = call.call_args[0][0][1]["content"]
        self.assertIn("先识别", prompt)
        self.assertNotIn("脚本不读", prompt)

    def test_organize_without_entry_or_with_bad_json_saves_nothing(self):
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value={"files": [{"path": "02-方法.md", "text": "x"}]}):
            with self.assertRaises(skillbook.SkillError):
                skillbook_ai.organize(self.p, BOARD, SOURCE)
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", side_effect=ai.AIError("坏格式")) as call:
            with self.assertRaises(skillbook.SkillError):
                skillbook_ai.organize(self.p, BOARD, SOURCE)
            self.assertEqual(call.call_count, 2)                                             # 校验不过重试一次
        self.assertEqual(skillbook.proposals(self.p, BOARD), [])

    def test_organize_refuses_oversized_material(self):
        with patch.object(skillbook_ai, "ORGANIZE_LIMIT", 5), patch.object(ai, "available", return_value=True), \
                patch.object(ai, "chat_json") as call, self.assertRaises(skillbook.SkillError):
            skillbook_ai.organize(self.p, BOARD, SOURCE)
        call.assert_not_called()

    def test_note_not_needed_and_needed(self):
        ctx = {"question": "题干", "answer": "A", "mine": "B", "explain": "师傅讲解"}
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value={"needed": False, "edits": []}):
            self.assertIsNone(skillbook_ai.note(self.p, BOARD, SOURCE, ctx, "来源")[0])
        reply = {"needed": True, "summary": "补一招", "edits": [{"path": "cheatsheet.md", "action": "append", "text": "新口诀", "reason": "缺"}]}
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value=reply) as call:
            prop, why = skillbook_ai.note(self.p, BOARD, SOURCE, ctx, "试炼复盘 粉笔1-1")
            again, why2 = skillbook_ai.note(self.p, BOARD, SOURCE, ctx, "试炼复盘 粉笔1-1")
        self.assertEqual((prop["summary"], again["id"], call.call_count), ("补一招", prop["id"], 1))
        self.assertIn("原速查", call.call_args[0][0][1]["content"])                            # 现有方法一起给 AI 判断
        self.assertFalse(skillbook.has_own(self.p, BOARD))

    def test_trainer_skillnote_messages(self):
        with api.open_game(save=False) as g:
            q = {"stem": "题干", "options": {"A": "甲", "B": "乙"}}
            self.assertIn("先点", trainer._skillnote(g, BOARD, q, "A", "B", None, "来源")[0]["text"])
            with patch.object(ai, "available", return_value=False):
                self.assertIn("没连上 AI", trainer._skillnote(g, BOARD, q, "A", "B", "讲解", "来源")[0]["text"])
            reply = {"needed": True, "summary": "补一招", "edits": [{"path": "cheatsheet.md", "action": "append", "text": "新口诀"}]}
            with patch.object(ai, "available", return_value=True), patch.object(ai, "chat_json", return_value=reply):
                text = trainer._skillnote(g, BOARD, q, "A", "B", "讲解", "来源")[0]["text"]
            self.assertIn("补一招", text)
            self.assertIn(g.T("skillbook"), text)
            self.assertEqual(trainer._q_text({"stem": "S", "options": "（见题目）"}), "S")      # 模考复盘的题没有选项字典


if __name__ == "__main__":
    unittest.main()
