"""冲刺刷题PDF（整本专项/模拟套卷）解析：按“套卷 → 题号 → 题干/选项”逐层切分，politics_import.import_pdf在冲刺刷题通道调用。

输入PDF文字层（文字PDF，扫描版先OCR）；输出
  papers：[{'title': 套卷标题}]，没有套卷标题时整份PDF算一套，标题取文件名；
  questions：[{'paper': 套卷序号, 'no': 套卷内题号, 'text': 题干+选项(每个选项一行, A.xxx), 'answer', 'analysis', 'flags': [...]}]
  report：识别报告（每套题数、选项不全的题、没有答案的题数），导入结果原样回报给用户。
规则：
- 套卷标题：一行里带“卷一/第一套/套卷三”等，≤40字、没有句内标点；它之后题号重新从1开始。
- 题号：同一套卷里按 1,2,3… 顺序接续才算新题（“3.【小黑政治理论】…”），题干里的数字、选项里的数字不会被当成新题；
  题号对不上时只有带【标签】或（单选）才认；题号回到1且上一套已有多题时自动另起一套。
- 选项：A/B/C/D可以各占一行，也可以“A.①③   B.①②   C.②④   D.③④”挤在一行；折行的续行并回上一项；
  每道题最多4项，缺项的题照收但标记“选项不全”并在报告里列出，不猜补。
- 答案：参考答案区按套卷分开（“卷一答案”标题，或按顺序一套一份；题号重新变成1就换下一套）。
不调用AI，不改判分规则。
"""
import re

from . import wanxiang_journal

PAPER = re.compile(r'卷[一二三四五六七八九十百0-9]+|第[一二三四五六七八九十0-9]+套|套卷[一二三四五六七八九十0-9]+|模拟卷[一二三四五六七八九十0-9]*')
QUESTION = re.compile(r'^(\d{1,3})[.．、](?!\d)\s*(.*)$')
OPTION = re.compile(r'(?<![A-Za-z])([A-Da-d])[.．、)）]\s*')      # 行内选项之间的空格会被clean收掉（如“A.①③B.①②”），所以不要求前面有空格
STATEMENT = re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩（(]')
ANSWER_HEAD = re.compile(r'^(?:参考)?答案(?:与|及)?(?:解析)?[：:]?$|参考答案|答案与解析|答案及解析')
ANSWER = re.compile(r'^(\d{1,3})\s*[.．、:：]?\s*(?:【答案】|答案[：:]?)?\s*([A-D](?:[A-D、，, ]*[A-D])?)(?![A-Za-z])[。.]?\s*(.*)$')
EXPLICIT = re.compile(r'^(?:(\d{1,3})[.．、]\s*)?(?:【答案】|答案[：:])\s*([A-D](?:[A-D、，, ]*[A-D])?)[。.]?\s*(.*)$')     # 题后紧跟的“1.【答案】A。解析：…”
LOOSE_START = re.compile(r'^([^\d\s.．、]{1,2})[.．、]\s*([【（(][^】）)]{2,14}[】）)].*)$')     # 题号被OCR认成别的字（“7.【小黑…”→“乙.（小黑…”）
TAG = re.compile(r'^(?:[【（(][^】）)]{2,14}[】）)]|[（(](?:单选|多选|不定项)[)）])')
SENTENCE_END = re.compile(r'[。！？；：:]$')
SECTION = re.compile(r'^[一二三四五六七八九十]+[、．]')


def _page_lines(page):
    out = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            text = wanxiang_journal.clean(''.join(s['text'] for s in line['spans']))
            if not text:
                continue
            x0, y0, _x1, y1 = line['bbox']
            out.append({'text': text, 'size': max((s['size'] for s in line['spans']), default=11), 'x': x0, 'y0': y0, 'y1': y1})
    return out


def _visual_order(lines):
    """按视觉行排序：纵向中心相差不到半个行高算同一行，同一行按x从左到右。
    四个选项并排（A.2项  B.3项  C.4项  D.5项）时OCR给的y会有±1磅的抖动，只按y排会变成 C D B A。"""
    rows = []
    for line in sorted(lines, key=lambda l: (l['y0']+l['y1'])/2):
        yc, h = (line['y0']+line['y1'])/2, line['y1']-line['y0']
        if rows and abs(yc-rows[-1]['yc']) <= .45*max(h, rows[-1]['h']):
            rows[-1]['items'].append(line)
        else:
            rows.append({'yc': yc, 'h': h, 'items': [line]})
    return [l for row in rows for l in sorted(row['items'], key=lambda l: l['x'])]


def _similar(a, b):
    import difflib
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= .72


def _running_heads(pages):
    """每页重复出现的页眉页脚（如“抖音关注公考小黑老师”“Hey，上岸吧！”“@公考小黑老师”）：位于页面上/下边缘，
    且在另一页的同一位置带也出现（允许OCR写错几个字）。返回要丢掉的行的id集合。"""
    band = lambda page, line: line['y0'] < page.rect.height*.09 or line['y1'] > page.rect.height*.915
    edges = [[l for l in lines if band(page, l)] for page, lines in pages]
    drop = set()
    for i, lines in enumerate(edges):
        for line in lines:
            if any(_similar(line['text'], other['text']) for j, others in enumerate(edges) if j != i for other in others):
                drop.add(id(line))
    return drop


def _rows(doc):
    """[(文字, 字号)]：按视觉行（同行从左到右）逐行，去掉页眉页脚与孤立页码。"""
    pages = [(page, _page_lines(page)) for page in doc]
    drop = _running_heads(pages) if len(pages) > 1 else set()
    rows = []
    for page, lines in pages:
        for line in _visual_order([l for l in lines if id(l) not in drop]):
            text = line['text']
            if text in wanxiang_journal.NOISE or re.fullmatch(r'\d{1,3}', text):
                continue
            rows.append((text, line['size']))
    return rows


def paper_title(text):
    """这一行是不是套卷标题 → (标题, 是否答案页标题)，不是返回None。"""
    if len(text) > 40 or re.search(r'[，。；！？]', text) or QUESTION.match(text) or OPTION.match(text):
        return None
    if not PAPER.search(text):
        return None
    return text.strip(), bool(re.search(r'答案|解析', text))


def split_options(text, expect='A'):
    """一行里的选项 → [(字母, 内容)]；必须从行首的选项字母开始（不早于expect：缺了的选项不补），之后字母依次递增，否则不当选项。"""
    marks = [(m.start(), m.end(), m.group(1)) for m in OPTION.finditer(text)]
    picked = []
    for start, end, letter in marks:
        # OCR常把大写选项字母识别成小写（“c.”）：小写只在正好接上下一个字母时才认，避免把“a.”之类当选项。
        if not picked:
            if start != 0 or letter.upper() < expect or (letter.islower() and letter.upper() != expect):
                return []
        elif letter.upper() != chr(ord(picked[-1][2].upper())+1):
            continue
        picked.append((start, end, letter.upper()))
    if not picked:
        return []
    out = []
    for i, (start, end, letter) in enumerate(picked):
        stop = picked[i+1][0] if i+1 < len(picked) else len(text)
        out.append((letter, text[end:stop].strip()))
    return out


CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩'
JUNK = '@＠'


def _numbers(text):
    return [CIRCLED.index(c)+1 if c in CIRCLED else None for c in text if c in CIRCLED or c in JUNK]


def repair_symbols(stem, opts):
    """OCR把①②③④里的个别圈数字认成“@”：能确定的补回去，补不准的保持原样。返回(确定补回数, 按均衡推测补回数)。
    确定：选项里的数字必须从小到大，卡在前后数字之间只剩一个可能。
    推测：仍有几个可能时，取在其他选项里出现最少的那个（这类“①③ ①② ②④ ③④”的选项通常每个数字出现次数一样多），并列则不补。"""
    sure = guessed = 0
    # 题干里的陈述编号按出现顺序重排：“@党的…”“③维护…（其实是⑤）”“5人民立场…”这类被OCR认错的编号都按顺序改回来
    last = 0
    for i, line in enumerate(stem):
        if line and (line[0] in CIRCLED or line[0] in JUNK) and last < len(CIRCLED):
            if line[0] != CIRCLED[last]:
                stem[i] = CIRCLED[last]+line[1:]
                sure += 1
            last += 1
    # 选项里整个都是数字符号的（①③ / ①②3 / 3④）：圈数字被认成普通数字时改回圈数字（题干里至少有两条圈数字陈述才这样做，避免改“A.1”之类的真数字选项）
    if last >= 2:
        for k, (letter, content) in enumerate(opts):
            if re.fullmatch(r'[①-⑩@＠1-9]{1,6}', content) and re.search(r'[1-9]', content):
                opts[k] = (letter, re.sub(r'[1-9]', lambda m: CIRCLED[int(m.group())-1], content))
                sure += 1
    present = sorted({CIRCLED.index(c)+1 for line in stem for c in line[:1] if c in CIRCLED}) or [1, 2, 3, 4]      # 陈述编号以题干里每条陈述开头的为准
    contents = [list(c) for _, c in opts]
    def used():
        count = {}
        for cs in contents:
            for c in cs:
                if c in CIRCLED:
                    count[CIRCLED.index(c)+1] = count.get(CIRCLED.index(c)+1, 0)+1
        return count
    for guess in (False, True):
        changed = True
        while changed:
            changed = False
            for cs in contents:
                for i, c in enumerate(cs):
                    if c not in JUNK:
                        continue
                    before = max([CIRCLED.index(x)+1 for x in cs[:i] if x in CIRCLED] or [0])
                    after = min([CIRCLED.index(x)+1 for x in cs[i+1:] if x in CIRCLED] or [99])
                    options = [n for n in present if before < n < after and CIRCLED[n-1] not in cs]
                    if not guess and len(options) == 1:
                        pick = options[0]
                    elif guess and len(options) > 1:
                        count = used()
                        low = min(count.get(n, 0) for n in options)
                        best = [n for n in options if count.get(n, 0) == low]
                        if len(best) != 1:
                            continue
                        pick = best[0]
                    else:
                        continue
                    cs[i] = CIRCLED[pick-1]
                    sure, guessed = (sure, guessed+1) if guess else (sure+1, guessed)
                    changed = True
    for k, cs in enumerate(contents):
        opts[k] = (opts[k][0], ''.join(cs))
    return sure, guessed


_OCR_WORDS = {'进人': '进入', '收人': '收入', '加人': '加入', '融人': '融入', '纳人': '纳入', '深人': '深入', '列人': '列入', '投人': '投入',
              '步人': '步入', '陷人': '陷入', '迈人': '迈入', '踏人': '踏入', '导人': '导入', '输人': '输入', '自已': '自己'}


def fix_words(text):
    """OCR常见的“入→人”“己→已”：只改这几个几乎不会是原文的词，其他识别错字不乱改。"""
    for wrong, right in _OCR_WORDS.items():
        text = text.replace(wrong, right)
    return text


def _join(a, b):
    """折行拼接：中文直接连，两侧都是字母数字时补空格。"""
    if a and b and re.search(r'[A-Za-z0-9]$', a) and re.match(r'[A-Za-z0-9]', b):
        return a+' '+b
    return a+b


def parse(doc, name):
    rows = _rows(doc)
    papers, questions = [], []
    answers = {}                       # 套卷序号 → {题号: (答案, 解析)}
    state = {'paper': None, 'q': None, 'last_no': 0, 'in_answers': False, 'answer_paper': 0, 'last_answer': None}

    def new_paper(title):
        papers.append({'title': title})
        state.update(paper=len(papers)-1, q=None, last_no=0)

    def finish():
        state['q'] = None

    for text, _size in rows:
        title = paper_title(text)
        if title:
            heading, is_answer = title
            if is_answer and papers:
                key = PAPER.search(heading).group()
                match = next((i for i, p in enumerate(papers) if PAPER.search(p['title']) and PAPER.search(p['title']).group() == key), None)
                state.update(in_answers=True, answer_paper=match if match is not None else state['answer_paper'], last_answer=None)
                finish()
            else:
                new_paper(heading)
                state.update(in_answers=False)
            continue
        if ANSWER_HEAD.search(text) and len(text) <= 24 and not QUESTION.match(text):
            state.update(in_answers=True, last_answer=None)
            if papers and state['answer_paper'] >= len(papers):
                state['answer_paper'] = len(papers)-1
            finish()
            continue
        if state['in_answers']:
            m = ANSWER.match(text)
            if m:
                no = int(m.group(1))
                book = answers.setdefault(state['answer_paper'], {})
                if no in book and state['answer_paper']+1 < len(papers):       # 题号重复：这一份答案属于下一套
                    state['answer_paper'] = min(state['answer_paper']+1, len(papers)-1)
                    book = answers.setdefault(state['answer_paper'], {})
                letters = ''.join(sorted(set(re.findall(r'[A-D]', m.group(2)))))
                book[no] = [letters, m.group(3).lstrip('。解析：:').strip()]
                state['last_answer'] = book[no]
            elif state['last_answer'] is not None and not SECTION.match(text):
                state['last_answer'][1] = (state['last_answer'][1]+' '+text).strip()
            continue
        q = state['q']
        given = EXPLICIT.match(text)
        if given and state['paper'] is not None:
            no = int(given.group(1)) if given.group(1) else None
            target = next((x for x in reversed(questions) if x['paper'] == state['paper'] and (no is None and x is q or x['no'] == no)), None)
            if target is not None:
                target['answer'] = ''.join(sorted(set(re.findall(r'[A-D]', given.group(2)))))
                target['analysis'] = given.group(3).lstrip('。解析：:').strip() or target['analysis']
                state['last_answer'] = None
                continue
        if re.match(r'^(?:解析[：:]|【解析】)', text) and q is not None:
            q['analysis'] = (q['analysis']+' '+text).strip()
            continue
        start = QUESTION.match(text)
        no = rest = None
        if start:
            no, rest = int(start.group(1)), start.group(2)
        elif state['last_no']:
            loose = LOOSE_START.match(text)
            if loose:
                no, rest = state['last_no']+1, loose.group(2)
        if no is not None:
            tagged = bool(TAG.match(rest))
            sequential = no == state['last_no']+1
            restart = no == 1 and state['last_no'] >= 3
            if sequential or restart or tagged:
                if state['paper'] is None:
                    new_paper(re.sub(r'\.pdf$', '', name, flags=re.I)[:60] or '冲刺刷题')
                elif restart:
                    new_paper(papers[state['paper']]['title']+'（续）')
                q = {'paper': state['paper'], 'no': no, 'stem': [re.sub(r'^[（(](小黑[^】）)]{0,12})[】）)]', r'【\1】', rest)], 'opts': [], 'answer': '', 'analysis': ''}
                questions.append(q)
                state.update(q=q, last_no=no)
                continue
        if q is None:
            continue
        if not q['opts'] and q['stem']:
            # OCR把陈述编号①②…认成数字（“1坚持…”“5坚持…”）：题干里已有圈数字陈述，或这是紧跟问句的“1”，就当陈述另起一行；编号稍后统一按顺序重排
            digit = re.match(r'^([1-9])(?=[\u4e00-\u9fff])(?![年月日个项%倍])', text)
            if digit and (any(l[:1] in CIRCLED for l in q['stem']) or (digit.group(1) == '1' and SENTENCE_END.search(q['stem'][-1]))):
                text = CIRCLED[int(digit.group(1))-1]+text[1:]
        if q['opts']:
            # 选项字母后面的“.”没认出来（“C绿色是…”）：正好接上下一个字母才算
            nodot = re.match(r'^([B-D])(?=[\u4e00-\u9fff“（(])', text)
            if nodot and q['opts'][-1][0] == chr(ord(nodot.group(1))-1):
                text = nodot.group(1)+'.'+text[1:]
        options = split_options(text, chr(ord(q['opts'][-1][0])+1) if q['opts'] else 'A')
        if options:
            q['opts'].extend(options)
            continue
        if SECTION.match(text) and q['opts']:
            finish()
            continue
        if q['opts']:
            letter, content = q['opts'][-1]
            q['opts'][-1] = (letter, _join(content, text))
        elif (STATEMENT.match(text) or (text[:1] in JUNK and any(l[:1] in CIRCLED for l in q['stem']))     # OCR把“③”认成“@”的陈述行也要另起一行
              or not q['stem'] or SENTENCE_END.search(q['stem'][-1])):
            q['stem'].append(text)
        else:
            q['stem'][-1] = _join(q['stem'][-1], text)
    out = []
    repaired = guessed_total = 0
    for q in questions:
        sure, guessed = repair_symbols(q['stem'], q['opts'])
        repaired += sure
        guessed_total += guessed
        letters = [letter for letter, _ in q['opts']]
        flags = ['符号推测'] if guessed else []
        if len(q['opts']) < 4:
            flags.append('选项不全')
        book = answers.get(q['paper'], {})
        if q['no'] in book:
            q['answer'], q['analysis'] = book[q['no']]
        lines = [fix_words(line) for line in q['stem'] if line] + [letter+'.'+fix_words(content) for letter, content in q['opts']]
        out.append({'paper': q['paper'], 'no': q['no'], 'text': '\n'.join(lines).strip(), 'answer': q['answer'],
                    'analysis': q['analysis'], 'flags': flags, 'letters': letters})
    out = [q for q in out if q['text'].strip()]
    report = {'papers': [{'title': p['title'], 'questions': sum(q['paper'] == i for q in out)} for i, p in enumerate(papers)],
              'incomplete': ['%s第%d题' % (papers[q['paper']]['title'][-12:], q['no']) for q in out if '选项不全' in q['flags']][:8],
              'incomplete_count': sum('选项不全' in q['flags'] for q in out), 'unanswered': sum(not q['answer'] for q in out),
              'repaired': repaired, 'guessed': guessed_total}
    return papers, out, report


# ---------------------------------------------------------------- 导入答案（套卷里原PDF没有答案时，另给一份答案文字/答案页PDF）
_KEY_ITEM = re.compile(r'(?<!\d)(\d{1,3})\s*[.．、:：)）]?\s*(?:【答案】|答案[：:]?)?\s*([A-Da-d]{1,4})(?![A-Za-z])')


def parse_key(text):
    """答案文字 → {题号: 'A' 或 'ABD'}。支持“1-20 BCDAB…”、每行“1.A 2.B”“3.【答案】AB”、答案页里“1.【答案】A。解析：…”。"""
    from . import importer
    text = str(text or '')
    if re.search(r'\d+\s*[-~—–至]\s*\d+', text):
        key = {k: v for k, v in importer.parse_key(text).items() if v in 'ABCD'}
        if key:
            return key
    key = {}
    for line in text.splitlines():
        line = re.sub(r'解析[：:].*$', '', line)           # 解析里的数字不当题号
        for m in _KEY_ITEM.finditer(line):
            key.setdefault(int(m.group(1)), ''.join(sorted(set(m.group(2).upper()))))
    if key:
        return key
    return {k: v for k, v in importer.parse_key(text).items() if v in 'ABCD'}


def _answer_sections(text, name=''):
    """保留套卷边界：标题或题号重新从1开始分组，重复/冲突题号不静默丢弃。"""
    from . import politics
    sections, current, title = [], {}, ''
    for line in str(text or '').splitlines():
        heading = paper_title(line.strip())
        if heading:
            if current:
                sections.append((title, current))
                current = {}
            title = heading[0]
            continue
        line = re.sub(r'解析[：:].*$', '', line)
        if re.search(r'\d+\s*[-~—–至]\s*\d+', line):
            pairs = sorted(parse_key(line).items())
        else:
            pairs = [(int(m.group(1)), ''.join(sorted(set(m.group(2).upper())))) for m in _KEY_ITEM.finditer(line)]
        for no, letters in pairs:
            if no == 1 and 1 in current:
                sections.append((title, current))
                current, title = {}, ''
            if no in current:
                raise politics.PoliticsError('同一套答案中题号%d重复，请检查后再导入' % no)
            current[no] = letters
    if current:
        sections.append((title, current))
    if not sections:
        key = parse_key(text)
        if key:
            sections.append(('', key))
    if len(sections) == 1 and not sections[0][0]:
        sections[0] = (str(name or ''), sections[0][1])
    return sections


def _answer_title(text):
    """优先按套卷编号匹配，其他标题只去扩展名、空白及答案标记。"""
    match = PAPER.search(text)
    if match:
        return re.sub(r'\s+', '', match.group())
    text = re.sub(r'\.(?:txt|pdf)$', '', text, flags=re.I)
    return re.sub(r'[\s·_—-]+|参考答案|答案及解析|答案与解析|答案|解析', '', text)


def apply_answers(pp, body):
    """单套/全部套卷批量补答案，先校验整批再原子保存；不动原PDF、学习记录或奖励。"""
    from . import politics
    exam = politics.exam_id(body.get('exam'))
    material = str(body.get('material') or '')
    batches = body.get('batches', [])
    if not isinstance(batches, list) or len(batches) > 100:
        raise politics.PoliticsError('答案文件最多一次100份')
    entries = ([body] if body.get('text') or body.get('pdf') else []) + batches
    sections = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise politics.PoliticsError('答案文件格式无效')
        text = str(entry.get('text') or '').strip()
        if not text and entry.get('pdf'):
            from . import exam_room
            try:
                text = exam_room._pdf_text(str(entry['pdf']))
            except exam_room.ExamError as error:
                raise politics.PoliticsError(str(error))
        if not text:
            raise politics.PoliticsError('请粘贴答案或选择答案文件，文件内容不能为空')
        parsed = _answer_sections(text, entry.get('name', ''))
        if not parsed:
            raise politics.PoliticsError('没认出答案：请写成“1-20 BCDAB…”或每行“1.A 2.B”的样子')
        sections.extend(parsed)
    if not sections:
        raise politics.PoliticsError('请粘贴答案或选择答案文件')
    with politics._LOCK:
        file = politics.exam_folder(pp, exam) / '补充.json'
        extra = politics.read_json(file, {'materials': [], 'questions': [], 'imports': []})
        papers = [m for m in extra['materials'] if m.get('practice_only')]
        assignments = []
        if material == 'all':
            used = set()
            for title, key in sections:
                matches = [m for m in papers if title and _answer_title(m['title']) == _answer_title(title)]
                if len(matches) == 1:
                    paper = matches[0]
                elif len(matches) > 1:
                    raise politics.PoliticsError('套卷标题不唯一，请分开选择套卷导入')
                else:
                    if title:
                        raise politics.PoliticsError('未找到与“%s”对应的套卷，请核对标题或单独选择套卷' % title)
                    # 没有明确标题时必须有完整的一套一组对应，不能悄悄写入第一套。
                    if len(sections) != len(papers):
                        raise politics.PoliticsError('答案分组数与套卷数不一致，请补上套卷标题或单独选择套卷')
                    paper = papers[len(assignments)]
                if paper['id'] in used:
                    raise politics.PoliticsError('同一套卷在本批答案中重复，请检查套卷标题')
                used.add(paper['id'])
                assignments.append((paper, key))
        else:
            paper = next((m for m in papers if m['id'] == material), None)
            if not paper:
                raise politics.PoliticsError('请先选择要补答案的套卷')
            if len(sections) > 1:
                raise politics.PoliticsError('识别到多套答案，请选择“全部套卷”后导入，避免同题号串卷')
            assignments = [(paper, sections[0][1])]
        results = []
        for paper, key in assignments:
            questions = [q for q in extra['questions'] if q.get('material') == paper['id'] and q.get('no') is not None]
            by_no = {int(q['no']): q for q in questions}
            if len(by_no) != len(questions):
                raise politics.PoliticsError('套卷题号重复，无法安全匹配答案')
            filled = changed = same = 0
            for no, letters in key.items():
                q = by_no.get(no)
                if not q:
                    continue
                if not q.get('answer'):
                    filled += 1
                elif q['answer'] != letters:
                    changed += 1
                else:
                    same += 1
                q['answer'] = letters
            results.append({'title': paper['title'], 'filled': filled, 'changed': changed, 'same': same, 'total': len(by_no),
                            'missing': sorted(n for n, q in by_no.items() if not q.get('answer')), 'unknown': sorted(n for n in key if n not in by_no)})
        if any(r['filled'] or r['changed'] for r in results):
            politics.atomic_json(file, extra)
        if len(results) == 1:
            return dict(results[0], papers=results)
        return dict(title='共%d套卷' % len(results), papers=results,
                    filled=sum(r['filled'] for r in results), changed=sum(r['changed'] for r in results),
                    same=sum(r['same'] for r in results), total=sum(r['total'] for r in results),
                    missing=['%s：%s' % (r['title'], '、'.join(map(str, r['missing']))) for r in results if r['missing']],
                    unknown=['%s：%s' % (r['title'], '、'.join(map(str, r['unknown']))) for r in results if r['unknown']])
