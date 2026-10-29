"""宗门大比：每周粉笔模考的成绩与走势。

- 每一季的对错来自 FB模考试卷复盘/板块复盘/第N季/NN-板块.md（✅ 对、❌ 错、⚪ 没做），自动统计各模块正确率；
- 粉笔成绩单上的数字（我的分数、大比平均分、最高分、已击败、排名 / 总人数、各模块用时、各模块得分）在大比页录入，
  存在存档 state["mocks"]["<季>"]；
- 各模块得分没录时估算：按答对题数折到总分（每道题同分；录了总分就按总分等比例分）；
- 导入一份模考试卷（拆分 PDF 或导入那一季）时，给演武 · 历练记记一笔 120 分钟（每季只记一次）。
"""
import datetime as dt

from . import vault

# 六大模块 ← 拆分出来的 13 个板块文件
MODULES = (
    ("政治理论", ("政治理论",)),
    ("常识判断", ("常识判断",)),
    ("言语理解", ("逻辑填空", "中心理解", "语句排序", "片段阅读")),
    ("数量关系", ("数量关系",)),
    ("判断推理", ("图形推理", "定义判断", "类比关系", "类比推理", "论证逻辑", "形式逻辑", "一拖五")),
    ("资料分析", ("资料分析",)),
)
MODULE_OF = {b: m for m, bs in MODULES for b in bs}
MODULE_NAMES = [m for m, _ in MODULES]
IMPORT_MINUTES = 120
FIELDS = ("score", "avg", "top", "beat", "rank", "people")


class MockError(Exception):
    pass


def season_name(g, n):
    """这一场模考给人看的名字：整卷考试的试卷用自己的名字（如“花生26下模拟卷第一套”），旧的粉笔季仍叫“第N季”。内部编号n不变。"""
    rec = g.state.get("mocks", {}).get(str(n), {})
    return str(rec.get("name") or "").strip() or "第%d季" % n


def safe_name(name):
    """名字用在文件名里：去掉不能做文件名的字符"""
    import re
    return re.sub(r'[\\/:*?"<>|\s]+', "", str(name))[:40] or "未命名"


def exam_date(value):
    """考试日共用唯一ISO字段；旧空日期不猜测，不因图表读取改存档。"""
    if not value:
        return ''
    try:
        value = str(value)
        parsed = dt.date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return value
    except (TypeError, ValueError):
        raise MockError('考试日期请填写有效的年月日')


def chronological_key(record):
    # 无日期旧成绩先按原季序保留；同日按原季序稳定排列。
    return (record.get('date') or '', record['season'])


def _num(v, lo=None, hi=None, integer=False):
    if v in (None, ""):
        return None
    try:
        x = int(v) if integer else round(float(v), 2)
    except (TypeError, ValueError):
        raise MockError("「%s」不是数字" % v)
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise MockError("数字 %s 超出范围" % v)
    return x


# 粉笔模考的题型分布是固定的：言语 30 题 = 逻辑填空 15 + 片段阅读 10 + 语句表达 5；
# 判断 35 题 = 图形推理 10 + 定义判断 10 + 类比推理 5 + 论证逻辑 5 + 一拖五 5。拆试卷时按题干猜的题型会有出入，
# 统计各小板块就按题号位置算（题数对得上才这样算，对不上按拆出来的文件）
FIXED = {"言语理解": (("逻辑填空", 15), ("片段阅读", 10), ("语句表达", 5)),
         "判断推理": (("图形推理", 10), ("定义判断", 10), ("类比推理", 5), ("论证逻辑", 5), ("一拖五", 5))}


def season_counts(paths, season_dir):
    """{模块: {"boards": {小板块: [对, 错, 没做, 总]}, "ok", "total", "done"}}"""
    out = {m: {"boards": {}, "ok": 0, "total": 0, "done": 0} for m in MODULE_NAMES}
    icons = {m: {} for m in MODULE_NAMES}      # 模块 → {题号: 图标}
    for f in sorted(season_dir.glob("[0-9][0-9]-*.md")):
        board = f.stem[3:]
        m = MODULE_OF.get(board)
        if not m:
            continue
        qs = vault.parse_board_file(f)
        for q in qs:
            icons[m][q["num"]] = q["icon"]
        v = out[m]["boards"].setdefault(board, [0, 0, 0, 0])
        v[0] += sum(q["icon"] == "✅" for q in qs)
        v[1] += sum(q["icon"] == "❌" for q in qs)
        v[2] += sum(q["icon"] == "⚪" for q in qs)
        v[3] += len(qs)
    for m, nums in icons.items():
        c = out[m]
        c["ok"] = sum(i == "✅" for i in nums.values())
        c["done"] = sum(i != "⚪" for i in nums.values())
        c["total"] = len(nums)
        fixed = FIXED.get(m)
        if fixed and len(nums) == sum(n for _, n in fixed):
            order = sorted(nums)
            c["boards"], k = {}, 0
            for name, n in fixed:
                part = [nums[x] for x in order[k:k + n]]
                c["boards"][name] = [part.count("✅"), part.count("❌"), part.count("⚪"), n]
                k += n
    return out


def _boss_score(g, n):
    """修仙录里以前记的大比成绩（名字里有“第N季”或“N季”）"""
    for b in reversed(g.state.get("boss", [])):
        if b.get("kind", "大比") == "大比" and ("第%d季" % n in b["name"] or "%d季" % n in b["name"]):
            return b["score"]
    return None


def unhide(g, season):
    """这一季重新导入或录了成绩：重新出现在考情/战绩里"""
    hidden = g.state.get("mocks_hidden")
    if hidden and str(season) in [str(x) for x in hidden]:
        g.state["mocks_hidden"] = [x for x in hidden if str(x) != str(season)]


def _credited(g, n):
    """这一季的录分奖励以前领过（删除记录后重新录分不重复发）"""
    return str(n) in [str(x) for x in g.state.get("mock_boss_credited", [])]


def _mark_credited(g, n):
    c = g.state.setdefault("mock_boss_credited", [])
    if str(n) not in [str(x) for x in c]:
        c.append(str(n))


def set_score(g, n, score, source):
    """只更新这一季的总分和来源（不动成绩单里的其他字段）。第一次有分时和录入一样记进宗门大比，奖励只发一次"""
    rec = g.state.setdefault("mocks", {}).setdefault(str(n), {})
    had = rec.get("score") is not None or _boss_score(g, n) is not None or _credited(g, n)
    rec["score"] = _num(score, 0, 100)
    rec["score_source"] = source if source in ("html", "estimate", "ocr", "manual", "exam") else "manual"
    rec["date"] = str(rec.get("date") or g.t)[:10]
    unhide(g, n)
    if rec["score"] is not None and not had:
        _mark_credited(g, n)
        return g.add_boss(season_name(g, n), rec["score"])
    return []


def summary(g):
    data = g.state.setdefault("mocks", {})
    hidden = set(str(x) for x in g.state.get("mocks_hidden", []))      # 在“录入”里删除的季：考情、复盘、战绩一并不显示（可恢复）
    seasons = []
    for n, d in vault.seasons(g.paths):
        if str(n) in hidden:
            continue
        counts = season_counts(g.paths, d)
        total_q = sum(c["total"] for c in counts.values())
        if not total_q:
            continue
        rec = data.get(str(n), {})
        score = rec.get("score")
        if score is None:
            score = _boss_score(g, n)
        estimate=None
        if g.subject=='行测':
            from . import mock_score
            estimate=mock_score.estimate(g,d,counts,rec)
        mods = []
        report = rec.get("report") or {}
        for m, r in report.get("modules", {}).items():          # 没导入答题卡截图的模块：用成绩截图里的“共几题、答对几题”
            c = counts.get(m)
            if c and c["total"] and not c["done"] and r.get("total") == c["total"]:
                c["ok"] = r["ok"]
                c["done"] = r["total"]
                c["boards"] = {b: [x["ok"], x["total"] - x["ok"], 0, x["total"]] for b, x in report.get("sub", {}).get(m, {}).items()} or c["boards"]
        ok_all = sum(c["ok"] for c in counts.values())
        for m in MODULE_NAMES:
            c = counts[m]
            if not c["total"]:
                continue
            if estimate and estimate['ready']:
                est=estimate['modules'].get(m,0)
            elif score is not None and ok_all:
                est = score * c["ok"] / ok_all
            else:
                est = 100 * c["ok"] / total_q
            real = (rec.get("scores") or {}).get(m)
            mods.append({"name": m, "ok": c["ok"], "total": c["total"], "acc": c["ok"] / c["total"],
                         "score": real if real is not None else round(est, 2), "estimated": real is None,
                         "minutes": (rec.get("minutes") or {}).get(m),
                         "boards": [{"board": b, "ok": v[0], "wrong": v[1], "blank": v[2], "total": v[3]} for b, v in c["boards"].items()]})
        mins = [x["minutes"] for x in mods if x["minutes"] is not None]
        rv = rec.get("reviewed") or {}             # 大比复盘：各板块复盘过哪些题（trainer.mock_review）
        pos = rec.get("review_pos") or {}          # “暂时离开”停在哪题
        review = []
        for f in sorted(d.glob("[0-9][0-9]-*.md")):
            qs = vault.parse_board_file(f)
            if qs:
                b = f.stem[3:]
                review.append({"board": b, "total": len(qs), "ok": sum(q["icon"] == "✅" for q in qs),
                               "wrong": sum(q["icon"] == "❌" for q in qs), "blank": sum(q["icon"] == "⚪" for q in qs),
                               "reviewed": len(set(rv.get(b, [])) & {q["num"] for q in qs}), "resume": pos.get(b)})
        seasons.append({"season": n, "name": season_name(g, n), "date": rec.get("date", ""), "score": score, "score_from_boss": rec.get("score") is None and score is not None,
                        "estimate":estimate,"reported_score":(rec.get("html_import") or {}).get("reported_score"),
                        "score_source":rec.get("score_source","manual"),
                        **{k: rec.get(k) for k in FIELDS[1:]},
                        "ok": ok_all, "total": total_q, "acc": ok_all / total_q,
                        "minutes": sum(mins) if mins else None, "modules": mods,
                        "imported": str(n) in g.state.get("mock_practice", []), "review": review,
                        "exam": __import__("rpg.exam_room", fromlist=["x"]).season_exam_info(rec) if g.subject == "行测" else None})
    seasons.sort(key=chronological_key)
    scored = [s for s in seasons if s["score"] is not None]
    mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    overall = {
        "count": len(seasons), "scored": len(scored),
        "mean": mean([s["score"] for s in scored]),
        "best": max((s["score"] for s in scored), default=None),
        "latest": scored[-1]["score"] if scored else None,
        "mean_avg": mean([s["avg"] for s in seasons if s.get("avg") is not None]),
        "mean_beat": mean([s["beat"] for s in seasons if s.get("beat") is not None]),
        "latest_rank": next(({"rank": s["rank"], "people": s["people"], "season": s["season"]} for s in reversed(seasons) if s.get("rank")), None),
        "mean_acc": mean([s["acc"] * 100 for s in seasons]),
    }
    modules = []
    for m in MODULE_NAMES:
        xs = [x for s in seasons for x in s["modules"] if x["name"] == m]
        if not xs:
            continue
        mins = [x["minutes"] for x in xs if x["minutes"] is not None]
        modules.append({"name": m, "acc": sum(x["ok"] for x in xs) / sum(x["total"] for x in xs),
                        "score": mean([x["score"] for x in xs]), "minutes": mean(mins), "seasons": len(xs)})
    return {"seasons": seasons, "overall": overall, "modules": modules, "module_names": MODULE_NAMES}


def save(g, body):
    """录入 / 修改一季的成绩单。分数第一次录入时也记进宗门大比（修为、悟道、突破丹照旧）"""
    n = _num(body.get("season"), 1, 999, integer=True)
    if not n:
        raise MockError("先选是第几季")
    date = exam_date(body.get("date"))
    data = g.state.setdefault("mocks", {})
    rec = data.setdefault(str(n), {})
    had_score = rec.get("score") is not None or _boss_score(g, n) is not None or _credited(g, n)
    unhide(g, n)
    rec["score"] = _num(body.get("score"), 0, 100)
    rec["score_source"] = body.get("score_source") if body.get("score_source") in ("html","estimate","ocr","manual") else "manual"
    rec["avg"] = _num(body.get("avg"), 0, 100)
    rec["top"] = _num(body.get("top"), 0, 100)
    rec["beat"] = _num(body.get("beat"), 0, 100)
    rec["rank"] = _num(body.get("rank"), 1, None, integer=True)
    rec["people"] = _num(body.get("people"), 1, None, integer=True)
    if rec["rank"] and rec["people"] and rec["rank"] > rec["people"]:
        raise MockError("排名不能大于总人数")
    rec["date"] = date or rec.get("date") or g.t
    name = str(body.get("name") or "").strip()[:40]
    if name:
        rec["name"] = name
    rec["minutes"] = {m: v for m in MODULE_NAMES
                      if (v := _num((body.get("minutes") or {}).get(m), 0, 300)) is not None}
    rep = body.get("report")
    if isinstance(rep, dict) and (rep.get("modules") or rep.get("sub")):    # 成绩截图里认出的各模块“共几题、答对几题”
        clean = lambda d: {k: {"total": int(v["total"]), "ok": int(v["ok"]), "minutes": v.get("minutes")}
                           for k, v in (d or {}).items() if isinstance(v, dict) and str(v.get("total", "")).isdigit()}
        rec["report"] = {"modules": clean(rep.get("modules")), "sub": {m: clean(x) for m, x in (rep.get("sub") or {}).items()}}
    rec["scores"] = {m: v for m in MODULE_NAMES
                     if (v := _num((body.get("scores") or {}).get(m), 0, 100)) is not None}
    ev = []
    if rec["score"] is not None and not had_score:
        _mark_credited(g, n)
        ev = g.add_boss(season_name(g, n), rec["score"])
    return ev


def on_import(g, season, credit=True):
    """导入了一份模考试卷：演武 · 历练记记 120 分钟（每季一次），题数、对的题数按那一季的复盘算"""
    unhide(g, season)
    done = g.state.setdefault("mock_practice", [])
    if not season or str(season) in {str(n) for n in done}:
        return []
    # 旧存档可能没有按季标记；复用已有学习记录，不再加时长/经验。
    source = "粉笔第%d季模考" % season
    recorded = any(x.get("source") == source for x in g.state.get("practice", []))
    if not credit or recorded:
        done.append(str(season))
        return []
    d = next((d for n, d in vault.seasons(g.paths) if n == season), None)
    counts = season_counts(g.paths, d) if d else {}
    total = sum(c["total"] for c in counts.values())
    ok = sum(c["ok"] for c in counts.values())
    done.append(str(season))
    return g.add_practice("模考", total, ok, IMPORT_MINUTES, "粉笔第%d季模考" % season, "导入模考试卷，自动记入 %d 分钟" % IMPORT_MINUTES)


# ---------------------------------------------------------------- 考情分析（师傅大比分析，可追问，存档 + 写 训练/宗门大比/第N季考情分析.md）
def _facts(g, season):
    import json
    d = summary(g)
    cur = next((s for s in d["seasons"] if s["season"] == season), None)
    if not cur:
        raise MockError("没有第%d季的模考复盘" % season)
    prev = d["seasons"][:d["seasons"].index(cur)]
    wrong = {}
    sd = next((x for n, x in vault.seasons(g.paths) if n == season), None)
    if sd:
        for f in sorted(sd.glob("[0-9][0-9]-*.md")):
            bad = [q["num"] for q in vault.parse_board_file(f) if q["icon"] == "❌"]
            blank = [q["num"] for q in vault.parse_board_file(f) if q["icon"] == "⚪"]
            if bad or blank:
                wrong[f.stem[3:]] = {"错": bad, "未作答/未录": blank}
    slim = lambda s: {"季": s["season"], "试卷名": s.get("name"), "日期": s["date"], "我的分数": s["score"], "大比平均分": s.get("avg"), "最高分": s.get("top"),
                      "已击败%": s.get("beat"), "排名": s.get("rank"), "总人数": s.get("people"), "答对": s["ok"], "题数": s["total"],
                      "总用时分钟": s["minutes"],
                      "模块": [{"模块": m["name"], "对": m["ok"], "题数": m["total"], "正确率%": round(m["acc"] * 100, 1),
                              "得分": m["score"], "得分是估算": m["estimated"], "用时分钟": m["minutes"],
                              "小板块": [{"板块": b["board"], "对": b["ok"], "错": b["wrong"], "未作答": b["blank"], "题数": b["total"]} for b in m["boards"]]}
                             for m in s["modules"]]}
    facts = {"这一季": slim(cur), "这一季错题题号": wrong,
             "上一季": slim(prev[-1]) if prev else None,
             "以前各季走势": [{"季": s["season"], "我的分数": s["score"], "大比平均分": s.get("avg"), "正确率%": round(s["acc"] * 100, 1),
                          "各模块正确率%": {m["name"]: round(m["acc"] * 100, 1) for m in s["modules"]}} for s in prev[-8:]],
             "历次平均": d["overall"], "各模块历次平均": d["modules"]}
    return json.dumps(facts, ensure_ascii=False)


def analysis(g, season):
    return g.state.setdefault("mocks", {}).setdefault(str(season), {}).setdefault("analysis", [])


def analyze(g, season, question=None, fresh=False):
    """师傅大比分析：没有分析或 fresh 时先做一份完整分析；带 question 是接着追问。返回整段对话"""
    from . import ai, prompts
    conv = analysis(g, season)
    if fresh:
        conv.clear()
    if question and not conv:
        analyze(g, season)
    hist = [{"role": m["role"], "content": m["content"]} for m in conv]
    if conv and not question:
        return conv
    reply = ai.chat(prompts.mock_analysis(g.persona, _facts(g, season), hist, question), temperature=0.5, max_tokens=2200)
    if question:
        conv.append({"role": "user", "content": question, "t": g.t})
    conv.append({"role": "assistant", "content": reply, "t": g.t})
    write_analysis(g, season)
    return conv


def write_analysis(g, season):
    if not g.paths.train:
        return
    conv = analysis(g, season)
    folder = g.paths.train / "宗门大比"
    folder.mkdir(parents=True, exist_ok=True)
    who = {"user": "🧑 我", "assistant": "🌸 " + g.persona["导师名"]}
    body = "\n\n".join("**%s**（%s）：\n\n%s" % (who[m["role"]], m.get("t", ""), m["content"].strip()) for m in conv)
    name = season_name(g, season)
    (folder / ("%s考情分析.md" % safe_name(name))).write_text("# %s · 宗门大比考情分析\n\n%s\n" % (name, body), encoding="utf-8", newline="\n")


def after_marks(g, season):
    """导入了对错截图：导入试卷时记的那笔演武（题数、对的题数）按新的对错改过来"""
    sd = next((d for n, d in vault.seasons(g.paths) if n == season), None)
    if not sd:
        return
    c = season_counts(g.paths, sd)
    ok = sum(x["ok"] for x in c.values())
    for p in g.state.get("practice", []):
        if p.get("source") in ("粉笔第%d季模考" % season, g.state.get("mocks", {}).get(str(season), {}).get("practice_source")) and p.get("board") == "模考":
            p["correct"] = min(ok, p.get("total") or ok)
