"""藏经阁「清除」：把导入的套卷、板块题目里混进来的广告文字（如“一手最全公考资源加微信 biguo368”）清掉。

导入时的文字识别分不出哪段是广告，所以由用户事后清除：
  找：输入一段广告文字，列出所有出现它的地方（哪份卷、第几题、前后文），命中处高亮；匹配时忽略空白和大小写。
  清：勾选要清的，只删这一段文字（整行都是广告就连行一起删）；删之前把原文件备份，可以“撤销上一次清除”。
  词库：点“以后导入自动清除”，这段文字记进广告词库，之后每次导入套卷、板块题时自动清掉。

范围（只处理程序自己写在 训练/ 里的内容，不碰库里原有的真题复盘、原 PDF 和笔记）：
  paper = 训练/模考复盘/ 下导入的套卷与模考复盘；bank = 训练/题库/ 下的板块题目（含待修）。

数据：
  训练/清除/广告词库.json   [{"text": 广告文字, "added": 日期}]
  训练/清除/备份/<时间>/manifest.json  {"time", "text", "files": {相对训练/的路径: 清除后文件的sha1}} + 备份的原文件（同相对路径）
"""
import datetime as dt
import hashlib
import json
import re
import shutil

SCOPES = ("paper", "bank")
SCOPE_DIRS = {"paper": "模考复盘", "bank": "题库"}
CONTEXT = 18                 # 命中处前后各取多少字做预览
DIR = "清除"
_WORDS_CACHE = {}


class AdError(ValueError):
    pass


def _guard(g):
    if getattr(g, "subject", "") != "行测":
        raise AdError("清除只在行测科目使用（整卷与板块题目都在行测里）")
    if not g.paths.train:
        raise AdError("请先选择行测学习库")


def _root(paths):
    return paths.train / DIR


def _pattern(text):
    """广告文字 → 正则：每个字之间允许任意空白，忽略大小写"""
    chars = [c for c in str(text or "") if not c.isspace()]
    if len(chars) < 3:
        raise AdError("广告文字太短（至少 3 个字），避免误删正文")
    return re.compile(r"\s*".join(re.escape(c) for c in chars), re.I)


def _files(paths, scopes):
    out = []
    for scope in scopes:
        d = paths.train / SCOPE_DIRS[scope]
        if d.is_dir():
            out += [(scope, f) for f in sorted(d.rglob("*.md")) if DIR not in f.relative_to(paths.train).parts]
    return out


def _scopes(value):
    chosen = [s for s in (value or SCOPES) if s in SCOPES]
    return chosen or list(SCOPES)


def _heading(text, pos):
    """pos 之前最近的一行 ### 标题（题号 / 题目编号）和所在文件夹里的卷名"""
    at = text.rfind("\n### ", 0, pos)
    if at < 0:
        at = 0 if text.startswith("### ") and pos > 0 else -1
    if at < 0:
        return ""
    line = text[at:].lstrip("\n").split("\n", 1)[0]
    return line.lstrip("# ").strip()[:40]


def _label(paths, f):
    rel = f.relative_to(paths.train)
    parts = rel.parts
    if parts[0] == SCOPE_DIRS["paper"] and len(parts) >= 3:
        return "套卷/复盘 · %s · %s" % (parts[1], f.stem)
    return "板块题库 · %s" % "/".join(parts[1:]).rsplit(".", 1)[0]


def _hits(paths, text, scopes):
    pat = _pattern(text)
    out = []
    for scope, f in _files(paths, scopes):
        try:
            raw = f.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for m in pat.finditer(raw):
            a, b = m.start(), m.end()
            ls = raw.rfind("\n", 0, a)+1
            le = raw.find("\n", b)
            le = len(raw) if le < 0 else le
            whole_line = not (raw[ls:a].strip() or raw[b:le].strip())
            left, right = raw[max(ls, a-CONTEXT):a], raw[b:min(le, b+CONTEXT)]
            mid = bool(raw[ls:a].strip()) and bool(raw[b:le].strip())
            out.append({"id": "%s@%d" % (f.relative_to(paths.train).as_posix(), a), "file": f.relative_to(paths.train).as_posix(),
                        "scope": scope, "where": _label(paths, f), "question": _heading(raw, a), "start": a,
                        "before": left, "hit": m.group(0), "after": right, "whole_line": whole_line, "check": mid})
    return out


def find(g, body):
    _guard(g)
    scopes = _scopes(body.get("scopes"))
    hits = _hits(g.paths, body.get("text"), scopes)
    return {"hits": hits[:500], "total": len(hits), "files": len({h["file"] for h in hits}), "truncated": len(hits) > 500}


def _remove(raw, spans):
    """spans：[(a,b)]（按位置从小到大）。整行都是广告就连换行一起删，否则只删这一段"""
    out, last = [], 0
    for a, b in spans:
        ls = raw.rfind("\n", 0, a)+1
        le = raw.find("\n", b)
        le = len(raw) if le < 0 else le
        if not (raw[ls:a].strip() or raw[b:le].strip()) and ls >= last:
            out.append(raw[last:ls])
            last = min(len(raw), le+1)
        else:
            out.append(raw[last:a])
            last = b
    out.append(raw[last:])
    return "".join(out)


def _sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def clean(g, body):
    """清除命中的文字。body.ids 给了就只清这些（id 来自 find），不给就清全部命中。清除前备份原文件。"""
    _guard(g)
    paths = g.paths
    text = body.get("text")
    pat = _pattern(text)
    want = body.get("ids")
    want = None if want is None else set(want)
    by_file = {}
    for h in _hits(paths, text, _scopes(body.get("scopes"))):
        if want is None or h["id"] in want:
            by_file.setdefault(h["file"], []).append(h["start"])
    if not by_file:
        return {"cleaned": 0, "files": 0, "undo": False}
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    box = _root(paths) / "备份" / stamp
    done, count = {}, 0
    for rel, starts in by_file.items():
        f = paths.train / rel
        raw = f.read_text(encoding="utf-8-sig")
        spans = []
        for a in sorted(starts):
            m = pat.match(raw, a)
            if m:
                spans.append((m.start(), m.end()))
        if not spans:
            continue
        new = _remove(raw, spans)
        keep = box / rel
        keep.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, keep)
        f.write_text(new, encoding="utf-8", newline="\n")
        done[rel] = _sha(new)
        count += len(spans)
    if not done:
        return {"cleaned": 0, "files": 0, "undo": False}
    (box / "manifest.json").write_text(json.dumps({"time": stamp, "text": str(text), "files": done}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"cleaned": count, "files": len(done), "undo": True, "backup": stamp}


def last_backup(paths):
    d = _root(paths) / "备份"
    items = sorted(p for p in d.iterdir() if (p / "manifest.json").is_file()) if d.is_dir() else []
    return items[-1] if items else None


def status(g, body=None):
    _guard(g)
    b = last_backup(g.paths)
    info = None
    if b:
        m = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
        info = {"time": m["time"], "text": m["text"], "files": len(m["files"])}
    return {"last": info, "words": words(g.paths)}


def undo(g, body=None):
    """撤销上一次清除：把备份的原文件放回去。清除之后这份文件又被改过（比如你在里面写了笔记）就跳过它，不覆盖你的新内容。"""
    _guard(g)
    b = last_backup(g.paths)
    if not b:
        raise AdError("没有可撤销的清除")
    m = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    restored, skipped = 0, []
    for rel, sha in m["files"].items():
        f = g.paths.train / rel
        try:
            now = f.read_text(encoding="utf-8-sig") if f.is_file() else None
        except OSError:
            now = None
        if now is None or _sha(now) != sha:
            skipped.append(rel)
            continue
        shutil.copy2(b / rel, f)
        restored += 1
    shutil.rmtree(b, ignore_errors=True)
    return {"restored": restored, "skipped": skipped}


# ---------------------------------------------------------------- 广告词库（导入时自动清除）
def _words_file(paths):
    return _root(paths) / "广告词库.json"


def words(paths):
    f = _words_file(paths)
    try:
        data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
    except (OSError, ValueError):
        data = []
    return [w for w in data if isinstance(w, dict) and w.get("text")]


def edit_words(g, body):
    _guard(g)
    act, text = body.get("act"), str(body.get("text") or "").strip()
    data = words(g.paths)
    if act == "add":
        _pattern(text)
        if any(_sq(w["text"]) == _sq(text) for w in data):
            return {"words": data, "again": True}
        data.append({"text": text, "added": dt.date.today().isoformat()})
    elif act == "remove":
        data = [w for w in data if _sq(w["text"]) != _sq(text)]
    else:
        raise AdError("不认识的操作")
    f = _words_file(g.paths)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    _WORDS_CACHE.pop(str(f), None)
    return {"words": data}


def _sq(text):
    return "".join(c for c in str(text) if not c.isspace()).lower()


def _compiled(paths):
    f = _words_file(paths)
    try:
        stamp = f.stat().st_mtime_ns if f.is_file() else 0
    except OSError:
        stamp = 0
    hit = _WORDS_CACHE.get(str(f))
    if hit and hit[0] == stamp:
        return hit[1]
    pats = []
    for w in words(paths):
        try:
            pats.append(_pattern(w["text"]))
        except AdError:
            continue
    _WORDS_CACHE[str(f)] = (stamp, pats)
    return pats


def strip_text(paths, text):
    """导入时用：把文字里命中广告词库的部分去掉（整行都是广告就整行去掉）。没有词库就原样返回。"""
    try:
        pats = _compiled(paths)
    except Exception:
        return text
    for pat in pats:
        spans = [(m.start(), m.end()) for m in pat.finditer(text)]
        if spans:
            text = _remove(text, spans)
    return text


def strip_files(paths, folder):
    """导入完一份套卷后，把这个文件夹里所有 .md 过一遍广告词库。返回清了几处。"""
    pats = _compiled(paths)
    if not pats or not folder.is_dir():
        return 0
    n = 0
    for f in folder.rglob("*.md"):
        try:
            raw = f.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        new = strip_text(paths, raw)
        if new != raw:
            f.write_text(new, encoding="utf-8", newline="\n")
            n += 1
    return n
