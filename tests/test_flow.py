"""
端到端测试：在临时文件夹里造一个迷你申论库，走一遍 面板 → 业务手册定稿 → 背诵 → 向领导汇报 → 实操 → 圆满 → 整改销号 → 专长养成
→ 年度考核 → 晋升考核 → 加班补课，外加职级、瓶颈、周例会、补卡券、过劳预警、风格切换等规则的单元测试。
AI 用假函数代替（不联网）。运行：

    python -m unittest discover -s tests -v

改了 engine / trainer 的规则后先跑这个，确认主流程没坏。
"""
import datetime as dt
import json
import shutil
import sys
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rpg import ai, api, engine, paths, skeleton, trainer  # noqa: E402

SKELETON = """---
题型: 归纳概括
状态: 草稿
来源skill: shenlun-xiaoti
---
# 归纳概括 · 骨架

## 1. 削弱题
- 【术语】否定论点：直接说论点不成立
- 【术语】拆桥：论据和论点说的不是一回事
- 【思路】先找论点和论据

## 2. 加强题
- 【术语】搭桥
- 【思路】补充论据和论点之间的联系
"""

BOARD_MD = """---
季数: 第36季
题型: 归纳概括
---

# 第36季 · 归纳概括

### 1. ✅

题干一

> [!check]- 答案
> 正确答案：**A**　我的答案：**A**　正确

> [!note] 复盘
>

---

### 2. ❌

![[S36-Q2.png]]
以下哪项最能削弱上述论证？

- **A.** 甲
- **B.** 乙

> [!check]- 答案
> 正确答案：**B**　我的答案：**A**　错误

> [!note] 复盘
> 【答案】B
> 【思路】否定论点。
> - 错因：

---
"""


def fake_chat(messages, json_mode=False, **kw):
    """假 AI：根据提示词里的关键字返回固定结果（全部判“通过”）"""
    text = messages[-1]["content"] if messages else ""
    sys_text = messages[0]["content"] if messages else ""
    if "请以你的身份对学员说一段话" in text:
        return "哎呀，学姐的现场台词。"
    if "知识骨架" in text:
        return SKELETON.split("# 归纳概括 · 骨架", 1)[1]
    if "要点是否说到了" in text:
        n = text.count("\n") and len([l for l in text.split("需要判断的思路要点（按顺序）：")[1].split("\n\n")[0].splitlines() if l.strip()])
        names = [l.split(". ", 1)[1] for l in text.split("需要判断的名称清单（按顺序）：")[1].split("\n\n")[0].splitlines() if ". " in l]
        answer = text.split("学员的默写：\n")[1].split("\n\n")[0]
        return json.dumps({"清单": [name in answer for name in names], "答到": [True] * n, "错误说法": [], "点评": "不错"})
    if "传授" in text and "同志还没学过" in text:
        return "我来讲：" + ("有例题" if "例题1：" in text else "无例题")
    if "陪学员复盘" in sys_text:
        return "主任：先看问法。" + text[:12]
    if "费曼学习法" in sys_text:
        return json.dumps({"reply": "讲得清楚", "done": True,
                           "维度": {"是什么": True, "识别信号": True, "怎么用": True, "易错": True}, "通过": True})
    if "自行举例" in text:
        return json.dumps({"通过": True, "点评": "机制清楚", "修改建议": ""})
    if "应用小题" in text and "判断学员" not in text:
        return json.dumps({"题目": "某论证……，以下哪项最能削弱？", "参考答案": "A", "参考思路": "否定论点"})
    if "判断学员对应用小题的作答" in text:
        return json.dumps({"通过": True, "点评": "对"})
    if "做错过的" in text:
        return json.dumps({"答案正确": True, "思路正确": True, "对应大项": "削弱题", "点评": "好", "正确思路": "否定论点"})
    return "好的"



def claim_all(g):
    """政绩够到哪就一层层点突破到哪（测试用）"""
    while g.realm_info()["ready"]:
        g.break_through()

class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        v = self.tmp / "申论"
        (v / "copilot/skills/shenlun-xiaoti").mkdir(parents=True)
        (v / "copilot/skills/shenlun-xiaoti/SKILL.md").write_text("---\nname: x\n---\n# 论证\n", encoding="utf-8")
        sd = v / "FB模考试卷复盘/题型复盘/第36季"
        (sd / "attachments").mkdir(parents=True)
        (sd / "10-归纳概括.md").write_text(BOARD_MD, encoding="utf-8")
        (sd / "attachments/S36-Q2.png").write_bytes(b"\x89PNG")
        (v / "训练").mkdir()   # 规则：第 1 批里只有“归纳概括”有 skill，“综合分析”没有（显示未解锁）
        (v / "训练/规则.md").write_text("- 配置版本: 1\n- 第1批: 归纳概括, 综合分析\n- 题型.归纳概括: shenlun-xiaoti | 归纳概括\n"
                                       "- 题型.综合分析: 没有这个skill | 综合分析\n", encoding="utf-8")
        self.vault = v
        # 隔离本机设置，不碰真实的 ~/.shenlun-rpg
        self._settings = paths.SETTINGS_FILE, paths.SETTINGS_DIR
        paths.SETTINGS_DIR = self.tmp / "home"
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / "settings.json"
        paths.save_settings({"vault": str(v), "api_key": "test"})
        self._chat = ai.chat
        ai.chat = fake_chat
        trainer.SESSIONS.clear()

    def tearDown(self):
        paths.SETTINGS_FILE, paths.SETTINGS_DIR = self._settings
        ai.chat = self._chat
        shutil.rmtree(self.tmp, ignore_errors=True)

    def state(self):
        return json.loads((self.vault / "训练/存档/存档.json").read_text(encoding="utf-8"))

    def run_task(self, task, answer="否定论点 拆桥 先找论点和论据 搭桥"):
        r = api.session_start({"task": dict(task, fresh=True)})
        while not r["finished"]:
            if any(b["id"] == "discuss_end" for b in r["input"].get("buttons", [])):   # 题后复盘：结束
                r = api.session_action({"session": r["session"], "action": "discuss_end"})
            elif r["input"]["mode"] == "text":
                r = api.session_reply({"session": r["session"], "text": answer})
            elif r["input"]["mode"] == "buttons":
                r = api.session_action({"session": r["session"], "action": r["input"]["buttons"][0]["id"]})
            else:
                break
        return r

    def test_daily_wrong_is_one_shared_task(self):
        d = api.dashboard({})
        wrongs = [t for t in d["plan"]["tasks"] if t["type"] == "wrong"]
        self.assertEqual([t["id"] for t in wrongs], ["wrong:daily"])     # 今日功课只有一项整改销号
        t = wrongs[0]
        self.assertIn("0/%d" % t["quota"], t["title"])
        # 整改录和今日功课用同一个 task_id，进度互通
        r = api.session_start({"task_id": "wrong:daily"})
        r = api.session_reply({"session": r["session"], "text": "削弱 否定论点 选A"})
        self.assertIn("wrong_next", [b["id"] for b in r["input"]["buttons"]])
        t = [x for x in self.state()["plan"]["tasks"] if x["id"] == "wrong:daily"][0]
        self.assertEqual(len(t["hits"]), 1)
        self.assertEqual(t["done"], t["quota"] == 1)
        # 旧版计划（一只一项）进来自动合成一项
        st = self.state()
        st["plan"]["tasks"] = [x for x in st["plan"]["tasks"] if x["type"] != "wrong"] + [
            {"id": "wrong:36|归纳概括|2", "type": "wrong", "board": "归纳概括", "title": "整改销号 · 第36季归纳概括第2题",
             "target": "36|归纳概括|2", "minutes": 5, "done": True, "ok": True, "optional": False},
            {"id": "wrong:36|归纳概括|3", "type": "wrong", "board": "归纳概括", "title": "整改销号 · 第36季归纳概括第3题",
             "target": "36|归纳概括|3", "minutes": 5, "done": False, "ok": None, "optional": False}]
        (self.vault / "训练/存档/存档.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        d = api.dashboard({})
        wrongs = [t for t in d["plan"]["tasks"] if t["type"] == "wrong"]
        self.assertEqual(len(wrongs), 1)
        self.assertEqual((wrongs[0]["quota"], wrongs[0]["hits"], wrongs[0]["minutes"]), (2, ["36|归纳概括|2"], 10))

    def test_full_flow(self):
        d = api.dashboard({})
        self.assertEqual(d["realm"]["name"], "办事员 · 试用期")
        titles = [t["title"] for t in d["plan"]["tasks"]]
        self.assertFalse(any(t["type"] in ("skeleton", "recite", "feynman", "apply") for t in d["plan"]["tasks"]))   # 办理殿改成便笺
        self.assertTrue(any("整改销号" in t for t in titles))

        # 生成业务手册 → 定稿
        r = api.session_start({"task": {"type": "skeleton", "board": "归纳概括", "target": "归纳概括", "title": "业务手册"}})
        r = api.session_action({"session": r["session"], "action": "gen"})
        self.assertIn("草稿", (self.vault / "训练/骨架/归纳概括.md").read_text(encoding="utf-8"))
        r = api.session_action({"session": r["session"], "action": "final"})
        self.assertTrue(r["finished"])
        board = [b for b in api.skeletons({})["boards"] if b["board"] == "归纳概括"][0]
        self.assertTrue(board["final"])
        self.assertEqual([i["name"] for i in board["items"]], ["削弱题", "加强题"])
        self.assertEqual(board["items"][0]["levelName"], "未接手")

        iid = "归纳概括::削弱题"
        t = {"board": "归纳概括", "target": iid, "title": "x"}
        r = self.run_task(dict(t, type="recite"), answer="否定论点，先找论点和论据")   # 缺要点“拆桥”
        self.assertTrue(any("汇报要点失败" in m["text"] for m in r["messages"]))
        # 传授：主任先讲，再追问 / 再举一例，结束后不改掌握程度
        r = api.session_start({"task": dict(t, type="teach")})
        self.assertIn("我来讲", str(r["messages"]))
        self.assertEqual([b["id"] for b in r["input"]["buttons"]], ["ask_more", "discuss_end"])
        r = api.session_action({"session": r["session"], "action": "ask_more"})
        self.assertIn("再举一个例子", str(r["messages"]))
        r = api.session_action({"session": r["session"], "action": "discuss_end"})
        self.assertTrue(r["finished"])
        self.assertEqual(self.state()["items"].get(iid, {}).get("level", 0), 0)
        # 办理记录：这次传授写进 训练/办理记录/归纳概括/<大项>.md；下次再点，往期对话折叠在最上面
        logs = list((self.vault / "训练/办理记录/归纳概括").glob("*.md"))
        self.assertEqual(len(logs), 1)
        log = logs[0].read_text(encoding="utf-8")
        self.assertIn("· 领导讲解 <!-- sid:", log)
        self.assertIn("· 汇报要点 <!-- sid:", log)          # 前面那次汇报要点也记了
        self.assertIn("我来讲", log)
        self.assertIn("🧑 我", log)                     # “再举一例”这句也记下了
        # 再点“传授”：接着上次那次传授聊（上次的对话原样摆出来，主任带着上次的上下文回答），写回同一段
        r = api.session_start({"task": dict(t, type="teach")})
        self.assertIn("接着", r["messages"][0]["text"])
        self.assertIn("我来讲", str(r["messages"]))
        self.assertEqual([b["id"] for b in r["input"]["buttons"]], ["ask_more", "fresh", "discuss_end"])
        r = api.session_reply({"session": r["session"], "text": "削弱和质疑是一回事吗"})
        self.assertIn("主任：先看问法", str(r["messages"]))
        api.session_action({"session": r["session"], "action": "discuss_end"})
        log = logs[0].read_text(encoding="utf-8")
        self.assertEqual(log.count("<!-- sid:"), 2)        # 没有新开一段
        self.assertIn("削弱和质疑是一回事吗", log)
        self.assertEqual(log.count("我来讲"), 1)          # 上次的内容没被重复写
        self.assertNotIn("接着", log)
        # 重新开始：开一次新的传授，旧的折叠在上面
        r = api.session_start({"task": dict(t, type="teach")})
        r = api.session_action({"session": r["session"], "action": "fresh"})
        self.assertTrue(r.get("replace"))
        self.assertEqual(len([m for m in r["messages"] if (m.get("fold") or "").startswith("📜 往期办理")]), 2)
        api.session_action({"session": r["session"], "action": "discuss_end"})
        self.assertEqual(logs[0].read_text(encoding="utf-8").count("<!-- sid:"), 3)
        self.run_task(dict(t, type="recite"))
        self.run_task(dict(t, type="recite"))
        self.assertEqual(self.state()["items"][iid]["level"], 1)
        self.run_task(dict(t, type="feynman"))
        self.assertEqual(self.state()["items"][iid]["level"], 2)
        self.run_task(dict(t, type="example"))
        self.run_task(dict(t, type="apply"))
        self.run_task(dict(t, type="apply"))
        self.assertEqual(self.state()["items"][iid]["level"], 3)

        r = api.session_start({"task": {"type": "wrong", "board": "归纳概括", "target": "36|归纳概括|2", "title": "整改"}})
        self.assertTrue(any(b["t"] == "img" for m in r["messages"] for b in m.get("blocks", [])))
        self.run_task({"type": "wrong", "board": "归纳概括", "target": "36|归纳概括|2", "title": "整改"})
        self.assertEqual(self.state()["wrong"]["36|归纳概括|2"]["status"], "done")

        # 自选题型整改销号（不指定哪题）→ 判完进入复盘，可以追问、请领导解惑，点结束才收工
        r = api.session_start({"task": {"type": "wrong", "board": "归纳概括", "target": "", "title": "整改"}})
        r = api.session_reply({"session": r["session"], "text": "削弱 否定论点 选A"})
        self.assertFalse(r["finished"])
        self.assertEqual([b["id"] for b in r["input"]["buttons"]], ["ask_explain", "wrong_next", "discuss_end"])
        r = api.session_reply({"session": r["session"], "text": "为什么不选B"})
        self.assertIn("主任：先看问法。为什么不选B", str(r["messages"]))
        r = api.session_action({"session": r["session"], "action": "ask_explain"})
        self.assertIn("请按 skill 的方法", str(r["messages"]))
        self.assertIn("已存入复盘解析", str(r["messages"]))
        r = api.session_action({"session": r["session"], "action": "ask_explain"})     # 再问一次：换掉，不重复
        files = [f for f in (self.vault / "FB模考试卷复盘").rglob("*.md") if "领导解惑" in f.read_text(encoding="utf-8")]
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding="utf-8")
        self.assertEqual(text.count("🧙 领导解惑"), 1)
        self.assertIn("> 主任：先看问法。请按 skill 的方法", text)
        r = api.session_action({"session": r["session"], "action": "discuss_end"})
        self.assertTrue(r["finished"])

        # 另一重也圆满 → 阶段打通、论证专长养成
        api.plan_regenerate({})
        t2 = {"board": "归纳概括", "target": "归纳概括::加强题", "title": "x"}
        for typ in ("recite", "recite", "feynman", "example", "apply", "apply"):
            self.run_task(dict(t2, type=typ))
        s = self.state()
        self.assertIn(1, s["cleared"]["1"])
        self.assertTrue(s["roots"]["归纳概括"]["on"])

        # 政绩推到副科线 → 瓶颈；两次考核 ≥ 60 → 可以晋升考核
        with api.open_game() as g:
            g.state["xp"] = int(g.xp_at(61)) + 10
            self.assertTrue(g.realm_info()["ready"])           # 政绩圆满不自动升，自己点突破
            while g.realm_info()["ready"]:
                g.break_through()
            info = g.realm_info()
        self.assertTrue(info["bottleneck"])
        self.assertEqual(info["name"], "科员九级")
        self.assertFalse(api.dashboard({})["trib"]["ready"])
        api.boss({"name": "第37季", "score": 61})
        api.boss({"name": "第38季", "score": 63})
        d = api.dashboard({})
        self.assertTrue(d["trib"]["ready"], d["trib"])
        self.assertEqual(d["trib"]["pills"], 2)   # 每次考核达到 60 分奖励一颗副科推荐函
        self.assertTrue(any(t["type"] == "tribulation" for t in d["plan"]["tasks"]) or api.plan_regenerate({}))
        r = self.run_task({"type": "tribulation", "board": "", "target": "60", "title": "晋升考核"})
        self.assertIn(60, self.state()["gates"])
        self.assertTrue(any(e.get("kind") == "realm" and e.get("major") for e in r["events"]))
        self.assertTrue(api.dashboard({})["realm"]["name"].startswith("副科级"))

        # 加班补课：一炉归纳概括，补课完成后额外政绩
        xp0 = self.state()["xp"]
        r = self.run_task({"type": "alchemy", "board": "归纳概括", "target": "归纳概括", "title": "加班补课"})
        self.assertTrue(any("提炼补课券" in e.get("msg", "") for e in r["events"]))
        self.assertGreater(self.state()["xp"], xp0)
        self.assertEqual(self.state()["pills"][-1]["grade"], "优秀")


    def test_time_split(self):
        with api.open_game() as g:
            g.add_seconds(600, "practice")
            g.add_seconds(1200, "review")
            g.state["seconds"]["2020-01-01"] = 300              # 旧存档：没分类的算复习
        api.practice({"board": "大作文", "total": "5", "correct": "4", "minutes": "30"})
        api.lecture_add({"minutes": 20})
        d = api.dashboard({})
        self.assertEqual(d["timesplit"]["today"], {"lecture": 20, "practice": 40, "review": 20, "self": 30, "self_review": 0})
        self.assertEqual(d["timesplit"]["all"]["review"], 25)
        self.assertEqual(d["timesplit"]["week"]["review"], 20)
        trainer.SESSIONS["x"] = {"type": "wrong"}
        self.assertEqual(trainer.study_kind("x"), "practice")
        trainer.SESSIONS["x"] = {"type": "recite"}
        self.assertEqual(trainer.study_kind("x"), "review")


    def test_selfstudy(self):
        old = self.vault / "训练/红尘历练"               # 旧版自练日志文件夹：第一次记自练时搬到 自练录
        old.mkdir(parents=True)
        (old / "2026-09.md").write_text("# 旧日志\n", encoding="utf-8")
        api.practice({"board": "归纳概括", "total": "5", "correct": "5", "minutes": "10"})
        self.assertFalse(old.exists())
        self.assertTrue((self.vault / "训练/自练录/2026-09.md").exists())
        xp0 = self.state()["xp"]
        api.selfstudy_add({"board": "归纳概括", "minutes": 40, "topic": "削弱题要点", "note": "他因还不熟"})
        api.selfstudy_add({"minutes": 20})
        d = api.dashboard({})
        self.assertEqual([x["minutes"] for x in d["selfstudy"]], [20, 40])
        self.assertEqual(d["timesplit"]["today"]["self_review"], 60)
        self.assertEqual(d["timesplit"]["today"]["review"], 60)
        self.assertEqual(d["timesplit"]["today"]["practice"], 10)
        bt = {b["board"]: b for b in d["boardtime"]["today"]["boards"]}
        self.assertEqual(bt["归纳概括"]["review"], 40)
        self.assertEqual(d["boardtime"]["today"]["loose"], 0)          # 不分模块的 20 分钟静修不再被分摊
        self.assertGreater(self.state()["xp"], xp0)
        text = next((self.vault / "训练/静修录").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("归纳概括 · 削弱题要点 · 40 分钟", text)
        self.assertIn("他因还不熟", text)
        api.selfstudy_delete({"id": d["selfstudy"][1]["id"]})
        self.assertEqual(api.dashboard({})["timesplit"]["today"]["self_review"], 20)
        with self.assertRaises(api.ApiError):
            api.selfstudy_add({"minutes": 0})




    def test_tribulation_failure_needs_healing(self):
        (self.vault / "训练/骨架").mkdir(parents=True, exist_ok=True)
        (self.vault / "训练/骨架/归纳概括.md").write_text(SKELETON.replace("状态: 草稿", "状态: 已定稿"), encoding="utf-8")
        with api.open_game() as g:
            for it in g.final_items("归纳概括"):
                g.item(it["id"]).update(level=3, stage=0, next="2099-01-01")
            g.state["xp"] = int(g.xp_at(60.5))
            g.state["boss"] = [{"d": g.t, "name": "a", "score": 60, "kind": "考核"}, {"d": g.t, "name": "b", "score": 60, "kind": "考核"}]
            g.housekeeping()
        self.assertTrue(api.dashboard({})["trib"]["ready"])
        ai.chat = fake_chat
        r = self.run_task({"type": "tribulation", "board": "", "target": "60", "title": "晋升考核"}, answer="不记得了")
        s = self.state()
        self.assertNotIn(60, s["gates"])
        self.assertTrue(s["trib"]["cooldown"])
        self.assertEqual(len(s["trib"]["heal"]), 1)
        d = api.dashboard({})
        self.assertFalse(d["trib"]["ready"])
        self.assertTrue(any(t["title"].startswith("补救") for t in d["plan"]["tasks"]))

    def test_ai_tutor(self):
        d = api.dashboard({})
        self.assertTrue(d["greet_pending"])
        self.assertEqual(api.tutor_greet({})["text"], "哎呀，学姐的现场台词。")
        d = api.dashboard({})
        self.assertFalse(d["greet_pending"])
        self.assertEqual(d["persona"]["tutor"], "陈主任")
        self.assertEqual(d["theme"]["terms"]["skeleton"], "业务手册")
        with api.open_game() as g:                      # 里程碑台词被换成 AI 现场说的
            ev = g._award(int(g.xp_at(52)), "bonus", note="测试", bonus=False)
            self.assertTrue(any(e.get("kind") == "ready" for e in ev))   # 政绩圆满：提醒去点突破
            ev = api.tutor.enrich(g, g.break_through())
        self.assertTrue(any(e.get("kind") == "realm" for e in ev))
        self.assertIn("哎呀，学姐的现场台词。", [e.get("msg") for e in ev])

    def test_no_ai_self_rating(self):
        paths.save_settings({"vault": str(self.vault)})  # 没有 key
        self.assertFalse(ai.available())
        (self.vault / "训练/骨架").mkdir(parents=True, exist_ok=True)
        (self.vault / "训练/骨架/归纳概括.md").write_text(SKELETON.replace("状态: 草稿", "状态: 已定稿"), encoding="utf-8")
        r = api.session_start({"task": {"type": "recite", "board": "归纳概括", "target": "归纳概括::加强题", "title": "x", "fresh": True}})
        r = api.session_reply({"session": r["session"], "text": "搭桥 补充联系"})
        self.assertEqual(r["input"]["mode"], "buttons")
        r = api.session_action({"session": r["session"], "action": "self_ok"})
        self.assertTrue(r["finished"])
        self.assertEqual(self.state()["items"]["归纳概括::加强题"]["l1"], 1)
        with self.assertRaises(trainer.TrainError):
            api.session_start({"task": {"type": "feynman", "board": "归纳概括", "target": "归纳概括::加强题", "title": "x", "fresh": True}})

    def test_tired_does_not_consume_task(self):
        (self.vault / "训练/骨架").mkdir(parents=True, exist_ok=True)
        (self.vault / "训练/骨架/归纳概括.md").write_text(SKELETON.replace("状态: 草稿", "状态: 已定稿"), encoding="utf-8")
        r = api.session_start({"task": {"type": "recite", "board": "归纳概括", "target": "归纳概括::加强题", "title": "x", "fresh": True}})
        r2 = api.session_reply({"session": r["session"], "text": "好累啊不想学了"})
        self.assertFalse(r2["finished"])
        self.assertEqual(r2["input"]["mode"], "text")
        self.assertEqual(self.state()["xp"], 0)

    def test_time_counts_only_while_studying(self):
        (self.vault / "训练/骨架").mkdir(parents=True, exist_ok=True)
        (self.vault / "训练/骨架/归纳概括.md").write_text(SKELETON.replace("状态: 草稿", "状态: 已定稿"), encoding="utf-8")
        self.assertEqual(api.heartbeat({"seconds": 30})["minutes"], 0)                   # 只是开着网页
        chat = api.session_start({"task": {"type": "chat", "board": "", "target": "", "title": "聊天"}})
        r = api.heartbeat({"seconds": 60, "session": chat["session"]})                     # 和导师闲聊
        self.assertFalse(r["studying"])
        self.assertEqual(r["minutes"], 0)
        s = api.session_start({"task": {"type": "recite", "board": "归纳概括", "target": "归纳概括::加强题", "title": "x", "fresh": True}})
        self.assertTrue(api.heartbeat({"seconds": 60, "session": s["session"]})["studying"])
        self.assertEqual(api.heartbeat({"seconds": 60, "session": s["session"]})["minutes"], 2)   # 做功课才计时
        api.session_reply({"session": s["session"], "text": "搭桥 补充论据和论点之间的联系"})
        self.assertEqual(api.heartbeat({"seconds": 60, "session": s["session"]})["minutes"], 3)   # 刚做完看解析也算
        self.assertFalse(api.heartbeat({"seconds": 60, "session": "不存在"})["studying"])

    def test_notes_writing_counts_as_review(self):
        """公务手账：1 分钟内真的写过字（存过有变化的笔迹）才算复习时间；只开着本子、或停笔太久不算"""
        from rpg import notes
        nid = api.notes_save({"title": "公务手账", "pages": [{"strokes": []}]})["id"]
        self.assertFalse(api.heartbeat({"seconds": 30, "notes": nid})["studying"])          # 新本子还没写
        api.notes_save({"id": nid, "pages": [{"strokes": [{"t": "pen", "c": "#222", "w": 3, "p": [[1, 2], [3, 4]]}]}]})
        r = api.heartbeat({"seconds": 60, "notes": nid})
        self.assertTrue(r["studying"])
        self.assertEqual(r["minutes"], 1)
        api.notes_save({"id": nid, "title": "改个名"})                                      # 只改名字不算写字
        notes.LAST_WRITE[nid] -= 200                                                        # 停笔 3 分多钟
        r = api.heartbeat({"seconds": 60, "notes": nid})
        self.assertFalse(r["studying"])
        self.assertEqual(r["minutes"], 1)
        self.assertFalse(api.heartbeat({"seconds": 60, "notes": "不存在的本子"})["studying"])



    def test_qi_deviation_after_repeated_failures(self):
        (self.vault / "训练/骨架").mkdir(parents=True, exist_ok=True)
        (self.vault / "训练/骨架/归纳概括.md").write_text(SKELETON.replace("状态: 草稿", "状态: 已定稿"), encoding="utf-8")
        task = {"type": "recite", "board": "归纳概括", "target": "归纳概括::加强题", "title": "x"}
        for _ in range(5):
            self.run_task(task, answer="忘了")
        with self.assertRaises(trainer.TrainError):
            api.session_start({"task": dict(task, fresh=True)})
        self.assertGreater(api.dashboard({})["rest"], 0)

    def test_semantic_recall_synonyms_errors_and_malformed_result(self):
        bone = self.vault / "训练/骨架/归纳概括.md"
        bone.parent.mkdir(parents=True, exist_ok=True)
        bone.write_text(SKELETON.replace("状态: 草稿", "状态: 已定稿"), encoding="utf-8")
        task = {"type": "recite", "board": "归纳概括", "target": "归纳概括::削弱题", "title": "x"}
        # 没有字面命中两个术语，但语义对应完整，AI按含义通过。
        ai.chat = lambda m, **kw: json.dumps({"清单": [True, True], "答到": [True, True, True], "错误说法": [], "点评": "含义正确"})
        r = self.run_task(task, "否认主张，以及破坏证据到主张的联系")
        self.assertTrue(any("成功" in m["text"] for m in r["messages"]))
        ai.chat = lambda m, **kw: json.dumps({"清单": [True, True], "答到": [True, True, True], "错误说法": ["把共现当因果"], "点评": "混淆"})
        self.run_task(task)
        self.assertEqual(self.state()["items"][task["target"]]["l1"], 0)
        ai.chat = lambda m, **kw: json.dumps({"清单": ["true"], "答到": [], "错误说法": []})
        r = api.session_start({"task": dict(task, fresh=True)})
        xp = self.state()["xp"]
        with self.assertRaises(trainer.TrainError):
            api.session_reply({"session": r["session"], "text": "讲解"})
        self.assertEqual(self.state()["xp"], xp)

    def test_example_gate_and_legacy_mastery(self):
        with api.open_game() as g:
            iid = "归纳概括::测试举例"
            st = g.item(iid)
            st["level"] = 2
            g.on_apply(iid, True)
            self.assertEqual(st["l3"], 0)
            g.on_example(iid, False)
            self.assertFalse(st["example_ok"])
            g.on_example(iid, True)
            g.on_apply(iid, True)
            self.assertEqual(st["l3"], 1)
            g.state["items"]["旧圆满::方法"] = {"level": 3}
            self.assertTrue(g.item("旧圆满::方法")["example_ok"])

    def test_full_chapter_body_and_example_not_recall_point(self):
        from rpg import skeleton, vault
        folder = self.vault / "copilot/skills/shenlun-xiaoti/chapters"
        folder.mkdir()
        (folder / "ch02.md").write_text("## 方法\n正文里的具体边界条件", encoding="utf-8")
        with api.open_game(save=False) as g:
            digest = vault.skill_digest(g.paths, "shenlun-xiaoti")
        self.assertIn("正文里的具体边界条件", digest)
        it = skeleton.parse("## 方法\n- 【思路】解释机制\n- 【举例】自行编情境", "归纳概括")["items"][0]
        self.assertEqual(it["thoughts"], ["解释机制"])
        self.assertEqual(it["examples"], ["自行编情境"])

    def test_unverified_draft_cannot_finalize(self):
        bone = self.vault / "训练/骨架/归纳概括.md"
        bone.parent.mkdir(parents=True, exist_ok=True)
        bone.write_text("---\n状态: 草稿\n---\n## 方法\n> 待核对：补充章节定义\n- 【术语】建立联系", encoding="utf-8")
        r = api.session_start({"task": {"type": "skeleton", "board": "归纳概括", "title": "审核"}})
        with self.assertRaises(trainer.TrainError):
            api.session_action({"session": r["session"], "action": "final"})
        self.assertIn("状态: 草稿", bone.read_text(encoding="utf-8"))



class MigrationTest(unittest.TestCase):
    def test_old_config_is_backed_up_and_replaced(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            v = tmp / "申论"
            (v / "copilot/skills").mkdir(parents=True)
            (v / "训练").mkdir()
            (v / "训练/角色设定.md").write_text("- 配置版本: 0\n- 官场.导师名: 老张\n", encoding="utf-8")  # 第二版的文件
            (v / "训练/规则.md").write_text((ROOT / "defaults/规则.md").read_text(encoding="utf-8"), encoding="utf-8")
            up = paths.Paths(v).ensure_train_dir()
            self.assertEqual(up, ["角色设定.md"])  # 台词库不存在 → 直接新建，不算升级
            self.assertIn("陈主任", (v / "训练/角色设定.md").read_text(encoding="utf-8"))
            self.assertIn("老张", (v / "训练/角色设定.旧版.md").read_text(encoding="utf-8"))
            self.assertTrue((v / "训练/台词库.md").exists())
            self.assertEqual(paths.Paths(v).ensure_train_dir(), [])
        finally:
            paths.UPGRADED.clear()
            shutil.rmtree(tmp, ignore_errors=True)



    def test_old_save_gates_are_reset(self):
        from rpg import store
        tmp = Path(tempfile.mkdtemp())
        try:
            v = tmp / "申论"
            (v / "copilot/skills").mkdir(parents=True)
            p = paths.Paths(v)
            p.ensure_train_dir()
            (v / "训练/存档/存档.json").write_text(json.dumps({"version": 1, "created": "2026-09-29", "xp": 500, "gates": [30]}),
                                                  encoding="utf-8")
            st = store.Store(p).load(dt.date(2026, 10, 1))
            self.assertEqual(st["gates"], [])
            self.assertEqual(st["xp"], 500)
            self.assertEqual(st["theme"], "官场")
        finally:
            paths.UPGRADED.clear()
            shutil.rmtree(tmp, ignore_errors=True)


class EngineTest(unittest.TestCase):
    def make(self, today, state=None, theme="官场"):
        import random
        from rpg import config, store
        p = paths.Paths(None)
        st = state or store.new_state(today)
        st["theme"] = theme
        return engine.Game(p, config.Rules(), config.Persona("", theme), config.Lines(), st, today, rng=random.Random(1))

    def test_realm_table(self):
        from rpg import themes
        names = {s: themes.realm_name("官场", s) for s in (50, 51, 53, 59, 60, 61, 62, 63, 64, 65, 69, 70, 80, 84, 85, 92)}
        self.assertEqual(names[50], "办事员 · 试用期")
        self.assertEqual(names[51], "科员一级")
        self.assertEqual(names[53], "科员三级")
        self.assertEqual(names[59], "科员九级")
        self.assertEqual([names[x] for x in (60, 61, 62, 63, 64)], ["副科级初任", "副科级初任", "副科级在任", "副科级在任", "副科级资深"])
        self.assertEqual([names[x] for x in (65, 69, 70)], ["正科级初任", "正科级资深", "副处级初任"])
        self.assertEqual([names[x] for x in (80, 84, 85, 92)], ["副厅级初任", "副厅级资深", "正厅级", "正厅级"])

    def test_score_follows_xp_and_target_date(self):
        g = self.make(dt.date(2026, 9, 29))
        total = 300 * (dt.date(2027, 12, 1) - dt.date(2026, 9, 29)).days
        g.state["xp"] = total
        g.state["gates"] = [60, 65, 70, 75, 80]
        self.assertAlmostEqual(g.realm_info()["score"], 80.0, places=1)   # 目标日的理想政绩 = 80 分
        g.state["xp"] = int(g.xp_at(51)) + 1                                # 前快后慢：练气一层只要理想政绩的一小部分
        self.assertLess(g.state["xp"], total / 100)
        g.state["xp"] = total
        g.state["xp"] = int(g.xp_at(86))
        claim_all(g)
        self.assertEqual(g.realm_info()["name"], "副厅级资深")               # 85 分线要晋升考核 → 卡在 84.99
        self.assertTrue(g.realm_info()["bottleneck"])

    def test_bottleneck_and_calibration_by_contest(self):
        g = self.make(dt.date(2026, 10, 1))
        g.add_boss("第37季", 57)
        self.assertEqual(g.realm_info()["name"], "办事员 · 试用期")   # 只有一次，不校准
        g.add_boss("第38季", 58)
        self.assertEqual(g.realm_info()["name"], "办事员 · 试用期")   # 政绩补上了，但要自己点突破
        self.assertEqual(g.realm_info()["ready_count"], 7)
        claim_all(g)
        self.assertEqual(g.realm_info()["name"], "科员七级")        # min(57, 58) = 57 → 直接跨到科员七级
        self.assertLessEqual(g.ideal()["diff_days"], 2)              # 考核认定的政绩不算年度目标进度
        g.add_boss("第39季", 66)
        g.add_boss("第40季", 64)
        claim_all(g)
        info = g.realm_info()
        self.assertEqual(info["name"], "科员九级")                  # 政绩补到 64，但副科级要晋升考核
        self.assertTrue(info["bottleneck"])
        st = g.tribulation_status()
        self.assertEqual(st["gate"], 60)
        self.assertTrue(st["conds"][1]["ok"])                       # 最近两次考核都 ≥ 60
        self.assertFalse(st["conds"][2]["ok"])                      # 还没养成专长

    def test_root_grades(self):
        from rpg import config
        r = config.Rules()
        self.assertEqual(r.root_thresholds("归纳概括"), [0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9])
        self.assertEqual(r.gate_roots(75), {"激活": 7, 1: 4, 2: 1})

    def test_streak_halves_on_miss_and_heart_pill(self):
        t = dt.date(2026, 10, 10)
        g = self.make(t)
        g.state["created"] = "2026-10-01"
        for d in range(1, 9):  # 10/1–10/8 学了，10/9 没学
            g.state["seconds"][f"2026-10-0{d}"] = 3600
        run, bonus = g.streak()
        self.assertEqual(run, 0)
        self.assertAlmostEqual(bonus, 0.08)
        g.bag_add("补卡券")
        g.housekeeping()                                            # 10/9 自动服补卡券
        self.assertEqual(g.streak()[0], 9)
        self.assertEqual(g.state["bag"]["补卡券"], 0)

    def test_ideal_line_and_dao(self):
        g = self.make(dt.date(2026, 10, 9))
        g.state["created"] = "2026-09-29"
        self.assertEqual(g.ideal()["diff_days"], 10.0)
        g.state["leave"] = ["2026-10-01"]
        self.assertEqual(g.ideal()["diff_days"], 9.0)
        self.assertEqual(g.dao(), 36)                               # 近 14 天：开始前 4 天 + 调休 1 天 = 5/14

    def test_weekly_quests(self):
        g = self.make(dt.date(2026, 10, 7))
        for _ in range(20):
            g._award(15, "wrong", "归纳概括", "", True, "斩", bonus=False)
        ev = g.housekeeping()
        self.assertTrue(any("周例会完成：整改销号" in e.get("msg", "") for e in ev))
        self.assertNotIn("all", g.state["weekly"][g.week_key()])


if __name__ == "__main__":
    unittest.main()

