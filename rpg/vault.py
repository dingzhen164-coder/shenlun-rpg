"""
只读访问 Obsidian 行测库：模考板块复盘、解题 skill、截图。本模块从不写库里的任何文件。

板块复盘文件由 xingce-mokao-split 生成，格式（节选）：

    ### 102. ❌                         ← 题号 + 结果图标（✅ 对 / ❌ 错 / ⚪ 未作答）
    ![[S36-Q102.png]]                   ← 可能有截图
    题干……
    - **A.** 选项
    > [!check]- 答案
    > 正确答案：**B**　我的答案：**A**　错误
    > [!note] 复盘
    > 【答案】B ……                       ← 解析（xingce-jiexi-all 写入）或自己的笔记
    ---

资料分析 / 一拖五 这类有“## 材料（第a-b题）”的，材料正文挂在对应题目上。
解析规则和 obsidian-to-xingce 仓库里的 jiexi.py 保持一致。
"""
import re
from pathlib import Path

HEAD_RE = re.compile(r"^### (\d+)\. (\S+)")
ANS_RE = re.compile(r"正确答案：\*\*([^*]*)\*\*\s*我的答案：\*\*([^*]*)\*\*")
MAT_RE = re.compile(r"^## 材料（第(\d+)-(\d+)题）")
IMG_RE = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]|!\[[^\]]*\]\(([^)]+)\)")
NOTE = "> [!note] 复盘"
CHECK = "> [!check]"
# 复盘栏里的空模板行（“- 错因：”这类），不算解析内容
PLACEHOLDER_RE = re.compile(r"^(?:[-*]\s*)?(?:\*\*)?[^：:>*]{1,12}[：:](?:\*\*)?\s*$")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}

_cache = {}  # 路径 → (mtime, 解析结果)


# ---------------------------------------------------------------- skill
def skill_dir(paths, name):
    """skill 文件夹（按文件夹名找）；不存在返回 None"""
    if not paths.skills or not name:
        return None
    d = paths.skills / name
    return d if (d / "SKILL.md").is_file() else None


def skill_digest(paths, name, limit=None):
    """读取全篇学习资料；可选上限超出时拒绝，不悄悄截断分类或章节。"""
    d = skill_dir(paths, name)
    if not d:
        return ""
    files = [d / fn for fn in ("SKILL.md", "cheatsheet.md", "patterns.md", "glossary.md")]
    files += sorted((d / "chapters").glob("*.md"))
    parts = ["=== %s ===\n%s" % (f.relative_to(d), f.read_text(encoding="utf-8", errors="ignore"))
             for f in files if f.is_file()]
    if not any(f.is_file() for f in files[4:]):
        parts.append("资料提示：没有章节正文。只可依据现有内容，方法细节缺失时应标注待核对。")
    text = "\n\n".join(parts)
    if limit is not None and len(text) > limit:
        raise ValueError("skill 正文超过读取上限，请分板块整理资料；未生成残缺草稿")
    return text


# skill 里常见的“操作规程”引用（脚本、调度器、本程序文件），不是知识资料
_NOT_MATERIAL = re.compile(r"\.py\b|[<>*$]|/scripts/|python|jiexi|board-map|^=== |^【|^\.|^-|projects/|\s")
_SKIP_DIRS = {".obsidian", ".opencode", ".trash", "训练", "FB模考试卷复盘", "node_modules", ".git"}
MATERIAL_LIMIT = 120000   # 引用资料总字数上限；超出的部分明确写“未读”，不悄悄截断


def _vault_find(paths, ref):
    """按名字在库里找资料：文件（xxx.md）或文件夹；先按相对路径，再全库按名字找（跳过程序、模考、隐藏目录）"""
    ref = ref.strip().strip("/").replace("\\", "/")
    if not ref or len(ref) > 80:
        return None
    for c in (paths.vault / ref, paths.vault / (ref + ".md")):
        if c.exists():
            return c
    name = Path(ref).name
    for p in sorted(paths.vault.rglob(name)) + sorted(paths.vault.rglob(name + ".md")):
        rel = p.relative_to(paths.vault).parts
        if any(x in _SKIP_DIRS for x in rel[:-1]) or (len(rel) > 1 and rel[0] == "copilot"):
            continue
        return p
    return None


_MATERIAL_CACHE = {}
MATERIAL_TTL = 30          # 秒：引用资料要在整个库里按名字找，很慢；同一份 skill 30 秒内不重复找（skill 自己的文件一改就重算）


def skill_material(paths, name, extra=()):
    """带短时缓存的 _skill_material。缓存键含 skill 文件夹里 .md 的修改时间，skill 自己一改就失效；
    被引用的库内资料最多 MATERIAL_TTL 秒后重新读。"""
    import time
    d = skill_dir(paths, name)
    sig = tuple(sorted((p.relative_to(d).as_posix(), p.stat().st_mtime_ns, p.stat().st_size) for p in d.rglob("*.md"))) if d else ()
    key = (str(paths.vault), name, tuple(extra))
    hit = _MATERIAL_CACHE.get(key)
    if hit and hit[1] == sig and time.time() - hit[0] < MATERIAL_TTL:
        return hit[2]
    out = _skill_material(paths, name, extra)
    _MATERIAL_CACHE[key] = (time.time(), sig, out)
    return out


def _skill_material(paths, name, extra=()):
    """生成骨架用的素材：skill 自己的文字 + 它引用的库内资料正文（`00-xxx.md`、`01-治理母逻辑` 文件夹、其他检索 skill 里的资料），
    再加上规则里“骨架素材.<板块>”指定的路径。返回 (文字, 读到的资料清单)。
    很多 skill 只是“去读某个文件、调用某个检索 skill”的操作规程，真正要背的知识在被引用的文件里，所以要一起读。"""
    base = skill_digest(paths, name)
    d = skill_dir(paths, name)
    if not d:
        return base, []
    refs = list(extra)
    for f in [d / "SKILL.md", *sorted((d / "chapters").glob("*.md"))]:
        if f.is_file():
            refs += re.findall(r"`([^`\n]{2,80})`", f.read_text(encoding="utf-8", errors="ignore"))
    files, seen = [], set()

    def add(p):
        if p.is_file() and p.suffix.lower() == ".md" and p.resolve() not in seen and not p.name.startswith("."):
            seen.add(p.resolve())
            files.append(p)

    for ref in dict.fromkeys(refs):
        ref = ref.strip()
        if ref in extra:
            pass
        elif _NOT_MATERIAL.search(ref) or ref == name:
            continue
        other = paths.skills / ref if paths.skills else None
        if other and other.is_dir() and other != d:      # 引用了另一个 skill（如检索知识库的 skill）：读它的资料，不读它的操作说明
            for p in sorted(other.rglob("*.md")):
                if p.name != "SKILL.md":
                    add(p)
            continue
        hit = _vault_find(paths, ref) if paths.vault else None
        if hit is None or d in hit.parents or hit == d:
            continue
        if hit.is_dir():
            for p in sorted(hit.rglob("*.md")):
                add(p)
        else:
            add(hit)
    parts, used, total = [], [], 0
    for f in files:
        rel = f.relative_to(paths.vault).as_posix() if paths.vault in f.parents else f.name
        t = f.read_text(encoding="utf-8", errors="ignore")
        if total + len(t) > MATERIAL_LIMIT:
            parts.append("=== 资料 %s ===\n（资料总量超过上限，这个文件没有读入；需要时在规则.md 用“骨架素材.板块”只列核心文件）" % rel)
            used.append(rel + "（未读入：超出上限）")
            continue
        total += len(t)
        parts.append("=== 资料 %s ===\n%s" % (rel, t))
        used.append(rel)
    text = base + ("\n\n######## 以下是 skill 引用的资料正文（知识以这里为准） ########\n\n" + "\n\n".join(parts) if parts else "")
    return text, used


TUTOR_LIMIT = 60000   # 讲题时给师傅的 skill 资料上限（字）


_DISPATCH = re.compile(r"^##[ \t]+被[^\n]*调度时[ \t]*$", re.M)


def strip_dispatch(text):
    """去掉 SKILL.md 里“被 xxx 调度时”那一节（给 AI 总调度用的脚本流程、写入格式、省 token 规则）：它和讲题无关，
    却会占上千字额度。从这个二级标题一直去到下一个二级标题或文末；文件本身不改，只是讲题时不读这一段"""
    m = _DISPATCH.search(text)
    if not m:
        return text
    nxt = re.search(r"^##[ \t]+[^#\n]", text[m.end():], re.M)
    return (text[:m.start()].rstrip("\n") + "\n" + (text[m.end() + nxt.start():] if nxt else "")).rstrip("\n") + "\n"


def skill_for_tutor(paths, name):
    """讲题（师傅解惑、复盘追问、传授）用的 skill 资料：skill 文件夹里所有 .md（SKILL.md 在前；scripts/ 不读），
    再加上 skill 里引用的库内资料。超出上限的文件写明“未读入”，不悄悄截断。返回 (文字, 读到的文件清单)"""
    d = skill_dir(paths, name)
    if not d:
        return "", []
    files = [d / "SKILL.md"] + sorted(p for p in d.rglob("*.md")
                                      if p.name != "SKILL.md" and "scripts" not in p.relative_to(d).parts and not p.name.startswith("."))
    parts, used, total = [], [], 0
    for f in files:
        t = strip_dispatch(f.read_text(encoding="utf-8", errors="ignore"))
        rel = f.relative_to(d).as_posix()
        if total + len(t) > TUTOR_LIMIT:
            used.append(rel + "（未读入：超出上限）")
            continue
        total += len(t)
        parts.append("=== %s ===\n%s" % (rel, t))
        used.append(rel)
    _, refs = skill_material(paths, name)      # skill 引用的库内资料（如“六种对应关系.md”）
    for rel in refs:
        if rel.endswith("）"):
            continue
        f = paths.vault / rel
        if not f.is_file():
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        if total + len(t) > TUTOR_LIMIT:
            used.append(rel + "（未读入：超出上限）")
            continue
        total += len(t)
        parts.append("=== 资料 %s ===\n%s" % (rel, t))
        used.append(rel)
    return "\n\n".join(parts), used


# ---------------------------------------------------------------- 模考复盘
def seasons(paths):
    """[(季数, 目录)]，按季数从小到大"""
    roots = [paths.seasons] if paths.seasons else []
    if paths.train and getattr(paths,'subject','') == '行测':
        roots.append(paths.train / '模考复盘')
    found = {}
    for root in roots:
        if not root.is_dir():
            continue
        for d in root.iterdir():
            m = re.fullmatch(r"第(\d+)季", d.name)
            if m and d.is_dir():
                # 原有复盘包含用户笔记；新训练目录只补没有旧复盘的季，不覆盖已有目录。
                found.setdefault(int(m.group(1)), d)
    return sorted(found.items())


def board_file(season_dir, source):
    fs = sorted(season_dir.glob(f"[0-9][0-9]-{source}.md"))
    return fs[0] if fs else None


def _clean_analysis(lines):
    out = []
    for ln in lines:
        s = ln.strip()
        s = s[1:].strip() if s.startswith(">") else s
        if not s or PLACEHOLDER_RE.match(s) or s.startswith("<!--"):
            continue
        out.append(s)
    return "\n".join(out)


def parse_seconds(value):
    """导入报告中的原答题用时（秒）；仅接受完整的时分秒/冒号格式，未知留空。"""
    value=re.sub(r'[\s*]', '', str(value or ''))
    if re.fullmatch(r'\d+:\d{1,2}(?::\d{1,2})?',value):
        parts=list(map(int,value.split(':')))
        if any(x>=60 for x in parts[1:]):return None
        seconds=sum(x*60**i for i,x in enumerate(reversed(parts)))
    elif re.fullmatch(r'(?:\d+(?:小时|时))?(?:\d+(?:分钟|分))?(?:\d+秒)?',value) and value:
        seconds=sum(int(n)*({'时':3600,'小时':3600,'分':60,'分钟':60,'秒':1}[unit]) for n,unit in re.findall(r'(\d+)(小时|时|分钟|分|秒)',value))
    else:return None
    return seconds if 0<=seconds<=86400 else None


def parse_board_file(path):
    """返回题目列表（dict），带缓存（按修改时间 + 大小；Windows 上连着写两次可能落在同一个时间刻度里）"""
    try:
        st = path.stat()
        mt = (st.st_mtime_ns, st.st_size)
    except OSError:
        return []
    hit = _cache.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    lines = path.read_text(encoding="utf-8", errors="ignore").split("\n")
    qs, mats, cur, mat, in_note = [], {}, None, None, False
    for ln in lines:
        h = HEAD_RE.match(ln)
        if h:
            cur = {"num": int(h.group(1)), "icon": h.group(2), "correct": "", "mine": "",
                   "body": [], "note": [], "material": None}
            if mat and mat[0] <= cur["num"] <= mat[1]:
                cur["material"] = mat
            qs.append(cur)
            in_note = False
            continue
        mm = MAT_RE.match(ln)
        if mm:
            mat = (int(mm.group(1)), int(mm.group(2)))
            mats[mat] = []
            cur = None
            continue
        if cur is None:
            if mat in mats and not ln.startswith("---"):
                mats[mat].append(ln)
            continue
        if ln.strip() == "---":
            cur = None
            continue
        if ln.startswith(NOTE):
            in_note = True
            continue
        if in_note:
            cur["note"].append(ln)
            continue
        a = ANS_RE.search(ln)
        if a:
            cur["correct"], cur["mine"] = a.group(1).strip("?"), a.group(2).strip("—")
        elif re.match(r'^>\s*(?:原答题)?用时[:：]',ln):
            seconds=parse_seconds(re.split('[:：]',ln,maxsplit=1)[1])
            if seconds is not None:cur['seconds']=seconds
        elif not ln.startswith(CHECK):
            cur["body"].append(ln)
    for q in qs:
        q["analysis"] = _clean_analysis(q.pop("note"))
        q["material_lines"] = mats.get(q["material"], []) if q["material"] else []
        q["body"] = "\n".join(q["body"]).strip()
    _cache[path] = (mt, qs)
    return qs


def questions(paths, source, last_n=0):
    """某个复盘板块在所有季里的题目，附上 season / source / key / dir"""
    ss = seasons(paths)
    if last_n:
        ss = ss[-last_n:]
    out = []
    for n, d in ss:
        f = board_file(d, source)
        if not f:
            continue
        for q in parse_board_file(f):
            q = dict(q, season=n, source=source, dir=str(d), key=f"{n}|{source}|{q['num']}")
            out.append(q)
    return out


def wrong_questions(paths, sources, last_n=0):
    """❌ / ⚪ 的题（错题池），新的季排在前面"""
    out = []
    for s in sources:
        out += [q for q in questions(paths, s, last_n) if q["icon"] in ("❌", "⚪")]
    return sorted(out, key=lambda q: (-q["season"], q["num"]))


TUTOR_HEAD = "> **🧙 师傅解惑**"
TUTOR_END = "> <!-- /师傅解惑 -->"


def save_tutor_note(paths, key, text, date):
    """把“师傅解惑”写进这道题的复盘笔记（> [!note] 复盘 里），下次“复盘解析”就能看到。
    同一题再问一次就换成新的那段，不越堆越多；自己写的笔记不动。返回写进的文件（库内相对路径）"""
    q = find_question(paths, key)
    if not q:
        return ""
    f = board_file(Path(q["dir"]), q["source"])
    lines = f.read_text(encoding="utf-8").split("\n")
    start = next((i for i, ln in enumerate(lines) if HEAD_RE.match(ln) and int(HEAD_RE.match(ln).group(1)) == q["num"]), None)
    if start is None:
        return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "---" or HEAD_RE.match(lines[i])
                or MAT_RE.match(lines[i])), len(lines))
    block = [TUTOR_HEAD + "（%s）" % date] + ["> " + ln if ln.strip() else ">" for ln in text.strip().split("\n")] + [TUTOR_END]
    seg = lines[start:end]
    old = next((i for i, ln in enumerate(seg) if ln.startswith(TUTOR_HEAD)), None)
    if old is not None:      # 换掉上一次的
        close = next((i for i in range(old, len(seg)) if seg[i].strip() == TUTOR_END), len(seg) - 1)
        seg[old:close + 1] = block
    else:
        note = next((i for i, ln in enumerate(seg) if ln.startswith(NOTE)), None)
        if note is None:     # 这题还没有复盘笔记：在题目末尾新开一段
            while seg and not seg[-1].strip():
                seg.pop()
            seg += ["", NOTE] + block + [""]
        else:                # 接在已有笔记后面（笔记是连续的 > 行）
            k = note + 1
            while k < len(seg) and seg[k].startswith(">"):
                k += 1
            seg[k:k] = [">"] + block
    lines[start:end] = seg
    f.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    _cache.pop(f, None)
    return str(f.relative_to(paths.vault)).replace("\\", "/")


def find_question(paths, key):
    n, source, num = key.split("|")
    for q in questions(paths, source):
        if q["season"] == int(n) and q["num"] == int(num):
            return q
    return None


def accuracy(paths, sources, last=3):
    """最近 last 季的实战正确率：{"rate", "trend": "↑/→/↓", "per": [(季, 对, 总)], "count"}"""
    per = []
    for n, d in seasons(paths):
        ok = tot = 0
        for s in sources:
            f = board_file(d, s)
            if not f:
                continue
            qs = parse_board_file(f)
            tot += len(qs)
            ok += sum(1 for q in qs if q["icon"] == "✅")
        if tot:
            per.append((n, ok, tot))
    if not per:
        return None
    recent = per[-last:]
    rate = sum(o for _, o, _ in recent) / sum(t for _, _, t in recent)
    trend = "→"
    if len(per) >= 2:
        last_r = per[-1][1] / per[-1][2]
        prev = per[-3:-1] if len(per) >= 3 else per[-2:-1]
        prev_r = sum(o for _, o, _ in prev) / sum(t for _, _, t in prev)
        trend = "↑" if last_r - prev_r > 0.05 else ("↓" if prev_r - last_r > 0.05 else "→")
    return {"rate": rate, "trend": trend, "per": per[-last:], "count": len(per)}


# ---------------------------------------------------------------- 截图
_img_index = {}


def find_image(paths, season_dir, name):
    """Obsidian 式查找：先找本季目录（含 attachments），再在整个模考复盘目录里按文件名找"""
    name = name.strip()
    direct = safe_vault_file(paths, name)
    if direct:
        return direct
    if season_dir:
        sd = Path(season_dir)
        for c in (sd / name, sd / "attachments" / name):
            if c.is_file():
                return c
    root = paths.vault / "FB模考试卷复盘" if paths.vault else None
    if root and root.is_dir():
        if name not in _img_index:
            hits = [p for p in root.rglob(Path(name).name) if p.is_file()]
            _img_index[name] = hits[0] if hits else None
        return _img_index[name]
    return None


CALLOUT_HEAD = re.compile(r"^\s*>?\s*\[![\w-]+\][-+]?.*$")


def clean_callout(text):
    """拆分脚本把材料写成 Obsidian 折叠块（> [!abstract]- 材料文字… / > 正文）：去掉块头那一行和每行开头的 >"""
    out = []
    for ln in str(text or "").split("\n"):
        if CALLOUT_HEAD.match(ln):
            continue
        out.append(re.sub(r"^\s*>\s?", "", ln) if ln.lstrip().startswith(">") else ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def material_text(q):
    """这道题的共用材料（资料分析、一拖五），清掉折叠块记号；没有就是空"""
    return clean_callout("\n".join(q.get("material_lines") or []))


def render_blocks(paths, q, material=True):
    """把题目（材料 + 题干 + 选项）转成网页用的块列表：[{"t":"text","v":…} | {"t":"img","v":库内相对路径}]
    material=False 只要题干 + 选项（材料另外用 render_material 放进“弹出材料”）"""
    blocks = []
    text = material_text(q) if material else ""
    if text.strip():
        text += "\n\n"
    text += q["body"]
    from . import question_images
    text = question_images.clean_text(paths, q.get("board") or q.get("source") or "", text)
    return text_blocks(paths, q.get("dir"), text)


def render_material(paths, q):
    t = material_text(q)
    from . import question_images
    t = question_images.clean_text(paths, q.get("board") or q.get("source") or "", t)
    return text_blocks(paths, q.get("dir"), t) if t else []


def text_blocks(paths, folder, text):
    """一段 Markdown 文字 → 网页块（![[图]] 按库里的位置找成图片块）"""
    blocks,buffer=[],""
    pos=0
    def flush():
        nonlocal buffer
        if buffer.strip():blocks.append({"t":"text","v":buffer.strip()})
        buffer=""
    for m in IMG_RE.finditer(text):
        buffer+=text[pos:m.start()]
        name=m.group(1) or m.group(2);p=find_image(paths,folder,name)
        if p and paths.vault:
            try:
                rel=p.resolve().relative_to(paths.vault.resolve()).as_posix()
                from . import inline_images
                if '/_净化/符号/' in rel or inline_images.small(paths,rel) is True:
                    buffer=inline_images.before(buffer)+'![[%s]]'%rel
                    pos=inline_images.after(text,m.end())
                else:
                    flush();blocks.append({"t":"img","v":rel})
            except ValueError:pass
        pos=max(pos,m.end())
    buffer+=text[pos:];flush()
    return blocks


def safe_vault_file(paths, rel):
    """网页请求库里的图片时用：只允许库内、图片后缀的文件，防止读到别的文件"""
    if not paths.vault or not rel:
        return None
    p = (paths.vault / rel).resolve()
    try:
        p.relative_to(paths.vault.resolve())
    except ValueError:
        return None
    return p if p.is_file() and p.suffix.lower() in IMAGE_EXT else None

