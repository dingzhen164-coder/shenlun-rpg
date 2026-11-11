"""每日文章的公务手账批注本（纯标准库，rpg/api.py 调用）。

原文快照及排版固定在训练/手札/手写/article-<文章id>.json：
  article: {id, title, source, date, url, paras, layout: 2}
  pages: [{strokes: [], article_lines: [原文行]}]，paper=article，revision=0。
每行按 Unicode 字宽分行，画布宽1000、高1414，正文右侧和页底留白。
前端复用 web/notes.js 的工具、坐标、自动保存和导出；快照不随文章修改重排。
删除原文不会连带删除手账。layout=2 每行64字宽单位，每页30行，不额外插空行。
旧版无笔迹本自动重排；有笔迹本原样保存在 article-<id>-v1，保留坐标和心得，原本改为紧凑版并递增revision。
layout=3（2026-11-11 用户嫌挤、看着累）：正文 24px、行距 46、段与段之间空半行（article_lines 里的 "" 占 20px）、每段首行缩进两字；
  电头 / 括号副标题单独成行、淡色、不缩进（行首 \x01 作记号）；旁批栏收窄到右侧约一成（正文 60–860，旁批线 880）。
  按高度分页：第一页有大标题，后面各页顶上一行小标题；每页 article_top = 第一行正文的基线 y，前端照着画，前后端不各算一遍。
  抓来的正文先 tidy：去多余空格 / 杂点、合并句子中间断开的段。旧版本（layout 1/2）有笔迹的原样另存 article-<id>-v<旧版号>，新本从头排、心得保留。
"""
import datetime as dt
import json
import re
import unicodedata

from . import articles, notes


def wrap(text, columns=64):
    """两单位为一个汉字宽度；避免截断正文，ASCII混排占半宽。"""
    lines, line, width = [], "", 0
    for char in str(text):
        if char == "\n":
            lines.append(line)
            line, width = "", 0
            continue
        size = 2 if unicodedata.east_asian_width(char) in ("W", "F", "A") else 1
        if width + size > columns and line:
            # 收尾标点不在行首、开括号不在行末；把末字带到下一行，不增删原文。
            if len(line) > 1 and (char in "，。！？；：、）》】”’…,.!?;:%％" or line[-1] in "（《【“‘("):
                last = line[-1]
                lines.append(line[:-1])
                line = last
                width = 2 if unicodedata.east_asian_width(last) in ("W", "F", "A") else 1
            else:
                lines.append(line)
                line, width = "", 0
        line += char
        width += size
    if line:
        lines.append(line)
    return lines


# ---- layout 3 的版面数字（web/notes.js 的 drawArticle 用同一套） ----
L3 = {"body_cols": 66, "muted_cols": 70, "title_cols": 58, "line": 46, "gap": 20, "bottom": 1270, "next_top": 112}
DATELINE = re.compile(r"^(?:新华社|人民日报|本报|央视|中新社|光明日报|经济日报|求是)[^。，]{0,24}电$|^[（(][^（）()]{4,90}[）)]$|^[（(]?记者[^。]{0,30}[）)]?$")
HEADING = re.compile(r"^(?:[一二三四五六七八九十]+、|[（(][一二三四五六七八九十\d]+[）)]|\d+[.．、]|第[一二三四五六七八九十]+[部章节条])")


def tidy(paras):
    """抓来的正文整理一下再排版：去多余空格和单独的杂点，句子中间断开的段接回去；不改字。"""
    cjk = "\u4e00-\u9fff，。；：！？、（）《》“”‘’【】"
    out = []
    for p in paras:
        t = re.sub(r"[ \t\u00a0\u3000]+", " ", str(p)).strip()
        t = re.sub(r"(?<=[%s])\s+(?=[%s])" % (cjk, cjk), "", t)
        if out and re.fullmatch(r"[。！？；，、]+", t):        # 被单独断开的句末标点：接回上一段，不丢
            out[-1] += t
            continue
        if not t or re.fullmatch(r"[·•.。、,，\-—_*~\s]+", t):   # 单独的杂点
            continue
        if (out and len(out[-1]) >= 30 and not re.search(r"[。！？；：…”’」』）)\]】]$", out[-1])
                and not HEADING.match(t) and not DATELINE.match(t) and not DATELINE.match(out[-1])):
            out[-1] += t
        else:
            out.append(t)
    return out


def layout3(art):
    """按高度分页：返回 [{article_lines, article_top}]"""
    title_lines = wrap(art.get("title", ""), L3["title_cols"])[:3] or [""]
    first_top = 64 + (len(title_lines) - 1) * 40 + 46 + 20 + 50
    rows = []
    for i, para in enumerate(tidy(art.get("paras", []))):
        if i:
            rows.append("")                                 # 段与段之间空半行
        if DATELINE.match(para):
            rows.extend("\x01" + x for x in wrap(para, L3["muted_cols"]))
        else:
            rows.extend(wrap("　　" + para, L3["body_cols"]))
    pages, cur, top = [], [], first_top
    y = top
    for r in rows:
        if r == "" and not cur:
            continue                                        # 页首不留空
        h = L3["gap"] if r == "" else L3["line"]
        if r != "" and y > L3["bottom"] and cur:
            pages.append({"strokes": [], "article_lines": cur, "article_top": top})
            cur, top = [], L3["next_top"]
            y = top
        cur.append(r)
        y += h
    pages.append({"strokes": [], "article_lines": cur, "article_top": top})
    return pages


def open_book(paths, iid):
    # 先用 find 校验文章编号；笔记文件名始终由程序生成。
    art = articles.find(paths, iid)
    nid = "article-" + art["id"]
    f = notes._file(paths, nid)
    revision, text, compiled, archived = 0, "", "", ""
    if f.is_file():
        old = json.loads(f.read_text(encoding="utf-8"))
        old_layout = old.get("article", {}).get("layout", 1)
        if old_layout >= 3:
            return {"id": nid}
        # 沿用原文快照；有笔迹的旧排版先原样留副本，不能把笔迹放到重排后的正文上。
        art = old["article"]
        revision, text = old.get("revision", 0) + 1, old.get("text", "")
        compiled = old.get("compiled", "")
        if any(p.get("strokes") for p in old.get("pages", [])):
            archived = "%s-v%d" % (nid, old_layout)
            archive = notes._file(paths, archived)
            if not archive.exists():
                backup = dict(old, id=archived, title="旧版批注 · " + art["title"][:50])
                tmp = archive.with_suffix(".tmp")
                tmp.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
                tmp.replace(archive)
    pages = layout3(art)
    if len(pages) > 200:
        raise articles.ArticleError("文章太长，批注本最多200页；请分段导入")
    d = {"id": nid, "title": "文章批注 · " + art["title"][:50], "paper": "article",
         "article": {k: art.get(k, "") for k in ("id", "title", "source", "date", "url", "paras")},
         "pages": pages or [{"strokes": [], "article_lines": []}], "revision": revision,
         "text": text, "compiled": compiled, "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    d["article"]["layout"] = 3
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)
    return {"id": nid, "archived": archived}
