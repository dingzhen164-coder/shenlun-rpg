"""🔮 万象时政：政治理论的时政学习（月半时政 + 专题时政）。

导入：从万象峰政治理论首页的统一导入区上传 PDF，按版面自动拆成：
- 月半时政（封面写“2026 年 9 月·下”）：课程讲义（一条条新闻，★ 星级、【分类】【标题】、正文，正文里夹着随堂题）、
  消化清单（讲义的挖空版）、小黑金卷（题）、答案与解析；
- 专题时政（封面写“…专题”）：小黑母题（每道题后面跟【原文速递】，按【小节】分组）、消化清单、答案与解析。
消化清单里的空（____）对着讲义 / 原文速递自动找出答案，不用 AI。

存放：训练/万象时政/月半时政/<年-月-上|下>.json、训练/万象时政/专题时政/<标题>.json（内容，坚果云同步，换电脑也在），
原 PDF 复制一份到 训练/万象时政/原文/。学习进度（读过哪条、哪些空没记住、精卷答案）存在存档 state["wanxiang_journal"][编号]。

数据格式（JSON）：
  {id, kind: month|topic, title, label, year, month, half, category, overview, groups: [小节名],
   news:  [{no, stars, tag, title, group, paras: [段落], qs: [题的序号 key]}]，  ← 研读
   cloze: [{no, title, news, parts: [{t: 文字} | {a: 答案}]}],              ← 消化（a 为 "" 表示没找出答案）
   questions: [{key, no, kind, stem, stmts: [①…], opts: {A: …}, answer, analysis, news}]}  ← 精卷（进度按 key 记）
调用：rpg/api.py 的 /api/wanxiang/journal*；网页 web/wanxiang_journal.js。
"""
import copy
import os
import tempfile
import datetime as dt
import json
import re
import shutil
import time
from pathlib import Path
from . import political_outline

DIR = "万象时政"
KINDS = {"month": "月半时政", "topic": "专题时政"}
CATEGORIES = ["两会·政府报告", "经济", "农业", "科技", "外交", "党建", "文化", "生态", "民生", "国防", "其他"]
CAT_WORDS = [("两会·政府报告", ("两会", "政府工作报告")), ("农业", ("农业", "农村", "乡村", "一号文件", "粮食")),
             ("外交", ("外交", "峰会", "上合", "金砖", "访问", "APEC", "一带一路", "中美", "中欧")),
             ("科技", ("科技", "创新", "航天", "人工智能", "数字")), ("经济", ("经济", "金融", "贸易", "财政", "消费")),
             ("党建", ("全会", "党", "纪律", "巡视", "政治局")), ("文化", ("文化", "文艺", "文明")),
             ("生态", ("生态", "环境", "碳", "绿色")), ("民生", ("民生", "教育", "医疗", "就业", "养老", "健康")),
             ("国防", ("国防", "军队", "阅兵", "军事"))]
HALF_ORDER = {"上": 1, "下": 2}
CN_NUM = "〇一二三四五六七八九十"
LAST_ACT = {"t": 0.0}          # 最近一次在万象时政里学（翻页、填空、答题），心跳靠它判断算不算学习时间


class JournalError(Exception):
    pass


def folder(paths):
    return paths.train / DIR


def touch():
    LAST_ACT["t"] = time.time()


def studying(window=300):
    return time.time() - LAST_ACT["t"] < window


# ---------------------------------------------------------------- PDF → 段落
NOISE = ("抖音关注公考小黑老师", "时政要点即时学", "Hey，上岸吧！", "@公考小黑老师")
CJK = r"[一-鿿　-〿＀-￯“”‘’《》（）【】①-⑳★]"


def clean(s):
    s = s.replace(" ", " ")
    s = re.sub(r"公众号：?考公资料\s*kk。?", "", s)
    s = re.sub(r"(?<=%s)\s+|\s+(?=%s)" % (CJK, CJK), "", s)
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s) if re.search(r"\d \d", s) and not re.search(r"[A-Za-z]", s) else s
    return s.strip()


def paragraphs(doc):
    """按版面把每页的行拼成段落：缩进（比正文左边距靠右）的行开新段，顶格的行接上一段（跨页也接）。
    页眉页脚、页码去掉。返回 [(页号, 文字)]"""
    rows = []
    for pno, page in enumerate(doc):
        h = page.rect.height
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                t = "".join(sp["text"] for sp in ln["spans"]).strip()
                x0, y0 = ln["bbox"][0], ln["bbox"][1]
                if not t or y0 < h * 0.095 or y0 > h * 0.94 or t in NOISE or re.fullmatch(r"\d{1,3}|[IVX]+", t):
                    continue
                lines.append((round(y0), x0, t, pno + 1))
        lines.sort(key=lambda l: (l[0], l[1]))
        rows += lines
    left = min((r[1] for r in rows), default=0)          # 正文左边距：整份文件最靠左的行
    out = []
    for _, x0, t, pno in rows:
        indent = x0 - left > 12
        starts = re.match(r"^(\d+\.|[①-⑳]|[A-D][\.．]|【)", t) or SECTION.search(t) or political_outline.heading(clean(t))
        closed = out and (re.fullmatch(r"【[^】]+】", out[-1][1].strip()) or SECTION.search(out[-1][1]) or political_outline.heading(out[-1][1]))
        if out and not indent and not starts and not closed:
            out[-1][1] += t
        else:
            out.append([pno, t])
    return [(p, clean(t)) for p, t in out if clean(t)]


# ---------------------------------------------------------------- 段落 → 结构
SECTION = re.compile(r"·(课程讲义|消化清单|小黑金卷|小黑母题)(·答案与解析)?$")
NEWS = re.compile(r"^(\d+)\.(★+)【(.+?)】【(.+)】$")
QSTART = re.compile(r"^(\d+)\.【小黑时政】（(单选|多选|不定项)）(.*)$")
ANS = re.compile(r"^(\d+)\.【答案】([A-D]+)。?(?:解析：)?(.*)$")
GROUP = re.compile(r"^【([^】]+)】$")
OPT = re.compile(r"^([A-D])[\.．](.*)$")
STMT = re.compile(r"^[①-⑳]")


def _sections(paras):
    """切成 {讲义, 清单, 卷, 答案}，每块是段落列表"""
    sec, cur = {}, None
    for _, t in paras:
        m = SECTION.search(t)
        if m and len(t) < 40:
            cur = "ans" if m.group(2) else {"课程讲义": "lecture", "消化清单": "cloze", "小黑金卷": "paper", "小黑母题": "paper"}[m.group(1)]
            sec.setdefault(cur, [])
            continue
        if cur:
            sec[cur].append(t)
    return sec


def _questions(lines):
    """从一串段落里拆出题目；返回 (题目列表, 其余段落及其所属题号)"""
    qs, rest, q = [], [], None
    for t in lines:
        m = QSTART.match(t)
        if m:
            q = {"no": int(m.group(1)), "kind": m.group(2), "stem": m.group(3), "stmts": [], "opts": {}}
            qs.append(q)
            continue
        if q is not None and len(q["opts"]) < 4:
            om = OPT.match(t)
            if om:
                q["opts"][om.group(1)] = om.group(2).strip()
            elif STMT.match(t):
                q["stmts"].append(t)
            elif q["opts"]:
                last = sorted(q["opts"])[-1]
                q["opts"][last] += t
            elif q["stmts"]:
                q["stmts"][-1] += t
            else:
                q["stem"] += t
            if len(q["opts"]) == 4:
                q = None
            continue
        rest.append((t, qs[-1]["no"] if qs else None))
    return qs, rest


def _answers(lines):
    out, cur = [], None
    for t in lines:
        m = ANS.match(t)
        if m:
            cur = {"no": int(m.group(1)), "answer": m.group(2), "analysis": m.group(3).strip()}
            out.append(cur)
        elif cur and not GROUP.match(t):
            cur["analysis"] += t
    for a in out:
        a["analysis"] = a["analysis"].strip()
    return out


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def _after(piece, nxt, src, cur):
    """空前面那段文字在原文里结束的位置（= 答案开始的位置）"""
    if not piece:          # 段首就是空：先找空后面的字，再往回退到上一个标点
        for n in (8, 5, 3):
            idx = src.find(nxt[:n], cur) if nxt[:n] else -1
            if idx >= 0:
                cut = max(src.rfind(c, cur, idx) for c in "，。；：、”“！？")
                return (cut + 1) if cut >= 0 else max(cur, idx - 12)
        return None
    for n in (10, 6, 3, 1):
        pre = piece[-n:]
        for base in (cur, 0):
            pos = src.find(pre, base)
            if pos >= 0:
                return pos + len(pre)
    return None


def _before(nxt, src, a0):
    """空后面那段文字在原文里开始的位置（= 答案结束的位置）"""
    for n in (8, 5, 3, 2, 1):
        suf = nxt[:n]
        if suf:
            idx = src.find(suf, a0)
            if 0 < idx - a0 <= 40:
                return idx
    m = re.search(r"[，。；、：！？”]", src[a0:a0 + 41])
    return a0 + m.start() if m and m.start() > 0 else None


def _fill(text, src, start=0):
    """消化清单的一段（空写成 ____）对着原文 src 找出每个空的答案 → parts，和找到的最后位置"""
    pieces = re.split(r"_{3,}", _norm(text))
    parts, cur = [], start
    for k, piece in enumerate(pieces):
        if piece:
            parts.append({"t": piece})
        if k == len(pieces) - 1:
            break
        ans = ""
        a0 = _after(piece, pieces[k + 1], src, cur)
        if a0 is not None:
            end = _before(pieces[k + 1], src, a0)
            if end is not None:
                ans, cur = src[a0:end], end
        parts.append({"a": ans})
    return parts, cur


def _title_info(doc):
    first = clean(" ".join(doc[0].get_text().split("\n")))
    m = re.search(r"(\d{4})年(\d{1,2})月·?(上|下)", first)
    if m and "专题" not in first:
        y, mo, half = int(m.group(1)), int(m.group(2)), m.group(3)
        return {"kind": "month", "year": y, "month": mo, "half": half,
                "id": "%d-%02d-%s" % (y, mo, half), "title": "%d年%d月·%s" % (y, mo, half), "label": "%s月%s" % (_cn(mo), half)}
    m = re.search(r"小黑月半时政班(.+?)专题", first)
    title = (m.group(1) if m else first).strip(" ·")
    y = re.search(r"(\d{4})年", title)
    return {"kind": "topic", "title": title, "id": _safe(title), "year": int(y.group(1)) if y else None,
            "category": guess_category(title), "label": "专题"}


def _cn(n):
    return CN_NUM[n] if n <= 10 else "十" + CN_NUM[n - 10]


def guess_category(title):
    for cat, words in CAT_WORDS:
        if any(w in title for w in words):
            return cat
    return "其他"


def _safe(name):
    name = re.sub(r'[\\/:*?"<>|#^\[\]\n\r\t]+', " ", str(name or "")).strip()[:60]
    if not name or name.startswith("."):
        raise JournalError("名字不能是空的")
    return name


def parse_pdf(path):
    """读一份小黑月半时政 PDF → 上面说的 JSON 结构（不存盘）"""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # 老版本 pymupdf
        except ImportError:
            raise JournalError("这台电脑缺少读 PDF 的组件（pymupdf）；用桌面版 exe / Mac App 就自带")
    doc = fitz.open(str(path))
    info = _title_info(doc)
    paras = paragraphs(doc)
    sec = _sections(paras)
    if "paper" not in sec and "lecture" not in sec:
        raise JournalError("没认出这是小黑月半时政的讲义（找不到“课程讲义 / 小黑金卷 / 小黑母题”）")
    overview = next((m.group(0) for _, t in paras[:12] for m in [re.search(r"\d{4}年[^。]*收录[^。]*。", t)] if m), "")
    answers = _answers(sec.get("ans", []))
    news, groups = [], []
    if info["kind"] == "month":
        lq, rest = _questions(sec.get("lecture", []))
        cur = None
        for t, _ in rest:
            m = NEWS.match(t)
            if m:
                cur = {"no": int(m.group(1)), "stars": len(m.group(2)), "tag": m.group(3), "title": m.group(4), "group": "", "paras": [], "qs": []}
                news.append(cur)
            elif cur is not None:
                cur["paras"].append(t)
        # 讲义里每道随堂题跟在哪条新闻后面
        order = []
        for t in sec.get("lecture", []):
            m, q = NEWS.match(t), QSTART.match(t)
            if m:
                order.append(("n", int(m.group(1))))
            elif q:
                order.append(("q", int(q.group(1))))
        owner, last = {}, None
        for k, v in order:
            if k == "n":
                last = v
            elif last is not None:
                owner[v] = last
        qs, _ = _questions(sec.get("paper", []))
        if not qs:
            qs = lq
        for q in qs:
            n = owner.get(q["no"])
            q["news"] = next((i for i, x in enumerate(news) if x["no"] == n), None)
            if q["news"] is not None:
                news[q["news"]]["qs"].append(q["no"])
    else:
        # 专题：小黑母题 = 题 + 【原文速递】，按【小节】分组；每道题和它的原文当一条“新闻”
        group, mode, cur, qs = "", "", None, []
        q = None
        for t in sec.get("paper", []):
            g = GROUP.match(t)
            if g and g.group(1) != "原文速递":
                group = g.group(1)
                if group not in groups:
                    groups.append(group)
                mode = ""
                continue
            if g:
                mode = "src"
                cur = {"no": q["no"] if q else len(news) + 1, "stars": 0, "tag": group, "title": group, "group": group, "paras": [], "qs": [q["no"]] if q else []}
                news.append(cur)
                if q:
                    q["news"] = len(news) - 1
                continue
            m = QSTART.match(t)
            if m:
                mode = "q"
                one, _ = _questions([t])
                q = one[0]
                q["group"] = group
                qs.append(q)
                continue
            if mode == "q" and q is not None:
                om = OPT.match(t)
                if om and len(q["opts"]) < 4:
                    q["opts"][om.group(1)] = om.group(2).strip()
                elif STMT.match(t) and not q["opts"]:
                    q["stmts"].append(t)
                elif q["opts"]:
                    k = sorted(q["opts"])[-1]
                    q["opts"][k] += t
                elif q["stmts"]:
                    q["stmts"][-1] += t
                else:
                    q["stem"] += t
            elif mode == "src" and cur is not None:
                cur["paras"].append(t)
    # 答案对题：按题号，题号重复（分组重新编号）时按顺序
    by_no = {}
    for a in answers:
        by_no.setdefault(a["no"], []).append(a)
    used = {}
    for i, q in enumerate(qs):
        lst = by_no.get(q["no"]) or []
        k = used.get(q["no"], 0)
        a = lst[k] if k < len(lst) else (answers[i] if i < len(answers) else None)
        used[q["no"]] = k + 1
        q["answer"] = a["answer"] if a else ""
        q["analysis"] = a["analysis"] if a else ""
    # 消化清单
    cloze = []
    src_all = _norm("".join("".join(n["paras"]) for n in news))
    if info["kind"] == "month":
        cur = None
        for t in sec.get("cloze", []):
            m = NEWS.match(t)
            if m:
                ni = next((i for i, x in enumerate(news) if x["no"] == int(m.group(1))), None)
                cur = {"no": int(m.group(1)), "title": m.group(4), "news": ni, "paras": []}
                cloze.append(cur)
            elif cur is not None:
                cur["paras"].append(t)
        for c in cloze:
            src = _norm("".join(news[c["news"]]["paras"])) if c["news"] is not None else src_all
            parts, pos = [], 0
            for k, p in enumerate(c.pop("paras")):
                if k:
                    parts.append({"br": 1})
                ps, pos = _fill(p, src, pos)
                if not any("a" in x and x["a"] for x in ps) and any("a" in x for x in ps):
                    ps, _ = _fill(p, src_all, 0)
                parts += ps
            c["parts"] = parts
    else:
        group, pos = "", 0
        for t in sec.get("cloze", []):
            g = GROUP.match(t)
            if g:
                group = g.group(1)
                continue
            m = re.match(r"^(\d+)\.(.*)$", t)
            if m:
                parts, pos = _fill(m.group(2), src_all, pos)
                cloze.append({"no": int(m.group(1)), "title": group, "news": None, "parts": parts})
            elif cloze:
                more, pos = _fill(t, src_all, pos)
                cloze[-1]["parts"] += more
        for c in cloze:     # 这一空出自哪道题的原文
            txt = "".join(x.get("t", "") + x.get("a", "") for x in c["parts"])[:12]
            c["news"] = next((i for i, n in enumerate(news) if txt and txt in _norm("".join(n["paras"]))), None)
    # 题目统一用序号（专题里每个小节重新编号，题号会重复）：q["key"] = 第几题（从 0 起），新闻的 qs 存序号
    for n in news:
        n["qs"] = []
    for i, q in enumerate(qs):
        q["key"] = i
        if q.get("news") is not None:
            news[q["news"]]["qs"].append(i)
    if info["kind"] == "topic":
        for index, n in enumerate(news):
            n['title'] = political_outline.title_of(n, index)
        overview = overview or "共 %d 道母题 · %d 条消化清单" % (len(qs), len(cloze))
    info.update(overview=overview, groups=groups, news=news, cloze=cloze, questions=qs, pages=doc.page_count)
    if not qs and not news:
        raise JournalError("PDF 里没拆出新闻和题目，可能不是小黑月半时政的版式")
    info['outline'] = political_outline.outline(info)
    doc.close()
    return info


# ---------------------------------------------------------------- 存取
def _file(paths, kind, iid):
    if kind not in KINDS or not isinstance(iid, str) or not iid or _safe(iid) != iid:
        raise JournalError("期刊编号无效")
    return folder(paths) / KINDS[kind] / (_safe(iid) + ".json")


def _write(f, data):
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="."+f.name, dir=str(f.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=1)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, str(f))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def save_import(paths, pdf_path, name=""):
    """解析 + 存进库（同一期再导入就覆盖内容，学习进度不动）。返回 {kind, id, title, …计数}"""
    data = parse_pdf(pdf_path)
    data["imported"] = dt.date.today().isoformat()
    f = _file(paths, data["kind"], data["id"])
    if f.exists() and data["kind"] == "topic":      # 再导入时保留自己改过的分类
        try:
            data["category"] = json.loads(f.read_text(encoding="utf-8")).get("category") or data["category"]
        except ValueError:
            pass
    src = folder(paths) / "原文" / ("%s-%s.pdf" % (KINDS[data["kind"]], data["id"]))
    src.parent.mkdir(parents=True, exist_ok=True)
    if Path(pdf_path).resolve() != src.resolve():
        shutil.copyfile(str(pdf_path), str(src))
    data["pdf"] = src.relative_to(paths.vault).as_posix()
    _write(f, data)
    blanks = sum(1 for c in data["cloze"] for p in c["parts"] if "a" in p)
    found = sum(1 for c in data["cloze"] for p in c["parts"] if p.get("a"))
    return {"kind": data["kind"], "id": data["id"], "title": data["title"], "news": len(data["news"]),
            "cloze": len(data["cloze"]), "blanks": blanks, "found": found, "questions": len(data["questions"]),
            "answered": sum(1 for q in data["questions"] if q.get("answer"))}


def load(paths, kind, iid):
    if kind not in KINDS or not isinstance(iid, str) or not iid or _safe(iid) != iid:
        raise JournalError("期刊编号无效")
    f = _file(paths, kind, iid)
    if not f.is_file():
        raise JournalError("这一期不见了（可能在另一台电脑上删了）")
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if kind == 'topic':
            data['outline'] = political_outline.outline(data)
        return data
    except ValueError:
        raise JournalError("这一期的文件坏了：%s" % f.name)


def progress_of(g, kind, iid):
    return g.state.setdefault("wanxiang_journal", {}).setdefault(kind + ":" + iid, {"read": [], "cloze": {}, "quiz": {}})


def news_source(data, kind, index):
    from . import politics_reading
    news = data['news'][index]
    text = '\n'.join(news['paras'])
    ranges, keys = politics_reading.cloze_ranges(text, [(row, i) for i, row in enumerate(data['cloze']) if row.get('news') == index])
    return {'text': text, 'title': news['title'], 'date': data.get('title', ''), 'support': {},
            'id': ['wanxiang_journal', data['id'], kind, index], 'emphasis': ranges, 'cloze_keys': keys}


def with_reading(paths, data, kind):
    from . import politics_reading
    data['reading'] = [politics_reading.reading(paths, news_source(data, kind, i)) for i in range(len(data['news']))]
    return data


def summary(data, pr):
    blanks = ['%d-%d' % (i,k) for i,c in enumerate(data['cloze']) for k,p in enumerate(c['parts']) if p.get('a')]
    seen = [b for b in blanks if b in pr['cloze']]
    forgot = sum(1 for b in seen if pr['cloze'][b] == 0)
    done = [q for q in data["questions"] if str(q["key"]) in pr["quiz"]]
    right = sum(1 for q in done if pr["quiz"][str(q["key"])].get("ok"))
    n_news = len(data["news"])
    read = len([i for i in pr["read"] if i < n_news])
    count=len(blanks);seen_count=len(seen)
    if data.get('digest'):
        count=data['digest']['counts']['blanks'];seen_count=data['digest']['counts']['seen'];forgot=data['digest']['counts']['forgot']
    parts = [read / n_news if n_news else 1, seen_count / count if count else 1,
             len(done) / len(data["questions"]) if data["questions"] else 1]
    return {"read": read, "news": n_news, "blanks": count, "seen": seen_count, "forgot": forgot,
            "questions": len(data["questions"]), "done": len(done), "right": right,
            "frac": round(sum(parts) / 3, 3), "last": pr.get("last", "")}


def listing(g):
    out = {"month": [], "topic": []}
    root = folder(g.paths)
    for kind in KINDS:
        d = root / KINDS[kind]
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            item = {k: data.get(k) for k in ("id", "kind", "title", "label", "year", "month", "half", "category", "overview", "pdf")}
            item["id"] = f.stem
            item["heads"] = [n["title"] for n in data.get("news", []) if n.get("stars", 0) >= 2][:5] or \
                            [g_ for g_ in data.get("groups", [])][:5]
            from . import politics_digest
            data['digest']=politics_digest.get(g,{'source':'wanxiang_journal','kind':kind,'id':f.stem})
            item["stat"] = summary(data, progress_of(g, kind, f.stem))
            out[kind].append(item)
    out["month"].sort(key=lambda x: (x.get("year") or 0, x.get("month") or 0, HALF_ORDER.get(x.get("half"), 0)), reverse=True)
    out["topic"].sort(key=lambda x: (CATEGORIES.index(x["category"]) if x.get("category") in CATEGORIES else 99, -(x.get("year") or 0), x["title"]))
    out["categories"] = CATEGORIES
    return out


def get(g, kind, iid):
    if kind not in KINDS:
        raise JournalError("种类不对")
    data = with_reading(g.paths, load(g.paths, kind, iid), kind)
    from . import politics_digest
    data['digest']=politics_digest.get(g,{'source':'wanxiang_journal','kind':kind,'id':iid})
    pr = progress_of(g, kind, iid)
    pr["last"] = g.t
    touch()
    return {"data": data, "progress": pr, "stat": summary(data, pr)}


def mark(g, kind, iid, body):
    """记进度：{read: 新闻序号} / {cloze: "条-空", ok: 0|1} / {quiz: 题号, choice: "B"}"""
    data = with_reading(g.paths, load(g.paths, kind, iid), kind)
    pr = progress_of(g, kind, iid)
    pr["last"] = g.t
    touch()
    ev = []
    if "read" in body:
        if type(body['read']) is not int:
            raise JournalError('阅读条目无效')
        i = int(body["read"])
        if 0 <= i < len(data["news"]):
            if body.get("off"):
                pr["read"] = [x for x in pr["read"] if x != i]
            elif i not in pr["read"]:
                pr["read"].append(i)
    if "cloze" in body:
        key = str(body["cloze"])
        allowed = {'%d-%d'%(i,k) for i,row in enumerate(data['cloze']) for k,p in enumerate(row['parts']) if p.get('a')}
        if key not in allowed:
            raise JournalError('消化条目不存在')
        if body.get("clear"):
            pr["cloze"].pop(key, None)
        else:
            pr["cloze"][key] = 1 if body.get("ok") else 0
    if "quiz" in body:
        q = next((x for x in data["questions"] if str(x["key"]) == str(body["quiz"])), None)
        if not q:
            raise JournalError("找不到这道题")
        choice = str(body.get("choice") or "").upper()
        if not re.fullmatch(r'[A-D]{1,4}', choice) or len(set(choice)) != len(choice):
            raise JournalError("请选择有效选项")
        if not q.get('answer'):
            raise JournalError('这道题没有参考答案，暂不判分')
        if len(q['answer']) == 1 and len(choice) != 1:
            raise JournalError('这是一道单选题')
        choice = ''.join(sorted(choice))
        old = pr["quiz"].get(str(q["key"]))
        ok = choice == ''.join(sorted(q['answer']))
        pr["quiz"][str(q["key"])] = {"a": choice, "ok": ok, "d": g.t, "n": (old or {}).get("n", 0) + 1}
        awarded = pr.setdefault("awarded", list(pr["quiz"].keys()) if old else [])
        if not old and str(q["key"]) not in awarded and q.get("answer"):
            awarded.append(str(q["key"]))
            ev = g._award(g.rules.xp("实战答对") if ok else g.rules.xp("实战答错"), "bank", g.news_board(), "wanxiang_journal:%s:%s" % (iid, q["key"]), ok,
                          "万象时政 · %s 第%s题" % (data["title"], q["no"]))
    if body.get("reset"):
        part = body["reset"]
        if part in ("read", "cloze", "quiz"):
            pr[part] = [] if part == "read" else {}
    from . import politics_digest
    data['digest']=politics_digest.get(g,{'source':'wanxiang_journal','kind':kind,'id':iid})
    return {"progress": pr, "stat": summary(data, pr), "events": ev}


def set_meta(g, kind, iid, body):
    data = load(g.paths, kind, iid)
    if body.get("category"):
        if body["category"] not in CATEGORIES:
            raise JournalError("没有这个分类")
        data["category"] = body["category"]
    _write(_file(g.paths, kind, iid), data)
    return {"ok": True}


def delete(g, kind, iid):
    f = _file(g.paths, kind, iid)
    if f.is_file():
        f.unlink()
    g.state.setdefault("wanxiang_journal", {}).pop(kind + ":" + iid, None)
    return {"ok": True}


def forgot_cards(g, kind, iid):
    """消化清单里没记住的空 → 玉简（填空），放进 <本科目的时政模块>::万象时政 简匣（行测 = 政治理论，申论 = 综合分析）；一个空一枚，已经做过的不重复"""
    from . import cards
    data = load(g.paths, kind, iid)
    pr = progress_of(g, kind, iid)
    made = set(pr.setdefault("carded", []))
    items = []
    for i,c in enumerate(data['cloze']):
        for k, p in enumerate(c["parts"]):
            key = '%d-%d'%(i,k)
            if "a" not in p or not p["a"] or pr["cloze"].get(key) != 0 or key in made:
                continue
            # 取这个空所在的那一句（前后到句号 / 分号）
            before = "".join(x.get("t", "") or x.get("a", "") for x in c["parts"][:k])
            after = "".join(x.get("t", "") or x.get("a", "") for x in c["parts"][k + 1:])
            b = re.split(r"[。；！？]", before)[-1]
            a = re.split(r"(?<=[。；！？])", after)[0]
            items.append({"type": "填空", "front": "%s{{c1::%s}}%s" % (b, p["a"], a),
                          "extra": "%s · %s" % (data["title"], c.get("title") or ""), "tags": ["万象时政", data["title"]]})
            made.add(key)
    if not items:
        return {"added": 0}
    r = cards.add_many(g, "%s::万象时政" % g.news_board(), items)
    pr["carded"] = sorted(made)
    r["deck"] = "%s › 万象时政" % g.news_board()
    return r


# ---------------------------------------------------------------- 🧙 问师傅（研读页左栏）：总结本条怎么记（尤其红字）/ 不懂的地方提问
ASK_SYSTEM = ("你是帮学员备考公务员政治理论（时政）的师傅。下面给你一条时政学习材料（讲义原文），"
              "以及消化清单要挖空考的字句（学员看到的“红字”）。回答以材料为准，不编造材料里没有的时间、数字、提法；"
              "需要补充背景常识时，单独标明“背景补充”，并尽量简短。\n"
              "用 Markdown，口语化、条理清楚，不超过 450 字。")
ASK_MEMORY = ("请帮我记住这一条：\n"
              "1. 用 3~5 条要点把这一条的核心内容理清（谁、什么时候、什么会 / 文件、提出了什么）；\n"
              "2. 红字逐个（或分组）给记忆办法：口诀 / 首字连读、谐音、对比易混提法、数字记忆、联想画面等；\n"
              "3. 指出最容易出题的 2~3 个点（选项常怎么偷换）；\n"
              "4. 最后给 3 道一句话自测题（只出题，答案放在最后一行）。")


def _news_context(data, i):
    n = data["news"][i]
    keys = [p["a"] for c in data["cloze"] if c.get("news") == i for p in c["parts"] if p.get("a")]
    head = "【%s · %s】%s" % (data["title"], n.get("tag") or n.get("group") or "", n["title"])
    qs = [data["questions"][k] for k in n.get("qs", []) if k < len(data["questions"])]
    if data.get("kind") == "topic" and qs:
        head += "\n【对应母题题干】" + qs[0]["stem"]
    return "%s\n【讲义原文】\n%s\n【红字（消化清单要考的空）】%s" % (
        head, "\n".join(n["paras"])[:6000], "、".join(keys) if keys else "（这一条没有挖空）")


def ask_prompt(data, i, question, history):
    if not 0 <= int(i) < len(data["news"]):
        raise JournalError("没有这一条")
    msgs = [{"role": "system", "content": ASK_SYSTEM},
            {"role": "user", "content": _news_context(data, int(i)) + "\n\n" + (question or ASK_MEMORY)}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.insert(-1, {"role": h["role"], "content": str(h["content"])[:2500]})
    return msgs


def save_ask(g, kind, iid, i, question, reply):
    """问过的存进进度（每条新闻最多留 12 问），下次打开还能看"""
    pr = progress_of(g, kind, iid)
    lst = pr.setdefault("ask", {}).setdefault(str(int(i)), [])
    lst.append({"q": question or "总结这一条怎么记", "a": reply, "t": dt.datetime.now().strftime("%m-%d %H:%M")})
    del lst[:-12]
    return lst


def ensure_legacy(g):
    """首次复制旧期刊、原PDF、批注和进度；独立快照，不改旧目录或奖励。"""
    from . import politics
    root = folder(g.paths)
    marker = root / '迁移.json'
    legacy = g.paths.train / '天机简报'
    if not marker.exists():
        for kind, label in KINDS.items():
            for file in sorted((legacy / label).glob('*.json')):
                if legacy.resolve() not in file.resolve().parents:
                    continue
                target = _file(g.paths, kind, file.stem)
                if target.exists():
                    continue
                try:
                    data = json.loads(file.read_text(encoding='utf-8'))
                    old_pdf = g.paths.vault / str(data.get('pdf') or '')
                    data['pdf'] = ''
                    if old_pdf.is_file() and (legacy/'原文').resolve() in old_pdf.resolve().parents:
                        pdf = root/'原文'/('%s-%s.pdf' % (label, _safe(file.stem)))
                        pdf.parent.mkdir(parents=True, exist_ok=True)
                        if not pdf.exists():
                            shutil.copyfile(str(old_pdf), str(pdf))
                        data['pdf'] = pdf.relative_to(g.paths.vault).as_posix()
                    for i, news in enumerate(data.get('news', [])):
                        text = '\n'.join(news['paras'])
                        old_id = politics.digest([['tianji', data['id'], kind, i], text])
                        new_id = politics.digest([['wanxiang_journal', data['id'], kind, i], text])
                        old_notes = g.paths.train/'词义批注'/(old_id+'.json')
                        new_notes = g.paths.train/'词义批注'/(new_id+'.json')
                        if old_notes.exists() and not new_notes.exists():
                            politics.atomic_json(new_notes, politics.read_json(old_notes, {}))
                    _write(target, data)
                except (ValueError, KeyError, TypeError) as error:
                    raise JournalError('旧期刊无法复制，原件未修改：%s（%s）' % (file.name, error))
        _write(marker, {'version': 1, 'date': g.t})
    if not g.state.get('wanxiang_journal_seeded'):
        progress = g.state.setdefault('wanxiang_journal', {})
        for key, value in g.state.get('tianji', {}).items():
            if key not in progress:
                item = copy.deepcopy(value)
                item['awarded'] = sorted(item.get('quiz', {}).keys())
                progress[key] = item
        g.state['wanxiang_journal_seeded'] = True


def register(api):
    """万象峰专用接口，行测限定；与旧天机台接口和前端完全分离。"""
    import base64
    from . import politics, politics_import, politics_digest, ai

    def run(fn, body):
        with api.open_game() as g:
            if g.subject != '行测' or not g.paths.vault:
                raise api.ApiError('万象峰时政仅在行测资料库中使用')
            try:
                ensure_legacy(g)
                return fn(g, body)
            except (JournalError, politics.PoliticsError, ValueError, TypeError, KeyError) as error:
                raise api.ApiError(str(error))

    def import_pdf(g, body):
        channel = body.get('channel', 'sprint-study')
        if channel not in ('month', 'topic', 'sprint-study', 'sprint-quiz', 'digest'):
            raise JournalError('请选择正确的导入栏目')
        if channel=='digest':return politics_digest.import_pdf(g,body)
        if channel.startswith('sprint-'):
            return dict(politics_import.import_pdf(g.paths, dict(body, mode='practice' if channel=='sprint-quiz' else 'study')), channel=channel)
        raw = str(body.get('data') or '').split(',', 1)[-1]
        if len(raw) > 56*1024*1024:
            raise JournalError('PDF过大，请拆成40MB以内后导入')
        try:
            content = base64.b64decode(raw, validate=True)
        except (ValueError, TypeError):
            raise JournalError('PDF数据无效')
        if len(content) > 40*1024*1024 or not content.startswith(b'%PDF'):
            raise JournalError('请选择40MB以内的PDF文件')
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp)/'upload.pdf'
            pdf.write_bytes(content)
            parsed = parse_pdf(pdf)
            if parsed['kind'] != channel:
                raise JournalError('识别为%s，请选择对应导入栏目；本次未写入' % KINDS[parsed['kind']])
            return dict(save_import(g.paths, pdf), channel=channel)

    def ask(body):
        with api.open_game(save=False) as g:
            if g.subject != '行测' or not g.paths.vault:
                raise api.ApiError('万象峰时政仅在行测资料库中使用')
            try:
                data = load(g.paths, body.get('kind'), body.get('id'))
                msgs = ask_prompt(data, int(body.get('news') or 0), str(body.get('question') or '').strip(), body.get('history'))
            except (JournalError, ValueError) as error:
                raise api.ApiError(str(error))
            vault = g.paths.vault
        if not ai.available():
            raise api.ApiError('请先在设置中配置AI接口，已有解释仍可查看')
        reply = ai.chat(msgs, temperature=.5, max_tokens=1200).strip()
        def save(g, b):
            if g.paths.vault != vault:
                raise JournalError('资料库已切换，本次回复未写入其他库')
            return {'reply': reply, 'saved': save_ask(g, b['kind'], b['id'], b.get('news', 0), b.get('question', ''), reply)}
        return run(save, body)

    api.ROUTES[('GET', '/api/wanxiang/journal')] = lambda b: run(lambda g, b: listing(g), b)
    api.ROUTES[('POST', '/api/wanxiang/journal')] = api.ROUTES[('GET', '/api/wanxiang/journal')]
    def pdf(g, b):
        from urllib.parse import quote
        rel = str(b.get('path') or '')
        path = (g.paths.vault / rel).resolve()
        if (folder(g.paths)/'原文').resolve() not in path.parents or not path.is_file():
            raise JournalError('原PDF不存在或不在万象峰资料目录中')
        return {'url': '/notes-file?p=%s&t=%s' % (quote(rel), api.export_token(rel))}
    api.ROUTES[('POST','/api/wanxiang/journal/pdf')] = lambda b: run(pdf,b)
    for name, fn in {
        'get': lambda g,b: get(g,b.get('kind'),b.get('id')),
        'mark': lambda g,b: mark(g,b.get('kind'),b.get('id'),b),
        'meta': lambda g,b: set_meta(g,b.get('kind'),b.get('id'),b),
        'delete': lambda g,b: delete(g,b.get('kind'),b.get('id')),
        'cards': lambda g,b: forgot_cards(g,b.get('kind'),b.get('id')),
    }.items():
        api.ROUTES[('POST','/api/wanxiang/journal/'+name)] = lambda b, fn=fn: run(fn,b)
    api.ROUTES[('POST','/api/wanxiang/journal/ask')] = ask
    api.ROUTES[('POST','/api/wanxiang/import')] = lambda b: run(import_pdf,b)
    api.ROUTES[('POST','/api/wanxiang/digest/targets')] = lambda b: run(lambda g,b:politics_digest.targets(g),b)
    api.ROUTES[('POST','/api/wanxiang/digest/get')] = lambda b: run(lambda g,b:politics_digest.get(g,b.get('target')),b)
    api.ROUTES[('POST','/api/wanxiang/digest/mark')] = lambda b: run(politics_digest.mark,b)
