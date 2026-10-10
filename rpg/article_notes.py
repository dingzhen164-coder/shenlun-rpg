"""每日文章的公务手账批注本（纯标准库，rpg/api.py 调用）。

原文快照及排版固定在训练/手札/手写/article-<文章id>.json：
  article: {id, title, source, date, url, paras, layout: 1}
  pages: [{strokes: [], article_lines: [原文行]}]，paper=article，revision=0。
每行按 Unicode 字宽分行，画布宽1000、高1414，正文右侧和页底留白。
前端复用 web/notes.js 的工具、坐标、自动保存和导出；快照不随文章修改重排。
删除原文不会连带删除手账。旧本子的数据结构与坐标不变。
"""
import datetime as dt
import json
import unicodedata

from . import articles, notes


def wrap(text, columns=42):
    """两单位为一个汉字宽度；避免截断正文，ASCII混排占半宽。"""
    lines, line, width = [], "", 0
    for char in str(text):
        if char == "\n":
            lines.append(line)
            line, width = "", 0
            continue
        size = 2 if unicodedata.east_asian_width(char) in ("W", "F", "A") else 1
        if width + size > columns and line:
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
    if f.is_file():
        return {"id": nid}
    lines = []
    for paragraph in art["paras"]:
        lines.extend(wrap("　　" + paragraph))
        lines.append("")
    pages = [{"strokes": [], "article_lines": lines[i:i + 18]} for i in range(0, len(lines), 18)]
    if len(pages) > 200:
        raise articles.ArticleError("文章太长，批注本最多200页；请分段导入")
    d = {"id": nid, "title": "文章批注 · " + art["title"][:50], "paper": "article",
         "article": {k: art.get(k, "") for k in ("id", "title", "source", "date", "url", "paras")},
         "pages": pages or [{"strokes": [], "article_lines": []}], "revision": 0,
         "text": "", "compiled": "", "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    d["article"]["layout"] = 1
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)
    return {"id": nid}
