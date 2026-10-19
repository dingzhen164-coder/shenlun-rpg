"""藏经阁·心法（skill）：每个板块一个专属、可随时修改的目录（3.5.3 起一律从空开始）。

存放：训练/技能/<板块>/**.md（程序可写）。初始是空的；内容来自三处：自己新建文件、在界面里直接修改、
导入别的平台生成的 .skill / .zip 包（见 import_package）。没有“原版 / 我的版本”之分：每个板块就是一份心法，
历史里留着每次修改前的样子，可以回滚。用户库里的 copilot/skills 不再读取（要用就导入进来）。
历史：训练/技能/.历史/<板块>/<相对路径>/<时间>.md（每次保存、导入覆盖、删除、改名前先留一份）。

讲题（解惑、复盘追问、传授等共用 tutor_material）读取：目录里全部 .md，SKILL.md 在前，其余按路径排序；
references/ 和 学习版/ 下的文件只供查阅 / 阅读，不自动读入；.历史 不读；SKILL.md 里“被 xxx 调度时”那一节不读（见 vault.strip_dispatch）。
读取总量上限 TUTOR_LIMIT 字，超出的文件明确标“未读入”，界面上同样显示，不悄悄截断。
保存带版本号（内容哈希）：两处同时改，后保存的会收到冲突提示，不会悄悄覆盖。程序算分、判分不读这里的任何内容。
"""
import hashlib
import io
import os
import re
import tempfile
import time
import zipfile
from pathlib import Path

from . import vault

DIR = "技能"
HIST = ".历史"
TUTOR_LIMIT = vault.TUTOR_LIMIT          # 讲题时给师傅的资料上限（字）
MAX_FILE = 200_000                         # 单个文件上限（字）
MAX_FILES = 150                            # 每个板块最多的文件数
MAX_DEPTH = 3                              # 相对路径最多几层（含文件名）
KEEP_HISTORY = 50                          # 每个文件最多留几份历史
REF_DIRS = ("references", "学习版")        # 这两个文件夹里的文件只供查阅 / 阅读，不自动读入讲题（学习版是给人看的，读进讲题只会白耗额度）
MAX_PACKAGE = 20_000_000                   # 导入的包解压后总大小上限（字节）
BAD_NAME = re.compile(r'[\\:*?"<>|\x00-\x1f]')
ZONGJUE_DIR = Path(__file__).parent / "data" / "zongjue"
ZONGJUE = [("蒸馏-第一步-提取例题.md", "第一步 · 提取例题", "从课程逐字稿里提取每道例题（只记老师说过的）"),
           ("蒸馏-第二步-归纳心法.md", "第二步 · 归纳心法", "把例题记录归纳成一套心法，并生成 SKILL.md"),
           ("蒸馏-第三步-生成学习版.md", "第三步 · 生成学习版", "改写成自己能学的学习版：老师怎么讲 + 例题怎么做出来"),
           ("配置-空白模板.md", "配置 · 空白模板", "每门课填一份，告诉 AI 这门课要蒸馏什么"),
           ("使用流程.md", "使用流程", "从配置到导入板块的完整步骤")]


class SkillError(ValueError):
    """用户能看懂的错误（路径不合法、冲突、超限……）；conflict=True 表示版本冲突"""

    def __init__(self, msg, conflict=False):
        super().__init__(msg)
        self.conflict = conflict


# ---------------------------------------------------------------- 路径
def root(paths):
    return paths.train / DIR if paths.train else None


def _board_name(board):
    b = str(board or "").strip()
    if not b or b in (".", "..") or b.startswith(".") or BAD_NAME.search(b) or "/" in b or len(b) > 40:
        raise SkillError("板块名不合法")
    return b


def board_dir(paths, board):
    r = root(paths)
    if not r:
        raise SkillError("还没有连接资料库")
    return r / _board_name(board)


def _rel(rel):
    """校验并规范相对路径：只允许 .md、不允许 .. / 绝对路径 / 隐藏名 / 过深"""
    s = str(rel or "").replace("\\", "/").strip()
    if s.startswith("/") or re.match(r"^[A-Za-z]:", s):
        raise SkillError("文件名不合法（不能是绝对路径）")
    parts = s.strip("/").split("/")
    if not s or len(parts) > MAX_DEPTH or any(not p or p in (".", "..") or p.startswith(".") or BAD_NAME.search(p) or len(p) > 80 for p in parts):
        raise SkillError("文件名不合法（只能是 .md，最多 %d 层）" % MAX_DEPTH)
    if not parts[-1].lower().endswith(".md"):
        raise SkillError("只能是 .md 文件")
    return "/".join(parts)


def _file(paths, board, rel):
    d = board_dir(paths, board)
    f = d / _rel(rel)
    if d.resolve() not in f.resolve().parents:
        raise SkillError("文件名不合法")
    return f


def _order(rel):
    """SKILL.md 在前，其余按路径各层比较"""
    return (rel != "SKILL.md", tuple(rel.split("/")))


def _rev(data):
    return hashlib.sha1(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()[:16]


def _atomic(f, text):
    _PLAN.clear()
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(f.parent), prefix=".tmp-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(text)
        os.replace(name, f)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _read(f):
    return f.read_text(encoding="utf-8", errors="ignore")


# ---------------------------------------------------------------- 训练/技能 里的心法
def own_files(paths, board):
    """训练/技能/<板块>/ 里的 .md（相对路径，SKILL.md 在前，其余按名字排序；.历史 和隐藏文件不算）"""
    try:
        d = board_dir(paths, board)
    except SkillError:
        return []
    if not d.is_dir():
        return []
    out = []
    for p in d.rglob("*.md"):
        rel = p.relative_to(d)
        if any(x.startswith(".") for x in rel.parts) or len(rel.parts) > MAX_DEPTH:
            continue
        out.append(rel.as_posix())
    return sorted(out, key=_order)


def has_own(paths, board):
    """这个板块里有没有心法文件（没有 = 空板块）"""
    return bool(own_files(paths, board))


_WORD = re.compile(r"[\u3400-\u9fff]|[A-Za-z0-9]+")


def words(text):
    """像文字处理软件那样数“字”：每个汉字算一个，连续的字母或数字算一个词；符号、空格、标记不算。
    （上限和读取量仍按字符计，因为字符数才是真正交给 AI 的量。）"""
    return len(_WORD.findall(text))


def title_of(text):
    """文件里第一个 # 标题（去掉标记），没有就是空串"""
    m = re.search(r"^#{1,3}[ \t]+(.+?)[ \t]*$", text, re.M)
    return m.group(1).strip()[:60] if m else ""


# ---------------------------------------------------------------- 解惑读取（透明度和实际读取共用同一份计划）
def reading_plan(paths, board):
    """返回 {items:[{rel,chars,words,title,read,kind}], total, words, limit, text}。
    kind：method=方法文件（自动读入）；ref=references/ 或 学习版/ 下的文件（只供查阅 / 阅读，不读入）。read=False 且 kind=method 表示超出上限没读入。"""
    items, parts, total = [], [], 0
    d = board_dir(paths, board)
    for rel in own_files(paths, board):
        text = _read(d / rel)
        if rel.rsplit("/", 1)[-1] == "SKILL.md":
            text = vault.strip_dispatch(text)
        n = len(text)
        if rel.split("/")[0] in REF_DIRS and "/" in rel:
            items.append({"rel": rel, "chars": n, "words": words(text), "title": title_of(text), "read": False, "kind": "ref"})
            continue
        item = {"rel": rel, "chars": n, "words": words(text), "title": title_of(text), "read": total + n <= TUTOR_LIMIT, "kind": "method"}
        items.append(item)
        if item["read"]:
            total += n
            parts.append("=== %s ===\n%s" % (rel, text))
    return {"items": items, "total": total, "words": sum(i["words"] for i in items if i["read"]),
            "limit": TUTOR_LIMIT, "text": "\n\n".join(parts)}


def tutor_material(paths, board):
    """讲题用的资料：(文字, 读到的文件清单)；板块是空的就返回 None（讲题时没有 skill 可依据）。"""
    if not has_own(paths, board):
        return None
    plan = reading_plan(paths, board)
    used = [i["rel"] if i["read"] else i["rel"] + "（未读入：超出上限）" for i in plan["items"] if i["kind"] == "method"]
    return plan["text"], used


# ---------------------------------------------------------------- 概览与读取（界面）
def overview(paths, boards):
    """书架用：boards：板块名列表。每个板块只给文件清单，**不算读取计划**（打开某个板块时再算，见 plan）。"""
    out = []
    for board in boards:
        files = own_files(paths, board)
        out.append({"board": board, "n_files": len(files), "files": files})
    return out


_PLAN = {}
PLAN_TTL = 60


def _plan_sig(paths, board):
    out = []
    d = board_dir(paths, board)
    for rel in own_files(paths, board):
        try:
            st = (d / rel).stat()
            out.append((rel, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(out)


def plan(paths, board):
    """打开某个板块时的读取计划（文件、字数、哪些未读入）；带缓存：文件没变且 60 秒内不重复计算。去掉正文，只留清单"""
    sig = _plan_sig(paths, board)
    key = (str(paths.train), board)
    hit = _PLAN.get(key)
    if hit and hit[1] == sig and time.time() - hit[0] < PLAN_TTL:
        return hit[2]
    p = reading_plan(paths, board)
    out = {"board": board, "items": p["items"], "total": p["total"], "words": p["words"], "limit": p["limit"]}
    _PLAN[key] = (time.time(), sig, out)
    return out


def read_file(paths, board, rel):
    rel = _rel(rel)
    f = _file(paths, board, rel)
    if not f.is_file():
        raise SkillError("没有这个文件")
    text = _read(f)
    return {"path": rel, "text": text, "rev": _rev(text), "editable": True}


# ---------------------------------------------------------------- 历史
def _hist_dir(paths, board, rel):
    return root(paths) / HIST / _board_name(board) / _rel(rel)


def _stash(paths, board, rel, text):
    """把当前内容存进历史（同内容不重复存）；超出份数删最旧的"""
    d = _hist_dir(paths, board, rel)
    d.mkdir(parents=True, exist_ok=True)
    if any(_read(p) == text for p in d.glob("*.md")):
        return
    name = time.strftime("%Y%m%d-%H%M%S")
    f = d / (name + ".md")
    i = 1
    while f.exists():
        i += 1
        f = d / ("%s-%d.md" % (name, i))
    _atomic(f, text)
    old = sorted(d.glob("*.md"))
    for p in old[:-KEEP_HISTORY]:
        try:
            p.unlink()
        except OSError:
            pass


def history(paths, board, rel):
    """[{id, at, chars}] 新的在前；文件已删除也能看到"""
    d = _hist_dir(paths, board, rel)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.md"), reverse=True):
        t = p.stem
        at = "%s-%s-%s %s:%s:%s" % (t[0:4], t[4:6], t[6:8], t[9:11], t[11:13], t[13:15]) if re.match(r"^\d{8}-\d{6}", t) else t
        out.append({"id": p.stem, "at": at, "chars": len(_read(p))})
    return out


def history_text(paths, board, rel, vid):
    f = _hist_dir(paths, board, rel) / (re.sub(r"[^0-9\-]", "", str(vid)) + ".md")
    if not f.is_file():
        raise SkillError("没有这个历史版本")
    return _read(f)


# ---------------------------------------------------------------- 修改
def _check_text(text):
    if not isinstance(text, str):
        raise SkillError("内容不对")
    if len(text) > MAX_FILE:
        raise SkillError("文件太长（上限 %d 字），请拆成几个文件" % MAX_FILE)


def save(paths, board, rel, text, base):
    """保存（新建或覆盖）。base：打开时拿到的版本号；新建传空串。版本不符 → 冲突，不覆盖。"""
    _check_text(text)
    f = _file(paths, board, rel)
    if f.is_file():
        cur = _read(f)
        if base != _rev(cur):
            raise SkillError("这个文件在别处被改过了，请先刷新再改（你的内容没有丢，先复制出来）", conflict=True)
        if cur == text:
            return {"rev": _rev(cur), "changed": False}
        _stash(paths, board, rel, cur)
    else:
        if base:
            raise SkillError("这个文件已经不存在了，请刷新", conflict=True)
        if len(own_files(paths, board)) >= MAX_FILES:
            raise SkillError("一个板块最多 %d 个文件" % MAX_FILES)
    _atomic(f, text)
    return {"rev": _rev(text), "changed": True}


def delete(paths, board, rel, base):
    f = _file(paths, board, rel)
    if not f.is_file():
        raise SkillError("没有这个文件")
    cur = _read(f)
    if base != _rev(cur):
        raise SkillError("这个文件在别处被改过了，请先刷新", conflict=True)
    _stash(paths, board, rel, cur)
    f.unlink()
    return {"deleted": _rel(rel)}


def rename(paths, board, rel, new_rel, base):
    f, g = _file(paths, board, rel), _file(paths, board, new_rel)
    if not f.is_file():
        raise SkillError("没有这个文件")
    if g.exists():
        raise SkillError("已经有同名文件")
    cur = _read(f)
    if base != _rev(cur):
        raise SkillError("这个文件在别处被改过了，请先刷新", conflict=True)
    if _rel(rel) == "SKILL.md":
        raise SkillError("入口 SKILL.md 不能改名")
    _stash(paths, board, rel, cur)
    _atomic(g, cur)
    f.unlink()
    return {"path": _rel(new_rel), "rev": _rev(cur)}


def restore(paths, board, rel, vid, base):
    """把某个历史版本放回来（作为一次新的保存，当前内容也会进历史）"""
    return save(paths, board, rel, history_text(paths, board, rel, vid), base)


# ---------------------------------------------------------------- 导入别的平台生成的 skill 包
def _put(paths, board, rel, text):
    """写入一个文件：已有同名文件就先把旧内容存进历史再覆盖。返回 'new' / 'overwritten' / 'same'"""
    f = _file(paths, board, rel)
    if f.is_file():
        cur = _read(f)
        if cur == text:
            return "same"
        _stash(paths, board, rel, cur)
        _atomic(f, text)
        return "overwritten"
    _atomic(f, text)
    return "new"


def _package_entries(name, raw):
    """把上传的文件变成 [(相对路径, 文字)]：.skill / .zip 是压缩包（去掉最外层同一个文件夹），.md / .txt 是单个文件。
    返回 (entries, skipped)；skipped 是 [(名字, 原因)]。"""
    skipped = []
    lower = str(name or "").lower()
    if lower.endswith((".md", ".txt", ".markdown")):
        base = re.sub(r"\.(txt|markdown)$", ".md", Path(str(name)).name, flags=re.I)
        return [(base, raw.decode("utf-8", errors="ignore"))], skipped
    if not raw[:2] == b"PK":
        raise SkillError("这不是 .skill / .zip 压缩包，也不是 .md 文件")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise SkillError("压缩包打不开，文件可能已损坏")
    infos = [i for i in z.infolist() if not i.is_dir()]
    if sum(i.file_size for i in infos) > MAX_PACKAGE:
        raise SkillError("压缩包解压后太大（上限 %d MB）" % (MAX_PACKAGE // 1_000_000))
    names = [i.filename.replace("\\", "/") for i in infos]
    usable = [n for n in names if not n.startswith("__MACOSX/") and "/__MACOSX/" not in n]
    tops = {n.split("/")[0] for n in usable if "/" in n}
    strip = len(tops) == 1 and all("/" in n for n in usable)           # 整包外面套了一层文件夹：去掉它
    out = []
    for i, n in zip(infos, names):
        if n not in usable:
            continue
        rel = n.split("/", 1)[1] if strip else n
        if any(x.startswith(".") and x not in (".", "..") for x in rel.split("/")):
            continue                                                    # .DS_Store 之类的隐藏文件：悄悄忽略，不算“跳过”
        if not rel.lower().endswith(".md"):
            skipped.append((rel, "不是 .md 文件（只导入文字说明）"))
            continue
        out.append((rel, z.read(i).decode("utf-8", errors="ignore")))
    return out, skipped


def import_package(paths, board, name, raw):
    """导入 .skill / .zip / .md 到这个板块：同名文件覆盖（旧内容进历史），其余文件原样保留。
    返回 {added:[...], overwritten:[...], same:[...], skipped:[(名字, 原因)]}"""
    _board_name(board)
    entries, skipped = _package_entries(name, raw)
    existing = set(own_files(paths, board))
    todo = []
    for rel, text in entries:
        try:
            r = _rel(rel)
        except SkillError:
            skipped.append((rel, "路径不合法或层数超过 %d 层" % MAX_DEPTH))
            continue
        if len(text) > MAX_FILE:
            skipped.append((rel, "文件太长（超过 %d 字）" % MAX_FILE))
            continue
        todo.append((r, text))
    if not todo:
        raise SkillError("包里没有可以导入的 .md 文件" + ("（%s）" % "；".join("%s：%s" % s for s in skipped[:3]) if skipped else ""))
    if len(existing | {r for r, _ in todo}) > MAX_FILES:
        raise SkillError("导入后这个板块会超过 %d 个文件，请先删掉一些再导入" % MAX_FILES)
    added, overwritten, same = [], [], []
    for r, text in sorted(todo, key=lambda x: _order(x[0])):
        {"new": added, "overwritten": overwritten, "same": same}[_put(paths, board, r, text)].append(r)
    return {"added": added, "overwritten": overwritten, "same": same, "skipped": skipped}


# ---------------------------------------------------------------- 心法总诀（随程序发布的四份文件，只读，可复制 / 下载）
def zongjue_list():
    return [{"file": f, "title": t, "desc": d} for f, t, d in ZONGJUE]


def zongjue_read(fname):
    if fname not in {f for f, _, _ in ZONGJUE}:
        raise SkillError("没有这份文件")
    f = ZONGJUE_DIR / fname
    if not f.is_file():
        raise SkillError("文件缺失，请重新安装程序")
    return {"file": fname, "text": f.read_text(encoding="utf-8")}
