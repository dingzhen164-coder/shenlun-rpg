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
OPTION = re.compile(r'(?<![A-Za-z])([A-D])[.．、)）]\s*')      # 行内选项之间的空格会被clean收掉（如“A.①③B.①②”），所以不要求前面有空格
STATEMENT = re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩（(]')
ANSWER_HEAD = re.compile(r'^(?:参考)?答案(?:与|及)?(?:解析)?[：:]?$|参考答案|答案与解析|答案及解析')
ANSWER = re.compile(r'^(\d{1,3})\s*[.．、:：]?\s*(?:【答案】|答案[：:]?)?\s*([A-D](?:[A-D、，, ]*[A-D])?)(?![A-Za-z])[。.]?\s*(.*)$')
EXPLICIT = re.compile(r'^(?:(\d{1,3})[.．、]\s*)?(?:【答案】|答案[：:])\s*([A-D](?:[A-D、，, ]*[A-D])?)[。.]?\s*(.*)$')     # 题后紧跟的“1.【答案】A。解析：…”
SENTENCE_END = re.compile(r'[。！？；：:]$')
SECTION = re.compile(r'^[一二三四五六七八九十]+[、．]')


def _rows(doc):
    """[(文字, 字号)]：整页按阅读顺序逐行，去掉页眉页脚与孤立页码。"""
    rows = []
    for page in doc:
        for block in page.get_text('dict', sort=True)['blocks']:
            for line in block.get('lines', []):
                text = wanxiang_journal.clean(''.join(s['text'] for s in line['spans']))
                if not text or text in wanxiang_journal.NOISE or re.fullmatch(r'\d{1,3}', text):
                    continue
                rows.append((text, max((s['size'] for s in line['spans']), default=11)))
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
        if not picked:
            if start != 0 or letter < expect:
                return []
        elif letter != chr(ord(picked[-1][2])+1):
            continue
        picked.append((start, end, letter))
    if not picked:
        return []
    out = []
    for i, (start, end, letter) in enumerate(picked):
        stop = picked[i+1][0] if i+1 < len(picked) else len(text)
        out.append((letter, text[end:stop].strip()))
    return out


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
        if start:
            no = int(start.group(1))
            tagged = bool(re.match(r'^(?:【[^】]+】|[（(](?:单选|多选|不定项)[)）])', start.group(2)))
            sequential = no == state['last_no']+1
            restart = no == 1 and state['last_no'] >= 3
            if sequential or restart or tagged:
                if state['paper'] is None:
                    new_paper(re.sub(r'\.pdf$', '', name, flags=re.I)[:60] or '冲刺刷题')
                elif restart:
                    new_paper(papers[state['paper']]['title']+'（续）')
                q = {'paper': state['paper'], 'no': no, 'stem': [start.group(2)], 'opts': [], 'answer': '', 'analysis': ''}
                questions.append(q)
                state.update(q=q, last_no=no)
                continue
        if q is None:
            continue
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
        elif STATEMENT.match(text) or not q['stem'] or SENTENCE_END.search(q['stem'][-1]):
            q['stem'].append(text)
        else:
            q['stem'][-1] = _join(q['stem'][-1], text)
    out = []
    for q in questions:
        letters = [letter for letter, _ in q['opts']]
        flags = []
        if len(q['opts']) < 4:
            flags.append('选项不全')
        book = answers.get(q['paper'], {})
        if q['no'] in book:
            q['answer'], q['analysis'] = book[q['no']]
        lines = [line for line in q['stem'] if line] + [letter+'.'+content for letter, content in q['opts']]
        out.append({'paper': q['paper'], 'no': q['no'], 'text': '\n'.join(lines).strip(), 'answer': q['answer'],
                    'analysis': q['analysis'], 'flags': flags, 'letters': letters})
    out = [q for q in out if q['text'].strip()]
    report = {'papers': [{'title': p['title'], 'questions': sum(q['paper'] == i for q in out)} for i, p in enumerate(papers)],
              'incomplete': ['%s第%d题' % (papers[q['paper']]['title'][-12:], q['no']) for q in out if '选项不全' in q['flags']][:8],
              'incomplete_count': sum('选项不全' in q['flags'] for q in out), 'unanswered': sum(not q['answer'] for q in out)}
    return papers, out, report
