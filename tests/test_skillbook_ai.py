"""藏经阁·心法：待审建议（整理成学习版、记入心法）、采纳规则。
假 AI、假库、假 HOME；不碰真实资料。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import ai, api, paths, prompts, skillbook, skillbook_ai, trainer

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

    def test_organize_accept_copies_source_first_and_adds_new_files(self):
        edits = [{"path": "00-怎么用.md", "action": "new", "text": "# 怎么用\n三步"}, {"path": "02-方法卡.md", "action": "new", "text": "# 方法卡\n步骤"}]
        p = self.prop(edits, kind="organize", key="o1")
        self.assertFalse(skillbook.has_own(self.p, BOARD))
        skillbook.accept(self.p, BOARD, SOURCE, p["id"], [0, 1])
        self.assertEqual(skillbook.own_files(self.p, BOARD), ["SKILL.md", "00-怎么用.md", "02-方法卡.md", "cheatsheet.md", "变更记录.md"])   # 原文件先复制过来，学习版是新增
        self.assertEqual(skillbook.read_file(self.p, BOARD, SOURCE, "SKILL.md")["text"], "# 原入口\n先识别。")
        self.assertTrue(self.src_same())


class FakeAITest(Base):
    def fake(self, reply):
        return patch.object(ai, "chat_json", side_effect=reply if isinstance(reply, list) else None, return_value=None if isinstance(reply, list) else reply)

    def test_ai_unavailable_is_explained(self):
        with patch.object(ai, "available", return_value=False), self.assertRaises(skillbook.SkillError) as c:
            skillbook_ai.organize(self.p, BOARD, SOURCE)
        self.assertIn("API key", str(c.exception))

    def chat_by_file(self, replies):
        """假 AI：按“现在只写文件「xxx」”里的文件名回复；replies：文件名 → 文字（或异常）；示范题单独回复 demo"""
        def fake(messages, **kw):
            user = messages[1]["content"]
            if "请写这道题的思考过程" in user:
                r = replies.get("demo", "第 1 步：看信号（用到：方法卡「甲」）\n小结：先找矛盾")
            else:
                path = next(p for p in prompts.SKILLBOOK_LEARN if "现在只写文件「%s」" % p in user)
                r = replies.get(path, "（无）")
            if isinstance(r, Exception):
                raise r
            return r
        return fake

    def questions(self, n=2):
        return [{"key": "论证逻辑::00%d" % i, "id": "00%d" % i, "board": BOARD, "stem": "题干%d" % i, "answer": "B", "analysis": "",
                 "options": {"A": "甲", "B": "乙", "C": "丙", "D": "丁"}} for i in range(1, n + 1)]

    def test_organize_writes_learner_files_one_per_call_and_reuses_result(self):
        replies = {"02-方法卡.md": "```markdown\n## 方法甲\n```", "00-怎么用.md": "# 怎么用", "03-陷阱.md": "（无）"}
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=self.chat_by_file(replies)) as call:
            a = skillbook_ai.organize(self.p, BOARD, SOURCE, self.questions())
            b = skillbook_ai.organize(self.p, BOARD, SOURCE, self.questions())
        self.assertEqual(call.call_count, 5 + 2)                                             # 5 个文件各一次 + 2 道示范，同样的资料第二次不再请求
        self.assertEqual(a["id"], b["id"])
        paths_ = [e["path"] for e in a["edits"]]
        self.assertEqual(paths_, ["02-方法卡.md", "00-怎么用.md", "04-示范.md"])                # “（无）”的不出，围栏被去掉，方法卡先写
        self.assertEqual(a["edits"][0]["text"], "## 方法甲")
        demo = a["edits"][2]["text"]
        self.assertIn("题干1", demo)
        self.assertIn("**正确答案**：B", demo)                                                # 原题由程序贴，AI 只写过程
        self.assertIn("用到：方法卡「甲」", demo)
        self.assertFalse(skillbook.has_own(self.p, BOARD))                                   # 只是建议，采纳前不写文件
        for c in call.call_args_list:
            self.assertTrue(c.kwargs["max_tokens"] <= 4000)
        first = call.call_args_list[0][0][0][1]["content"]
        self.assertIn("先识别", first)
        self.assertNotIn("脚本不读", first)
        self.assertIn("不用 LaTeX", first)
        self.assertIn("方法甲", call.call_args_list[1][0][0][1]["content"])                  # 后面的文件看得到方法卡，名字对得上

    def test_organize_material_does_not_include_dispatch_section(self):
        (self.src / "SKILL.md").write_text("# 入口\n讲解\n\n## 被 xingce-jiexi-all 调度时\n运行 jiexi.py 写入\n\n## 后记\n保留", encoding="utf-8")
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=self.chat_by_file({"02-方法卡.md": "x"})) as call:
            skillbook_ai.organize(self.p, BOARD, SOURCE)
        first = call.call_args_list[0][0][0][1]["content"]
        self.assertIn("讲解", first)
        self.assertIn("保留", first)
        self.assertNotIn("jiexi.py", first)

    def test_organize_retries_shorter_when_reply_is_cut_off(self):
        calls = []

        def fake(messages, **kw):
            user = messages[1]["content"]
            calls.append(user)
            if "现在只写文件「02-方法卡.md」" in user and "不超过 1800 字" in user:
                raise ai.AIError("AI回复达到长度上限，尚未保存残缺结果")
            return "# 内容" if "「02-方法卡.md」" in user else "（无）"
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=fake):
            r = skillbook_ai.organize(self.p, BOARD, SOURCE)
        self.assertEqual([e["path"] for e in r["edits"]], ["02-方法卡.md"])
        self.assertTrue(any("不超过 900 字" in c and "02-方法卡.md" in c for c in calls))        # 换更短的上限重试

    def test_organize_skips_a_file_that_never_fits_but_needs_the_method_cards(self):
        def fake(messages, **kw):
            user = messages[1]["content"]
            if "「03-陷阱.md」" in user:
                raise ai.AIError("AI回复达到长度上限")
            return "# 内容"
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=fake):
            r = skillbook_ai.organize(self.p, BOARD, SOURCE)
        self.assertNotIn("03-陷阱.md", [e["path"] for e in r["edits"]])
        self.assertIn("03-陷阱.md 没能生成", r["summary"])
        for p in skillbook.proposals(self.p, BOARD):
            skillbook.dismiss(self.p, p["id"])
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=ai.AIError("AI回复达到长度上限")), \
                self.assertRaises(skillbook.SkillError):
            skillbook_ai.organize(self.p, BOARD, SOURCE)                                      # 方法卡写不出来就整个不保存
        self.assertEqual(skillbook.proposals(self.p, BOARD), [])

    def test_organize_skips_files_that_already_exist_and_demo_failure_is_not_fatal(self):
        skillbook.ensure_own(self.p, BOARD, SOURCE)
        skillbook.save(self.p, BOARD, "02-方法卡.md", "# 我的方法卡\n## 方法甲", "")
        replies = {"00-怎么用.md": "# 怎么用", "demo": ai.AIError("AI回复达到长度上限")}
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=self.chat_by_file(replies)) as call:
            r = skillbook_ai.organize(self.p, BOARD, SOURCE, self.questions(1))
        self.assertEqual([e["path"] for e in r["edits"]], ["00-怎么用.md"])                    # 已有的方法卡不重写
        self.assertIn("示范第 1 道 没能生成", r["summary"])
        self.assertTrue(all("现在只写文件「02-方法卡.md」" not in c[0][0][1]["content"] for c in call.call_args_list))

    def test_pick_examples_prefers_wrong_questions_with_answers(self):
        folder = self.p.train / "题库"
        folder.mkdir(parents=True, exist_ok=True)
        def q(i, ans, analysis):
            return "## 题目 %s\n\n### 知识点\n甲\n\n### 题干\n题干%s\n\n### 选项\nA. 一\nB. 二\nC. 三\nD. 四\n\n### 答案\n%s\n\n### 解析\n%s\n\n" % (i, i, ans, analysis)
        (folder / (BOARD + "真题.md")).write_text(q("001", "A", "") + q("002", "B", "有解析") + q("003", "（待补）", "") + q("004", "C", ""), encoding="utf-8")
        with api.open_game(save=False) as g:
            ids = [x["id"] for x in skillbook_ai.pick_examples(g, BOARD)]
            self.assertEqual(ids, ["002", "001"])                                            # 有解析的先；答案待补的不选
            g.state.setdefault("bank", {"records": {}, "runs": {}, "groups": []})["records"]["%s::004" % BOARD] = {"wrong": True, "history": []}
            self.assertEqual([x["id"] for x in skillbook_ai.pick_examples(g, BOARD)][0], "004")   # 做错过的排最前
            self.assertEqual(skillbook_ai.pick_examples(g, "没有题库的板块"), [])

    def test_organize_without_method_cards_saves_nothing(self):
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=self.chat_by_file({"00-怎么用.md": "x"})):
            with self.assertRaises(skillbook.SkillError):
                skillbook_ai.organize(self.p, BOARD, SOURCE)
        self.assertEqual(skillbook.proposals(self.p, BOARD), [])

    def test_organize_refuses_oversized_material(self):
        with patch.object(skillbook, "TUTOR_LIMIT", 5), patch.object(ai, "available", return_value=True), \
                patch.object(ai, "chat") as call, self.assertRaises(skillbook.SkillError):
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
