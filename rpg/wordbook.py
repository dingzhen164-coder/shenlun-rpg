"""藏经阁·成语实词录（2026-11 重做）：以“一组易混词”为单位，只读用户在本地维护的两份文档。

文件（程序只读，从不改写；用户在本地照格式增改）：
    训练/成语实词录/成语区别汇总.md
    训练/成语实词录/实词区别汇总.md
    训练/成语实词录/_模板.md          首次打开时写入的格式说明（已存在就不动）

文档格式（与用户 2026-11-04 提供的《成语区别汇总》一致）：
    # 标题 + 开头的 > 说明（显示为“说明”，可折叠）
    ## 1. 组名                                  一组；编号可省略，按出现顺序编号
    **最深区别：……** / **维度一（……）：……**     段落；以“最深区别/维度”开头的加粗段落是判别轴
    | 成语 | 回答的问题 | 一句话区别 | 出处与例句 |   表格；“成语/实词/词语”所在列是词，含“区别”的列是一句话区别
    **易混**：……                                 提示框
    组内可以有多个维度（多段落 + 多张表）。表格里写 〔推断〕〔待核〕〔二手〕〔常识〕 会显示成小标签；
    “出处与例句”格里 <br> 之后以 **生僻字**/**熟词僻义**/**类似** 开头的字义部分默认折叠。

组的显示名：第N组—该组各词（只取表格“词”列里单独一个词的格子；“（无关）短褐不全”这类括号开头的不算）。
卡片（辨言峰温习）：每组一张组卡，牌组 逻辑填空::成语组 / 逻辑填空::实词组；
    正面 = 组名 + “最深区别是什么？各词分别是什么意思？”，背面 = 判别轴 + 每个词的一句话区别 + 易混。
    state["wordbook_cards"][<种类>|<组标题>] = 玉简编号；用户点“同步到卡片”时增改删，温习进度跟着编号走。
旧版（自动收录的单词条，state["idioms"]、state["idiom_cards"]、训练/成语实词录.md）在第一次打开时
    备份到 训练/词录备份/旧成语实词录-<日期>.json 后清除（用户 2026-11-04 确认）。
"""
import datetime as dt
import json
import os
import re
from pathlib import Path

from . import question_bank

FOLDER = '成语实词录'
KINDS = {'成语': '成语区别汇总.md', '实词': '实词区别汇总.md'}
DECKS = {'成语': '逻辑填空::成语组', '实词': '逻辑填空::实词组'}
TEMPLATE = '_模板.md'
CN = '零一二三四五六七八九'
TAG = re.compile(r'〔(推断|待核|二手|常识)〕')
HEAD = re.compile(r'^##\s+(?:(\d+)\s*[.、．]\s*)?(.+?)\s*$')
AXIS = re.compile(r'^\*\*(最深区别|维度[一二三四五六七八九十\d]+)')
WORD_COL = ('成语', '实词', '词语', '词')


def cn_num(n):
    """1→一 10→十 12→十二 20→二十"""
    if n < 10:
        return CN[n]
    tens, ones = divmod(n, 10)
    return ('' if tens == 1 else CN[tens]) + '十' + (CN[ones] if ones else '')


def folder(paths):
    return paths.train / FOLDER


def _cells(line):
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def _plain(s):
    return re.sub(r'\*\*|__|`', '', s or '').strip()


def _single_word(cell):
    w = _plain(cell)
    if not w or w.startswith(('（', '(')) or re.search(r'[、，,；;（()\s<]', w):
        return ''
    return w if re.fullmatch(r'[一-鿿]{1,8}', w) else ''


def _blocks(lines):
    """组内正文 → [{type: para|axis|tip|table, ...}]"""
    out, para, i = [], [], 0

    def flush():
        text = '\n'.join(para).strip()
        para.clear()
        if not text:
            return
        if text.startswith('**易混'):
            out.append({'type': 'tip', 'md': text})
        elif AXIS.match(text):
            out.append({'type': 'axis', 'md': text})
        else:
            out.append({'type': 'para', 'md': text})
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith('|'):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(_cells(lines[i]))
                i += 1
            head = rows[0]
            body = [r for r in rows[1:] if not all(re.fullmatch(r':?-{2,}:?', c or '-') for c in r)]
            wc = next((k for k, h in enumerate(head) if _plain(h) in WORD_COL), 0)
            dc = next((k for k, h in enumerate(head) if '区别' in h), 1 if len(head) > 1 else 0)
            out.append({'type': 'table', 'head': head, 'rows': body, 'word_col': wc, 'diff_col': dc})
            continue
        if not ln.strip() or ln.strip() == '---':
            flush()
        else:
            para.append(ln)
        i += 1
    flush()
    return out


def parse(text):
    """整份文档 → {intro, groups:[{no, heading, name, words, blocks, diffs}], problems}"""
    lines = (text or '').replace('\r\n', '\n').split('\n')
    intro, groups, cur, problems = [], [], None, []
    for ln in lines:
        m = HEAD.match(ln)
        if m and not ln.startswith('###'):
            cur = {'no': int(m.group(1)) if m.group(1) else len(groups) + 1, 'heading': m.group(2).strip(), 'lines': []}
            groups.append(cur)
            continue
        if cur is None:
            if not ln.startswith('# '):
                intro.append(ln)
        else:
            cur['lines'].append(ln)
    out = []
    for gidx, gr in enumerate(groups):
        blocks = _blocks(gr.pop('lines'))
        words, diffs = [], {}
        for b in blocks:
            if b['type'] != 'table':
                continue
            for r in b['rows']:
                w = _single_word(r[b['word_col']]) if b['word_col'] < len(r) else ''
                if not w:
                    continue
                if w not in words:
                    words.append(w)
                d = r[b['diff_col']] if b['diff_col'] < len(r) and b['diff_col'] != b['word_col'] else ''
                if d and not _plain(d).startswith('同上') and w not in diffs:
                    diffs[w] = d
        if not words:
            problems.append('第 %d 个分组「%s」里没找到词：表格第一行要有“成语”或“实词”这一列' % (gidx + 1, gr['heading']))
        name = '第%s组—%s' % (cn_num(gr['no']), '、'.join(words) if words else gr['heading'])
        out.append(dict(gr, name=name, words=words, blocks=blocks, diffs=diffs))
    nos = [g['no'] for g in out]
    if len(set(nos)) != len(nos):
        problems.append('分组编号有重复：%s' % '、'.join(str(n) for n in sorted({n for n in nos if nos.count(n) > 1})))
    return {'intro': '\n'.join(intro).strip(), 'groups': out, 'problems': problems}


TEMPLATE_TEXT = """# 成语区别汇总 · 格式说明（模板）

> 软件只读这个文件夹里的 成语区别汇总.md（成语）和 实词区别汇总.md（实词），照下面的格式写，保存后重新打开「词录」就能看到。
> 本文件是说明，软件不显示。改坏了也没关系：删掉它，下次打开会重新生成。

规则：
1. 每一组以 `## 编号. 组名` 开头（如 `## 1. 夸文章、作品`）。软件显示为“第一组—这组的各个词”。
2. 组里先写判别轴：一段以 `**最深区别：……**` 或 `**维度一（适用：……）：……**` 开头的加粗文字。一组可以有几个维度。
3. 每个维度下面一张表。表头里要有一列叫“成语”（实词文档叫“实词”），有一列名字带“区别”（一句话区别，会放进卡片）。
4. 想加提示就写 `**易混**：……`，会显示成提示框。
5. 〔推断〕〔待核〕〔二手〕〔常识〕 会显示成小标签；出处格里 `<br>` 后面以 **生僻字**/**熟词僻义**/**类似** 开头的字义默认折叠。

---

## 1. 夸文章、作品

**最深区别：拿什么当参照物，也就是在回答"和谁比"。**

| 成语 | 回答的问题 | 一句话区别 | 出处与例句 |
|---|---|---|---|
| 力透纸背 | 文字有劲吗？ | **无外部参照**，夸作品自身的力度 | **熟词僻义**：背，纸的背面 |
| 洛阳纸贵 | 有多少人抢着读？ | **参照读者**，夸影响范围 | **熟词僻义**：贵，价格上涨 |

**易混**：力透纸背夸作品自身，洛阳纸贵夸读者反应。
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
            tmp.write_text(TEMPLATE_TEXT, encoding='utf-8', newline='\n')
            os.replace(tmp, f)
    except OSError:
        pass


def load(paths, kind):
    f = folder(paths) / KINDS[kind]
    try:
        text = f.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        return dict(parse(''), exists=False)
    except OSError as e:
        return dict(parse(''), exists=False, problems=['读不了 %s：%s' % (f.name, e)])
    return dict(parse(text), exists=True)


# ---------------------------------------------------------------- 真题出处：词出现在哪些逻辑填空题的选项里
_SEEN = {'sig': None, 'index': {}}


def _bank_index(paths):
    files = question_bank.files(paths, '逻辑填空') if paths.train else []
    sig = tuple((str(f), f.stat().st_mtime_ns) for f in files)
    if _SEEN['sig'] != sig:
        index = {}
        for q in question_bank.read_all(paths, '逻辑填空')[0]:
            text = ' '.join(str(v) for v in (q.get('options') or {}).values())
            index[q['key']] = (q['id'], q.get('board') or '逻辑填空', q.get('paper') or q.get('source') or '', text)
        _SEEN.update(sig=sig, index=index)
    return _SEEN['index']


def sources(paths, words, limit=4):
    idx = _bank_index(paths)
    out = {}
    for w in words:
        hits = [{'key': k, 'id': i, 'board': b, 'paper': p} for k, (i, b, p, t) in idx.items() if w in t]
        if hits:
            out[w] = hits[:limit]
    return out


# ---------------------------------------------------------------- 旧版清理（只做一次）
def retire_old(g):
    """旧的自动收录词条与它生成的玉简：备份成一份 JSON 后清掉（用户确认不再需要）"""
    st = g.state
    if st.get('wordbook_retired'):
        return False
    old, links = st.get('idioms') or {}, st.get('idiom_cards') or {}
    if g.paths.train and (old or links):
        bak = g.paths.train / '词录备份' / ('旧成语实词录-%s.json' % dt.date.today().isoformat())
        bak.parent.mkdir(parents=True, exist_ok=True)
        tmp = bak.with_suffix('.tmp')
        tmp.write_text(json.dumps({'idioms': old, 'idiom_cards': links, 'idioms_deleted': st.get('idioms_deleted')},
                                  ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(tmp, bak)
    if links:
        from . import cards
        try:
            cards.delete(g, list(links.values()))
        except Exception:
            pass
    old_file = g.paths.train / '成语实词录.md' if g.paths.train else None
    if old_file and old_file.is_file():
        dest = g.paths.train / '词录备份' / ('旧成语实词录-%s.md' % dt.date.today().isoformat())
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(old_file, dest)
        except OSError:
            pass
    for k in ('idioms', 'idiom_cards', 'idioms_deleted', 'idioms_v', 'idiom_sync'):
        st.pop(k, None)
    st['wordbook_retired'] = True
    return True


# ---------------------------------------------------------------- 组卡
def card_fields(kind, gr):
    axes = [b['md'] for b in gr['blocks'] if b['type'] == 'axis']
    items = ['- **%s**：%s' % (w, _plain(gr['diffs'][w]).replace('<br>', ' ') if gr['diffs'].get(w) else '（见词录表格）')
             for w in gr['words']]
    tips = [b['md'] for b in gr['blocks'] if b['type'] == 'tip']
    parts = ['\n\n'.join(axes), '\n'.join(items), '\n\n'.join(tips)]
    word = '词' if kind == '实词' else '成语'
    return {'deck': DECKS[kind], 'type': '问答', 'tags': ['成语实词录', kind + '组'],
            'front': '**%s**\n\n这组的最深区别是什么？各%s分别是什么意思？' % (gr['name'], word),
            'back': '\n\n'.join(p for p in parts if p).strip() or '（见词录）',
            'extra': '由藏经阁「词录」按 训练/成语实词录/%s 生成；改文档后在词录里点“同步到卡片”更新' % KINDS[kind]}


def sync_cards(g, kind):
    """把这份文档的每组同步成一张组卡：新组新建、改过的组更新（进度保留）、文档里没有了的组删卡"""
    from . import cards
    doc = load(g.paths, kind)
    if not doc['exists']:
        raise ValueError('还没有 训练/%s/%s，先照 _模板.md 写好再同步' % (FOLDER, KINDS[kind]))
    links = g.state.setdefault('wordbook_cards', {})
    seen, made, updated = set(), 0, 0
    for gr in doc['groups']:
        if not gr['words']:
            continue
        key = '%s|%s' % (kind, gr['heading'])
        seen.add(key)
        old = links.get(key)
        nid = cards.upsert(g, old, card_fields(kind, gr))
        made += old is None or old != nid
        updated += old is not None and old == nid
        links[key] = nid
    gone = [k for k in list(links) if k.startswith(kind + '|') and k not in seen]
    if gone:
        cards.delete(g, [links.pop(k) for k in gone])
    return {'cards': len(seen), 'new': made, 'kept': updated, 'removed': len(gone), 'deck': DECKS[kind]}


def listing(g, kind):
    kind = kind if kind in KINDS else '成语'
    ensure_template(g.paths)
    doc = load(g.paths, kind)
    words = [w for gr in doc['groups'] for w in gr['words']]
    where = {}
    for gr in doc['groups']:
        for w in gr['words']:
            where.setdefault(w, []).append(gr['no'])
    links = g.state.get('wordbook_cards') or {}
    return {'kind': kind, 'kinds': list(KINDS), 'file': '训练/%s/%s' % (FOLDER, KINDS[kind]),
            'template': '训练/%s/%s' % (FOLDER, TEMPLATE), 'exists': doc['exists'], 'intro': doc['intro'],
            'groups': doc['groups'], 'problems': doc['problems'], 'where': where,
            'sources': sources(g.paths, words) if words else {},
            'synced': sum(1 for k in links if k.startswith(kind + '|')), 'deck': DECKS[kind]}
