"""藏经阁·心法·蒸馏（3.5）：把课程逐字稿 / 习题册解题过程 / 自己的话，蒸馏成一套能学、能迭代的心法。

流程：素材（逐字稿等）→ 切分成片段（框架 / 考点 / 例题 / 闲聊）→ 每个片段拆成一张卡 → 卡片汇总成蒸馏版文件（待审建议）→ 采纳后存成版本快照。
卡片是源头，蒸馏版文件由程序按模板从卡片生成（不花 AI 额度）；之后加新素材、拆出新卡，「更新」只把新卡合进现有文件，生成下一个版本。

存放（都在 训练/技能/<板块>/ 下，以点开头的目录不当心法文本读）：
  .素材/<id>.json    素材原文 + 片段（起止下标、类型、是否采用）
  .卡片/<id>.json    卡片：{id, kind: 考点|例题|总纲, data, sources, created, rev, edited, extra}
  .版本/<版本号>/    manifest.json（基于哪些卡、更新说明）+ files/（当时蒸馏版全部文件的快照）
  .检验/             固定的测试集、每次检验的结果（做对率）
  蒸馏/              蒸馏版文件（讲题时读它们）：00-总流程、01-总纲、02-识别信号、03-考点/*、04-丑的选项、05-例题/*

AI 只做三件事（切分、拆卡、写总流程；以及检验时做题、诊断错题），结果都要过程序校验才保存；
每个 AI 步骤既可以「用软件里的 AI」，也可以「复制提示词，到别的平台做，再粘贴结果」（见 distill_ai.py），两条路最后走同一个校验和保存。
"""
import bisect
import difflib
import hashlib
import json
import re
import time

from . import skillbook
from .skillbook import SkillError

FOLDER = skillbook.DISTILL
D_MAT, D_CARD, D_VER, D_TEST = ".素材", ".卡片", ".版本", ".检验"
KINDS = ("转写", "习题册", "自述")                       # 素材种类
SEG_TYPES = ("框架", "考点", "例题", "闲聊")               # 片段类型；闲聊 = 寒暄、广告、预告，不拆卡
CARD_OF = {"框架": "总纲", "考点": "考点", "例题": "例题"}
MAX_MATERIAL = 200_000
MAX_MATERIALS = 60
MAX_CARDS = 300
SEG_TEXT = 9000                                          # 一个片段拆卡时最多读多少字


class DistillError(SkillError):
    pass


# ---------------------------------------------------------------- 通用
def _sub(paths, board, name):
    return skillbook.board_dir(paths, board) / name


def _id(prefix, *parts):
    return prefix + hashlib.sha1((str(time.time()) + "|".join(map(str, parts))).encode("utf-8")).hexdigest()[:8]


def _load(f):
    return skillbook._load_json(f) if f.is_file() else None


def _save(f, data):
    skillbook._atomic_any(f, data)


def _norm_name(s):
    return re.sub(r"\s+", "", str(s or ""))


def _s(v, n):
    return str(v if v is not None else "").strip()[:n]


def _slist(v, n, item=200):
    out = []
    for x in v if isinstance(v, (list, tuple)) else ([] if v in (None, "") else [v]):
        t = _s(x, item)
        if t and t not in out:
            out.append(t)
    return out[:n]


def slug(name):
    t = re.sub(r'[\\/:*?"<>|\x00-\x1f\s]+', "", str(name or ""))[:40]
    return t.strip(".") or "未命名"


def now():
    return time.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- 素材与片段
def add_material(paths, board, kind, title, text, whole_type=None):
    """加一份素材。whole_type：自述 / 习题册这类短文字可以直接整份当作一个片段（例题或考点），不用切分"""
    if kind not in KINDS:
        raise DistillError("素材种类不对")
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) < 20:
        raise DistillError("内容太短了，先把文字贴进来")
    if len(text) > MAX_MATERIAL:
        raise DistillError("这份素材太长了（上限 %d 字），请分成几份" % MAX_MATERIAL)
    if len(materials(paths, board)) >= MAX_MATERIALS:
        raise DistillError("一个板块最多 %d 份素材" % MAX_MATERIALS)
    m = {"id": _id("m", board, title), "kind": kind, "title": _s(title, 40) or ("%s %s" % (kind, time.strftime("%m-%d %H:%M"))),
         "text": text, "created": now(), "segments": [], "chunks_done": []}
    if whole_type:
        if whole_type not in CARD_OF:
            raise DistillError("片段类型不对")
        m["segments"] = [_seg(1, whole_type, m["title"], 0, len(text))]
        m["chunks_done"] = ["all"]
    _save(_sub(paths, board, D_MAT) / (m["id"] + ".json"), m)
    return m


def _seg(n, typ, title, start, end, include=True):
    return {"id": "s%d" % n, "type": typ, "title": _s(title, 60), "start": int(start), "end": int(end), "include": bool(include), "card": None}


def materials(paths, board):
    d = _sub(paths, board, D_MAT)
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        m = _load(f)
        if isinstance(m, dict) and m.get("id") == f.stem:
            out.append(m)
    return sorted(out, key=lambda m: m.get("created", ""))


def get_material(paths, board, mid):
    m = _load(_sub(paths, board, D_MAT) / (re.sub(r"[^0-9a-z]", "", str(mid)) + ".json"))
    if not isinstance(m, dict):
        raise DistillError("没有这份素材")
    return m


def _save_material(paths, board, m):
    _save(_sub(paths, board, D_MAT) / (m["id"] + ".json"), m)


def delete_material(paths, board, mid):
    m = get_material(paths, board, mid)
    (_sub(paths, board, D_MAT) / (m["id"] + ".json")).unlink()
    return {"deleted": m["id"]}


def chunks(text, size=SEG_TEXT):
    """把长逐字稿切成几块（尽量在换行或句号处切），返回 [(起点下标, 文字)]。块和块之间不重叠"""
    out, i, n = [], 0, len(text)
    size = max(1500, int(size or SEG_TEXT))
    while i < n:
        j = min(n, i + size)
        if j < n:
            cut = max(text.rfind("\n", i + size // 2, j), text.rfind("。", i + size // 2, j), text.rfind("？", i + size // 2, j))
            j = cut + 1 if cut > i else j
        out.append((i, text[i:j]))
        i = j
    return out


_KEEP = re.compile(r"[㐀-鿿A-Za-z0-9]")


def _norm_map(text):
    """只留汉字字母数字（去掉标点空白），并记下每个字符在原文里的下标：AI 引用起止句时标点、空格可以不一样"""
    chars, idx = [], []
    for i, c in enumerate(text):
        if _KEEP.match(c):
            chars.append(c.lower())
            idx.append(i)
    return "".join(chars), idx


def locate(text, start, end, lo=0):
    """在 text 里找 [start 句 … end 句] 的范围，返回 (起点, 终点) 原文下标；找不到返回 None。lo：从这个下标之后找。
    起止句找不到完整的，就用开头 / 结尾的 12、8 个字再试一次"""
    norm, idx = _norm_map(text)
    base = bisect.bisect_left(idx, lo)
    a = "".join(_KEEP.findall(str(start or ""))).lower()
    b = "".join(_KEEP.findall(str(end or ""))).lower()
    if not a or not b:
        return None
    s = -1
    for n in dict.fromkeys((len(a), 12, 8)):
        if n and n <= len(a):
            s = norm.find(a[:n], base)
            if s >= 0:
                break
    if s < 0:
        return None
    e = -1
    sizes = [n for n in dict.fromkeys((len(b), 12, 8, 6)) if n <= len(b)]
    for cand in [b[-n:] for n in sizes] + [b[:n] for n in sizes]:         # 先用结尾的几个字找；结尾识别错了就用开头的几个字
        k = norm.find(cand, s)
        if k >= 0:
            e = k + len(cand)
            break
    if e < 0:
        return None
    return idx[s], idx[e - 1] + 1


def locate_start(text, start, lo=0):
    """找一句开头原文在 text 里的位置（忽略标点），返回原文下标；找不到返回 None。整句找不到就用前 16、12、8、6 个字再试"""
    norm, idx = _norm_map(text)
    base = bisect.bisect_left(idx, lo)
    a = "".join(_KEEP.findall(str(start or ""))).lower()
    if len(a) < 4:
        return None
    for n in dict.fromkeys((len(a), 16, 12, 8, 6)):
        if 4 <= n <= len(a):
            k = norm.find(a[:n], base)
            if k >= 0:
                return idx[k]
    return None


def apply_segments(paths, board, mid, offset, chunk_text, segs, chunk_no):
    """把 AI 给的切分结果（类型 + 每段的开头句）定位到原文：每段从自己的开头到下一段的开头，整块文字都有归属，不会漏掉。
    替换这一块之前的结果。返回 {n, lost:[找不到的片段标题]}"""
    m = get_material(paths, board, mid)
    starts, lost, lo = [], [], 0
    for sg in segs:
        typ = sg.get("type") if sg.get("type") in SEG_TYPES else "闲聊"
        a = locate_start(chunk_text, sg.get("start"), lo)
        if a is None:
            lost.append(_s(sg.get("title"), 30) or "（没有标题）")
            continue
        if starts and a <= starts[-1][0]:
            continue
        starts.append((a, typ, sg.get("title")))
        lo = a + 1
    found = []
    if starts and starts[0][0] >= 30:
        found.append((offset, offset + starts[0][0], "闲聊", "开头（未分类）"))
    for k, (a, typ, title) in enumerate(starts):
        e = starts[k + 1][0] if k + 1 < len(starts) else len(chunk_text)
        found.append((offset + a, offset + e, typ, title))
    lo_abs, hi_abs = offset, offset + len(chunk_text)
    keep = [x for x in m["segments"] if not (lo_abs <= x["start"] < hi_abs)]       # 重跑这一块，只换这一块的结果
    old_cards = {(x["start"], x["end"]): x.get("card") for x in m["segments"] if lo_abs <= x["start"] < hi_abs}
    for a, b, typ, title in found:
        keep.append(_seg(0, typ, title, a, b, include=typ != "闲聊"))
        keep[-1]["card"] = old_cards.get((a, b))
    keep.sort(key=lambda x: x["start"])
    for i, x in enumerate(keep, 1):
        x["id"] = "s%d" % i
    m["segments"] = keep
    if str(chunk_no) not in [str(c) for c in m["chunks_done"]]:
        m["chunks_done"].append(chunk_no)
    _save_material(paths, board, m)
    return {"n": len(found), "lost": lost}


def segment_text(m, seg):
    return m["text"][seg["start"]:seg["end"]]


def update_segment(paths, board, mid, sid, patch):
    m = get_material(paths, board, mid)
    seg = next((x for x in m["segments"] if x["id"] == sid), None)
    if not seg:
        raise DistillError("没有这个片段")
    if "type" in patch:
        if patch["type"] not in SEG_TYPES:
            raise DistillError("片段类型不对")
        seg["type"] = patch["type"]
    if "include" in patch:
        seg["include"] = bool(patch["include"])
    if "title" in patch:
        seg["title"] = _s(patch["title"], 60)
    _save_material(paths, board, m)
    return seg


def merge_segments(paths, board, mid, sid):
    """把这个片段和它后面的一个合成一个（一道题被切成两段时用）"""
    m = get_material(paths, board, mid)
    segs = m["segments"]
    i = next((k for k, x in enumerate(segs) if x["id"] == sid), -1)
    if i < 0 or i + 1 >= len(segs):
        raise DistillError("后面没有可以合并的片段了")
    a, b = segs[i], segs.pop(i + 1)
    a["end"] = b["end"]
    a["card"] = a.get("card") or b.get("card")
    for k, x in enumerate(segs, 1):
        x["id"] = "s%d" % k
    _save_material(paths, board, m)
    return a


def skipped_ranges(m, min_len=30):
    """没有被任何片段盖住的文字（切分时被略过的内容），界面里可以展开检查有没有误删"""
    out, pos = [], 0
    for sg in sorted(m["segments"], key=lambda x: x["start"]):
        if sg["start"] - pos >= min_len:
            out.append((pos, sg["start"]))
        pos = max(pos, sg["end"])
    if len(m["text"]) - pos >= min_len and m["segments"]:
        out.append((pos, len(m["text"])))
    return out


# ---------------------------------------------------------------- 卡片：格式与校验
def _quotes(v, n=4):
    out = []
    for x in v if isinstance(v, (list, tuple)) else []:
        if isinstance(x, dict):
            t, kind = _s(x.get("text"), 160), x.get("kind") if x.get("kind") in KINDS else "转写"
        else:
            t, kind = _s(x, 160), "转写"
        if t and t not in [q["text"] for q in out]:
            out.append({"text": t, "kind": kind})
    return out[:n]


def validate_card(kind, d):
    """AI（或你手改）给的卡片 → 干净的卡片数据；缺必填项就报错。未知字段丢掉，列表去重截断"""
    if not isinstance(d, dict):
        raise DistillError("卡片格式不对（应该是一个 JSON 对象）")
    unsure = _slist(d.get("uncertain"), 8)
    if kind == "考点":
        name = _s(d.get("name"), 30)
        steps = _slist(d.get("steps"), 12, 160)
        if not name:
            raise DistillError("考点卡缺少名称（name）")
        if not steps:
            raise DistillError("考点卡缺少做法步骤（steps）")
        sg = d.get("signals") if isinstance(d.get("signals"), dict) else {}
        return {"name": name, "one_line": _s(d.get("one_line"), 140),
                "signals": {"category": _s(sg.get("category"), 80), "examples": _slist(sg.get("examples"), 16, 20), "test": _s(sg.get("test"), 120)},
                "steps": steps, "contrasts": _slist(d.get("contrasts"), 6, 200), "tips": _slist(d.get("tips"), 8, 200),
                "prereq": _slist(d.get("prereq"), 6, 60), "priority_note": _s(d.get("priority_note"), 160),
                "quotes": _quotes(d.get("quotes")), "uncertain": unsure}
    if kind == "例题":
        title = _s(d.get("title"), 50)
        steps = _slist(d.get("steps"), 14, 200)
        if not title:
            raise DistillError("例题卡缺少标题（title）")
        if not steps:
            raise DistillError("例题卡缺少拆解步骤（steps）")
        q = d.get("question") if isinstance(d.get("question"), dict) else {}
        opts = q.get("options") if isinstance(q.get("options"), dict) else {}
        options = {k: _s(opts.get(k), 200) for k in "ABCD" if _s(opts.get(k), 200)}
        answer = _s(q.get("answer"), 4).upper()
        complete = bool(q.get("complete")) and bool(_s(q.get("stem"), 20)) and len(options) == 4
        excl = []
        for x in d.get("exclusions") if isinstance(d.get("exclusions"), list) else []:
            if isinstance(x, dict) and _s(x.get("reason"), 200):
                excl.append({"option": _s(x.get("option"), 6), "reason": _s(x.get("reason"), 200), "type": _s(x.get("type"), 20)})
        return {"title": title, "exam": _s(d.get("exam"), 60),
                "question": {"complete": complete, "stem": _s(q.get("stem"), 1200), "options": options, "answer": answer if answer in options or not options else ""},
                "concepts": _slist(d.get("concepts"), 6, 30), "steps": steps, "exclusions": excl[:8], "rules": _slist(d.get("rules"), 6, 200),
                "notes": _slist(d.get("notes"), 6, 240), "quotes": _quotes(d.get("quotes")), "uncertain": unsure}
    if kind == "总纲":
        name = _s(d.get("name"), 30)
        if not name:
            raise DistillError("总纲卡缺少名称（name）")
        items = []
        for x in d.get("items") if isinstance(d.get("items"), list) else []:
            nm = _s(x.get("name") if isinstance(x, dict) else x, 30)
            if nm and nm not in [i["name"] for i in items]:
                items.append({"name": nm, "note": _s(x.get("note") if isinstance(x, dict) else "", 120)})
        pr = d.get("priority") if isinstance(d.get("priority"), dict) else {}
        ugly = []
        for x in d.get("ugly") if isinstance(d.get("ugly"), list) else []:
            nm = _s(x.get("name") if isinstance(x, dict) else x, 30)
            if nm and nm not in [u["name"] for u in ugly]:
                ugly.append({"name": nm, "test": _s(x.get("test") if isinstance(x, dict) else "", 160)})
        return {"name": name, "one_line": _s(d.get("one_line"), 200), "items": items[:30],
                "priority": {k: _slist(pr.get(k), 20, 30) for k in ("肉", "排骨", "渣渣")}, "ugly": ugly[:30],
                "notes": _slist(d.get("notes"), 8, 240), "uncertain": unsure}
    raise DistillError("不认识的卡片种类")


def card_title(c):
    d = c["data"]
    return d.get("name") or d.get("title") or c["id"]


# ---------------------------------------------------------------- 卡片：存取与合并
def cards(paths, board):
    d = _sub(paths, board, D_CARD)
    out = []
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        c = _load(f)
        if isinstance(c, dict) and c.get("id") == f.stem and c.get("kind") in CARD_OF.values():
            out.append(c)
    return sorted(out, key=lambda c: (c.get("created", ""), c["id"]))


def get_card(paths, board, cid):
    c = _load(_sub(paths, board, D_CARD) / (re.sub(r"[^0-9a-z]", "", str(cid)) + ".json"))
    if not isinstance(c, dict):
        raise DistillError("没有这张卡")
    return c


def _put_card(paths, board, c):
    _save(_sub(paths, board, D_CARD) / (c["id"] + ".json"), c)


def _label(m, seg):
    return "%s · %s" % (m["title"], seg.get("title") or ("片段 " + seg["id"][1:]))


def _tag_quotes(data, kind_of_source):
    for q in data.get("quotes") or []:
        q["kind"] = kind_of_source
    return data


def save_card(paths, board, kind, data, source):
    """保存一张新拆出来的卡。考点：同名的并进已有那张（补充信号、步骤、原话，记下来源）；总纲：整个板块只有一张，新的并进去；
    例题：每道一张。返回 (卡片, 是新建还是并入)"""
    data = validate_card(kind, data)
    if kind != "总纲":
        _tag_quotes(data, source.get("kind") or "转写")
    allc = cards(paths, board)
    if len(allc) >= MAX_CARDS:
        raise DistillError("一个板块最多 %d 张卡" % MAX_CARDS)
    same = None
    if kind == "考点":
        same = next((c for c in allc if c["kind"] == "考点" and _norm_name(c["data"]["name"]) == _norm_name(data["name"])), None)
    elif kind == "总纲":
        same = next((c for c in allc if c["kind"] == "总纲"), None)
    if same:
        before = json.dumps(same["data"], ensure_ascii=False, sort_keys=True)
        same["data"] = _merge(kind, same["data"], data, source)
        if json.dumps(same["data"], ensure_ascii=False, sort_keys=True) != before or source.get("label") not in [x.get("label") for x in same["sources"]]:
            same["rev"] = int(same.get("rev", 1)) + 1
        if source.get("label") not in [x.get("label") for x in same["sources"]]:
            same["sources"].append(source)
        _put_card(paths, board, same)
        return same, "merged"
    c = {"id": _id("c", board, kind), "kind": kind, "data": data, "sources": [source], "created": now(), "rev": 1, "edited": False, "extra": []}
    _put_card(paths, board, c)
    return c, "new"


def _merge(kind, old, new, source):
    """同一个考点 / 总纲又讲了一遍：并集，不丢旧内容。做法不同的，记成「另一种讲法」，不替换原来的"""
    out = json.loads(json.dumps(old))
    if kind == "考点":
        out["one_line"] = out.get("one_line") or new.get("one_line", "")
        sg, ns = out["signals"], new["signals"]
        sg["category"] = sg.get("category") or ns.get("category", "")
        sg["test"] = sg.get("test") or ns.get("test", "")
        sg["examples"] = _slist(sg.get("examples", []) + ns.get("examples", []), 16, 20)
        for k, n in (("contrasts", 6), ("tips", 8), ("prereq", 6), ("uncertain", 8)):
            out[k] = _slist(out.get(k, []) + new.get(k, []), n, 200)
        out["priority_note"] = out.get("priority_note") or new.get("priority_note", "")
        known = [q["text"] for q in out.get("quotes", [])]
        qs = out.get("quotes", []) + [q for q in new.get("quotes", []) if q["text"] not in known]
        out["quotes"] = sorted(qs, key=lambda q: q["kind"] != "自述")[:6]
        if new["steps"] != out["steps"]:
            alts = out.setdefault("alt_steps", [])
            if new["steps"] not in [a["steps"] for a in alts]:
                alts.append({"label": source.get("label", ""), "steps": new["steps"]})
        return out
    if kind == "总纲":
        out["one_line"] = out.get("one_line") or new.get("one_line", "")
        have = [i["name"] for i in out["items"]]
        out["items"] = (out["items"] + [i for i in new["items"] if i["name"] not in have])[:30]
        for k in ("肉", "排骨", "渣渣"):
            out["priority"][k] = _slist(out["priority"].get(k, []) + new["priority"].get(k, []), 20, 30)
        have = [u["name"] for u in out["ugly"]]
        out["ugly"] = (out["ugly"] + [u for u in new["ugly"] if u["name"] not in have])[:30]
        out["notes"] = _slist(out.get("notes", []) + new.get("notes", []), 8, 240)
        out["uncertain"] = _slist(out.get("uncertain", []) + new.get("uncertain", []), 8, 200)
    return out


def update_card(paths, board, cid, kind_data):
    """手改一张卡（界面里是 JSON 文本）：校验通过才保存"""
    c = get_card(paths, board, cid)
    c["data"] = validate_card(c["kind"], kind_data)
    c["rev"] = int(c.get("rev", 1)) + 1
    c["edited"] = True
    _put_card(paths, board, c)
    return c


def delete_card(paths, board, cid):
    c = get_card(paths, board, cid)
    (_sub(paths, board, D_CARD) / (c["id"] + ".json")).unlink()
    for m in materials(paths, board):                    # 素材里引用这张卡的片段，恢复成“还没拆”
        ch = False
        for sg in m["segments"]:
            if sg.get("card") == cid:
                sg["card"], ch = None, True
        if ch:
            _save_material(paths, board, m)
    return {"deleted": cid}


def link_segment(paths, board, mid, sid, cid):
    m = get_material(paths, board, mid)
    for sg in m["segments"]:
        if sg["id"] == sid:
            sg["card"] = cid
    _save_material(paths, board, m)


def evidence(allc, c):
    """一张考点卡的证据：几次讲解 + 几道用到它的例题。至少 2 处才算“已印证”"""
    if c["kind"] != "考点":
        return {"n": 0, "examples": [], "status": ""}
    key = _norm_name(c["data"]["name"])
    ex = [x for x in allc if x["kind"] == "例题" and key in [_norm_name(t) for t in x["data"]["concepts"]]]
    n = len(c["sources"]) + len(ex)
    return {"n": n, "examples": ex, "status": "已印证" if n >= 2 else "待验证"}


# ---------------------------------------------------------------- 把卡片写成蒸馏版文件（程序模板，不花 AI 额度）
def _ul(items, bullet="- "):
    return "\n".join(bullet + x for x in items)


def _ol(items):
    return "\n".join("%d. %s" % (i, x) for i, x in enumerate(items, 1))


def _quote_block(quotes):
    qs = sorted(quotes or [], key=lambda q: q["kind"] != "自述")
    return "\n".join("> %s：%s" % ("我的话" if q["kind"] == "自述" else ("习题册" if q["kind"] == "习题册" else "老师原话"), q["text"]) for q in qs)


def _uncertain(items):
    return "## 待核对\n" + _ul(items) if items else ""


def _join(*parts):
    return "\n\n".join(p.strip("\n") for p in parts if p and p.strip()) + "\n"


def _extra_blocks(c):
    return ["## 补充（来自错题 %s，待核实）\n%s" % (x.get("from", ""), x["text"].strip()) for x in c.get("extra") or []]


def render_point(c, allc, ex_paths):
    d, ev = c["data"], evidence(allc, c)
    sg = d["signals"]
    sig = []
    if sg["category"]:
        sig.append("- 类别：" + sg["category"])
    if sg["examples"]:
        sig.append("- 举例（不限于此）：" + "、".join(sg["examples"]))
    if sg["test"]:
        sig.append("- 判别问法：" + sg["test"])
    alts = "\n\n".join("**%s**\n%s" % (a["label"] or "另一次讲解", _ol(a["steps"])) for a in d.get("alt_steps") or [])
    seen = "\n".join("- [%s](%s)" % (x["data"]["title"], ex_paths[x["id"]]) for x in ev["examples"])
    body = _join("# " + d["name"], ("> " + d["one_line"]) if d["one_line"] else "",
                 "- 证据：%d 处（%d 次讲解 + %d 道例题）· **%s**" % (ev["n"], len(c["sources"]), len(ev["examples"]), ev["status"]),
                 ("## 识别信号\n" + "\n".join(sig)) if sig else "", "## 做法\n" + _ol(d["steps"]),
                 ("## 另一种讲法\n" + alts) if alts else "",
                 ("## 和相近考点的区别\n" + _ul(d["contrasts"])) if d["contrasts"] else "", ("## 小窍门\n" + _ul(d["tips"])) if d["tips"] else "",
                 ("## 前置知识\n" + _ul(d["prereq"])) if d["prereq"] else "", ("## 优先级\n" + d["priority_note"]) if d["priority_note"] else "",
                 ("## 原话\n" + _quote_block(d["quotes"])) if d["quotes"] else "", _uncertain(d["uncertain"]),
                 ("## 见于例题\n" + seen) if seen else "", "来源：" + "；".join(s["label"] for s in c["sources"]))
    extra = _extra_blocks(c)
    return body.rstrip("\n") + ("\n\n" + "\n\n".join(extra) + "\n" if extra else "\n")


def render_example(c):
    d, q = c["data"], c["data"]["question"]
    qtxt = ""
    if q["stem"] or q["options"]:
        opts = "\n".join("- %s. %s" % (k, v) for k, v in q["options"].items())
        qtxt = "## 题目%s\n%s\n\n%s\n\n**答案**：%s" % ("" if q["complete"] else "（⚠ 不完整，待补全）", q["stem"] or "（转写里没有完整题干）", opts, q["answer"] or "（未给出）")
    ex = "\n".join("- %s：%s%s" % (x["option"] or "某项", ("【%s】" % x["type"]) if x["type"] else "", x["reason"]) for x in d["exclusions"])
    return _join("# " + d["title"], ("来源题：" + d["exam"]) if d["exam"] else "", qtxt,
                 ("用到的考点：" + "、".join(d["concepts"])) if d["concepts"] else "", "## 拆解步骤\n" + _ol(d["steps"]),
                 ("## 小规则\n" + _ul(d["rules"])) if d["rules"] else "", ("## 逐项排除\n" + ex) if ex else "",
                 ("## 备注\n" + _ul(d["notes"])) if d["notes"] else "", ("## 原话\n" + _quote_block(d["quotes"])) if d["quotes"] else "",
                 _uncertain(d["uncertain"]), "来源：" + "；".join(s["label"] for s in c["sources"]))


def render_outline(c, point_cards):
    d = c["data"]
    learned = {_norm_name(p["data"]["name"]) for p in point_cards}
    rows = ["| 项 | 说明 | 状态 |", "|---|---|---|"]
    for it in d["items"]:
        rows.append("| %s | %s | %s |" % (it["name"], it["note"], "✅ 已学" if _norm_name(it["name"]) in learned else "⬜ 未学"))
    pr = d["priority"]
    prio = "\n".join("- **%s**：%s" % (k, "、".join(pr[k])) for k in ("肉", "排骨", "渣渣") if pr[k])
    return _join("# " + d["name"], ("> " + d["one_line"]) if d["one_line"] else "", ("## 清单\n" + "\n".join(rows)) if d["items"] else "",
                 ("## 优先级\n" + prio) if prio else "", ("## 不要选的选项（丑）\n" + _ul(["**%s**：%s" % (u["name"], u["test"]) if u["test"] else "**%s**" % u["name"] for u in d["ugly"]])) if d["ugly"] else "",
                 ("## 备注\n" + _ul(d["notes"])) if d["notes"] else "", _uncertain(d["uncertain"]), "来源：" + "；".join(s["label"] for s in c["sources"]))


def render_signals(point_cards):
    rows = ["| 题干 / 选项里的信号 | 判别问法 | 对应考点 |", "|---|---|---|"]
    for c in point_cards:
        sg = c["data"]["signals"]
        if sg["category"] or sg["examples"]:
            rows.append("| %s（如 %s 等） | %s | [%s](03-考点/%s.md) |" % (sg["category"] or "—", "、".join(sg["examples"][:6]) or "—", sg["test"] or "—", c["data"]["name"], slug(c["data"]["name"])))
    return _join("# 识别信号", "看到下面的信号，先想对应的考点（举例不是穷举，按「判别问法」判断）。", "\n".join(rows)) if len(rows) > 2 else ""


def render_ugly(example_cards, outline):
    groups = {}
    for c in example_cards:
        for x in c["data"]["exclusions"]:
            if x["type"]:
                groups.setdefault(x["type"], []).append((c["data"]["title"], x))
    defs = {u["name"]: u["test"] for u in (outline["data"]["ugly"] if outline else [])}
    names = list(dict.fromkeys(list(defs) + list(groups)))
    if not names:
        return ""
    blocks = []
    for nm in names:
        items = groups.get(nm, [])
        blocks.append("## %s\n%s%s" % (nm, ("判断办法：" + defs[nm] + "\n\n") if defs.get(nm) else "",
                                       _ul(["%s · 选项 %s：%s" % (t, x["option"] or "?", x["reason"]) for t, x in items]) if items else "（还没有例题）"))
    return _join("# 丑的选项（一定不要选的挖坑选项）", "\n\n".join(blocks))


def render_default_flow(point_cards):
    steps = ["看题干和选项里有没有下面「识别信号」里的信号，判断这道题可能考哪个考点"]
    for c in point_cards[:6]:
        steps.append("如果是「%s」：%s" % (c["data"]["name"], c["data"]["steps"][0]))
    steps.append("逐项排除：对照「丑的选项」，把挖坑的选项划掉")
    return _join("# 总流程", "拿到一道题，按顺序想（这是根据已有考点卡自动列的草稿，可以点「✨ 让 AI 写总流程」重写）：", _ol(steps))


def render_files(paths, board, flow_text=None):
    """所有卡片 → {相对路径: 文本}，以及每个文件的来源说明。路径都在 蒸馏/ 下"""
    allc = cards(paths, board)
    points = [c for c in allc if c["kind"] == "考点"]
    examples = [c for c in allc if c["kind"] == "例题"]
    outline = next((c for c in allc if c["kind"] == "总纲"), None)
    files, why, used = {}, {}, set()

    def path(sub, name, cid):
        base = "%s/%s/%s" % (FOLDER, sub, slug(name))
        p, n = base + ".md", 2
        while p in used:
            p, n = "%s-%d.md" % (base, n), n + 1
        used.add(p)
        return p

    ex_paths = {c["id"]: path("05-例题", c["data"]["title"], c["id"]) for c in examples}
    for c in points:
        p = path("03-考点", c["data"]["name"], c["id"])
        files[p] = render_point(c, allc, {k: "../" + v[len(FOLDER) + 1:] for k, v in ex_paths.items()})
        why[p] = "考点卡「%s」（%s）" % (c["data"]["name"], "；".join(s["label"] for s in c["sources"]))
    for c in examples:
        files[ex_paths[c["id"]]] = render_example(c)
        why[ex_paths[c["id"]]] = "例题卡「%s」（%s）" % (c["data"]["title"], "；".join(s["label"] for s in c["sources"]))
    if outline:
        files[FOLDER + "/01-总纲.md"] = render_outline(outline, points)
        why[FOLDER + "/01-总纲.md"] = "总纲卡"
    sig = render_signals(points)
    if sig:
        files[FOLDER + "/02-识别信号.md"] = sig
        why[FOLDER + "/02-识别信号.md"] = "由各考点卡的识别信号汇总"
    ugly = render_ugly(examples, outline)
    if ugly:
        files[FOLDER + "/04-丑的选项.md"] = ugly
        why[FOLDER + "/04-丑的选项.md"] = "由各例题卡的逐项排除理由汇总"
    if points or flow_text:
        files[FOLDER + "/00-总流程.md"] = (flow_text.strip() + "\n") if flow_text else render_default_flow(points)
        why[FOLDER + "/00-总流程.md"] = "AI 写的总流程" if flow_text else "由考点卡自动列的总流程草稿"
    return files, why


def card_preview(paths, board, cid):
    """一张卡写成文件后的样子（给界面预览用）：{path, text}"""
    c = get_card(paths, board, cid)
    allc = cards(paths, board)
    if c["kind"] == "考点":
        ex = {x["id"]: "#" for x in allc if x["kind"] == "例题"}
        return render_point(c, allc, ex)
    if c["kind"] == "例题":
        return render_example(c)
    return render_outline(c, [x for x in allc if x["kind"] == "考点"])


# ---------------------------------------------------------------- 版本
def _ver_dir(paths, board):
    return _sub(paths, board, D_VER)


def _vkey(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)) or (0,)


def versions(paths, board):
    """[{version, created, note, changelog, n_cards, accuracy…}] 新的在前"""
    d, out = _ver_dir(paths, board), []
    for f in d.glob("*/manifest.json") if d.is_dir() else []:
        m = _load(f)
        if isinstance(m, dict) and m.get("version"):
            out.append(m)
    out.sort(key=lambda m: _vkey(m["version"]), reverse=True)
    tests = test_results(paths, board)
    for m in out:
        last = next((t for t in tests if t["version"] == m["version"]), None)
        m["test"] = {"date": last["date"], "n": last["n"], "correct": last["correct"]} if last else None
    return out


def current_version(paths, board):
    v = versions(paths, board)
    return v[0]["version"] if v else None


def next_version(cur, major=False):
    if not cur:
        return "1.0"
    a, b = (_vkey(cur) + (0, 0))[:2]
    return "%d.0" % (a + 1) if major else "%d.%d" % (a, b + 1)


def _own_distill_files(paths, board):
    d = skillbook.board_dir(paths, board)
    return {rel: skillbook._read(d / rel) for rel in skillbook.own_files(paths, board) if rel.startswith(FOLDER + "/")}


def snapshot(paths, board, version, note="", card_revs=None, changelog=None):
    """把现在的蒸馏版全部文件存成一个版本（同版本号再存会覆盖）"""
    files = _own_distill_files(paths, board)
    if not files:
        raise DistillError("还没有蒸馏版文件，没有东西可以存成版本")
    base = _ver_dir(paths, board) / version
    if base.is_dir():
        import shutil
        shutil.rmtree(base)
    for rel, text in files.items():
        f = base / "files" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    if card_revs is None:
        card_revs = {c["id"]: c.get("rev", 1) for c in cards(paths, board)}
    m = {"version": version, "created": now(), "note": _s(note, 200), "cards": card_revs, "n_cards": len(card_revs),
         "files": {rel: skillbook._rev(t) for rel, t in files.items()}, "changelog": [str(x)[:200] for x in (changelog or [])][:30]}
    _save(base / "manifest.json", m)
    return m


def save_version(paths, board, major=False, note=""):
    """手动存一个新版本（把现在的状态定为新版本，包括你手改的）"""
    cur = current_version(paths, board)
    return snapshot(paths, board, next_version(cur, major), note or "手动存档（包含手改的内容）", changelog=["手动存档"])


def _ver_files(paths, board, version):
    base = _ver_dir(paths, board) / re.sub(r"[^0-9.]", "", str(version)) / "files"
    if not base.is_dir():
        raise DistillError("没有这个版本")
    return {p.relative_to(base).as_posix(): p.read_text(encoding="utf-8", errors="ignore") for p in base.rglob("*.md")}


def compare(paths, board, a, b):
    """版本对比：b 传 "当前" 就是和现在的文件比。返回 {added, removed, changed:[{path, diff}]}"""
    fa = _ver_files(paths, board, a)
    fb = _own_distill_files(paths, board) if b in ("当前", "", None) else _ver_files(paths, board, b)
    added = sorted(set(fb) - set(fa))
    removed = sorted(set(fa) - set(fb))
    changed = []
    for rel in sorted(set(fa) & set(fb)):
        if fa[rel] != fb[rel]:
            diff = "\n".join(difflib.unified_diff(fa[rel].splitlines(), fb[rel].splitlines(), "v" + a, "v%s" % (b or "当前"), lineterm="", n=1))
            changed.append({"path": rel, "diff": diff[:6000]})
    return {"a": a, "b": b or "当前", "added": added, "removed": removed, "changed": changed}


def restore(paths, board, version):
    """回到某个版本：现在的蒸馏版文件换成那个版本的样子；被换掉、被删掉的内容先存进历史，可以再找回"""
    snap = _ver_files(paths, board, version)
    cur = _own_distill_files(paths, board)
    for rel, text in snap.items():
        if rel in cur and cur[rel] != text:
            skillbook.save(paths, board, rel, text, skillbook._rev(cur[rel]))
        elif rel not in cur:
            skillbook.save(paths, board, rel, text, "")
    for rel, text in cur.items():
        if rel not in snap:
            skillbook.delete(paths, board, rel, skillbook._rev(text))
    skillbook._PLAN.clear()
    return {"restored": version, "files": len(snap)}


def new_cards(paths, board):
    """还没并进最新版本的卡：新卡，或者上个版本之后又改过 / 并入了新内容的卡"""
    v = versions(paths, board)
    inc = v[0]["cards"] if v else {}
    return [c for c in cards(paths, board) if c["id"] not in inc or int(c.get("rev", 1)) > int(inc[c["id"]])]


def build(paths, board, source=None):
    """汇总：卡片 → 蒸馏版文件，和现在的文件比，生成待审建议（没有的文件新建，有变化的整个替换）。
    采纳后自动存成新版本（第一次是 1.0）。你手改过的文件会标出来、默认不勾选。"""
    allc = cards(paths, board)
    if not allc:
        raise DistillError("还没有卡片：先把素材切分、拆成卡")
    flow = (skillbook.board_settings(paths, board).get("flow_draft") or "").strip() or None
    desired, why = render_files(paths, board, flow)
    vs = versions(paths, board)
    last = _ver_files(paths, board, vs[0]["version"]) if vs else {}
    d = skillbook.board_dir(paths, board)
    edits = []
    for rel in sorted(desired):
        f, text = d / rel, desired[rel]
        if not f.is_file():
            edits.append({"path": rel, "action": "new", "text": text, "reason": "新增：" + why[rel]})
            continue
        cur = skillbook._read(f)
        if cur.strip() == text.strip():
            continue
        e = {"path": rel, "action": "replace", "text": text, "before": cur, "base": skillbook._rev(cur), "reason": "更新：" + why[rel]}
        if rel in last and cur != last[rel]:
            e["flag"] = "你改过这个文件（和上个版本不一样），默认不勾选"
        elif rel not in last and vs:
            e["flag"] = "这个文件不是上个版本生成的，默认不勾选"
        edits.append(e)
    if not edits:
        raise DistillError("没有需要更新的内容：现有文件已经和卡片一致")
    fresh = new_cards(paths, board)
    ver = next_version(vs[0]["version"] if vs else None)
    log = ["新增文件 %d 个，更新文件 %d 个" % (sum(e["action"] == "new" for e in edits), sum(e["action"] == "replace" for e in edits))]
    if fresh:
        log.append("吸收的卡：" + "、".join(card_title(c) for c in fresh[:12]) + ("等 %d 张" % len(fresh) if len(fresh) > 12 else ""))
    meta = {"version": ver, "cards": {c["id"]: c.get("rev", 1) for c in allc}, "changelog": log}
    key = "distill:" + hashlib.sha1((ver + "".join(sorted(e["path"] + e["text"] for e in edits))).encode("utf-8")).hexdigest()[:12]
    kind = "update" if vs else "distill"
    summary = ("更新到 v%s（吸收 %d 张新卡）" % (ver, len(fresh))) if vs else "生成蒸馏版 v1.0（基于 %d 张卡）" % len(allc)
    return skillbook.add_proposal(paths, board, kind, summary, edits, {"label": "蒸馏（%d 张卡）" % len(allc)}, key, meta)


def after_accept(paths, board, proposal, applied_edits):
    """采纳蒸馏 / 更新 / 诊断建议后调用：卡片补上错题补充、存版本快照、默认讲题只读蒸馏版。返回新版本号"""
    kind, meta = proposal.get("kind"), proposal.get("meta") or {}
    if kind == "diagnose":
        for e in applied_edits:
            if e.get("card"):
                try:
                    c = get_card(paths, board, e["card"])
                except DistillError:
                    continue
                c.setdefault("extra", []).append({"text": e["text"].split("\n", 1)[1].strip() if e["text"].startswith("## ") else e["text"], "from": meta.get("run", "")})
                c["rev"] = int(c.get("rev", 1)) + 1
                _put_card(paths, board, c)
    if kind in ("distill", "update", "diagnose"):
        vs = versions(paths, board)
        ver = meta.get("version") or next_version(vs[0]["version"] if vs else None)
        if kind == "diagnose":
            ver = next_version(vs[0]["version"] if vs else None)
        revs = meta.get("cards") if kind != "diagnose" else None
        snapshot(paths, board, ver, proposal.get("summary", ""), revs, meta.get("changelog") or [proposal.get("summary", "")])
        if not vs:
            skillbook.set_board_setting(paths, board, "only_distilled", True)
        return ver
    return None


# ---------------------------------------------------------------- 检验：用题库的题（只看题干、选项、答案，不看题库的解析）测心法
BATCH = 5                  # 软件里的 AI 一次做几道题（一批一次调用）


def test_results(paths, board):
    d = _sub(paths, board, D_TEST)
    out = []
    for f in sorted(d.glob("result-*.json"), reverse=True) if d.is_dir() else []:
        r = _load(f)
        if isinstance(r, dict):
            out.append(r)
    return out


def get_result(paths, board, rid):
    r = _load(_sub(paths, board, D_TEST) / ("result-%s.json" % re.sub(r"[^0-9a-z\-]", "", str(rid))))
    if not isinstance(r, dict):
        raise DistillError("没有这次检验的结果")
    return r


def get_run(paths, board, rid):
    r = _load(_sub(paths, board, D_TEST) / ("run-%s.json" % re.sub(r"[^0-9a-z\-]", "", str(rid))))
    if not isinstance(r, dict):
        raise DistillError("没有这次检验")
    return r


def _fp(stem):
    return "".join(_KEEP.findall(str(stem or "")))[:30].lower()


def test_set(paths, board, n=20, reseed=False):
    """固定的测试集：第一次从题库抽 n 道（有答案、四个选项、不是例题卡里用过的题），之后一直用同一批，不同版本才能比。reseed 重抽"""
    import random
    from . import question_bank
    f = _sub(paths, board, D_TEST) / "测试集.json"
    qs, _ = question_bank.read(paths, board)
    used = {_fp(c["data"]["question"]["stem"]) for c in cards(paths, board) if c["kind"] == "例题" and c["data"]["question"]["stem"]}
    pool = {q["key"]: q for q in qs if q.get("answer") and set(q.get("options") or {}) == set("ABCD") and _fp(q["stem"]) not in used}
    old = _load(f) if not reseed else None
    keys = [k for k in (old or {}).get("keys", []) if k in pool]
    n = max(5, min(int(n or 20), 60))
    if len(keys) < n:
        rest = sorted(set(pool) - set(keys))
        random.Random(time.time()).shuffle(rest)
        keys += rest[:n - len(keys)]
    keys = keys[:n]
    if not keys:
        raise DistillError("题库里这个板块没有可用的题（要有四个选项和答案）")
    _save(f, {"keys": keys, "created": now()})
    return [pool[k] for k in keys]


def start_run(paths, board, n=20, reseed=False):
    """开始一次检验：用现在的版本，抽（或沿用）测试集，分批。题目的内容存一份快照，题库之后改了也不影响这次"""
    if not current_version(paths, board):
        raise DistillError("还没有蒸馏版：先生成并采纳 v1.0，再检验")
    qs = test_set(paths, board, n, reseed)
    rid = time.strftime("%m%d%H%M%S") + hashlib.sha1(str(time.time()).encode()).hexdigest()[:3]
    keys = [q["key"] for q in qs]
    run = {"id": rid, "version": current_version(paths, board), "created": now(), "keys": keys,
           "questions": {q["key"]: {"id": q["id"], "stem": q["stem"], "options": q["options"], "answer": q["answer"]} for q in qs},
           "batches": [keys[i:i + BATCH] for i in range(0, len(keys), BATCH)], "answers": {}, "done": False}
    _save(_sub(paths, board, D_TEST) / ("run-%s.json" % rid), run)
    return run


def record_answers(paths, board, rid, got):
    """记下一批题的作答；所有批都答完就由程序判对错，存结果（做对率）"""
    run = get_run(paths, board, rid)
    run["answers"].update(got)
    _save(_sub(paths, board, D_TEST) / ("run-%s.json" % rid), run)
    if not all(k in run["answers"] for k in run["keys"]):
        left = sum(1 for k in run["keys"] if k not in run["answers"])
        return {"done": False, "left": left, "message": "已记下这一批，还有 %d 道题没答" % left}
    items = []
    for k in run["keys"]:
        q, a = run["questions"][k], run["answers"][k]
        items.append({"key": k, "id": q["id"], "stem": q["stem"], "options": q["options"], "my": a["answer"], "answer": q["answer"], "ok": a["answer"] == q["answer"], "why": a.get("why", "")})
    res = {"id": run["id"], "run": run["id"], "version": run["version"], "date": now(), "n": len(items), "correct": sum(i["ok"] for i in items), "items": items}
    _save(_sub(paths, board, D_TEST) / ("result-%s.json" % run["id"]), res)
    run["done"] = True
    _save(_sub(paths, board, D_TEST) / ("run-%s.json" % rid), run)
    return {"done": True, "result": res["id"], "n": res["n"], "correct": res["correct"], "message": "做完了：%d / %d 题做对（v%s）" % (res["correct"], res["n"], res["version"])}


# ---------------------------------------------------------------- 界面用的整体状态
def overview(paths, board):
    allc = cards(paths, board)
    fresh = {c["id"] for c in new_cards(paths, board)}
    mats = []
    for m in materials(paths, board):
        segs = []
        for sg in m["segments"]:
            t = segment_text(m, sg)
            segs.append(dict(sg, chars=len(t), preview=t[:60].replace("\n", " "), tail=t[-40:].replace("\n", " ")))
        mats.append({"id": m["id"], "kind": m["kind"], "title": m["title"], "created": m["created"], "chars": len(m["text"]),
                     "n_chunks": len(chunks(m["text"])), "chunks_done": len(m["chunks_done"]), "segments": segs,
                     "skipped": [{"start": a, "end": b, "preview": m["text"][a:a + 80].replace("\n", " "), "chars": b - a} for a, b in skipped_ranges(m)]})
    cl = []
    for c in allc:
        ev = evidence(allc, c)
        cl.append({"id": c["id"], "kind": c["kind"], "title": card_title(c), "rev": c.get("rev", 1), "edited": bool(c.get("edited")), "new": c["id"] in fresh,
                   "status": ev["status"], "n_evidence": ev["n"], "sources": [s["label"] for s in c["sources"]],
                   "complete": c["data"]["question"]["complete"] if c["kind"] == "例题" else None,
                   "unsure": len(c["data"].get("uncertain") or [])})
    st = skillbook.board_settings(paths, board)
    runs = []
    for f in sorted(_sub(paths, board, D_TEST).glob("run-*.json")) if _sub(paths, board, D_TEST).is_dir() else []:
        r = _load(f)
        if isinstance(r, dict) and not r.get("done"):
            runs.append({"id": r["id"], "version": r["version"], "created": r["created"], "n": len(r["keys"]), "answered": len(r["answers"]), "batches": len(r["batches"])})
    return {"runs_open": runs, "materials": mats, "cards": cl, "versions": versions(paths, board), "n_new": len(fresh),
            "only_distilled": bool(st.get("only_distilled", True)), "has_skill_md": (skillbook.board_dir(paths, board) / "SKILL.md").is_file(),
            "flow_draft": bool((st.get("flow_draft") or "").strip()), "tests": [{k: r.get(k) for k in ("id", "version", "date", "n", "correct")} for r in test_results(paths, board)[:10]]}
