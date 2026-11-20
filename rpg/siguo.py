"""行测 · 思过崖（2026-11，替换行测的天机台；天机简报的时政内容在万象峰「万象时政」里继续看）。

做题复盘汇总：只收 7 个板块，每个板块一个文档，程序只读不改（用户在本地照格式增改）：
    训练/思过崖/<板块>.md        板块 = 中心理解 / 逻辑填空 / 数量关系 / 定义判断 / 论证逻辑 / 类比推理 / 一拖五
    训练/思过崖/_模板.md         首次打开时写入的格式说明（已存在就不动）

文档格式（一个板块一个文档，开头可有题目索引；用户 2026-11-04 定）：
    ## 001 · 标题                  一道题（“题目索引 / 说明 / 错因分类 / 目录”等标题不算题）
    ### 原题                       题干 + 选项行“- A. ……”（“原题干 / 题目”也认）
    ### 答案                       “正确答案：C；我的选择：B”，或两列表格“| 正确答案 | 我的选择 |”；
                                   选项行末写“**← 答案**”也认
    ### 其他小节（区别、解析、错因分析、一句话教训、辨析卡……）   重做选完之后才展开，按文档顺序显示
    兼容旧写法：一个文件只有一道题、用 ## 原题 / ## 解析 分节时，整份当一道题，标题取 # 标题。
    “我当时的真实想法”这类小节不显示（用户 2026-11-04 定）。

重做：只显示题干和选项，选一个 → 判对错、展开其余小节。记录在 state["siguo"][<板块>|<题指纹>] =
    {"last": "ok"|"bad", "date", "reward_date", "tries", "ok"}；题指纹 = 题干+选项的摘要，改标题不丢记录。
奖励：学习时间照常按心跳计（做题）；重做答对另给 规则 经验.思过崖答对（默认 3）修为，每题每天最多一次。
"""
import hashlib
import os
import re
import time
from pathlib import Path

from . import paths as paths_mod
from . import wordbook

FOLDER = '思过崖'
ASSETS_DIR = 'assets'
TEMPLATE = '_模板.md'
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
# (文档名, 程序里的板块名)：中心理解在题库里叫片段阅读
BOARDS = [('中心理解', '片段阅读'), ('逻辑填空', '逻辑填空'), ('数量关系', '数量关系'), ('定义判断', '定义判断'),
          ('论证逻辑', '论证逻辑'), ('类比推理', '类比推理'), ('一拖五', '一拖五')]
# 词录汇总在 gk-skill 里的常见相对位置（先新目录结构，后兼容旧路径）
WORDBOOK_DIRS = (Path('笔记与题集') / '成语实词录', Path('言语') / '成语实词录', Path('成语实词录'))
SKIP_Q = re.compile(r'题目索引|^说明|错因分类|^目录|^索引|迷惑性质标签')
STEM = re.compile(r'^(原题干?|题目|题干)\s*(?:[（(：:].*)?$')   # “题目索引”不算
ANSWER = re.compile(r'^答案')
HIDE = re.compile(r'我当时的真实想法')
OPT = re.compile(r'^\s*[-*]?\s*\**([A-D])\**\s*[.．、:：]\s*(.+?)\s*$')
MARK = re.compile(r'\*{0,2}\s*←\s*答案\s*\*{0,2}')
LAST_ACT = {'t': 0.0}


def touch():
    LAST_ACT['t'] = time.time()


def studying(window=300):
    return time.time() - LAST_ACT['t'] < window


def folder(paths):
    return paths.train / FOLDER


def _sections(lines, level):
    """按某一级标题切：[(标题, [行])]；第一个标题之前的行标题为空"""
    mark = '#' * level + ' '
    out = [('', [])]
    for ln in lines:
        if ln.startswith(mark):
            out.append((ln[len(mark):].strip(), []))
        else:
            out[-1][1].append(ln)
    return out


def _letters(text):
    return re.findall(r'[A-D]', re.sub(r'[^A-D]', ' ', text or ''))


def _answer(lines):
    """(正确答案, 我的选择)：认“正确答案：C；我的选择：B”和两列表格"""
    text = '\n'.join(lines)
    right = re.search(r'正确答案\s*[：:]?\s*\**\s*([A-D])', text)
    mine = re.search(r'我的选择\s*[：:]?\s*\**\s*([A-D])', text)
    rows = [l for l in lines if l.strip().startswith('|')]
    if len(rows) >= 3 and not right:
        head = [c.strip() for c in rows[0].strip().strip('|').split('|')]
        vals = [c.strip() for c in rows[2].strip().strip('|').split('|')]
        for k, h in enumerate(head):
            got = (_letters(vals[k]) if k < len(vals) else []) or ['']
            if '正确' in h:
                right = right or got[0]
            elif '我的' in h:
                mine = mine or got[0]
    pick = lambda m: (m.group(1) if hasattr(m, 'group') else m) or ''
    return pick(right), pick(mine)


SHULIANG_18_LECTURES = {
    1: '第01课-方程思维',
    2: '第02课-和差倍比',
    3: '第03课-经济利润',
    4: '第04课-工程问题',
    5: '第05课-行程问题（一）',
    6: '第06课-行程问题（二）',
    7: '第07课-溶液问题',
    8: '第08课-最值问题',
    9: '第09课-排列组合（一）',
    10: '第10课-排列组合（二）',
    11: '第11课-排列组合（三）',
    12: '第12课-概率问题',
    13: '第13课-周期问题',
    14: '第14课-平面几何（一）',
    15: '第15课-平面几何（二）面积问题',
    16: '第16课-立体几何',
    17: '第17课-特殊题型',
    18: '第18课-其它题型',
}
_COURSE_LINE_RE = re.compile(r'\*\*所属课程\*\*\s*[：:]\s*([^\n]+)')
_LECTURE_NUM_RE = re.compile(r'第\s*0?(\d{1,2})\s*[课讲]')


def _extract_group(title: str, chunks, index_groups: dict) -> str:
    for _name, lines in chunks:
        for ln in lines:
            m = _COURSE_LINE_RE.search(ln)
            if m:
                val = m.group(1).strip()
                nm = _LECTURE_NUM_RE.search(val)
                if nm and int(nm.group(1)) in SHULIANG_18_LECTURES and '-' not in val:
                    return SHULIANG_18_LECTURES[int(nm.group(1))]
                return val
    ident_m = re.match(r'^(\d{1,4})\s*[·.．、]', title.strip())
    if ident_m and ident_m.group(1) in index_groups:
        return index_groups[ident_m.group(1)]
    nm = _LECTURE_NUM_RE.search(title)
    if nm and int(nm.group(1)) in SHULIANG_18_LECTURES:
        return SHULIANG_18_LECTURES[int(nm.group(1))]
    return ''


def is_shuliang_wrong_or_slow(block: str) -> bool:
    """判断数量关系 18 课汇总文档中的单题块是否属于错题或慢题（无 18 课『所属方法与来源』标记的普通错题一律保留）。"""
    lines = block.strip().splitlines()
    if not lines:
        return False
    title = lines[0]
    if '已做对' in title:
        return False
    ans = re.search(r'正确答案\s*[：:]\s*\**([A-D])\**(?:[；;\s]*我的选择\s*[：:]\s*\**([A-D]|—)\**)?', block)
    right = ans.group(1) if ans else ''
    mine = (ans.group(2) or '') if ans else ''
    if mine in ('A', 'B', 'C', 'D') and right in ('A', 'B', 'C', 'D') and mine != right:
        return True
    res_m = re.search(r'-\s*\*\*结果\*\*\s*[：:]\s*(.+)', block)
    res = res_m.group(1).strip() if res_m else ''
    if any(k in res or k in title for k in ('做错', '没做出来', '不会', '算错', '慢', '猜对', '蒙对', '猜的', '与讲义答案')):
        return True
    if '**卡点**' in block:
        return True
    if '### 所属方法与来源' not in block:
        return True
    return False


def prune_shuliang_doc(text: str) -> str:
    """清理数量关系错题集中的非错题与非慢题，并同步更新顶部题目索引表。若无需清理则原样返回。"""
    if not text or ('### 所属方法与来源' not in text and '练习，已做对' not in text):
        return text
    norm = text.replace('\r\n', '\n')
    parts = re.split(r'(?=^## \d{3} · )', norm, flags=re.M)
    if len(parts) <= 1:
        return text
    head = parts[0]
    blocks = parts[1:]
    kept = []
    kept_ids = set()
    for b in blocks:
        if is_shuliang_wrong_or_slow(b):
            kept.append(b.rstrip() + '\n\n')
            m = re.match(r'^## (\d{3}) · ', b.strip())
            if m:
                kept_ids.add(m.group(1))
    if len(kept) == len(blocks):
        return text
    # 同步过滤顶部 ## 题目索引 表格行并更新总题数
    new_head_lines = []
    for ln in head.splitlines():
        row_m = re.match(r'^\|\s*(\d{3})\s*\|', ln.strip())
        if row_m and row_m.group(1) not in kept_ids:
            continue
        ln = re.sub(r'（共\s*\d+\s*题）', '（仅收录错题与慢题，共 %d 题）' % len(kept), ln)
        new_head_lines.append(ln)
    new_head = '\n'.join(new_head_lines).rstrip() + '\n\n'
    return new_head + ''.join(kept)


def _question(title, chunks, index_groups=None):
    """chunks = [(小节名, [行])] → 题；没有选项返回 None"""
    stem_lines, options, right, mine, rest = [], {}, '', '', []
    for name, lines in chunks:
        if STEM.match(name):
            for ln in lines:
                m = OPT.match(ln)
                if m:
                    body = m.group(2)
                    if MARK.search(body):
                        right = right or m.group(1)
                        body = MARK.sub('', body).strip()
                    options[m.group(1)] = body
                elif not options:
                    stem_lines.append(ln)
        elif ANSWER.match(name):
            r, m_ = _answer(lines)
            right, mine = right or r, mine or m_
        elif name and not HIDE.search(name):
            md = '\n'.join(lines).strip()
            md = '\n'.join(l for l in md.split('\n') if not HIDE.search(l))
            if md:
                rest.append({'title': name, 'md': md})
    stem = '\n'.join(stem_lines).strip()
    if not stem or len(options) < 2:
        return None
    group = _extract_group(title, chunks, index_groups or {})
    key = hashlib.sha1(('%s\n%s' % (re.sub(r'\s+', '', stem), '|'.join('%s%s' % kv for kv in sorted(options.items())))).encode('utf-8')).hexdigest()[:16]
    return {'key': key, 'title': title, 'group': group, 'stem': stem, 'options': options, 'answer': right, 'mine': mine, 'sections': rest}


def parse(text):
    """一个板块文档 → {questions, problems}"""
    lines = (text or '').replace('\r\n', '\n').split('\n')
    h1 = next((l[2:].strip() for l in lines if l.startswith('# ')), '')
    top = _sections(lines, 2)
    problems = []
    index_groups = {}
    for name, body in top[1:]:
        if '题目索引' in name or '目录' in name:
            for ln in body:
                m = re.match(r'^\|\s*(\d{1,4})\s*\|\s*([^|]+?)\s*\|', ln.strip())
                if m and '第' in m.group(2):
                    index_groups[m.group(1).strip()] = m.group(2).strip()
    if any(STEM.match(name) for name, _ in top):          # 旧写法：一个文件一道题（## 原题 / ## 解析）
        q = _question(h1 or '这道题', top, index_groups)
        qs = [q] if q else []
        if not q:
            problems.append('「原题」里没读到题干和 A–D 选项')
    else:
        qs = []
        for name, body in top[1:]:
            if SKIP_Q.search(name):
                continue
            q = _question(name, _sections(body, 3), index_groups)
            if q:
                qs.append(q)
            elif any(l.strip() for l in body):
                problems.append('「%s」没读到题：要有 ### 原题（题干 + “- A. ……”选项）' % name)
    for q in qs:
        if not q['answer']:
            problems.append('「%s」没写正确答案：在 ### 答案 里写“正确答案：C”' % q['title'])
    seen = {}
    for q in qs:                                          # 同一题写了两次：后面的加序号，记录各算各的
        seen[q['key']] = seen.get(q['key'], 0) + 1
        if seen[q['key']] > 1:
            q['key'] += '-%d' % seen[q['key']]
    return {'questions': qs, 'problems': problems}


TEMPLATE_TEXT = """# 思过崖 · 格式说明（模板）

> 每个板块一个文档：中心理解.md、逻辑填空.md、数量关系.md、定义判断.md、论证逻辑.md、类比推理.md、一拖五.md，放在这个文件夹里。
> 照下面的格式往里加题，保存后重新打开思过崖就能看到。软件只读不改；本文件是说明，软件不显示。

规则：
1. 每道题以 `## 编号 · 标题` 开头（标题随便写，改标题不会丢重做记录）。“## 题目索引”“## 错因分类”这类标题不算题。
2. `### 原题`：题干，然后每个选项一行 `- A. ……`。
3. `### 答案`：写 `正确答案：C；我的选择：B`（也可以用两列表格）。
4. 其余 `###` 小节（区别、解析、错因分析、一句话教训、辨析卡……）随便加，重做选完答案后才展开，按你写的顺序显示。

---

## 001 · 月牙儿（力透纸背）

### 原题

老舍《月牙儿》……这篇小说之所以能____，掷地有声，就是因为在创作中，作家不是旁观者，而是经历者。

填入画横线部分最恰当的一项是：

- A. 不落窠臼
- B. 洛阳纸贵
- C. 力透纸背
- D. 巧夺天工

### 答案

正确答案：C；我的选择：B

### 区别（先看这里）

| 成语 | 参照物 | 在夸什么 |
|---|---|---|
| 力透纸背 | 无外部参照 | 作品自身的力度 |
| 洛阳纸贵 | 读者 | 影响范围 |

### 错因分析

被“掷地有声”的影响力联想带去了洛阳纸贵。

### 一句话教训

> 夸文章的成语，先问“参照物是谁”。
"""


def ensure_template(paths):
    if not paths.train:
        return
    d = folder(paths)
    try:
        d.mkdir(parents=True, exist_ok=True)
        f = d / TEMPLATE
        if not f.exists():
            tmp = f.with_suffix('.tmp')
            with tmp.open('w', encoding='utf-8', newline='\n') as stream:
                stream.write(TEMPLATE_TEXT)
            os.replace(tmp, f)
    except OSError:
        pass


def _atomic_write_text(f: Path, text: str) -> bool:
    data = text.encode('utf-8')
    if f.is_file():
        try:
            if f.read_bytes() == data:
                return False
        except OSError:
            pass
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, f)
    return True


def _doc(paths, name):
    f = folder(paths) / (name + '.md')
    try:
        text = f.read_text(encoding='utf-8-sig')
        if name == '数量关系':
            cleaned = prune_shuliang_doc(text)
            if cleaned != text:
                try:
                    _atomic_write_text(f, cleaned)
                except OSError:
                    pass
                text = cleaned
        return f, text
    except FileNotFoundError:
        return f, None


def _rec(g):
    return g.state.setdefault('siguo', {})


def _atomic_copy(src: Path, dst: Path):
    """按字节比对，内容有变化才原子写入；返回 True 表示已更新，False 表示无变化。"""
    data = src.read_bytes()
    if dst.is_file():
        try:
            if dst.read_bytes() == data:
                return False
        except OSError:
            pass
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, dst)
    return True


def _looks_like_sync_dir(p: Path):
    """是否像 gk-skill 根目录或错题集目录"""
    if not p or not p.is_dir():
        return False
    if (p / '错题集').is_dir():
        return True
    if any((p / (name + '.md')).is_file() for name, _ in BOARDS):
        return True
    return any((p / rel / fn).is_file() for rel in WORDBOOK_DIRS for fn in wordbook.KINDS.values())


def resolve_sync_source(paths):
    """查找 gk-skill 同步源：优先本机设置 gk_skill_dir，其次自动识别 <行测库>/gk-skill/。"""
    configured = str(paths_mod.load_settings().get('gk_skill_dir') or '').strip()
    if configured:
        p = Path(configured).expanduser()
        if p.is_dir():
            return {'source': p.resolve(), 'mode': 'custom', 'configured': configured}
        return {'source': None, 'mode': 'custom_missing', 'configured': configured}
    if paths and paths.vault:
        cand = paths.vault / 'gk-skill'
        if _looks_like_sync_dir(cand):
            return {'source': cand.resolve(), 'mode': 'vault', 'configured': ''}
    return {'source': None, 'mode': '', 'configured': ''}


def _sync_meta(paths):
    info = resolve_sync_source(paths)
    return {'source': str(info['source']) if info['source'] else '', 'mode': info['mode'], 'configured': info['configured']}


def _find_wordbook_file(root: Path, filename: str):
    """在 gk-skill 根目录（以及当用户直接选了 错题集/ 时的上一级目录）里找词录汇总文档。"""
    bases = [root]
    if root.name == '错题集' and root.parent.is_dir():
        bases.append(root.parent)
    for base in bases:
        for rel in WORDBOOK_DIRS:
            f = base / rel / filename
            if f.is_file():
                return f
        direct = base / filename
        if direct.is_file():
            return direct
    return None


def sync_from_source(g, source_dir=None):
    """手动把本地 gk-skill 的错题集（7 板块 + 政治理论易错题 + assets 配图）与词录汇总同步进 训练/（不同步心法）。"""
    if not g.paths.train:
        raise ValueError('请先指定行测库')
    if source_dir and str(source_dir).strip():
        src_root = Path(str(source_dir).strip()).expanduser()
        if not src_root.is_dir():
            raise ValueError('找不到同步目录：%s' % src_root)
        src_root = src_root.resolve()
        mode = 'custom'
    else:
        info = resolve_sync_source(g.paths)
        if not info['source']:
            if info['mode'] == 'custom_missing':
                raise ValueError('设置的 gk-skill 目录不存在：%s（请到设置里检查路径）' % info['configured'])
            raise ValueError('未找到 gk-skill 目录：把 gk-skill 放进行测库根目录，或在「设置」里填写它的路径')
        src_root = info['source']
        mode = info['mode']

    cuoti_dir = (src_root / '错题集') if (src_root / '错题集').is_dir() else src_root
    dst_siguo = folder(g.paths)
    dst_siguo.mkdir(parents=True, exist_ok=True)
    ensure_template(g.paths)

    same_siguo = False
    try:
        same_siguo = cuoti_dir.resolve() == dst_siguo.resolve()
    except OSError:
        same_siguo = False

    boards_updated, boards_unchanged, boards_missing = [], [], []
    if not same_siguo:
        for name, _ in BOARDS:
            src_f = cuoti_dir / (name + '.md')
            if not src_f.is_file():
                boards_missing.append(name)
                continue
            dst_f = dst_siguo / (name + '.md')
            before = len(parse(dst_f.read_text(encoding='utf-8-sig'))['questions']) if dst_f.is_file() else 0
            raw_text = src_f.read_text(encoding='utf-8-sig')
            if name == '数量关系':
                cleaned = prune_shuliang_doc(raw_text)
                if cleaned != raw_text:
                    try:
                        _atomic_write_text(src_f, cleaned)
                    except OSError:
                        pass
                changed = _atomic_write_text(dst_f, cleaned)
            else:
                changed = _atomic_copy(src_f, dst_f)
            after = len(parse(dst_f.read_text(encoding='utf-8-sig'))['questions'])
            if changed:
                boards_updated.append({'name': name, 'before': before, 'after': after})
            else:
                boards_unchanged.append(name)

    # 政治理论易错题（不在思过崖 7 石碑显示，同步到 训练/万象峰/易错题.md 供时政地图『易错题』栏展示）
    politics_wrong_updated = False
    for cand_name in ('政治理论.md', '易错题.md'):
        src_pw = cuoti_dir / cand_name
        if src_pw.is_file():
            dst_pw = politics_wrong_file(g.paths)
            try:
                if src_pw.resolve() != dst_pw.resolve() and _atomic_copy(src_pw, dst_pw):
                    politics_wrong_updated = True
            except OSError:
                pass
            break

    # 将万象峰时政地图导出的 md 文档同步一份到 gk-skill/时政地图/ 下，并写入本地 Agent 规则说明，方便本地 agent 检索
    try:
        from . import politics
        exported_dirs = politics.export_exam_markdowns(g.paths)
        if src_root.is_dir() and (src_root / '错题集').is_dir():
            dst_maps = src_root / '时政地图'
            for ed in exported_dirs:
                for md_file in ed.rglob('*.md'):
                    rel_md = md_file.relative_to(ed.parent)
                    _atomic_copy(md_file, dst_maps / rel_md)
        agent_tpl = paths_mod.RES_DIR / 'defaults' / 'gk-skill-AGENTS.md'
        if agent_tpl.is_file():
            _atomic_copy(agent_tpl, g.paths.train / '规则与设定' / 'AGENTS.md')
            if src_root.is_dir() and (src_root / '错题集').is_dir():
                _atomic_copy(agent_tpl, src_root / 'GK_AGENT_RULES.md')
    except Exception:
        pass

    assets_updated, assets_unchanged = 0, 0
    src_assets = cuoti_dir / ASSETS_DIR
    if src_assets.is_dir() and not same_siguo:
        dst_assets = dst_siguo / ASSETS_DIR
        for p in sorted(src_assets.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in IMAGE_EXT:
                continue
            rel = p.relative_to(src_assets)
            if any(part.startswith('.') for part in rel.parts):
                continue
            if _atomic_copy(p, dst_assets / rel):
                assets_updated += 1
            else:
                assets_unchanged += 1

    wb_updated, wb_unchanged = [], []
    dst_wb = wordbook.folder(g.paths)
    for kind, fn in wordbook.KINDS.items():
        src_wb = _find_wordbook_file(src_root, fn)
        if not src_wb:
            continue
        dst_f = dst_wb / fn
        try:
            if src_wb.resolve() == dst_f.resolve():
                wb_unchanged.append(kind)
                continue
        except OSError:
            pass
        if _atomic_copy(src_wb, dst_f):
            wb_updated.append(kind)
        else:
            wb_unchanged.append(kind)

    if not boards_updated and not boards_unchanged and not assets_updated and not assets_unchanged and not wb_updated and not wb_unchanged and not politics_wrong_updated:
        raise ValueError('这个目录里没有找到思过崖 7 板块错题文档或词录汇总：%s' % src_root)

    parts = []
    if boards_updated:
        parts.append('错题集更新 %s' % '、'.join('%s(%d题)' % (x['name'], x['after']) for x in boards_updated))
    if politics_wrong_updated:
        parts.append('政治理论易错题')
    if assets_updated:
        parts.append('配图 %d 张' % assets_updated)
    if wb_updated:
        parts.append('词录(%s)' % '、'.join(wb_updated))
    summary = '已同步：' + '；'.join(parts) if parts else '已是最新，没有需要更新的文件'

    out = boards(g)
    out['sync_result'] = {
        'source': str(src_root),
        'mode': mode,
        'boards_updated': boards_updated,
        'boards_unchanged': boards_unchanged,
        'boards_missing': boards_missing,
        'politics_wrong_updated': politics_wrong_updated,
        'assets_updated': assets_updated,
        'assets_unchanged': assets_unchanged,
        'wordbook_updated': wb_updated,
        'wordbook_unchanged': wb_unchanged,
        'summary': summary,
    }
    return out


def boards(g):
    """七块石碑：每块 {name, board, exists, total, done, ok, bad}"""
    ensure_template(g.paths)
    rec = _rec(g)
    out = []
    for name, board in BOARDS:
        _f, text = _doc(g.paths, name)
        qs = parse(text)['questions'] if text is not None else []
        rs = [rec.get('%s|%s' % (name, q['key'])) for q in qs]
        out.append({'name': name, 'board': board, 'exists': text is not None, 'total': len(qs),
                    'done': sum(1 for r in rs if r), 'ok': sum(1 for r in rs if r and r['last'] == 'ok'),
                    'bad': sum(1 for r in rs if r and r['last'] == 'bad')})
    return {'boards': out, 'folder': '训练/%s/' % FOLDER, 'template': '训练/%s/%s' % (FOLDER, TEMPLATE),
            'sync': _sync_meta(g.paths)}


def _board(name):
    for n, b in BOARDS:
        if n == name:
            return n, b
    raise ValueError('思过崖没有这个板块：%s' % name)


def board(g, name):
    """一个板块的题：重做前只给题干和选项；做过的附上次结果"""
    name, eng = _board(name)
    touch()
    f, text = _doc(g.paths, name)
    if text is None:
        return {'name': name, 'board': eng, 'exists': False, 'file': '训练/%s/%s.md' % (FOLDER, name),
                'template': '训练/%s/%s' % (FOLDER, TEMPLATE), 'questions': [], 'problems': []}
    d = parse(text)
    rec = _rec(g)
    qs = [{'key': q['key'], 'title': q['title'], 'group': q.get('group', ''), 'stem': q['stem'],
           'options': q['options'], 'has_answer': bool(q['answer']),
           'record': rec.get('%s|%s' % (name, q['key']))} for q in d['questions']]
    return {'name': name, 'board': eng, 'exists': True, 'file': '训练/%s/%s.md' % (FOLDER, name), 'questions': qs,
            'problems': d['problems']}


def answer(g, name, key, choice):
    """重做一题：判对错、记录、答对给少量修为（每题每天一次），返回解析小节"""
    name, eng = _board(name)
    choice = str(choice or '').strip().upper()
    if choice not in 'ABCD' or len(choice) != 1:
        raise ValueError('选一个 A–D')
    _f, text = _doc(g.paths, name)
    q = next((x for x in parse(text or '')['questions'] if x['key'] == key), None)
    if not q:
        raise ValueError('这道题在文档里找不到了（可能刚改过），重新打开思过崖')
    touch()
    ok = bool(q['answer']) and choice == q['answer']
    r = _rec(g).setdefault('%s|%s' % (name, key), {'tries': 0, 'ok': 0})
    if 'reward_date' not in r and r.get('last') == 'ok':
        r['reward_date'] = r.get('date')
    first_today = r.get('reward_date') != g.t
    r.update(tries=r.get('tries', 0) + 1, ok=r.get('ok', 0) + ok, last='ok' if ok else 'bad', date=g.t, pick=choice)
    events = []
    if ok and first_today:
        r['reward_date'] = g.t
        base = g.rules.xp('思过崖答对')
        if base:
            events = g._award(base, 'siguo', eng, item=key, ok=True, note='思过崖 · %s 重做答对' % name, bonus=False)
    return {'ok': ok if q['answer'] else None, 'answer': q['answer'], 'mine': q['mine'], 'choice': choice,
            'sections': q['sections'], 'record': r, 'events': events}


def politics_wrong_file(paths, exam_title: str = '') -> Path:
    """政治理论易错题文档路径：优先读当前时政地图文件夹下的 易错题.md，否则读 训练/万象峰/易错题.md（并自动从 gk-skill/错题集/政治理论.md 首次同步）。"""
    raw_train = paths.train._raw() if hasattr(paths.train, '_raw') else Path(paths.train)
    wx_root = raw_train / '万象峰'
    wx_root.mkdir(parents=True, exist_ok=True)
    shared = wx_root / '易错题.md'
    if not shared.is_file():
        info = resolve_sync_source(paths)
        if info['source']:
            cuoti = (info['source'] / '错题集') if (info['source'] / '错题集').is_dir() else info['source']
            for cand in ('政治理论.md', '易错题.md'):
                if (cuoti / cand).is_file():
                    try:
                        _atomic_copy(cuoti / cand, shared)
                    except OSError:
                        pass
                    break
    if exam_title:
        per_exam = wx_root / exam_title / '易错题.md'
        if per_exam.is_file():
            return per_exam
    return shared


def politics_wrong_board(g, exam_title: str = ''):
    """时政地图『易错题』栏（思过崖同款格式与重做记录，不在思过崖七碑显示）。"""
    touch()
    f = politics_wrong_file(g.paths, exam_title)
    rel = f.relative_to(g.paths.vault).as_posix() if g.paths.vault and f.exists() else '训练/万象峰/易错题.md'
    if not f.is_file():
        return {'name': '政治理论', 'board': '政治理论', 'exists': False, 'file': rel,
                'template': '训练/%s/%s' % (FOLDER, TEMPLATE), 'questions': [], 'problems': []}
    text = f.read_text(encoding='utf-8-sig')
    d = parse(text)
    rec = _rec(g)
    qs = [{'key': q['key'], 'title': q['title'], 'group': q.get('group', ''), 'stem': q['stem'],
           'options': q['options'], 'has_answer': bool(q['answer']),
           'record': rec.get('政治理论|%s' % q['key'])} for q in d['questions']]
    return {'name': '政治理论', 'board': '政治理论', 'exists': True, 'file': rel, 'questions': qs,
            'problems': d['problems']}


def politics_wrong_answer(g, key, choice, exam_title: str = ''):
    """时政地图『易错题』重做一题。"""
    choice = str(choice or '').strip().upper()
    if choice not in 'ABCD' or len(choice) != 1:
        raise ValueError('选一个 A–D')
    f = politics_wrong_file(g.paths, exam_title)
    text = f.read_text(encoding='utf-8-sig') if f.is_file() else ''
    q = next((x for x in parse(text)['questions'] if x['key'] == key), None)
    if not q:
        raise ValueError('这道题在文档里找不到了（可能刚改过），请刷新重试')
    touch()
    ok = bool(q['answer']) and choice == q['answer']
    r = _rec(g).setdefault('政治理论|%s' % key, {'tries': 0, 'ok': 0})
    if 'reward_date' not in r and r.get('last') == 'ok':
        r['reward_date'] = r.get('date')
    first_today = r.get('reward_date') != g.t
    r.update(tries=r.get('tries', 0) + 1, ok=r.get('ok', 0) + ok, last='ok' if ok else 'bad', date=g.t, pick=choice)
    events = []
    if ok and first_today:
        r['reward_date'] = g.t
        base = g.rules.xp('思过崖答对')
        if base:
            events = g._award(base, 'siguo', '政治理论', item=key, ok=True, note='政治理论 · 易错题重做答对', bonus=False)
    return {'ok': ok if q['answer'] else None, 'answer': q['answer'], 'mine': q['mine'], 'choice': choice,
            'sections': q['sections'], 'record': r, 'events': events}
