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

FOLDER = '思过崖'
TEMPLATE = '_模板.md'
# (文档名, 程序里的板块名)：中心理解在题库里叫片段阅读
BOARDS = [('中心理解', '片段阅读'), ('逻辑填空', '逻辑填空'), ('数量关系', '数量关系'), ('定义判断', '定义判断'),
          ('论证逻辑', '论证逻辑'), ('类比推理', '类比推理'), ('一拖五', '一拖五')]
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


def _question(title, chunks):
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
    key = hashlib.sha1(('%s\n%s' % (re.sub(r'\s+', '', stem), '|'.join('%s%s' % kv for kv in sorted(options.items())))).encode('utf-8')).hexdigest()[:16]
    return {'key': key, 'title': title, 'stem': stem, 'options': options, 'answer': right, 'mine': mine, 'sections': rest}


def parse(text):
    """一个板块文档 → {questions, problems}"""
    lines = (text or '').replace('\r\n', '\n').split('\n')
    h1 = next((l[2:].strip() for l in lines if l.startswith('# ')), '')
    top = _sections(lines, 2)
    problems = []
    if any(STEM.match(name) for name, _ in top):          # 旧写法：一个文件一道题（## 原题 / ## 解析）
        q = _question(h1 or '这道题', top)
        qs = [q] if q else []
        if not q:
            problems.append('「原题」里没读到题干和 A–D 选项')
    else:
        qs = []
        for name, body in top[1:]:
            if SKIP_Q.search(name):
                continue
            q = _question(name, _sections(body, 3))
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


def _doc(paths, name):
    f = folder(paths) / (name + '.md')
    try:
        return f, f.read_text(encoding='utf-8-sig')
    except FileNotFoundError:
        return f, None


def _rec(g):
    return g.state.setdefault('siguo', {})


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
    return {'boards': out, 'folder': '训练/%s/' % FOLDER, 'template': '训练/%s/%s' % (FOLDER, TEMPLATE)}


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
    qs = [{'key': q['key'], 'title': q['title'], 'stem': q['stem'], 'options': q['options'], 'has_answer': bool(q['answer']),
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
    first_today = r.get('reward_date', r.get('date') if r.get('last') == 'ok' else None) != g.t
    r.update(tries=r.get('tries', 0) + 1, ok=r.get('ok', 0) + ok, last='ok' if ok else 'bad', date=g.t, pick=choice)
    events = []
    if ok and first_today:
        r['reward_date'] = g.t
        base = g.rules.xp('思过崖答对')
        if base:
            events = g._award(base, 'siguo', eng, item=key, ok=True, note='思过崖 · %s 重做答对' % name, bonus=False)
    return {'ok': ok if q['answer'] else None, 'answer': q['answer'], 'mine': q['mine'], 'choice': choice,
            'sections': q['sections'], 'record': r, 'events': events}
