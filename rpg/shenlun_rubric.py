"""
采分点（rubric）：文件格式解析 / 校验 / 序列化 / 分值分配 / 程序算分。

文件格式（训练/采分点/<题目编号>.md，详见 DESIGN.md 4.2）：

    ---
    题目: 国考2026-副省-01
    状态: 草稿              # 草稿 / 已定稿，只有已定稿的题进入计分
    总分: 10
    字数: 250               # 字数上限，可空
    题型: 归纳概括
    来源: 用户提供
    ---
    ## 采分点
    - [2] 出台规划文件 | 关键词: 《总体规划》；分区域亮度管理 | 依据: 第2-3段
    ## 加分点
    - [+1] 核心理念 | 关键词: 金山银山

“关键词”用中文分号“；”或英文 “;” 分隔（关键词里常有顿号和逗号，不能用它们分隔）。

算分（score）：AI 只返回每个采分点的 hit（full/half/none）和 evidence（作答里的原句）；
分数、字数扣分都由这里计算。evidence 必须是作答里真实出现的片段，否则该点判 none。

谁调用：rpg/shenlun_analysis.py（从解析文档起草）、rpg/shenlun_grader.py（批改）、rpg/shenlun.py（题库与定稿）。
"""
import re

STATUS_DRAFT, STATUS_FINAL = "草稿", "已定稿"
HIT_FACTOR = {"full": 1.0, "half": 0.5, "none": 0.0}

# 硬规则默认值（用户可在 规则.md 里覆盖，M2 接入）
DEFAULT_RULES = {
    "超字数宽限": 0.10,      # 超出字数上限 10% 以内不扣
    "超字数扣分比例": 0.10,   # 超过宽限，扣总分的 10%
    "字数不足比例": 0.50,     # 少于上限一半视为严重不足
    "字数不足扣分比例": 0.20,  # 严重不足，扣总分的 20%
}

FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
POINT_RE = re.compile(r"^\s*-\s*\[\s*(\+?)\s*([\d.]+)\s*\]\s*(.+?)\s*$")


class RubricError(Exception):
    pass


def split_keywords(s):
    return [x.strip() for x in re.split(r"[；;]", s or "") if x.strip()]


def _num(x):
    f = float(x)
    return int(f) if f == int(f) else f


def parse(text):
    """文件文本 → {meta, points, bonus, rules}；格式不对抛 RubricError"""
    m = FRONT_RE.match(text)
    if not m:
        raise RubricError("缺少文件头（--- 包起来的 题目/状态/总分）")
    meta = {}
    for ln in m.group(1).splitlines():
        kv = re.match(r"^\s*([^:：#]+?)\s*[:：]\s*(.*?)\s*(?:\s{2,}#.*)?$", ln)
        if kv:
            meta[kv.group(1)] = kv.group(2)
    try:
        total = _num(meta["总分"])
    except Exception:
        raise RubricError("文件头里的“总分”缺失或不是数字")
    r = {
        "qid": meta.get("题目", ""), "status": meta.get("状态", STATUS_DRAFT), "total": total,
        "words": int(meta["字数"]) if meta.get("字数", "").isdigit() else None,
        "type": meta.get("题型", ""), "source": meta.get("来源", ""),
        "points": [], "bonus": [], "rules": [], "stem": "",
    }
    sec, stem_lines = None, []
    for ln in text[m.end():].splitlines():
        h = re.match(r"^##\s+(.+?)\s*$", ln)
        if h:
            sec = h.group(1)
            continue
        if sec in ("采分点", "加分点"):
            pm = POINT_RE.match(ln)
            if not pm:
                continue
            plus, sc, rest = pm.groups()
            parts = [x.strip() for x in rest.split("|")]
            item = {"name": parts[0], "score": _num(sc), "keywords": [], "source": ""}
            for p in parts[1:]:
                kv = re.match(r"^(关键词|依据|同义)\s*[:：]\s*(.*)$", p)
                if not kv:
                    continue
                if kv.group(1) == "关键词":
                    item["keywords"] = split_keywords(kv.group(2))
                elif kv.group(1) == "同义":
                    item["keywords"] += split_keywords(kv.group(2))
                else:
                    item["source"] = kv.group(2)
            if sec == "采分点":
                item["id"] = len(r["points"]) + 1
                r["points"].append(item)
            else:
                item["id"] = "加%d" % (len(r["bonus"]) + 1)
                r["bonus"].append(item)
        elif sec == "题干":
            stem_lines.append(ln)
        elif sec == "扣分规则":
            em = re.match(r"^\s*-\s+(.+?)\s*$", ln)
            if em:
                r["rules"].append(em.group(1))
    r["stem"] = "\n".join(stem_lines).strip()
    return r


def validate(r, final=False):
    """返回问题列表（空 = 通过）。final=True 时按定稿标准：分值之和必须等于总分"""
    errs = []
    if not r["qid"]:
        errs.append("缺少“题目”编号")
    if not r["points"]:
        errs.append("没有采分点")
    for p in r["points"]:
        if not p["name"]:
            errs.append("采分点 %s 没有名称" % p["id"])
        if p["score"] <= 0:
            errs.append("采分点 %s 的分值必须大于 0" % p["id"])
        if not p["keywords"]:
            errs.append("采分点 %s（%s）没有关键词" % (p["id"], p["name"]))
    s = sum(p["score"] for p in r["points"])
    if final and abs(s - r["total"]) > 1e-6:
        errs.append("采分点分值之和 %s 不等于总分 %s" % (s, r["total"]))
    if s > r["total"] + 1e-6:
        errs.append("采分点分值之和 %s 超过总分 %s" % (s, r["total"]))
    return errs


def allocate(total, n, weights=None):
    """把总分按 0.5 分粒度分给 n 个点；weights 为空则均分，余数从前往后每次补 0.5"""
    if n <= 0:
        return []
    units = int(round(total * 2))
    w = list(weights) if weights else [1] * n
    ws = float(sum(w))
    base = [int(units * x / ws) for x in w]
    rest = units - sum(base)
    i = 0
    while rest > 0:
        base[i % n] += 1
        rest -= 1
        i += 1
    return [_num(b / 2.0) for b in base]


def dumps(r):
    """{meta, points, bonus, rules} → 文件文本（与 parse 互逆）"""
    out = ["---", "题目: %s" % r["qid"], "状态: %s" % r["status"], "总分: %s" % r["total"]]
    if r.get("words"):
        out.append("字数: %s" % r["words"])
    if r.get("type"):
        out.append("题型: %s" % r["type"])
    if r.get("source"):
        out.append("来源: %s" % r["source"])
    out += ["---", "## 采分点"]
    for sec, items, plus in (("采分点", r["points"], ""), ("加分点", r["bonus"], "+")):
        if sec == "加分点":
            if not items:
                continue
            out.append("## 加分点")
        for p in items:
            ln = "- [%s%s] %s | 关键词: %s" % (plus, p["score"], p["name"], "；".join(p["keywords"]))
            if p.get("source"):
                ln += " | 依据: %s" % p["source"]
            out.append(ln)
    if r.get("stem"):
        out += ["## 题干"] + r["stem"].splitlines()
    if r["rules"]:
        out += ["## 扣分规则"] + ["- %s" % x for x in r["rules"]]
    return "\n".join(out) + "\n"


def count_words(text):
    """申论字数：含标点，不含空白和换行"""
    return len(re.sub(r"\s", "", text or ""))


def _norm(s):
    return re.sub(r"\s", "", s or "")


def score(r, answer, judgments, rules=None):
    """
    r: parse() 的结果；answer: 作答原文；judgments: {采分点id: {"hit": full/half/none, "evidence": 原句}}（加分点 id 形如 "加1"）
    返回 {content, bonus, deductions, total, full, rate, words, points: [...]}
    """
    rl = dict(DEFAULT_RULES)
    rl.update(rules or {})
    norm_answer = _norm(answer)
    rows, content, bonus = [], 0.0, 0.0
    for kind, items in (("point", r["points"]), ("bonus", r["bonus"])):
        for p in items:
            j = judgments.get(p["id"]) or judgments.get(str(p["id"])) or {}
            hit = j.get("hit") if j.get("hit") in HIT_FACTOR else "none"
            ev, flag = j.get("evidence") or "", ""
            if hit != "none" and (not _norm(ev) or _norm(ev) not in norm_answer):
                hit, flag = "none", "依据句不在作答中，按未命中处理"
            earned = p["score"] * HIT_FACTOR[hit]
            if kind == "point":
                content += earned
            else:
                bonus += earned
            rows.append({"id": p["id"], "name": p["name"], "score": p["score"], "hit": hit,
                         "earned": earned, "evidence": ev if hit != "none" else "", "flag": flag, "bonus": kind == "bonus"})
    words = count_words(answer)
    ded = []
    lim = r.get("words")
    if lim:
        if words > lim * (1 + rl["超字数宽限"]):
            ded.append({"reason": "超字数（%d/%d 字）" % (words, lim), "points": round(r["total"] * rl["超字数扣分比例"] * 2) / 2.0})
        elif words < lim * rl["字数不足比例"]:
            ded.append({"reason": "字数严重不足（%d/%d 字）" % (words, lim), "points": round(r["total"] * rl["字数不足扣分比例"] * 2) / 2.0})
    total = content + bonus - sum(d["points"] for d in ded)
    total = max(0.0, min(float(r["total"]), total))
    return {"content": content, "bonus": bonus, "deductions": ded, "total": total, "full": r["total"],
            "rate": total / r["total"] if r["total"] else 0.0, "words": words, "points": rows}
