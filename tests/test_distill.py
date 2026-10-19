"""藏经阁·心法·蒸馏 3.5：素材切分定位、卡片校验与合并、汇总成蒸馏版（待审建议）、版本快照 / 对比 / 回滚、增量更新（含手改冲突）、
提示词包导入、检验做对率与错题诊断。假 AI、假库、假 HOME；不碰真实资料。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import ai, api, distill, distill_ai, paths, skillbook, vault

BOARD = "论证逻辑"
SOURCE = "xue-rui-argument-logic"

TRANSCRIPT = """好，同学们大家好，今天我们先讲补全逻辑啊。呃，这个考点的特征是题干里有逻辑连词，比如如果、那么、只要、就、除非、否则、必须。
所以看到逻辑连词，就把它连一连箭头，做做逆否。一会儿再给大家讲例题啊，先听免费系统课。

好，我们来看这道2026年福建事业单位的题啊。结论是人工智能的艺术品本质是模仿，引词是因此。论据一，人工智能没有自我意识；论据二，审美需求对于创造性劳动是不可或缺的。
所以这里缺一环：没有A就没有B，也就是只有A才B。C选项补上了这个逻辑，直接选C。A选项逻辑外挖坑，B选项题干没说将来。这道题选C。

好，今天就到这里，大家下课。"""

SEGMENTS = {"segments": [
    {"type": "考点", "title": "补全逻辑", "start": "好，同学们大家好，今天我们先讲补全逻辑啊", "end": "做做逆否。"},
    {"type": "闲聊", "title": "预告", "start": "一会儿再给大家讲例题啊", "end": "先听免费系统课。"},
    {"type": "例题", "title": "2026福建事业单位", "start": "好，我们来看这道2026年福建事业单位的题啊", "end": "这道题选C。"},
    {"type": "闲聊", "title": "下课", "start": "好，今天就到这里", "end": "大家下课。"},
]}
POINT = {"name": "补全逻辑", "one_line": "论据和结论之间缺一环，选项用逻辑连词补上", "signals": {"category": "表示条件关系的逻辑连词", "examples": ["如果", "只要", "除非"], "test": "能不能改写成如果…那么…"},
         "steps": ["找结论", "找论据", "连箭头做逆否", "选补上缺口的选项"], "tips": ["非补全逻辑的题里带逻辑连词的选项多是迷惑项"], "quotes": ["连一连箭头，做做逆否"], "uncertain": []}
EXAMPLE = {"title": "2026福建事业单位", "exam": "2026 福建事业单位", "question": {"complete": False, "stem": "结论：人工智能艺术品本质是模仿", "options": {"C": "只有A才B"}, "answer": "C"},
           "concepts": ["补全逻辑"], "steps": ["找结论（引词因此）", "找论据", "发现缺没有A就没有B", "选补上的C"],
           "exclusions": [{"option": "A", "reason": "讨论方向超出论证", "type": "逻辑外挖坑"}, {"option": "B", "reason": "题干没说将来", "type": "题干未提及"}], "quotes": ["这就是数学题"]}
OUTLINE = {"name": "十三美十三丑", "items": [{"name": "补全逻辑"}, {"name": "建立联系"}], "priority": {"肉": ["建立联系"], "排骨": [], "渣渣": []}, "ugly": [{"name": "逻辑外挖坑", "test": "讨论的方向超出论证"}]}


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
        src = self.p.vault / "copilot/skills" / SOURCE
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("# 原入口\n书里的内容", encoding="utf-8")
        paths.save_settings({"subject": "行测", "vaults": {"行测": str(self.p.vault)}})
        self.p = paths.Paths(self.p.vault, "行测")

    def material(self, text=TRANSCRIPT, kind="转写", title="328课"):
        m = distill.add_material(self.p, BOARD, kind, title, text)
        distill.apply_segments(self.p, BOARD, m["id"], 0, m["text"], SEGMENTS["segments"], 0)
        return distill.get_material(self.p, BOARD, m["id"])

    def card(self, kind, data, m, sid, source_kind="转写"):
        return distill.save_card(self.p, BOARD, kind, data, {"material": m["id"], "segment": sid, "kind": source_kind, "label": "%s · %s" % (m["title"], sid)})[0]

    def two_cards(self):
        m = self.material()
        a = self.card("考点", POINT, m, "s1")
        b = self.card("例题", EXAMPLE, m, "s3")
        return m, a, b

    def adopt(self, prop, picks=None):
        return skillbook.accept(self.p, BOARD, SOURCE, prop["id"], picks if picks is not None else list(range(len(prop["edits"]))))

    def bank(self, rows):
        folder = self.p.train / "题库"
        folder.mkdir(parents=True, exist_ok=True)
        text = ""
        for i, (stem, ans) in enumerate(rows, 1):
            text += "## 题目 %03d\n\n### 知识点\n甲\n\n### 题干\n%s\n\n### 选项\nA. 一\nB. 二\nC. 三\nD. 四\n\n### 答案\n%s\n\n### 解析\n（待补）\n\n" % (i, stem, ans)
        (folder / (BOARD + "真题.md")).write_text(text, encoding="utf-8")


class LocateTest(Base):
    def test_locate_ignores_punctuation_and_falls_back(self):
        t = "开头废话。好，我们来看，这道题啊！结论是甲。所以选C，再见"
        a, b = distill.locate(t, "好我们来看这道题啊", "所以选C")
        self.assertEqual(t[a:b], "好，我们来看，这道题啊！结论是甲。所以选C")
        self.assertIsNone(distill.locate(t, "完全没有的话", "所以选C"))
        a, b = distill.locate(t, "好我们来看这道题啊（识别错了几个字", "所以选C再见哦")             # 起止句末尾有错字：退到更短的开头 / 结尾再找
        self.assertTrue(t[a:b].startswith("好，我们") and t[a:b].endswith("再见"))

    def test_chunks_cover_text_without_overlap(self):
        t = ("句子一。" * 700 + "\n") * 3
        cs = distill.chunks(t, 2000)
        self.assertTrue(len(cs) > 1)
        self.assertEqual("".join(c for _, c in cs), t)
        self.assertEqual([o for o, _ in cs], [sum(len(c) for _, c in cs[:i]) for i in range(len(cs))])

    def test_segments_are_located_replaced_by_chunk_and_skipped_ranges_shown(self):
        m = self.material()
        self.assertEqual([(s["type"], s["include"]) for s in m["segments"]], [("考点", True), ("闲聊", False), ("例题", True), ("闲聊", False)])
        self.assertIn("连一连箭头", distill.segment_text(m, m["segments"][0]))
        r = distill.apply_segments(self.p, BOARD, m["id"], 0, m["text"], SEGMENTS["segments"][:1] + [{"type": "例题", "title": "找不到", "start": "根本没有这句话", "end": "也没有"}], 0)
        self.assertEqual((r["n"], r["lost"]), (1, ["找不到"]))                       # 重跑这一块：只换这一块；找不到的不采用
        self.assertEqual(len(distill.get_material(self.p, BOARD, m["id"])["segments"]), 1)
        self.assertTrue(distill.skipped_ranges(distill.get_material(self.p, BOARD, m["id"])))   # 没被片段盖住的文字能看到

    def test_update_and_merge_segments(self):
        m = self.material()
        distill.update_segment(self.p, BOARD, m["id"], "s2", {"include": True, "type": "考点"})
        distill.merge_segments(self.p, BOARD, m["id"], "s1")
        m2 = distill.get_material(self.p, BOARD, m["id"])
        self.assertEqual(len(m2["segments"]), 3)
        self.assertIn("一会儿再给大家讲例题", distill.segment_text(m2, m2["segments"][0]))
        with self.assertRaises(distill.DistillError):
            distill.update_segment(self.p, BOARD, m["id"], "s1", {"type": "乱写"})

    def test_whole_material_as_one_segment_for_short_own_words(self):
        m = distill.add_material(self.p, BOARD, "自述", "我的解法", "先划论点论据，看中间跳了什么，削弱就是堵这个跳。" * 3, whole_type="例题")
        self.assertEqual([(s["type"], s["start"]) for s in m["segments"]], [("例题", 0)])
        with self.assertRaises(distill.DistillError):
            distill.add_material(self.p, BOARD, "自述", "太短", "短")


class CardTest(Base):
    def test_validate_cleans_and_requires_core_fields(self):
        d = distill.validate_card("考点", dict(POINT, steps=["a", "a", "b"], extra="丢掉", quotes=[{"text": "原话", "kind": "自述"}]))
        self.assertEqual(d["steps"], ["a", "b"])
        self.assertNotIn("extra", d)
        self.assertEqual(d["quotes"], [{"text": "原话", "kind": "自述"}])
        for bad in ({"name": "x"}, {"steps": ["a"]}, "不是字典"):
            with self.assertRaises(distill.DistillError):
                distill.validate_card("考点", bad)
        ex = distill.validate_card("例题", EXAMPLE)
        self.assertFalse(ex["question"]["complete"])                                  # 选项不全：不算完整
        full = distill.validate_card("例题", dict(EXAMPLE, question={"complete": True, "stem": "题干", "options": {k: k for k in "ABCD"}, "answer": "B"}))
        self.assertTrue(full["question"]["complete"])
        self.assertEqual(distill.validate_card("总纲", OUTLINE)["items"][0]["name"], "补全逻辑")

    def test_same_point_merges_and_outline_is_single_and_example_is_new(self):
        m = self.material()
        a = self.card("考点", POINT, m, "s1")
        m2 = distill.add_material(self.p, BOARD, "自述", "我的话", "我的做法：先看逻辑连词，再连箭头。" * 2, whole_type="考点")
        mine = dict(POINT, steps=["我的做法第一步", "第二步"], signals={"category": "条件词", "examples": ["倘若"], "test": ""}, quotes=["我自己的话"])
        b, how = distill.save_card(self.p, BOARD, "考点", mine, {"material": m2["id"], "segment": "s1", "kind": "自述", "label": "我的话"})
        self.assertEqual((b["id"], how), (a["id"], "merged"))
        d = distill.get_card(self.p, BOARD, a["id"])
        self.assertEqual(d["rev"], 2)
        self.assertIn("倘若", d["data"]["signals"]["examples"])                         # 信号并集
        self.assertEqual(d["data"]["steps"], POINT["steps"])                             # 原来的做法不替换
        self.assertEqual(d["data"]["alt_steps"][0]["steps"], ["我的做法第一步", "第二步"])    # 不同的记成另一种讲法
        self.assertEqual(d["data"]["quotes"][0], {"text": "我自己的话", "kind": "自述"})   # 自己的话排在前面
        self.assertEqual(len(d["sources"]), 2)
        self.card("总纲", OUTLINE, m, "s1")
        distill.save_card(self.p, BOARD, "总纲", dict(OUTLINE, items=[{"name": "指出相同"}]), {"material": m["id"], "segment": "s2", "kind": "转写", "label": "x"})
        outs = [c for c in distill.cards(self.p, BOARD) if c["kind"] == "总纲"]
        self.assertEqual(len(outs), 1)
        self.assertEqual([i["name"] for i in outs[0]["data"]["items"]], ["补全逻辑", "建立联系", "指出相同"])
        self.card("例题", EXAMPLE, m, "s3")
        self.card("例题", dict(EXAMPLE, title="另一道"), m, "s3")
        self.assertEqual(len([c for c in distill.cards(self.p, BOARD) if c["kind"] == "例题"]), 2)

    def test_evidence_status_and_user_edit_and_delete(self):
        m, a, b = self.two_cards()
        ev = distill.evidence(distill.cards(self.p, BOARD), a)
        self.assertEqual((ev["n"], ev["status"]), (2, "已印证"))                          # 1 次讲解 + 1 道例题
        c = distill.update_card(self.p, BOARD, a["id"], dict(a["data"], one_line="我改的一句话"))
        self.assertEqual((c["rev"], c["edited"]), (2, True))
        with self.assertRaises(distill.DistillError):
            distill.update_card(self.p, BOARD, a["id"], {"name": ""})
        distill.link_segment(self.p, BOARD, m["id"], "s1", a["id"])
        distill.delete_card(self.p, BOARD, a["id"])
        self.assertIsNone(distill.get_material(self.p, BOARD, m["id"])["segments"][0]["card"])
        self.assertEqual(distill.evidence(distill.cards(self.p, BOARD), b)["status"], "")


class BuildTest(Base):
    def test_render_files_are_plain_chinese_markdown_with_sources_and_links(self):
        m, a, b = self.two_cards()
        self.card("总纲", OUTLINE, m, "s1")
        files, why = distill.render_files(self.p, BOARD)
        self.assertEqual(sorted(files), ["蒸馏/00-总流程.md", "蒸馏/01-总纲.md", "蒸馏/02-识别信号.md", "蒸馏/03-考点/补全逻辑.md",
                                        "蒸馏/04-丑的选项.md", "蒸馏/05-例题/2026福建事业单位.md"])
        point = files["蒸馏/03-考点/补全逻辑.md"]
        self.assertIn("证据：2 处", point)
        self.assertIn("已印证", point)
        self.assertIn("判别问法：能不能改写成如果…那么…", point)
        self.assertIn("[2026福建事业单位](../05-例题/2026福建事业单位.md)", point)
        self.assertIn("来源：328课 · s1", point)
        self.assertIn("✅ 已学", files["蒸馏/01-总纲.md"])                                 # 清单里的补全逻辑已经有考点卡
        self.assertIn("⬜ 未学", files["蒸馏/01-总纲.md"])
        self.assertIn("逻辑外挖坑", files["蒸馏/04-丑的选项.md"])
        self.assertIn("不完整", files["蒸馏/05-例题/2026福建事业单位.md"])
        for t in files.values():
            self.assertNotIn("$", t)
        self.assertTrue(why["蒸馏/03-考点/补全逻辑.md"].startswith("考点卡"))

    def test_first_build_adopt_makes_v1_0_and_tutor_reads_only_distilled(self):
        self.two_cards()
        prop = distill.build(self.p, BOARD, SOURCE)
        self.assertEqual((prop["kind"], prop["meta"]["version"]), ("distill", "1.0"))
        self.assertTrue(all(e["action"] == "new" for e in prop["edits"]))
        self.assertIn("v1.0", prop["summary"])
        self.assertEqual(distill.build(self.p, BOARD, SOURCE)["id"], prop["id"])         # 同样的内容不重复生成
        self.assertFalse(skillbook.has_own(self.p, BOARD))                                  # 采纳前什么也没写
        r = self.adopt(prop)
        self.assertEqual(r["version"], "1.0")
        self.assertFalse((skillbook.board_dir(self.p, BOARD) / "SKILL.md").exists())         # 没有把原 skill 复制进来
        v = distill.versions(self.p, BOARD)
        self.assertEqual((v[0]["version"], v[0]["n_cards"]), ("1.0", 2))
        self.assertTrue(skillbook.only_distilled(self.p, BOARD))
        plan = skillbook.reading_plan(self.p, BOARD, SOURCE)
        self.assertEqual(plan["mode"], "mine")
        self.assertIn("补全逻辑", plan["text"])
        self.assertNotIn("书里的内容", plan["text"])                                        # 原 skill 不读
        self.assertTrue(all(i["rel"].startswith("蒸馏/") for i in plan["items"] if i["kind"] == "method"))
        self.assertEqual(distill.new_cards(self.p, BOARD), [])
        with self.assertRaises(distill.DistillError):
            distill.build(self.p, BOARD, SOURCE)                                              # 没有新东西

    def test_incremental_update_new_card_merge_hand_edit_flag_and_conflict(self):
        m, a, b = self.two_cards()
        self.adopt(distill.build(self.p, BOARD, SOURCE))
        pf = "蒸馏/03-考点/补全逻辑.md"
        d = skillbook.board_dir(self.p, BOARD)
        skillbook.save(self.p, BOARD, pf, skillbook._read(d / pf) + "\n我自己加的一句\n", skillbook._rev(skillbook._read(d / pf)))   # 你手改了考点文件
        m2 = distill.add_material(self.p, BOARD, "自述", "第二课", "第二课：指出相同的做法是……" * 3, whole_type="考点")
        self.card("考点", dict(POINT, name="指出相同", steps=["找共同点"]), m2, "s1", "自述")
        self.card("考点", dict(POINT, signals={"category": "", "examples": ["倘若"], "test": ""}), m2, "s1", "自述")     # 并进补全逻辑
        self.assertEqual(sorted(c["data"]["name"] for c in distill.new_cards(self.p, BOARD)), ["指出相同", "补全逻辑"])
        prop = distill.build(self.p, BOARD, SOURCE)
        self.assertEqual((prop["kind"], prop["meta"]["version"]), ("update", "1.1"))
        by = {e["path"]: e for e in prop["edits"]}
        self.assertEqual(by["蒸馏/03-考点/指出相同.md"]["action"], "new")
        self.assertEqual(by[pf]["action"], "replace")
        self.assertIn("你改过", by[pf]["flag"])                                               # 手改过的：标出来
        self.assertIn("我自己加的一句", by[pf]["before"])                                    # 有修改前的内容，界面能对比
        self.assertNotIn("蒸馏/05-例题/2026福建事业单位.md", by)                              # 没变化的不动
        # 只采纳新文件和总流程，不覆盖手改过的
        picks = [i for i, e in enumerate(prop["edits"]) if e["path"] != pf]
        r = self.adopt(prop, picks)
        self.assertEqual(r["version"], "1.1")
        self.assertIn("我自己加的一句", skillbook._read(d / pf))
        # 别处又改了：整个替换不会盖掉
        left = skillbook.proposals(self.p, BOARD)[0]
        skillbook.save(self.p, BOARD, pf, "又被改了", skillbook._rev(skillbook._read(d / pf)))
        r = skillbook.accept(self.p, BOARD, SOURCE, left["id"], [i for i, e in enumerate(left["edits"]) if not e["done"]])
        self.assertTrue(any("又被改过" in x for x in r["skipped"]))
        self.assertEqual(skillbook._read(d / pf).strip(), "又被改了")

    def test_versions_compare_restore_and_manual_save(self):
        m, a, b = self.two_cards()
        self.adopt(distill.build(self.p, BOARD, SOURCE))
        distill.update_card(self.p, BOARD, a["id"], dict(a["data"], one_line="新的一句话"))
        self.adopt(distill.build(self.p, BOARD, SOURCE))
        self.assertEqual([v["version"] for v in distill.versions(self.p, BOARD)], ["1.1", "1.0"])
        cmp = distill.compare(self.p, BOARD, "1.0", "1.1")
        self.assertEqual([c["path"] for c in cmp["changed"]], ["蒸馏/03-考点/补全逻辑.md"])
        self.assertIn("新的一句话", cmp["changed"][0]["diff"])
        distill.restore(self.p, BOARD, "1.0")
        d = skillbook.board_dir(self.p, BOARD)
        self.assertNotIn("新的一句话", skillbook._read(d / "蒸馏/03-考点/补全逻辑.md"))
        self.assertTrue(skillbook.history(self.p, BOARD, "蒸馏/03-考点/补全逻辑.md"))          # 被换掉的内容进历史
        self.assertEqual(distill.compare(self.p, BOARD, "1.0", "当前")["changed"], [])
        m3 = distill.save_version(self.p, BOARD, major=True)
        self.assertEqual(m3["version"], "2.0")

    def test_only_distilled_switch_when_skill_md_exists(self):
        self.two_cards()
        skillbook.ensure_own(self.p, BOARD, SOURCE)                                          # 原 skill 已经复制过
        self.adopt(distill.build(self.p, BOARD, SOURCE))
        self.assertNotIn("书里的内容", skillbook.reading_plan(self.p, BOARD, SOURCE)["text"])
        skillbook.set_board_setting(self.p, BOARD, "only_distilled", False)
        self.assertIn("书里的内容", skillbook.reading_plan(self.p, BOARD, SOURCE)["text"])


class PackTest(Base):
    def test_pack_import_segment_and_card_steps_with_clear_errors(self):
        m = distill.add_material(self.p, BOARD, "转写", "328课", TRANSCRIPT)
        pk = distill_ai.pack(self.p, BOARD, "segment", {"material": m["id"]})
        self.assertEqual(len(pk["parts"]), 1)
        self.assertIn("补全逻辑", pk["parts"][0]["text"])
        self.assertIn('"segments"', pk["parts"][0]["text"])
        with self.assertRaises(distill.DistillError) as c:
            distill_ai.import_result(self.p, BOARD, "segment", pk["parts"][0]["params"], "我觉得切成三段比较好")
        self.assertIn("没有可用的 JSON", str(c.exception))
        with self.assertRaises(distill.DistillError) as c:
            distill_ai.import_result(self.p, BOARD, "segment", pk["parts"][0]["params"], '{"segments": [{"type":"例题","title":"x","start":"原文没有这句话","end":"也没有"}]}')
        self.assertIn("找不到", str(c.exception))
        reply = "好的，结果如下：\n```json\n" + json.dumps(SEGMENTS, ensure_ascii=False) + "\n```"
        r = distill_ai.import_result(self.p, BOARD, "segment", pk["parts"][0]["params"], reply)
        self.assertEqual(r["segments"], 4)
        sids = [s["id"] for s in distill.get_material(self.p, BOARD, m["id"])["segments"] if s["include"]]
        cp = distill_ai.pack(self.p, BOARD, "card", {"material": m["id"], "segments": sids})
        self.assertEqual(len(cp["parts"]), 1)                                                # 两个片段合进一包
        self.assertIn("考点卡", cp["parts"][0]["text"])
        self.assertIn("例题卡", cp["parts"][0]["text"])
        self.assertNotIn("一会儿再给大家讲例题", cp["parts"][0]["text"])                       # 闲聊不在里面
        bad = json.dumps({"cards": [{"segment": "s1", "card": {"name": "补全逻辑"}}, {"segment": "s3", "card": EXAMPLE}]}, ensure_ascii=False)
        r = distill_ai.import_result(self.p, BOARD, "card", cp["parts"][0]["params"], bad)
        self.assertEqual(r["cards"], ["2026福建事业单位"])                                    # 缺做法的考点卡没通过，不影响另一张
        self.assertTrue(any("缺少做法" in e for e in r["errors"]))
        seg = {s["id"]: s for s in distill.get_material(self.p, BOARD, m["id"])["segments"]}
        self.assertIsNotNone(seg["s3"]["card"])
        self.assertIsNone(seg["s1"]["card"])

    def test_pack_splits_long_material_by_size(self):
        m = distill.add_material(self.p, BOARD, "转写", "长课", ("这是一句很长的废话，讲课讲课。" * 40 + "\n") * 40)
        pk = distill_ai.pack(self.p, BOARD, "segment", {"material": m["id"]}, size=6000)
        self.assertTrue(len(pk["parts"]) >= 3)
        self.assertTrue(all(pt["params"]["chunk"] == i for i, pt in enumerate(pk["parts"])))

    def test_flow_import_and_default_flow(self):
        self.two_cards()
        self.assertIn("总流程", distill.render_default_flow([c for c in distill.cards(self.p, BOARD) if c["kind"] == "考点"]))
        with self.assertRaises(distill.DistillError):
            distill_ai.import_result(self.p, BOARD, "flow", {}, "太短")
        distill_ai.import_result(self.p, BOARD, "flow", {}, "# 总流程\n\n1. 先看有没有逻辑连词，对照「补全逻辑」\n2. 找结论\n3. 找论据，判断缺哪一环\n4. 选补上这一环的选项")
        prop = distill.build(self.p, BOARD, SOURCE)
        self.assertIn("先看有没有逻辑连词", {e["path"]: e for e in prop["edits"]}["蒸馏/00-总流程.md"]["text"])


class FakeAITest(Base):
    def test_run_with_software_ai_segments_then_cards_and_reports_progress(self):
        m = distill.add_material(self.p, BOARD, "转写", "328课", TRANSCRIPT)

        def fake(messages, **kw):
            user = messages[1]["content"]
            if "切成片段" in user:
                return json.dumps(SEGMENTS, ensure_ascii=False)
            if "片段 s1" in user and "片段 s3" in user:
                return json.dumps({"cards": [{"segment": "s1", "card": POINT}, {"segment": "s3", "card": EXAMPLE}]}, ensure_ascii=False)
            if "片段 s3" in user:
                return json.dumps({"cards": [{"segment": "s3", "card": EXAMPLE}]}, ensure_ascii=False)
            return json.dumps({"cards": [{"segment": "s1", "card": POINT}]}, ensure_ascii=False)
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=fake) as call:
            est = distill_ai.estimate(self.p, BOARD, "card", {"material": m["id"], "segments": ["s1", "s3"]}) if False else None
            r = distill_ai.run(self.p, BOARD, "segment", {"material": m["id"]})
            self.assertIn("切出 4 个片段", r["message"])
            before = call.call_count
            est = distill_ai.estimate(self.p, BOARD, "card", {"material": m["id"], "segments": ["s1", "s3"]})
            self.assertEqual(est["calls"], 2)
            self.assertEqual(call.call_count, before)                                       # 估算不花钱
            r = distill_ai.run(self.p, BOARD, "card", {"material": m["id"], "segments": ["s1", "s3"]})
            self.assertEqual(call.call_count, before + 2)                                    # 一个片段一次调用
        self.assertEqual(len(distill.cards(self.p, BOARD)), 2)

    def test_run_without_key_is_explained_and_failure_keeps_earlier_results(self):
        m = distill.add_material(self.p, BOARD, "转写", "328课", TRANSCRIPT)
        with patch.object(ai, "available", return_value=False), self.assertRaises(skillbook.SkillError) as c:
            distill_ai.run(self.p, BOARD, "segment", {"material": m["id"]})
        self.assertIn("复制提示词", str(c.exception))
        distill_ai.import_result(self.p, BOARD, "segment", {"material": m["id"], "chunk": 0}, json.dumps(SEGMENTS, ensure_ascii=False))
        replies = [json.dumps({"cards": [{"segment": "s1", "card": POINT}]}, ensure_ascii=False), ai.AIError("AI回复达到长度上限")]

        def fake(messages, **kw):
            r = replies.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=fake), self.assertRaises(distill.DistillError) as c:
            distill_ai.run(self.p, BOARD, "card", {"material": m["id"], "segments": ["s1", "s3"]})
        self.assertIn("前面 1 个已保存", str(c.exception))
        self.assertEqual(len(distill.cards(self.p, BOARD)), 1)


class TestLoopTest(Base):
    def prepare(self):
        self.two_cards()
        self.adopt(distill.build(self.p, BOARD, SOURCE))
        self.bank([("题干%d" % i, "ABCD"[i % 4]) for i in range(1, 13)] + [("结论：人工智能艺术品本质是模仿", "C")])

    def test_needs_a_version_and_test_set_is_fixed_and_excludes_example_stems(self):
        self.two_cards()
        with self.assertRaises(distill.DistillError):
            distill.start_run(self.p, BOARD)
        self.adopt(distill.build(self.p, BOARD, SOURCE))
        self.bank([("题干%d" % i, "ABCD"[i % 4]) for i in range(1, 13)] + [("结论：人工智能艺术品本质是模仿", "C")])
        a = [q["key"] for q in distill.test_set(self.p, BOARD, 6)]
        b = [q["key"] for q in distill.test_set(self.p, BOARD, 6)]
        self.assertEqual(a, b)                                                               # 固定的一批
        self.assertNotIn("论证逻辑::013", a)                                                  # 例题卡里用过的题不当测试题
        self.assertEqual(len(distill.test_set(self.p, BOARD, 8)), 8)

    def test_grade_by_program_batches_and_pack_import(self):
        self.prepare()
        run = distill.start_run(self.p, BOARD, 6)
        self.assertEqual([len(b) for b in run["batches"]], [5, 1])
        pk = distill_ai.pack(self.p, BOARD, "test", {"run": run["id"], "batch": 0})
        text = pk["parts"][0]["text"]
        self.assertIn("补全逻辑", text)                                                         # 心法给 AI
        self.assertNotIn("正确答案", text)                                                      # 答案不给
        keys = run["batches"][0]
        right = {i: run["questions"][k]["answer"] for i, k in enumerate(keys, 1)}
        reply = json.dumps({"answers": [{"n": i, "answer": (a if i != 1 else ("A" if a != "A" else "B")), "why": "用了补全逻辑"} for i, a in right.items()]}, ensure_ascii=False)
        r = distill_ai.import_result(self.p, BOARD, "test", pk["parts"][0]["params"], reply)
        self.assertFalse(r["done"])
        with self.assertRaises(distill.DistillError) as c:
            distill_ai.import_result(self.p, BOARD, "test", {"run": run["id"], "batch": 1}, '{"answers":[{"n":1,"answer":""}]}')
        self.assertIn("第 1 题", str(c.exception))
        k2 = run["batches"][1][0]
        r = distill_ai.import_result(self.p, BOARD, "test", {"run": run["id"], "batch": 1}, json.dumps({"answers": [{"n": 1, "answer": run["questions"][k2]["answer"]}]}))
        self.assertEqual((r["done"], r["n"], r["correct"]), (True, 6, 5))                    # 程序判对错：错了一道
        v = distill.versions(self.p, BOARD)[0]
        self.assertEqual(v["test"]["correct"], 5)
        self.assertEqual(distill.overview(self.p, BOARD)["tests"][0]["n"], 6)

    def test_software_ai_runs_all_remaining_batches(self):
        self.prepare()
        run = distill.start_run(self.p, BOARD, 6)

        def fake(messages, **kw):
            n = messages[1]["content"].count("\n[")
            return json.dumps({"answers": [{"n": i, "answer": "A", "why": "x"} for i in range(1, 6)]})
        with patch.object(ai, "available", return_value=True), patch.object(ai, "chat", side_effect=fake) as call:
            self.assertEqual(distill_ai.estimate(self.p, BOARD, "test", {"run": run["id"]})["calls"], 2)
            r = distill_ai.run(self.p, BOARD, "test", {"run": run["id"]})
        self.assertEqual(call.call_count, 2)
        self.assertTrue(distill.get_result(self.p, BOARD, run["id"])["n"] == 6)

    def test_diagnose_makes_append_proposal_and_card_extra_keeps_rebuild_consistent(self):
        self.prepare()
        run = distill.start_run(self.p, BOARD, 5)
        wrong = {k: {"answer": "D" if run["questions"][k]["answer"] != "D" else "A", "why": "错用了"} for k in run["keys"]}
        distill.record_answers(self.p, BOARD, run["id"], wrong)
        reply = json.dumps({"suggestions": [{"concept": "补全逻辑", "problem": "漏了必要条件的方向", "fix": "- 必要条件的箭头指向必须的一方"}, {"concept": "新增", "problem": "缺一类陷阱", "fix": "新陷阱：偷换概念"}]}, ensure_ascii=False)
        r = distill_ai.import_result(self.p, BOARD, "diagnose", {"run": run["id"]}, reply)
        prop = skillbook.proposals(self.p, BOARD)[0]
        self.assertEqual((prop["kind"], len(prop["edits"])), ("diagnose", 2))
        self.assertEqual(prop["edits"][0]["action"], "append")
        self.assertEqual(prop["edits"][0]["path"], "蒸馏/03-考点/补全逻辑.md")
        self.assertEqual(prop["edits"][1]["action"], "new")
        res = self.adopt(prop)
        self.assertEqual(res["version"], "1.1")
        d = skillbook.board_dir(self.p, BOARD)
        self.assertIn("必要条件的箭头", skillbook._read(d / "蒸馏/03-考点/补全逻辑.md"))
        files, _ = distill.render_files(self.p, BOARD)
        self.assertEqual(files["蒸馏/03-考点/补全逻辑.md"].strip(), skillbook._read(d / "蒸馏/03-考点/补全逻辑.md").strip())   # 卡片里记了补充，重新汇总时文件一致、不会冲突
        with self.assertRaises(distill.DistillError):
            distill_ai.import_result(self.p, BOARD, "diagnose", {"run": distill.get_result(self.p, BOARD, run["id"])["id"]}, "不是 json")


class ApiTest(Base):
    def test_api_flow_state_material_pack_import_build_and_version(self):
        for body, name in (({"board": BOARD}, "state"),):
            self.assertEqual(api.distill_state(body)["materials"], [])
        added = api.distill_material_add({"board": BOARD, "kind": "转写", "title": "328课", "text": TRANSCRIPT})
        pk = api.distill_step({"board": BOARD, "step": "segment", "mode": "pack", "params": {"material": added["id"]}, "size": 6000})
        api.distill_step({"board": BOARD, "step": "segment", "mode": "import", "params": pk["parts"][0]["params"], "text": json.dumps(SEGMENTS, ensure_ascii=False)})
        st = api.distill_state({"board": BOARD})
        self.assertEqual([s["type"] for s in st["materials"][0]["segments"]], ["考点", "闲聊", "例题", "闲聊"])
        self.assertTrue(st["materials"][0]["skipped"] == [] or isinstance(st["materials"][0]["skipped"], list))
        cp = api.distill_step({"board": BOARD, "step": "card", "mode": "pack", "params": {"material": added["id"], "segments": ["s1", "s3"]}})
        api.distill_step({"board": BOARD, "step": "card", "mode": "import", "params": cp["parts"][0]["params"],
                          "text": json.dumps({"cards": [{"segment": "s1", "card": POINT}, {"segment": "s3", "card": EXAMPLE}]}, ensure_ascii=False)})
        st = api.distill_state({"board": BOARD})
        self.assertEqual((len(st["cards"]), st["n_new"]), (2, 2))
        prop = api.distill_build({"board": BOARD})["proposal"]
        r = api.skillbook_accept({"board": BOARD, "id": prop["id"], "picks": list(range(len(prop["edits"])))})
        self.assertEqual(r["version"], "1.0")
        st = api.distill_state({"board": BOARD})
        self.assertEqual((st["versions"][0]["version"], st["n_new"]), ("1.0", 0))
        card = api.distill_card({"board": BOARD, "id": st["cards"][0]["id"], "action": "get"})["card"]
        self.assertIn("data", card)
        self.assertEqual(api.distill_version({"board": BOARD, "action": "compare", "a": "1.0", "b": "当前"})["changed"], [])
        with api.open_game(save=False) as g:
            from rpg import trainer
            text, used = trainer._tutor_material(g, BOARD)
            self.assertIn("补全逻辑", text)
            self.assertNotIn("书里的内容", text)
        with self.assertRaises(api.ApiError):
            api.distill_state({"board": "不存在的板块"})
        with patch.dict(os.environ, {"SHENLUN_SUBJECT": "申论"}), patch("rpg.subjects.active", return_value="申论"), self.assertRaises(api.ApiError):
            api.distill_state({"board": BOARD})


if __name__ == "__main__":
    unittest.main()
