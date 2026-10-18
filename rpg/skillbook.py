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


# ================================================================ 待审建议（整理向导 / 记入心法 生成，用户逐条采纳后才写入）
PENDING = ".待审"
MAX_EDITS = 6
MAX_EDIT_TEXT = 12000


def _pend_dir(paths):
    return root(paths) / PENDING


def _clean_edits(edits, allowed_new=None):
    """校验 AI 给的修改：只允许 append（追加）和 new（新建），路径合法、文字不空不超长；不允许覆盖或删除"""
    out = []
    for e in edits or []:
        if not isinstance(e, dict):
            continue
        action = e.get("action")
        text = str(e.get("text") or "").strip()
        if action not in ("append", "new") or not text:
            continue
        try:
            rel = _rel(e.get("path"))
        except SkillError:
            continue
        if allowed_new is not None and action == "new" and rel not in allowed_new:
            continue
        out.append({"path": rel, "action": action, "text": text[:MAX_EDIT_TEXT], "reason": str(e.get("reason") or "")[:300],
                    "done": False})
    return out[:MAX_EDITS]


def add_proposal(paths, board, kind, summary, edits, source=None, key=""):
    """保存一条待审建议；同一个 key（同一来源同一内容）已有未处理的就直接返回它，不重复保存。"""
    _board_name(board)
    d = _pend_dir(paths)
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        old = _load_json(p)
        if old and key and old.get("board") == board and old.get("key") == key:
            return old
    edits = _clean_edits(edits)
    if not edits:
        raise SkillError("没有可用的修改建议")
    pid = "%s-%s" % (time.strftime("%Y%m%d%H%M%S"), hashlib.sha1((board + str(time.time()) + summary).encode("utf-8")).hexdigest()[:6])
    data = {"id": pid, "board": board, "kind": kind, "summary": str(summary or "")[:200], "source": source or {}, "key": key,
            "created": time.strftime("%Y-%m-%d %H:%M"), "edits": edits}
    _atomic_any(d / (pid + ".json"), data)
    return data


def _load_json(f):
    import json
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_any(f, data):
    import json
    f.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=str(f.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=1)
        os.replace(name, f)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def proposals(paths, board=None):
    d = _pend_dir(paths) if root(paths) else None
    out = []
    for p in sorted(d.glob("*.json"), reverse=True) if d and d.is_dir() else []:
        data = _load_json(p)
        if isinstance(data, dict) and data.get("id") == p.stem and (board is None or data.get("board") == board):
            out.append(data)
    return out


def _proposal(paths, pid):
    pid = re.sub(r"[^0-9a-f\-]", "", str(pid or ""))
    f = _pend_dir(paths) / (pid + ".json")
    data = _load_json(f) if f.is_file() else None
    if not isinstance(data, dict) or data.get("id") != pid:
        raise SkillError("这条建议已经不存在了")
    return f, data


def dismiss(paths, pid):
    f, _ = _proposal(paths, pid)
    f.unlink()
    return {"dismissed": True}


def change_log(paths, board, line):
    """在变更记录.md 末尾追加一行（没有就新建）；变更记录也是普通文件，可以自己改"""
    f = board_dir(paths, board) / "变更记录.md"
    cur = _read(f) if f.is_file() else "# 变更记录\n\n每次采纳建议、发布都会在这里留一行。\n"
    if f.is_file():
        _stash(paths, board, "变更记录.md", cur)
    _atomic(f, cur.rstrip("\n") + "\n- " + line + "\n")


def accept(paths, board, source, pid, picks):
    """采纳一条建议里被勾选的修改（picks 是下标列表）。没有我的版本会先创建；'new' 遇到同名文件不覆盖；
    写完记进变更记录。全部处理完的建议自动移走。返回 {applied:[...], skipped:[...]}"""
    f, data = _proposal(paths, pid)
    if data.get("board") != board:
        raise SkillError("这条建议不属于这个板块")
    edits = data["edits"]
    chosen = [i for i in (picks or []) if isinstance(i, int) and 0 <= i < len(edits) and not edits[i].get("done")]
    if not chosen:
        raise SkillError("请先勾选要采纳的修改")
    if not has_own(paths, board):
        if data.get("kind") == "organize":
            if not any(edits[i]["path"] == "SKILL.md" for i in chosen):
                raise SkillError("第一次采纳整理结果，请同时勾选入口 SKILL.md")      # 用建议里的 SKILL.md 起头，不混入原文件
        elif vault.skill_dir(paths, source):
            create_from_source(paths, board, source)
        else:
            create_template(paths, board)
    applied, skipped = [], []
    for i in chosen:
        e = edits[i]
        target = _file(paths, board, e["path"])
        if e["action"] == "new" or not target.is_file():
            if target.is_file():
                skipped.append("%s（已有同名文件，没有覆盖）" % e["path"])
                continue
            save(paths, board, e["path"], e["text"].rstrip("\n") + "\n", "")
        else:
            cur = _read(target)
            save(paths, board, e["path"], cur.rstrip("\n") + "\n\n" + e["text"].rstrip("\n") + "\n", _rev(cur))
        e["done"] = True
        applied.append(e["path"])
    if applied:
        src = data.get("source") or {}
        change_log(paths, board, "%s 采纳「%s」→ %s%s" % (time.strftime("%Y-%m-%d %H:%M"), data.get("summary", ""), "、".join(applied),
                                                      "（来源：%s）" % src["label"] if src.get("label") else ""))
    if all(e.get("done") for e in edits):
        f.unlink()
    else:
        _atomic_any(f, data)
    return {"applied": applied, "skipped": skipped, "left": sum(not e.get("done") for e in edits)}


# ================================================================ 发布回原 skill（手动、默认关闭；写之前备份，可恢复）
BACKUP = ".发布备份"


def _source_md(d):
    return {r: (d / r) for r in [p.relative_to(d).as_posix() for p in d.rglob("*.md")]
            if not any(x.startswith(".") or x == "scripts" for x in r.split("/"))}


def publish_preview(paths, board, source, others=()):
    """写回前的差异：每个文件是 new / changed / same；原 skill 里有而我的版本没有的只提示，不删除。others=共用同一原 skill 的其他板块"""
    if not has_own(paths, board):
        raise SkillError("这个板块还没有我的版本")
    d = vault.skill_dir(paths, source)
    if not d:
        raise SkillError("库里没有原 skill「%s」，不能写回" % (source or "未配置"))
    d2 = {}
    mine = own_files(paths, board)
    sig = hashlib.sha1()
    for rel in mine:
        text = _read(board_dir(paths, board) / rel)
        f = d / rel
        old = _read(f) if f.is_file() else None
        d2[rel] = "new" if old is None else ("same" if old == text else "changed")
        sig.update((rel + _rev(text) + (_rev(old) if old is not None else "-")).encode("utf-8"))
    missing = [r for r in _source_md(d) if r not in mine]
    return {"source": source, "files": [{"path": r, "status": s} for r, s in d2.items()], "only_in_source": missing,
            "shared_with": [b for b in others if b != board], "digest": sig.hexdigest()}


def publish(paths, board, source, digest, others=()):
    """把我的版本写回库里的原 skill（只写 .md，不删原文件，不碰 scripts/）。写之前把会被改动的原文件备份到 训练/技能/.发布备份/。"""
    pv = publish_preview(paths, board, source, others)
    if digest != pv["digest"]:
        raise SkillError("文件在预览后变化了，请重新预览", conflict=True)
    d = vault.skill_dir(paths, source)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = root(paths) / BACKUP / _board_name(board) / stamp
    manifest = {"source": source, "board": board, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "files": []}
    changes = [(x["path"], x["status"]) for x in pv["files"] if x["status"] != "same"]
    for rel, status in changes:                                   # 先备份，再写；备份失败就一个都不写
        if status == "changed":
            _atomic(bak / rel, _read(d / rel))
        manifest["files"].append({"path": rel, "had": status == "changed"})
    _atomic_any(bak / "清单.json", manifest)
    for rel, _ in changes:
        _atomic(d / rel, _read(board_dir(paths, board) / rel))
    change_log(paths, board, "%s 发布回原 skill「%s」：%s" % (time.strftime("%Y-%m-%d %H:%M"), source, "、".join(r for r, _ in changes) or "没有变化"))
    return {"written": [r for r, _ in changes], "backup": stamp}


def publish_backups(paths, board):
    d = root(paths) / BACKUP / _board_name(board)
    out = []
    for p in sorted(d.glob("*/清单.json"), reverse=True) if d.is_dir() else []:
        m = _load_json(p)
        if isinstance(m, dict) and not m.get("restored"):
            out.append({"id": p.parent.name, "at": m.get("at", ""), "source": m.get("source", ""), "files": [x["path"] for x in m.get("files", [])]})
    return out


def publish_restore(paths, board, source, bid):
    """撤回一次发布：被覆盖的原文件还原，发布时新建的文件删掉"""
    bid = re.sub(r"[^0-9\-]", "", str(bid or ""))
    base = root(paths) / BACKUP / _board_name(board) / bid
    m = _load_json(base / "清单.json") if (base / "清单.json").is_file() else None
    if not isinstance(m, dict) or m.get("restored") or m.get("source") != source:
        raise SkillError("这次发布的备份不可用")
    d = vault.skill_dir(paths, source)
    if not d:
        raise SkillError("库里没有原 skill，不能还原")
    for x in m.get("files", []):
        rel = _rel(x["path"])
        if x.get("had"):
            _atomic(d / rel, _read(base / rel))
        elif (d / rel).is_file():
            (d / rel).unlink()
    m["restored"] = True
    _atomic_any(base / "清单.json", m)
    change_log(paths, board, "%s 撤回发布（%s）" % (time.strftime("%Y-%m-%d %H:%M"), bid))
    return {"restored": [x["path"] for x in m.get("files", [])]}
