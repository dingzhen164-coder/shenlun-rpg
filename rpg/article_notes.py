"""每日文章的公务手账批注本（纯标准库，rpg/api.py 调用）。

原文快照及排版固定在训练/手札/手写/article-<文章id>.json：
  article: {id, title, source, date, url, paras, layout: 2}
  pages: [{strokes: [], article_lines: [原文行]}]，paper=article，revision=0。
每行按 Unicode 字宽分行，画布宽1000、高1414，正文右侧和页底留白。
前端复用 web/notes.js 的工具、坐标、自动保存和导出；快照不随文章修改重排。
删除原文不会连带删除手账。layout=2 每行64字宽单位，每页30行，不额外插空行。
旧版无笔迹本自动重排；有笔迹本原样保存在 article-<id>-v1，保留坐标和心得，原本改为紧凑版并递增revision。
"""
import datetime as dt
import json
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


def open_book(paths, iid):
    # 先用 find 校验文章编号；笔记文件名始终由程序生成。
    art = articles.find(paths, iid)
    nid = "article-" + art["id"]
    f = notes._file(paths, nid)
    revision, text, compiled, archived = 0, "", "", ""
    if f.is_file():
        old = json.loads(f.read_text(encoding="utf-8"))
        if old.get("article", {}).get("layout", 1) >= 2:
            return {"id": nid}
        # 沿用原文快照；有笔迹的旧排版先原样留副本，不能把笔迹放到重排后的正文上。
        art = old["article"]
        revision, text = old.get("revision", 0) + 1, old.get("text", "")
        compiled = old.get("compiled", "")
        if any(p.get("strokes") for p in old.get("pages", [])):
            archived = nid + "-v1"
            archive = notes._file(paths, archived)
            if not archive.exists():
                backup = dict(old, id=archived, title="旧版批注 · " + art["title"][:50])
                tmp = archive.with_suffix(".tmp")
                tmp.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
                tmp.replace(archive)
    lines = []
    for paragraph in art["paras"]:
        lines.extend(wrap("　　" + paragraph))
    pages = [{"strokes": [], "article_lines": lines[i:i + 30]} for i in range(0, len(lines), 30)]
    if len(pages) > 200:
        raise articles.ArticleError("文章太长，批注本最多200页；请分段导入")
    d = {"id": nid, "title": "文章批注 · " + art["title"][:50], "paper": "article",
         "article": {k: art.get(k, "") for k in ("id", "title", "source", "date", "url", "paras")},
         "pages": pages or [{"strokes": [], "article_lines": []}], "revision": revision,
         "text": text, "compiled": compiled, "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    d["article"]["layout"] = 2
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)
    return {"id": nid, "archived": archived}
