"""藏经阁·心法（skill）：每个板块一个专属、可随时修改的目录。

存放：训练/技能/<板块>/**.md（程序可写）。用户库里原来的 copilot/skills/<skill名>/ 始终只读，只当“来源”。
历史：训练/技能/.历史/<板块>/<相对路径>/<时间>.md（每次保存、删除、改名前先留一份，可回滚）。

读取顺序（解惑、复盘追问、传授等所有讲题处共用 tutor_material）：
  1. 训练/技能/<板块>/ 里有 SKILL.md → 用“我的版本”（目录里全部 .md，SKILL.md 在前，.历史 不读）；
  2. 没有 → 回退用户库里的原 skill（行为与 3.3 完全一致）；
  3. 都没有 → 空。
“我的版本”仍会带上原 skill 引用的库内资料（如“六种对应关系.md”），它们是资料、不是方法，不随版本复制。
读取总量上限 TUTOR_LIMIT 字，超出的文件明确标“未读入”，界面上同样显示，不悄悄截断。

保存带版本号（内容哈希）：两处同时改，后保存的会收到冲突提示，不会悄悄覆盖。程序算分、判分不读这里的任何内容。
"""
import hashlib
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from . import vault

DIR = "技能"
HIST = ".历史"
TUTOR_LIMIT = vault.TUTOR_LIMIT          # 讲题时给师傅的资料上限（字），与旧逻辑同一个数
MAX_FILE = 200_000                         # 单个文件上限（字）
MAX_FILES = 60                             # 每个板块最多的文件数
MAX_DEPTH = 3                              # 相对路径最多几层（含文件名）
KEEP_HISTORY = 50                          # 每个文件最多留几份历史
BAD_NAME = re.compile(r'[\\:*?"<>|\x00-\x1f]')

TEMPLATE = {
    "SKILL.md": "# {board} · 心法\n\n> 入口：遇到这类题先做什么、按什么顺序、用到哪些文件。\n\n"
                "1. 先看 `01-识别.md`，认出这题属于哪一类；\n2. 按 `02-方法.md` 的步骤做；\n"
                "3. 对照 `03-陷阱.md` 排除干扰项；\n4. 不会时看 `04-例题.md`，记口诀看 `05-速查.md`。\n",
    "01-识别.md": "# 识别\n\n怎么认出题型：（写出判断标志）\n",
    "02-方法.md": "# 方法与步骤\n\n1. \n2. \n3. \n",
    "03-陷阱.md": "# 常见陷阱与排除\n\n- \n",
    "04-例题.md": "# 例题\n\n（题目 → 用到哪个方法 → 过程）\n",
    "05-速查.md": "# 口诀速查\n\n- \n",
}


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
    """SKILL.md 在前，其余与原读取逻辑一致（按路径各层比较）"""
    return (rel != "SKILL.md", tuple(rel.split("/")))


def _rev(data):
    return hashlib.sha1(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()[:16]


def _atomic(f, text):
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


# ---------------------------------------------------------------- 我的版本
def own_files(paths, board):
    """我的版本里的 .md（相对路径，SKILL.md 在前，其余按名字排序；.历史 和隐藏文件不算）"""
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
    try:
        return (board_dir(paths, board) / "SKILL.md").is_file()
    except SkillError:
        return False


def source_files(paths, source):
    """用户库里原 skill 的 .md（只读；scripts/ 和隐藏文件不要）"""
    d = vault.skill_dir(paths, source)
    if not d:
        return []
    out = []
    for p in d.rglob("*.md"):
        rel = p.relative_to(d)
        if any(x.startswith(".") or x == "scripts" for x in rel.parts):
            continue
        out.append(rel.as_posix())
    return sorted(out, key=_order)


def mode(paths, board, source):
    """mine = 用我的版本；source = 用库里原 skill；none = 都没有"""
    if has_own(paths, board):
        return "mine"
    return "source" if vault.skill_dir(paths, source) else "none"


# ---------------------------------------------------------------- 解惑读取（透明度和实际读取共用同一份计划）
def reading_plan(paths, board, source):
    """返回 {mode, items:[{rel,chars,read,kind}], total, limit, text}。
    kind：method=方法文件；material=skill 引用的库内资料。read=False 表示超出上限没读入。"""
    m = mode(paths, board, source)
    items, parts, total = [], [], 0

    def take(label, rel, text, kind):
        nonlocal total
        n = len(text)
        if total + n > TUTOR_LIMIT:
            items.append({"rel": rel, "chars": n, "read": False, "kind": kind})
            return
        total += n
        parts.append("=== %s ===\n%s" % (label, text))
        items.append({"rel": rel, "chars": n, "read": True, "kind": kind})

    if m == "mine":
        d = board_dir(paths, board)
        for rel in own_files(paths, board):
            take(rel, rel, _read(d / rel), "method")
    elif m == "source":
        d = vault.skill_dir(paths, source)
        for rel in source_files(paths, source):
            take(rel, rel, _read(d / rel), "method")
    if m != "none" and vault.skill_dir(paths, source):
        # 原 skill 引用的库内资料：知识在这里，随版本一起读（与 3.3 行为一致）
        _, refs = vault.skill_material(paths, source)
        for ref in refs:
            if ref.endswith("）"):
                continue
            f = paths.vault / ref
            if f.is_file():
                take("资料 " + ref, ref, _read(f), "material")
    return {"mode": m, "items": items, "total": total, "limit": TUTOR_LIMIT, "text": "\n\n".join(parts)}


def tutor_material(paths, board, source):
    """讲题用的资料：(文字, 读到的文件清单)。只在有“我的版本”时返回；没有则返回 None，由调用方走原逻辑。"""
    if not has_own(paths, board):
        return None
    plan = reading_plan(paths, board, source)
    used = [i["rel"] if i["read"] else i["rel"] + "（未读入：超出上限）" for i in plan["items"]]
    return plan["text"], used


# ---------------------------------------------------------------- 概览与读取（界面）
def overview(paths, boards):
    """boards：[(板块, 原skill名)]。每个板块的状态与读取计划（不含正文）。"""
    out = []
    for board, source in boards:
        plan = reading_plan(paths, board, source)
        out.append({"board": board, "source": source or "", "mode": plan["mode"],
                    "source_exists": bool(vault.skill_dir(paths, source)),
                    "items": plan["items"], "total": plan["total"], "limit": plan["limit"],
                    "files": own_files(paths, board) if plan["mode"] == "mine" else source_files(paths, source)})
    return out


def read_file(paths, board, source, rel):
    rel = _rel(rel)
    if has_own(paths, board):
        f = _file(paths, board, rel)
        if not f.is_file():
            raise SkillError("没有这个文件")
        text = _read(f)
        return {"path": rel, "text": text, "rev": _rev(text), "mode": "mine", "editable": True}
    d = vault.skill_dir(paths, source)
    if not d:
        raise SkillError("这个板块还没有心法")
    f = d / rel
    if rel not in source_files(paths, source) or not f.is_file():
        raise SkillError("没有这个文件")
    text = _read(f)
    return {"path": rel, "text": text, "rev": "", "mode": "source", "editable": False}


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


# ---------------------------------------------------------------- 创建我的版本
def create_from_source(paths, board, source):
    """把库里原 skill 的 .md 复制成我的版本（只复制方法文件；库里原文件不动）。已有我的版本则拒绝。"""
    if has_own(paths, board):
        raise SkillError("已经有我的版本了")
    files = source_files(paths, source)
    d = vault.skill_dir(paths, source)
    if not d or "SKILL.md" not in files:
        raise SkillError("没有可复制的原 skill")
    if len(files) > MAX_FILES:
        raise SkillError("原 skill 文件太多（%d 个），请先精简" % len(files))
    if any(len(r.split("/")) > MAX_DEPTH for r in files):
        raise SkillError("原 skill 的文件夹层数太深（最多 %d 层），请先整理" % MAX_DEPTH)
    for rel in files:
        text = _read(d / rel)
        if len(text) > MAX_FILE:
            raise SkillError("原文件 %s 太长（上限 %d 字），请先拆分" % (rel, MAX_FILE))
    for rel in files:
        _atomic(board_dir(paths, board) / rel, _read(d / rel))
    return {"files": files}


def create_template(paths, board):
    if has_own(paths, board):
        raise SkillError("已经有我的版本了")
    for rel, text in TEMPLATE.items():
        _atomic(board_dir(paths, board) / rel, text.replace("{board}", board))
    return {"files": list(TEMPLATE)}
