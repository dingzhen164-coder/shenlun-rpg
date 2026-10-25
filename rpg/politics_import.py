"""考试时政地图PDF增量导入，politics.register调用；不调用AI、不改旧材料与进度。

优先使用万象峰独立版式解析，普通文字PDF按明确资料标题切分并提取题目/答案；
不能明确归属的题目放在整份讲义配套练习，不猜测挂到某次会议。
原PDF按内容摘要存训练/时政知识地图/原文，新增数据仅原子写对应考试的补充.json。
"""
import base64
import hashlib
import re
import statistics
from functools import lru_cache
from pathlib import Path

from . import politics, political_outline, politics_exam, wanxiang_journal

Q = re.compile(r'^(\d+)[.．、]\s*(?:【[^】]+】)?(?:[（(](单选|多选|不定项)[)）])?(.*)')
OPTION = re.compile(r'^([A-D])[.．、)）]\s*(.*)')
ANSWER = re.compile(r'^(\d+)[.．、]\s*(?:【答案】|答案[：:])\s*([A-D、，, ]+)[。.]?(.*)')
GENRE = re.compile(r'会议|讲话|致辞|指示|批示|指导|文件|意见|通知|报告|决定|规划|纲要')


def genre(title, override=''):
    if override in politics.SOURCE_KINDS:
        return override
    if re.search(r'讲话|致辞|发言', title):
        return '讲话'
    if re.search(r'指示|批示|指导', title):
        return '指导'
    if re.search(r'会议|全会|大会|座谈会', title):
        return '重大会议'
    return '文件'


def _rows(doc):
    """保留真实标题、选项与段落边界；正文软换行跨页接续。"""
    rows, sizes = [], []
    for page in doc:
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                text = wanxiang_journal.clean(''.join(s['text'] for s in line['spans']))
                if not text or text in wanxiang_journal.NOISE or re.fullmatch(r'\d{1,3}', text):
                    continue
                size = max((s['size'] for s in line['spans']), default=11)
                rows.append((text, size, line['bbox'][0]))
                sizes.append(size)
    normal = statistics.median(sizes) if sizes else 11
    out = []
    for text, size, x in rows:
        is_head = bool(political_outline.heading(text)) or (size > normal * 1.12 and len(text) < 70)
        boundary = is_head or Q.match(text) or OPTION.match(text) or text.startswith(('【', '答案', '解析', '参考答案', '配套', '练习'))
        if out and not boundary and not out[-1]['head'] and not re.search(r'[。！？；：:]$', out[-1]['text']) and abs(x-out[-1]['x']) < 12:
            out[-1]['text'] += text
        else:
            out.append({'text': text, 'head': is_head, 'x': x})
    return out


def _known(path):
    data = wanxiang_journal.parse_pdf(path)
    units = []
    for i, n in enumerate(data['news']):
        if not n.get('paras'):
            continue
        title = n.get('heading') or n['title']
        units.append({'title': title, 'original': '\n\n'.join(n['paras']),
                      'event_key': n.get('group') or title,
                      'source_title': n.get('group') or title, 'refs': [i], 'cloze': [c for c in data.get('cloze', []) if c.get('news') == i]})
    questions = []
    for q in data['questions']:
        owner = next((i for i, u in enumerate(units) if q.get('news') in u['refs']), None)
        text = q['stem'] + '\n' + '\n'.join(q.get('stmts', [])) + '\n' + '\n'.join(k+'.'+v for k,v in sorted(q['opts'].items()))
        questions.append({'text': text.strip(), 'answer': q.get('answer', ''), 'analysis': q.get('analysis', ''), 'owner': owner})
    return units, questions


def _layout_text(doc, questions, rows=None):
    """按PDF真实行序恢复可确认的题面；匹配失败保留既有题文，不猜换行。

    与语义解析分开，保留同行选项、题干续行及跨页续行。只补layout_text，不改判分文本。
    """
    if rows is None:
        rows = _layout_rows(doc)
    norm = lambda s: re.sub(r'[\W_]+', '', s)
    for q in questions:
        expected = norm(q['text'])
        if not expected:
            continue
        for i, row in enumerate(rows):
            start = Q.match(wanxiang_journal.clean(row))
            if not start or not norm(start.group(3)) or not expected.startswith(norm(start.group(3))):
                continue
            parts = [row]
            got = norm(start.group(3))
            for following in rows[i+1:i+100]:
                if got == expected:
                    break
                got += norm(following)
                if not expected.startswith(got):
                    break
                parts.append(following)
            if got == expected:
                q['layout_text'] = '\n'.join(parts)
                break


def _layout_rows(doc):
    rows = []
    for page in doc:
        for block in page.get_text('dict', sort=True)['blocks']:
            for line in block.get('lines', []):
                text = ''.join(s['text'] for s in line['spans']).strip()
                if text and text not in wanxiang_journal.NOISE and not re.fullmatch(r'\d{1,3}', text):
                    rows.append(text)
    return rows


@lru_cache(maxsize=8)
def _saved_layout(file, stamp, size):
    import fitz
    with fitz.open(file) as doc:
        return _layout_rows(doc)


def restore_layout(pp, questions, imports):
    """旧导入只在返回数据中补原始行；不改题目ID、进度和补充.json，也不重导原文。"""
    missing = [q for q in questions if not q.get('layout_text')]
    for ident in imports:
        if not missing:
            break
        if not isinstance(ident, str) or not re.fullmatch(r'[0-9a-f]{64}', ident):
            continue
        file = pp.train/'时政知识地图/原文'/(ident+'.pdf')
        if file.is_symlink() or not file.is_file():
            continue
        try:
            stat = file.stat()
            rows = _saved_layout(str(file), stat.st_mtime_ns, stat.st_size)
            _layout_text(None, missing, rows=rows)
        except (ImportError, OSError, RuntimeError, ValueError):
            continue
        missing = [q for q in missing if not q.get('layout_text')]


def _generic(doc, name):
    rows = _rows(doc)
    units, questions, answers = [], [], {}
    current, q, answer_no = None, None, None
    for index, row in enumerate(rows):
        text = row['text']
        answer = ANSWER.match(text)
        if answer:
            answer_no = int(answer.group(1))
            answers[answer_no] = (''.join(sorted(set(re.findall(r'[A-D]', answer.group(2))))), answer.group(3).lstrip('。解析：:'))
            q = None
            continue
        if text.startswith(('【答案】', '答案：', '答案:')) and q:
            choice = re.search(r'[A-D](?:[A-D、，, ]*[A-D])?', text)
            if choice:
                q['answer'] = ''.join(sorted(set(re.findall(r'[A-D]', choice.group()))))
            continue
        if text.startswith(('解析：', '解析:', '【解析】')):
            if q:
                q['analysis'] = text
            elif answer_no in answers:
                a, old = answers[answer_no]
                answers[answer_no] = (a, old+text)
            continue
        start = Q.match(text)
        has_options = any(OPTION.match(r['text']) for r in rows[index+1:index+7])
        if start and (start.group(2) or '【小黑时政】' in text or has_options):
            q = {'no': int(start.group(1)), 'text': start.group(3), 'answer': '', 'analysis': '', 'owner': None}
            questions.append(q)
            continue
        if q:
            option = OPTION.match(text)
            if option:
                q['text'] += '\n' + option.group(1) + '.' + option.group(2)
                continue
            if not row['head'] and not text.startswith(('配套练习', '参考答案', '练习题')):
                q['text'] += '\n'+text
                continue
        if text.startswith(('配套练习', '参考答案', '练习题', '答案与解析')):
            q = None
            continue
        if row['head'] and GENRE.search(text):
            current = {'title': political_outline.heading(text) or text, 'original': '', 'source_title': text}
            units.append(current)
            q = None
        elif text and not questions:
            if current is None:
                current = {'title': Path(name).stem[:90] or '导入时政资料', 'original': '', 'source_title': Path(name).stem}
                units.append(current)
            current['original'] += ('\n\n' if current['original'] else '') + text
        elif current and not q:
            current['original'] += '\n\n' + text
    units = [u for u in units if u['original'].strip()]
    for q in questions:
        if q['no'] in answers:
            q['answer'], q['analysis'] = answers[q['no']]
        # 单份材料可直接关联；多份仅按题目明确提及的资料标题关联，不按题目相邻位置猜。
        matches = [i for i,u in enumerate(units) if len(u['title']) > 3 and u['title'] in q['text']]
        q['owner'] = 0 if len(units)==1 else matches[0] if len(matches)==1 else None
    return units, questions


def import_pdf(pp, body):
    exam = politics.exam_id(body.get('exam'))
    raw = str(body.get('data') or '').split(',', 1)[-1]
    if len(raw) > 56*1024*1024:
        raise politics.PoliticsError('PDF过大，请拆成40MB以内的文件后导入')
    try:
        content = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError):
        raise politics.PoliticsError('PDF数据无效')
    if len(content) > 40*1024*1024:
        raise politics.PoliticsError('PDF过大，请拆成40MB以内的文件后导入')
    if not content.startswith(b'%PDF'):
        raise politics.PoliticsError('请选择PDF文件')
    try:
        import pymupdf as fitz
    except ImportError:
        raise politics.PoliticsError('当前环境缺少PDF组件，请使用完整电脑安装包')
    file_hash = hashlib.sha256(content).hexdigest()
    directory = pp.train / '时政知识地图/原文'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (file_hash+'.pdf')
    if not path.exists():
        path.write_bytes(content)
    try:
        with fitz.open(str(path)) as doc:
            if doc.needs_pass:
                raise politics.PoliticsError('请先解密PDF后再导入')
            if not any(p.get_text().strip() for p in doc):
                raise politics.PoliticsError('这份PDF没有可提取文字，请先做文字识别（OCR）再导入')
            exam_report = None
            if body.get('mode') == 'practice':
                # 冲刺刷题：按套卷→题号→选项切分；识别不到题再退回通用解析。
                papers, parsed, exam_report = politics_exam.parse(doc, str(body.get('name') or '冲刺刷题.pdf'))
                if parsed:
                    units = [{'title': x['title'], 'original': '', 'practice_only': True} for x in papers]
                    questions = [{'text': q['text'], 'answer': q['answer'], 'analysis': q['analysis'], 'owner': q['paper'], 'no': q['no'],
                                  'paper': papers[q['paper']]['title']} for q in parsed]
                else:
                    exam_report = None
            if exam_report is None:
                try:
                    units, questions = _known(path)
                except wanxiang_journal.JournalError:
                    units, questions = _generic(doc, str(body.get('name') or '时政资料.pdf'))
            _layout_text(doc, questions)
    except (RuntimeError, ValueError) as error:
        if isinstance(error, politics.PoliticsError):
            raise
        raise politics.PoliticsError('PDF无法读取，请确认文件完整且未加密')
    if not units and questions and body.get('mode') == 'practice':
        units = [{'title': Path(str(body.get('name') or '冲刺刷题')).stem, 'original': '', 'practice_only': True}]
        for q in questions:
            q['owner'] = 0
    if not units:
        raise politics.PoliticsError('没有找到讲义正文，未加入地图；请导入包含正文的资料')
    if any(q['owner'] is None for q in questions):
        helper = len(units)
        units.append({'title': Path(str(body.get('name') or '导入讲义')).stem+' · 配套练习',
                      'original': '\n\n'.join(u['title']+'\n'+u['original'] for u in units),
                      'source_title': '', 'practice_only': True})
        for q in questions:
            if q['owner'] is None:
                q['owner'] = helper
    with politics._LOCK:
        data = politics.atlas(pp, exam)
        file = politics.exam_folder(pp, exam) / '补充.json'
        extra = politics.read_json(file, {'materials': [], 'questions': [], 'imports': []})
        if file_hash in extra.get('imports', []):
            return {'added': 0, 'questions': 0, 'duplicate': True, 'counts': politics.source_counts(data)}
        known = {politics.digest(re.sub(r'\s+', '', m['original'])): m for m in data['materials'] if not m.get('practice_only')}
        ids, added = {}, 0
        for i,u in enumerate(units):
            key = (politics.digest(['practice', file_hash, u['title']]) if u.get('practice_only')
                   else politics.digest(re.sub(r'\s+', '', u['original'])))
            if key in known:
                ids[i] = known[key]
                continue
            kind = '配套练习' if u.get('practice_only') else genre(u.get('source_title') or u['title'], body.get('kind'))
            chapter = politics.SOURCE_KINDS.index(kind) if kind in politics.SOURCE_KINDS else 3
            text = u['original']
            route = 'imported'
            m = {'id': 'pdf-'+key[:24], 'title': u['title'], 'original': text, 'originalEmphasis': [],
                 'date': next(iter(re.findall(r'\d{4}年\d{1,2}月(?:\d{1,2}日)?', text)), ''),
                 'chapter': chapter, 'kind': kind, 'event_key': u.get('event_key') or u['title'], 'tags': [route],
                 'why': '研读原文，理解政策表述', 'how': [], 'trap': '', 'questions': [],
                 'understanding': {'context': '这份材料来自你导入的PDF，可直接研读原文并选词解释批注。', 'actions': [], 'distinctions': [], 'recall': []},
                 'pdf': path.relative_to(pp.vault).as_posix(), 'practice_only': bool(u.get('practice_only')), 'cloze': u.get('cloze', [])}
            extra['materials'].append(m)
            known[key] = m
            ids[i] = m
            added += 1
        next_id = max((int(q['id']) for q in data['questions']), default=0)+1
        sign = lambda q: politics.digest([q['text'], q['answer']] + ([q['paper'], q['no']] if q.get('no') else []))
        seen = {sign(q) for q in data['questions']}
        added_q = 0
        for q in questions:
            signature = sign(q)
            if signature in seen:
                continue
            m = ids[q['owner']]
            # 同正文不重复建材料：题目关联用旁表补充，不改内置资料文件。
            stored = next((x for x in extra['materials'] if x['id'] == m['id']), None)
            links = stored['questions'] if stored else extra.setdefault('links', {}).setdefault(m['id'], [])
            extra['questions'].append({'id': next_id, 'material': m['id'], 'text': q['text'], 'answer': q['answer'], 'analysis': q.get('analysis', ''), 'tags': m['tags'],
                                       'layout_text': q.get('layout_text', ''), 'pdf': path.relative_to(pp.vault).as_posix(),
                                       **({'no': q['no'], 'paper': q['paper']} if q.get('no') else {})})
            links.append(next_id)
            next_id += 1
            added_q += 1
            seen.add(signature)
        extra.setdefault('imports', []).append(file_hash)
        politics.atomic_json(file, extra)
        combined = politics.atlas(pp, exam)
        return {'added': added, 'questions': added_q, 'duplicate': False, 'counts': politics.source_counts(combined),
                'unanswered': sum(not q['answer'] for q in questions), 'whole_document_questions': sum(units[q['owner']].get('practice_only', False) for q in questions),
                'exam': exam_report}
