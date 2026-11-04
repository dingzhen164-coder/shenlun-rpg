"""导入时自动清广告（2026-11：藏经阁「清除」页签取消，只保留导入时按广告词库自动清）。

导入套卷（exam_room.finish_import）和板块题（importer._append）时，把命中广告词库的文字去掉：整行都是广告就连行删，
夹在句中只删这一段；匹配时每个字之间允许任意空白、忽略大小写。只处理程序自己写在 训练/ 里的内容。

广告词库是本地文档（用户照格式增删，程序只读）：
  训练/清除/广告词库.txt    一行一条广告文字（至少 3 个字）；# 开头的行是注释
  旧版的 训练/清除/广告词库.json（[{"text","added"}]）第一次读到时转成 .txt，原 json 留着不删。
"""
import json
import re

DIR = "清除"
_WORDS_CACHE = {}
HEAD = "# 广告词库：一行一条广告文字（至少 3 个字），导入套卷和题目时自动清掉。# 开头的行是注释。\n"


class AdError(ValueError):
    pass


def _root(paths):
    return paths.train / DIR


def _pattern(text):
    """广告文字 → 正则：每个字之间允许任意空白，忽略大小写"""
    chars = [c for c in str(text or "") if not c.isspace()]
    if len(chars) < 3:
        raise AdError("广告文字太短（至少 3 个字），避免误删正文")
    return re.compile(r"\s*".join(re.escape(c) for c in chars), re.I)


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


def _words_file(paths):
    return _root(paths) / "广告词库.txt"


def words(paths):
    """[{"text": 广告文字}]：读 广告词库.txt；只有旧版 json 时先转成 txt"""
    f = _words_file(paths)
    old = _root(paths) / "广告词库.json"
    if not f.is_file() and old.is_file():
        try:
            data = json.loads(old.read_text(encoding="utf-8"))
            lines = [str(w.get("text")).strip() for w in data if isinstance(w, dict) and w.get("text")]
            f.write_text(HEAD + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        except (OSError, ValueError):
            pass
    try:
        text = f.read_text(encoding="utf-8-sig") if f.is_file() else ""
    except OSError:
        text = ""
    return [{"text": ln.strip()} for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


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
