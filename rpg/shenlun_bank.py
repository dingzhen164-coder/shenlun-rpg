"""完整申论真题的本地题库（标准库，shenlun/api调用）。
训练/题库/申论真题/<年份>-<地区>-<卷名>.md 保存可读可改真题（兼容导入的 <paper-id>.json）；_模板.md 为自建示例。
训练/作答/草稿/<qid>.json 保存答案、revision、累计有效编辑秒数；不混入真题。
导入幂等、不覆盖已有作答；题干/材料原文只读加载，用户在本地改 .md 后点“刷新本地题库”生效。
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import threading
import urllib.parse
import urllib.request
import unicodedata
from pathlib import Path, PurePosixPath
from contextlib import closing
from . import net


class BankError(Exception):
    pass

TYPES = ('归纳概括', '综合分析', '提出对策', '贯彻执行', '大作文')
GWY_COMMIT = '9ebfb7ca9ec8473391445bde3758945d8b3337a8'
GWY_RAW_BASE = 'https://raw.githubusercontent.com/ProfessorZhi/gwy-zhenti/' + GWY_COMMIT + '/'
GWY_MANIFEST_URL = GWY_RAW_BASE + 'catalog/manifest.jsonl'
SOURCE_COMMIT = '12cf8e73be8fd18f6157482e7a5748b0ca7f39ce2'
TEMPLATE_NAME = '_模板.md'
_CJK_RADICALS = str.maketrans('⺠⻄⻋⻓⻔⻩⻰⻥⻦⻨⻢⻘⻅⻉⾛⻝⻛⻠⻤⻫⻮⻯⻲', '民西车长门黄龙鱼鸟麦马青见贝走食风食鬼齐齿龙龟')
TEMPLATE_TEXT = """---
考试: 省考
地区: 四川
年份: 2026
卷型: 县乡卷
真题性质: 自整理真题
来源: 用户本地录入
试卷编号: custom-2026-sc-demo
---

<!-- 说明：
1. 以“_”开头的文件（如本 _模板.md）不会计入题库；复制本文件并改名为“2026-四川-示例卷.md”即可录入。
2. 材料内用空行或换行自然分段，阅读区会原样按段显示。
3. 修改或新增 .md 文件后，在档案室或实操中心点「刷新本地题库」立即生效。
-->

# 2026年四川省公务员录用考试《申论》示例卷

## 给定材料

### 材料 1

这里是第一则材料的第一自然段。材料段落按空行或换行原样保留，不再机械切句。

这里是第一则材料的第二自然段。

### 材料 2

这里是第二则材料的第一自然段。

## 题目

### 第 1 题

关联材料：材料 1

根据“给定资料1”，概括基层便民服务的主要做法。（20分）

作答要求：全面、准确、有条理，不超过250字。

<details>
<summary>展开答案与解析</summary>

**参考答案**

1. 走访摸排群众办事需求；2. 推动跨部门资料共享，减少重复提交。

**解析**

回到材料1逐段提炼核心动作，同类做法合并表述。

**考点**

归纳概括

</details>
"""
_JOB_LOCK = threading.Lock()
_IMPORT_LOCK = threading.RLock()
JOBS = {}
_CACHE = {}


def folder(p):
    return p.train / '题库' / '申论真题'


def ensure_template(p):
    if not p or not p.train:
        return None
    d = folder(p)
    d.mkdir(parents=True, exist_ok=True)
    f = d / TEMPLATE_NAME
    if not f.exists():
        with open(f, 'w', encoding='utf-8', newline='\n') as fp:
            fp.write(TEMPLATE_TEXT)
    return f


def _id(prefix, value):
    return prefix + hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:20]


def _safe(value):
    if not re.fullmatch(r'sl[pq]-[0-9a-f]{20}', str(value)):
        raise BankError('题目或试卷编号不正确')
    return value


def _write(f, d):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fp:
        fp.write(json.dumps(d, ensure_ascii=False, indent=2))
    os.replace(tmp, f)


def _clean_cjk(s):
    return str(s or '').translate(_CJK_RADICALS).replace('\xa0', ' ')


def text(value):
    s = str(value or '')
    s = re.sub(r'<(?:br\s*/?|/p|/div|/li)>', '\n', s, flags=re.I)
    return _clean_cjk(html.unescape(re.sub(r'<[^>]+>', '', s))).strip()


def infer_type(stem):
    if re.search(r'自拟题目|自拟标题|议论文|写.{0,12}(?:文章|作文)', stem):
        return '大作文'
    if re.search(r'报告|讲话|发言|提纲|倡议|通知|公开信|宣传稿|工作方案|建议书|简报|短评|编者按|推介|回信|复信|导言|讲解稿|发言稿|推介词|公开信', stem):
        return '贯彻执行'
    if re.search(r'建议|对策|措施|解决', stem):
        return '提出对策'
    if re.search(r'理解|分析|评价|评析|谈谈|看法|解释', stem):
        return '综合分析'
    return '归纳概括'


_KAODIAN_TYPES = (
    ('文章写作', '大作文'), ('申发论述', '大作文'), ('大作文', '大作文'),
    ('贯彻执行', '贯彻执行'), ('公文写作', '贯彻执行'), ('应用文', '贯彻执行'),
    ('提出对策', '提出对策'), ('解决问题', '提出对策'),
    ('综合分析', '综合分析'), ('词句理解', '综合分析'),
    ('归纳概括', '归纳概括'),
)
_DETAIL_HEAD_RE = re.compile(
    r'^(?:\*\*(参考答案[^*\n]*|答案|解析|题目解析|考点|来源)\*\*\s*(?:[:：]\s*(.*))?|#{4,6}\s*(参考答案[^\n]*|答案|解析|题目解析|考点|来源)\s*)$'
)


def _strip_md_inline(s):
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', str(s or ''))
    s = re.sub(r'\*\*([^*\n]+)\*\*', r'\1', s)
    lines = [ln.strip() for ln in _clean_cjk(s).splitlines()]
    out = []
    for ln in lines:
        if ln or (out and out[-1] != ''):
            out.append(ln)
    return '\n'.join(ln for ln in out if ln).strip()


def _parse_details(blocks, default_source):
    refs, analyses, kaodian = [], [], ''
    for raw in blocks:
        body = re.sub(r'<summary\b[^>]*>[\s\S]*?</summary>', '', raw, flags=re.I)
        body = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', body)
        kind, label, buf = 'answer', '参考答案', []

        def flush():
            nonlocal kaodian
            content = _strip_md_inline('\n'.join(buf))
            buf.clear()
            if not content:
                return
            if kind == 'answer':
                src = label if label and label not in ('答案', '参考答案') else (default_source or '来源库参考答案')
                refs.append({'source': src, 'answer': content})
            elif kind == 'analysis':
                analyses.append(content)
            elif kind == 'kaodian' and not kaodian:
                kaodian = content

        for ln in body.splitlines():
            m = _DETAIL_HEAD_RE.match(ln.strip())
            if m:
                flush()
                head = (m.group(1) or m.group(3) or '').strip()
                rest = (m.group(2) or '').strip()
                if head.startswith(('参考答案', '答案')):
                    kind, label = 'answer', head
                elif head in ('解析', '题目解析'):
                    kind, label = 'analysis', head
                elif head == '考点':
                    kind, label = 'kaodian', head
                else:
                    kind, label = 'source', head
                if rest:
                    buf.append(rest)
            else:
                buf.append(ln)
        flush()
    return refs, '\n\n'.join(analyses), kaodian


def _parse_score_words(full_text, explicit_score=None, explicit_words=None):
    if explicit_score is not None:
        score = float(explicit_score)
    else:
        sm = re.search(r'[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]', full_text)
        if not sm:
            sm = re.search(r'(?:本题|满分|分值|计|共)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*分(?![钟子])', full_text)
        if not sm:
            sm = re.search(r'(?<!\d)(\d{1,3}(?:\.\d+)?)\s*分(?![钟子])', full_text)
        score = float(sm.group(1)) if sm else 0.0
    if explicit_words is not None:
        words = int(explicit_words)
    else:
        rm = re.search(r'(\d{2,4})\s*(?:字)?\s*[-—～~至到]\s*(\d{2,4})\s*字', full_text)
        if rm:
            words = int(rm.group(2))
        else:
            wm = re.search(r'(?:不超过|不多于|最多|以内|限)\s*(\d{2,4})\s*字', full_text)
            if not wm:
                wm = re.search(r'(\d{2,4})\s*字\s*(?:以内|以下|左右)', full_text)
            if not wm and not re.search(r'(?:不少于|不低于|至少)\s*\d+\s*字', full_text):
                wm = re.search(r'(\d{2,4})\s*字', full_text)
            words = int(wm.group(1)) if wm else 0
    return score, (words if 0 < words <= 5000 else None)


def _split_h3(section_text):
    matches = list(re.finditer(r'(?m)^###\s+(.+?)\s*$', section_text))
    out = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section_text)
        out.append((m.group(1).strip(), section_text[m.end():end]))
    return out


def parse_markdown(md_text, filename=''):
    raw = str(md_text or '').lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    fm = {}
    if raw.startswith('---\n'):
        end_fm = raw.find('\n---\n', 4)
        if end_fm != -1:
            for ln in raw[4:end_fm].splitlines():
                if ':' in ln:
                    k, v = ln.split(':', 1)
                    fm[k.strip()] = v.strip().strip('\'"')
            raw = raw[end_fm + 5:]
    raw = re.sub(r'<!--[\s\S]*?-->', '', raw)
    hm = re.search(r'(?m)^#\s+(.+?)\s*$', raw)
    title = _clean_cjk(hm.group(1) if hm else (fm.get('标题') or Path(filename).stem)).strip()
    if not title:
        raise BankError('试卷缺少标题')
    raw_id = str(fm.get('id') or '').strip()
    src_pid = str(fm.get('源试卷ID') or '').strip()
    custom_no = str(fm.get('试卷编号') or '').strip()
    if re.fullmatch(r'slp-[0-9a-f]{20}', raw_id):
        pid = raw_id
    elif src_pid:
        pid = _id('slp-', 'gwy-paper-' + src_pid)
    elif custom_no:
        pid = _id('slp-', 'md-paper-' + custom_no)
    else:
        pid = _id('slp-', 'md-paper|' + (Path(filename).stem or title))
    year = str(fm.get('年份') or (re.search(r'(20\d{2}|19\d{2})', title + ' ' + filename) or [''])[0]).strip()
    area = str(fm.get('地区') or '').strip()
    exam = str(fm.get('考试') or '').strip()
    if area in ('全国', '国考') or exam == '国考':
        region = '国考'
    elif area:
        region = area[:-1] if len(area) > 2 and area.endswith(('省', '市')) else area
    else:
        m_fn = re.match(r'^\d{4}-([^-]+)-', Path(filename).name)
        region = m_fn.group(1) if m_fn else '其他'
    vol = str(fm.get('卷型') or '').strip()
    nature = str(fm.get('真题性质') or '').strip()
    edition = ' · '.join(x for x in (vol, nature) if x) or ('网友回忆版' if '回忆' in title else '公开真题整理版')
    src_label = str(fm.get('来源') or '').strip()
    source = ('ProfessorZhi/gwy-zhenti（%s）' % src_label if src_label else 'ProfessorZhi/gwy-zhenti') if src_pid else (src_label or '本地Markdown题库')
    source_url = 'https://github.com/ProfessorZhi/gwy-zhenti' if src_pid else ''

    h2s = list(re.finditer(r'(?m)^##\s+(.+?)\s*$', raw))
    sections = {}
    for idx, m in enumerate(h2s):
        end = h2s[idx + 1].start() if idx + 1 < len(h2s) else len(raw)
        sections[m.group(1).strip()] = raw[m.end():end]
    mat_sec = next((v for k, v in sections.items() if any(w in k for w in ('材料', '资料'))), '')
    q_sec = next((v for k, v in sections.items() if any(w in k for w in ('题目', '试题', '作答要求', '申论要求'))), '')

    mats = []
    h3_mats = _split_h3(mat_sec)
    if h3_mats:
        used_ids = set()
        for i, (m_head, m_body) in enumerate(h3_mats, 1):
            paras = [_clean_cjk(ln).strip() for ln in m_body.splitlines() if _clean_cjk(ln).strip()]
            if not paras:
                continue
            label = re.sub(r'\s+', '', _clean_cjk(m_head)) or ('材料%d' % i)
            nm = re.search(r'\d+', label)
            mid = nm.group(0) if nm and nm.group(0) not in used_ids else str(i)
            while mid in used_ids:
                mid = str(int(mid) + 1 if mid.isdigit() else i)
            used_ids.add(mid)
            mats.append({'id': mid, 'label': label, 'text': '\n'.join(paras)})
    elif mat_sec.strip():
        paras = [_clean_cjk(ln).strip() for ln in mat_sec.splitlines() if _clean_cjk(ln).strip()]
        if paras:
            mats.append({'id': '1', 'label': '给定材料', 'text': '\n'.join(paras)})

    qs = []
    h3_qs = _split_h3(q_sec)
    if not h3_qs and q_sec.strip():
        h3_qs = [('第 1 题', q_sec)]
    for i, (q_head, q_chunk) in enumerate(h3_qs, 1):
        det_blocks = re.findall(r'<details\b[^>]*>([\s\S]*?)</details>', q_chunk, flags=re.I)
        q_main = re.sub(r'<details\b[^>]*>[\s\S]*?</details>', '', q_chunk, flags=re.I)
        refs, analysis, kaodian = _parse_details(det_blocks, src_label or '来源库参考答案')
        assoc_line = ''
        exp_type = ''
        exp_score = exp_words = None
        body_lines = []
        for ln in q_main.splitlines():
            s = _clean_cjk(ln).strip()
            if not s:
                body_lines.append('')
                continue
            m_assoc = re.match(r'^(?:关联材料|对应材料|材料范围)\s*[:：]\s*(.+)$', s)
            if m_assoc and not any(body_lines):
                assoc_line = m_assoc.group(1).strip()
                continue
            m_type = re.match(r'^题型\s*[:：]\s*(.+)$', s)
            if m_type:
                exp_type = m_type.group(1).strip()
                continue
            m_sc = re.match(r'^(?:分值|满分)\s*[:：]\s*(\d+(?:\.\d+)?)\s*(?:分)?\s*$', s)
            if m_sc:
                exp_score = float(m_sc.group(1))
                continue
            m_wd = re.match(r'^(?:字数|字数上限|限字)\s*[:：]\s*(\d+)\s*(?:字)?\s*$', s)
            if m_wd:
                exp_words = int(m_wd.group(1))
                continue
            body_lines.append(s)
        req_idx = next((idx for idx, s in enumerate(body_lines) if re.match(r'^(?:作答)?要求\s*[:：]', s)), None)
        if req_idx is not None and any(body_lines[:req_idx]):
            stem = '\n'.join(x for x in body_lines[:req_idx] if x).strip()
            requirement = '\n'.join(x for x in body_lines[req_idx:] if x).strip()
        else:
            stem = '\n'.join(x for x in body_lines if x).strip()
            requirement = ''
        stem = _strip_md_inline(stem)
        requirement = _strip_md_inline(requirement)
        if not stem:
            raise BankError('第%d题缺少题干' % i)
        full_q = stem + ('\n' + requirement if requirement else '') + '\n' + _clean_cjk(q_head)
        score, words = _parse_score_words(full_q, exp_score, exp_words)
        if not 0 <= score <= 150:
            raise BankError('第%d题分值超出范围' % i)
        typ = exp_type if exp_type in TYPES else ''
        if not typ and kaodian:
            for kw, mapped in _KAODIAN_TYPES:
                if kw in kaodian:
                    typ = mapped
                    break
        inferred = infer_type(full_q)
        if not typ or (inferred == '大作文' and (words or 0) >= 700):
            typ = inferred
        mids = []
        if assoc_line and mats:
            mids = infer_material_ids('给定' + assoc_line, mats)
        qs.append({
            'qid': _id('slq-', pid + '|' + str(i)),
            'no': i,
            'type': typ,
            'stem': stem,
            'requirement': requirement,
            'total': score,
            'words': words,
            'material_ids': mids,
            'references': refs,
            'analysis': analysis,
        })
    if not qs:
        raise BankError('试卷至少需要一道题')
    return {
        'id': pid, 'title': title, 'year': year, 'region': region,
        'source': source, 'source_url': source_url, 'edition': edition,
        'materials': mats, 'questions': qs, 'schema': 1,
    }


def normalize(raw, origin='用户导入'):
    if not isinstance(raw, dict):
        raise BankError('每套试卷必须是一个对象')
    title = str(raw.get('title') or raw.get('name') or '').strip()
    if not title:
        raise BankError('试卷缺少标题')
    source = str(raw.get('sourceName') or raw.get('source') or origin)
    pid = _id('slp-', raw.get('source_id') or source + '|' + title)
    mats = []
    for i, m in enumerate(raw.get('materials') or []):
        if not isinstance(m, dict):
            raise BankError('材料格式不正确')
        body = text(m.get('text'))
        if body:
            mats.append({'id': str(m.get('id') or i+1), 'label': str(m.get('label') or '材料%d' % (i+1)), 'text': body})
    if len({m['id'] for m in mats})!=len(mats):
        raise BankError('材料编号重复')
    qs = []
    for i, q in enumerate(raw.get('questions') or []):
        if not isinstance(q, dict):
            raise BankError('题目格式不正确')
        stem = str(q.get('text') or q.get('stem') or '').strip()
        if not stem:
            raise BankError('第%d题缺少题干' % (i+1))
        try:
            score, words = float(q.get('score') or q.get('total') or 0), int(q.get('limit') or q.get('words') or 0)
        except (ValueError, TypeError):
            raise BankError('分值或字数必须是数字')
        if not 0 <= score <= 150 or not 0 <= words <= 5000:
            raise BankError('分值或字数超出范围')
        typ = q.get('type') or infer_type(stem)
        if typ not in TYPES:
            raise BankError('题型必须是五种申论题型之一')
        mids = [str(x) for x in q.get('material_ids') or []]
        if any(x not in [m['id'] for m in mats] for x in mids):
            raise BankError('题目引用了不存在的材料')
        refs = [{'source': str(x.get('organization') or x.get('source') or '用户参考资料'),
                 'answer': str(x.get('answer') or '').strip()} for x in q.get('references') or [] if isinstance(x, dict) and x.get('answer')]
        qs.append({'qid': _id('slq-', pid+'|'+str(q.get('source_id') or i+1)), 'no': i+1, 'type': typ,
                   'stem': stem, 'requirement': str(q.get('requirement') or ''), 'total': score, 'words': words or None,
                   'material_ids': mids, 'references': refs, 'analysis': str(q.get('analysis') or '')})
    if len({q['qid'] for q in qs})!=len(qs):
        raise BankError('题目编号重复')
    if not qs:
        raise BankError('试卷至少需要一道题')
    year = str(raw.get('year') or (re.search(r'(20\d{2}|19\d{2})', title) or [''])[0])
    return {'id':pid, 'title':title, 'year':year, 'region':str(raw.get('region') or raw.get('category') or '其他'),
            'source':source, 'source_url':str(raw.get('source_url') or ''), 'edition':str(raw.get('edition') or '来源未注明版本'),
            'materials':mats, 'questions':qs, 'schema':1}


def import_packages(p, raw):
    raws = raw if isinstance(raw, list) else [raw]
    if not raws or len(raws)>1000:
        raise BankError('一次导入1至1000套试卷')
    # 先全部校验，再写入；不因后面的坏题导致前面半途入库。
    papers = [normalize(x) for x in raws]
    added = skipped = 0
    with _IMPORT_LOCK:
        for paper in papers:
            f = folder(p)/(paper['id']+'.json')
            if f.exists():
                skipped += 1
                continue
            _write(f,paper); added += 1
    return {'added':added,'skipped':skipped,'questions':sum(len(x['questions']) for x in papers)}


def _scan_files(p):
    d = folder(p)
    if not d.exists():
        return [], []
    mds = sorted(f for f in d.glob('*.md') if not f.name.startswith('_') and not f.name.startswith('.'))
    jsons = sorted(f for f in d.glob('*.json') if not f.name.startswith('.'))
    return mds, jsons


def _load_all(p):
    mds, jsons = _scan_files(p)
    sig = tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in mds + jsons)
    out, seen, errors = [], set(), []
    for f in mds:
        try:
            d = parse_markdown(f.read_text(encoding='utf-8'), f.name)
            if d['id'] not in seen:
                seen.add(d['id'])
                out.append(d)
        except (OSError, ValueError, BankError) as e:
            errors.append('%s：%s' % (f.name, e))
    for f in jsons:
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
            if d.get('schema') == 1 and d.get('id') not in seen:
                seen.add(d['id'])
                out.append(d)
        except (OSError, ValueError) as e:
            errors.append('%s：%s' % (f.name, e))
    return sig, out, errors


def papers(p):
    mds, jsons = _scan_files(p)
    sig = tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in mds + jsons)
    key = str(folder(p))
    if key in _CACHE and _CACHE[key][0] == sig:
        return _CACHE[key][1]
    sig, out, _ = _load_all(p)
    if len(_CACHE) > 4:
        _CACHE.clear()
    _CACHE[key] = (sig, out)
    return out


def reload(p):
    with _IMPORT_LOCK:
        ensure_template(p)
        _CACHE.pop(str(folder(p)), None)
        _SUGGEST.clear()
        from . import shenlun_training
        shenlun_training._AUTO.pop(str(p.train), None)
        sig, out, errors = _load_all(p)
        _CACHE[str(folder(p))] = (sig, out)
        return {
            'papers': len(out),
            'questions': sum(len(x['questions']) for x in out),
            'errors': errors,
            'folder': str(folder(p)),
        }


def _listing_source(p, paper, q, picked):
    if len(paper['materials'])<2:
        return 'single'
    source=material_choice(p,paper,q,picked)[1]
    if source=='all' and suggest_materials(q['stem'],paper['materials'],q['qid'])[1]=='quote':
        return 'quote'
    return source


def listing(p):
    ensure_template(p)
    out=[]
    picked=_picked(p)
    for d in papers(p):
        out.append({k:d[k] for k in ('id','title','year','region','source','edition')})
        out[-1].update(count=len(d['questions']), materials=len(d['materials']), questions=[
            {'qid':q['qid'],'no':q['no'],'type':q['type'],'total':q['total'],'words':q['words'],
             'stem':q['stem'],'complete':bool(d['materials']) and q['total']>0,
             'material_source':_listing_source(p,d,q,picked)} for q in d['questions']])
    from . import shenlun_training
    shenlun_training.classify(p,papers(p),out)
    return sorted(out,key=lambda x:(x['year'],x['region'],x['title']),reverse=True)


def question(p,qid, reveal=False):
    _safe(qid)
    for paper in papers(p):
        for q in paper['questions']:
            if q['qid']==qid:
                d=dict(q, paper_id=paper['id'],paper_title=paper['title'],source=paper['source'],edition=paper['edition'])
                ids,source=material_choice(p,paper,q)
                d['material_ids'],d['material_source']=ids,source
                d['all_materials']=[{'id':m['id'],'label':m['label']} for m in paper['materials']]
                d['suggested_material_ids'],d['suggest_kind']=suggest_materials(q['stem'],paper['materials'],q['qid']) if source=='all' else ([],'')
                d['materials']=[dict(m,text=text(m['text'])) for m in paper['materials'] if not ids or m['id'] in ids]
                d['material_mark_keys']=[hashlib.sha256((str(m['id'])+'\n'+m['text']).encode('utf-8')).hexdigest() for m in d['materials']]
                d['complete']=bool(d['materials']) and d['total']>0
                if not reveal:
                    d.pop('references',None); d.pop('analysis',None)
                return d
    raise BankError('题目不存在')


_CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
_NUM = r'(?:\d{1,2}|[一二三四五六七八九十]{1,3})'
_REF = re.compile(r'(?:给定)?(?:资料|材料)\s*(' + _NUM + r'(?:\s*(?:[、，,和及与]|[～~—\-－至到]|(?:[～~—\-－至到]\s*)?(?:资料|材料))\s*' + _NUM + r')*)')


def _to_num(x):
    if x.isdigit():
        return int(x)
    if len(x)==1:
        return _CN_NUM.get(x)
    if x[0]=='十':
        return 10+_CN_NUM.get(x[1],0)
    if x[-1]=='十':
        return _CN_NUM.get(x[0],0)*10
    if len(x)==2 and x[0] in _CN_NUM and x[1]=='十':
        return _CN_NUM[x[0]]*10
    return _CN_NUM.get(x[0],0)*10+_CN_NUM.get(x[-1],0)


def _material_numbers(mats):
    """材料标签里带的序号；缺失或重复时退回出现顺序。"""
    nums=[]
    for i,m in enumerate(mats):
        found=re.search(r'(\d{1,2})|([一二三四五六七八九十]{1,3})',m['label'])
        nums.append(_to_num(found.group(0)) if found else i+1)
    return nums if len(set(nums))==len(nums) else list(range(1,len(mats)+1))


def infer_material_ids(stem, mats):
    """只认题干里明确写出的“给定资料X”“资料2、4”“资料1～3”；写不出来不猜，返回空表示沿用整卷。"""
    stem=re.sub(r'\[materialid\]\d+\[/materialid\]','',str(stem))
    if not mats or re.search(r'全部(?:给定)?(?:资料|材料)|所有(?:给定)?(?:资料|材料)|全部给定',stem):
        return []
    nums=_material_numbers(mats)
    wanted=set()
    for found in _REF.finditer(stem):
        span=found.group(1)
        parts=re.findall(_NUM+r'|[、，,和及与]|[～~—\-－至到]',span)
        last=None; ranged=False
        for part in parts:
            if re.fullmatch(r'[～~—\-－至到]',part):
                ranged=True; continue
            if part in '、，,和及与':
                ranged=False; continue
            n=_to_num(part)
            if n is None:
                continue
            if ranged and last and last<n:
                wanted.update(range(last,n+1))
            else:
                wanted.add(n)
            last=n; ranged=False
    ids=[m['id'] for m,n in zip(mats,nums) if n in wanted]
    return ids if ids and len(ids)<len(mats) else []


_TAG = re.compile(r'\[materialid\]\d+\[/materialid\]')


def mentions_specific(stem):
    """题干是否指明了具体材料（编号或标签）。没有的话“给定资料”就是整套，显示全卷是对的。"""
    return bool(_TAG.search(stem) or re.search(r'(?:资料|材料)\s*(?:\d{1,2}|[一二三四五六七八九十]{1,3})(?![\d年月日%％])',stem))


_QUOTE = re.compile(r'[“"「『]([^”"」』]{6,200})[”"」』]')
_SQUASH = re.compile(r'[\s，。、；：！？,.;:!?“”‘’"\'（）()\[\]《》…—\-]')


def _squash(value):
    return _SQUASH.sub('', unicodedata.normalize('NFKC', str(value or '')))


_SUGGEST = {}


def suggest_materials(stem, mats, key=None):
    """题干没写明材料时给出推测，只用于界面提示，不改变批改用的材料。
    先看题干引号里的原文片段（逐字出现在某则材料里最可靠），再按用词重合度。返回 (材料id列表, 'quote'|'overlap'|'')。"""
    if key and key in _SUGGEST:
        return _SUGGEST[key]
    out=_suggest(stem,mats)
    if key:
        if len(_SUGGEST)>20000:
            _SUGGEST.clear()
        _SUGGEST[key]=out
    return out


def _suggest(stem, mats):
    stem=re.sub(r'\[materialid\]\d+\[/materialid\]','',str(stem))
    if len(mats)<2:
        return [],''
    body=[(m['id'],_squash(text(m['text']))) for m in mats]
    hit=[]
    for q in _QUOTE.findall(stem):
        key=_squash(q)
        if len(key)<6:
            continue
        found=[i for i,t in body if key in t]
        if len(found)==1 and found[0] not in hit:
            hit.append(found[0])
    if hit:
        return [i for i,_ in body if i in hit],'quote'
    stem=re.sub(r'[请根据概括分析提出要求不超过字全面准确有条理分]|给定资料|材料','',stem)
    grams={stem[i:i+2] for i in range(len(stem)-1) if not re.search(r'[\s，。、；：“”（）()\d]',stem[i:i+2])}
    if len(grams)<3:
        return [],''
    scores=[(sum(1 for g in grams if g in text(m['text'])),m['id']) for m in mats]
    best=max(scores)[0]
    ids=[i for n,i in scores if best>=3 and n>=best*0.6]
    return (ids,'overlap') if ids and len(ids)<len(mats) else ([],'')


def _pick_file(p,qid):
    return p.reviews/'材料选择'/(_safe(qid)+'.json')


def _picked(p):
    d=p.reviews/'材料选择'
    return {f.stem for f in d.glob('*.json')} if d.exists() else set()


def material_choice(p, paper, q, picked=None):
    """(材料id列表, 来源)。来源：manual 用户选定 / import 题目自带 / stem 题干写明 / all 整卷未确认。"""
    known={m['id'] for m in paper['materials']}
    f=_pick_file(p,q['qid'])
    if (picked is None or q['qid'] in picked) and f.exists():
        try:
            ids=[x for x in json.loads(f.read_text(encoding='utf-8')).get('ids',[]) if x in known]
            if ids:
                return ids,'manual'
        except (OSError,ValueError):
            pass
    if q['material_ids']:
        return q['material_ids'],'import'
    ids=infer_material_ids(q['stem'],paper['materials'])
    if ids:
        return ids,'stem'
    return ([],'all') if mentions_specific(q['stem']) else ([],'whole')


def material_pick(p, body):
    qid=body.get('qid'); q=question(p,qid)
    known={m['id'] for m in q['all_materials']}
    ids=[str(x) for x in body.get('ids') or []]
    if any(x not in known for x in ids):
        raise BankError('材料不存在')
    with _IMPORT_LOCK:
        f=_pick_file(p,qid)
        if ids and len(ids)<len(known):
            _write(f,{'qid':qid,'ids':ids})
        elif f.exists():
            f.unlink()
    return question(p,qid)


def material_auto(p, paper_id):
    """把整套卷里“题干引用的原文逐字出现在某则材料”的题批量定为对应材料；已手动选定的不动。"""
    paper=next((x for x in papers(p) if x['id']==paper_id),None)
    if paper is None:
        raise BankError('试卷不存在')
    picked=_picked(p); done=0
    with _IMPORT_LOCK:
        for q in paper['questions']:
            if q['qid'] in picked or material_choice(p,paper,q,picked)[1]!='all':
                continue
            ids,kind=suggest_materials(q['stem'],paper['materials'],q['qid'])
            if kind=='quote' and ids:
                _write(_pick_file(p,q['qid']),{'qid':q['qid'],'ids':ids,'auto':'quote'}); done+=1
    return {'done':done}


def answer_file(p,qid):
    return p.reviews / '草稿' / (_safe(qid)+'.json')


def answer_get(p,qid):
    f=answer_file(p,qid)
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'qid':qid,'text':'','revision':0,'seconds':0}


def answer_save(p,body):
    # revision检查和原子替换作为一个临界区，两个标签页不能同时写入旧版本。
    with _IMPORT_LOCK:
        return _answer_save(p,body)


def _answer_save(p,body):
    qid=body.get('qid'); question(p,qid)
    old=answer_get(p,qid)
    if type(body.get('revision')) is not int or body.get('revision')!=old['revision']:
        raise BankError('答案已在另一处更新，请保留当前文字，再重新打开题目')
    value=str(body.get('text') or '')
    if len(value)>30000: raise BankError('答案太长')
    from . import shenlun_handwriting as hw, shenlun_materials as marks
    annotations=marks.validate(body['material_marks']) if 'material_marks' in body else old.get('material_marks',{})
    c=hw.card(body['card']) if 'card' in body else old.get('card',hw.card(None))
    confirmed=old.get('confirmed_card_hash','') if c==old.get('card',hw.card(None)) else ''
    if body.get('confirm_handwriting'):confirmed=hw.digest(c)
    d=dict(old,qid=qid,text=value,revision=old['revision']+1,seconds=old['seconds'],
           material_marks=annotations,card=c,confirmed_card_hash=confirmed,updated=dt.datetime.now().isoformat(timespec='seconds'))
    _write(answer_file(p,qid),d)
    return d


def import_sqlite(p, dbfile, matfile):
    added=skipped=questions=0
    with closing(sqlite3.connect(Path(dbfile).resolve().as_uri()+'?mode=ro',uri=True)) as db, closing(sqlite3.connect(Path(matfile).resolve().as_uri()+'?mode=ro',uri=True)) as md:
        db.row_factory=md.row_factory=sqlite3.Row
        for row in db.execute("SELECT * FROM papers WHERE subjectName IN ('公务员·申论','申论') ORDER BY id"):
            r=dict(row)
            mats=[{'id':str(m['idx']),'label':m['title'] or '材料%s'%m['idx'],'text':unicodedata.normalize('NFKC',text(m['text'])).translate(str.maketrans('⺠⻄⻋⻓⻔⻩⻰⻥⻦⻨⻢⻘⻅⻉','民西车长门黄龙鱼鸟麦马青见贝'))} for m in md.execute('SELECT * FROM materials WHERE paperId=? ORDER BY idx',(r['id'],))]
            qs=[]
            for qrow in db.execute('SELECT * FROM questions WHERE paperId=? ORDER BY id',(r['id'],)):
                q=dict(qrow); stem=text(q['content'] or q.get('contentHtml'))
                if not stem: continue
                sm=re.search(r'[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]',stem)
                if not sm: sm=re.search(r'(?:本题|满分|分值|计)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*分',stem)
                if not sm: sm=re.search(r'(\d+(?:\.\d+)?)\s*分',stem)
                wm=re.search(r'(?:不超过|不多于|最多|以内|限)\s*(\d+)\s*字',stem)
                if not wm: wm=re.search(r'(?:\d+\s*[-—～~至到]\s*)?(\d+)\s*字',stem)
                if re.search(r'不少于\s*\d+\s*字',stem) and not re.search(r'不超过|不多于|最多|[-—～~至到]',stem): wm=None
                refs=[{'source':'来源库参考资料（非官方细则）','answer':text(q.get('answer'))}] if q.get('answer') else []
                qs.append({'source_id':'errrc-question-'+str(q['questionId']),'text':stem,'score':float(sm.group(1)) if sm else 0,
                           'limit':int(wm.group(1)) if wm else 0,'references':refs,'analysis':text(q.get('analysis'))})
            if not qs: continue
            data={'source_id':'errrc-paper-'+str(r['id']),'title':r['name'],'region':r['category'],'materials':mats,'questions':qs,
                  'sourceName':'ERRRC/kaogong-shuati','source_url':'https://github.com/ERRRC/kaogong-shuati',
                  'edition':'网友回忆版' if '回忆' in r['name'] else '来源库真题（未核验官方原卷）'}
            result=import_packages(p,data); added+=result['added'];skipped+=result['skipped'];questions+=result['questions']
    return {'added':added,'skipped':skipped,'questions':questions}


def _digest(f):
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def source_status(p):
    with _JOB_LOCK:
        return dict(JOBS.get(str(p.train), {'running': False, 'message': '尚未下载', 'progress': 0}))


_EDITION_TAGS = ('行政执法', '副省', '地市', '市地', '乡镇', '县乡', '县级', '市级', '省级', 'A卷', 'B卷', 'C卷', '甲卷', '乙卷', '丙卷', '公安')


def _norm_paper_title(s):
    s = unicodedata.normalize('NFKC', str(s or ''))
    s = re.sub(r'网友回忆版|回忆版|公务员录用考试|公务员考试|申论|试卷|真题', '', s)
    return re.sub(r'[\s《》（）()\[\]【】·—\-_:：,，。]', '', s).lower()


def _has_question_work(p, qid):
    from . import shenlun_handwriting as hw
    af = answer_file(p, qid)
    if af.exists():
        try:
            d = json.loads(af.read_text(encoding='utf-8'))
            if str(d.get('text') or '').strip() or hw.has_ink(d.get('card') or {'pages': []}) or d.get('material_marks'):
                return True
        except (OSError, ValueError):
            return True
    gd = p.reviews / '综合' / qid
    return gd.is_dir() and any(gd.iterdir())


def _match_errrc_paper(old_p, candidates):
    ot = _norm_paper_title(old_p.get('title'))
    oy = str(old_p.get('year') or '')
    oreg = str(old_p.get('region') or '')
    otags = {t for t in _EDITION_TAGS if t in str(old_p.get('title') or '')}
    om_sq = _squash(old_p['materials'][0]['text'])[:90] if old_p.get('materials') else ''
    best_score, best_np = 0, None
    for np in candidates:
        ny = str(np.get('year') or '')
        if oy and ny and oy != ny:
            continue
        nt = _norm_paper_title(np.get('title') + ' ' + np.get('edition', ''))
        nt_main = _norm_paper_title(np.get('title'))
        score = 0
        if ot and (ot == nt_main or ot == nt):
            score += 100
        elif ot and nt_main and (ot in nt or nt_main in ot):
            score += 60
        nreg = str(np.get('region') or '')
        if oreg and nreg and (oreg == nreg or oreg in nreg or nreg in oreg):
            score += 30
        ntags = {t for t in _EDITION_TAGS if t in (str(np.get('title') or '') + str(np.get('edition') or ''))}
        if otags and ntags:
            if otags & ntags:
                score += 40
            else:
                score -= 80
        if len(om_sq) >= 24:
            probe = om_sq[:60]
            if any(probe in _squash(m['text']) for m in np.get('materials', [])):
                score += 90
        if score > best_score:
            best_score, best_np = score, np
    return best_np if best_score >= 70 else None


def _migrate_question_files(p, old_qid, new_qid, valid_mat_ids):
    from . import shenlun_handwriting as hw
    if old_qid == new_qid:
        return
    of, nf = answer_file(p, old_qid), answer_file(p, new_qid)
    if of.exists():
        try:
            od = json.loads(of.read_text(encoding='utf-8'))
            od_work = bool(str(od.get('text') or '').strip() or hw.has_ink(od.get('card') or {'pages': []}) or od.get('material_marks') or od.get('seconds', 0) > 0)
            nf_work = False
            if nf.exists():
                nd = json.loads(nf.read_text(encoding='utf-8'))
                nf_work = bool(str(nd.get('text') or '').strip() or hw.has_ink(nd.get('card') or {'pages': []}) or nd.get('material_marks'))
            if od_work and not nf_work:
                od['qid'] = new_qid
                _write(nf, od)
                of.unlink()
            elif not od_work:
                of.unlink()
        except (OSError, ValueError):
            pass
    op, npf = _pick_file(p, old_qid), _pick_file(p, new_qid)
    if op.exists():
        try:
            if not npf.exists():
                ids = [x for x in json.loads(op.read_text(encoding='utf-8')).get('ids', []) if x in valid_mat_ids]
                if ids and len(ids) < len(valid_mat_ids):
                    _write(npf, {'qid': new_qid, 'ids': ids})
            op.unlink()
        except (OSError, ValueError):
            pass
    odir, ndir = p.reviews / '综合' / old_qid, p.reviews / '综合' / new_qid
    if odir.is_dir():
        ndir.mkdir(parents=True, exist_ok=True)
        for item in sorted(odir.iterdir()):
            dst = ndir / item.name
            if dst.exists():
                continue
            if item.suffix == '.json':
                try:
                    jd = json.loads(item.read_text(encoding='utf-8'))
                    if isinstance(jd.get('result'), dict) and jd['result'].get('review_file'):
                        jd['result']['review_file'] = jd['result']['review_file'].replace('/' + old_qid + '/', '/' + new_qid + '/')
                    _write(dst, jd)
                    item.unlink()
                    continue
                except (OSError, ValueError):
                    pass
            os.replace(item, dst)
        try:
            if not any(odir.iterdir()):
                odir.rmdir()
        except OSError:
            pass
    for sub in ('立意', '提纲'):
        oe = p.train / '大作文' / sub / (old_qid + '.json')
        ne = p.train / '大作文' / sub / (new_qid + '.json')
        if oe.exists() and not ne.exists():
            try:
                ed = json.loads(oe.read_text(encoding='utf-8'))
                ed['qid'] = new_qid
                _write(ne, ed)
                oe.unlink()
            except (OSError, ValueError):
                pass


def _migrate_errrc(p, md_papers):
    """把旧 ERRRC/kaogong-shuati 题库上的草稿/批改/领取/主题迁移到对应 .md 试卷，并清理未作答的旧 JSON 与原始 SQLite。"""
    d = folder(p)
    if not d.exists():
        return {'migrated_questions': 0, 'removed_papers': 0}
    qid_map, pid_map = {}, {}
    removed_papers = 0
    with _IMPORT_LOCK:
        for jf in sorted(d.glob('*.json')):
            try:
                old_p = json.loads(jf.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if old_p.get('source') != 'ERRRC/kaogong-shuati':
                continue
            np = _match_errrc_paper(old_p, md_papers) if md_papers else None
            if np:
                pid_map[old_p['id']] = np['id']
                valid_mids = {m['id'] for m in np.get('materials', [])}
                used_nq = set()
                old_qs = old_p.get('questions', [])
                new_qs = np.get('questions', [])
                for oq in old_qs:
                    osq = _squash(oq.get('stem', ''))
                    ograms = {osq[i:i + 2] for i in range(max(0, len(osq) - 1))}
                    best_q, best_sc = None, 0.0
                    for nq in new_qs:
                        if nq['qid'] in used_nq:
                            continue
                        nsq = _squash(nq.get('stem', '') + nq.get('requirement', ''))
                        ngrams = {nsq[i:i + 2] for i in range(max(0, len(nsq) - 1))}
                        overlap = len(ograms & ngrams) / max(1, min(len(ograms), len(ngrams))) if ograms and ngrams else 0.0
                        sc = overlap + (0.25 if oq.get('no') == nq.get('no') else 0.0) + (0.1 if oq.get('type') == nq.get('type') else 0.0)
                        if sc > best_sc:
                            best_sc, best_q = sc, nq
                    if best_q and (best_sc >= 0.25 or len(old_qs) == len(new_qs)):
                        used_nq.add(best_q['qid'])
                        qid_map[oq['qid']] = best_q['qid']
                        _migrate_question_files(p, oq['qid'], best_q['qid'], valid_mids)
            if not any(_has_question_work(p, oq['qid']) for oq in old_p.get('questions', [])):
                try:
                    jf.unlink()
                    removed_papers += 1
                except OSError:
                    pass
        if qid_map:
            from . import shenlun_claims
            cf = shenlun_claims.path(p)
            if cf.exists():
                try:
                    cd = json.loads(cf.read_text(encoding='utf-8'))
                    if isinstance(cd.get('qids'), list):
                        cd['qids'] = list(dict.fromkeys(qid_map.get(x, x) for x in cd['qids']))
                    if isinstance(cd.get('removed'), list):
                        cd['removed'] = list(dict.fromkeys(qid_map.get(x, x) for x in cd['removed']))
                    _write(cf, cd)
                except (OSError, ValueError):
                    pass
        if qid_map or pid_map:
            from . import shenlun_training
            tf = shenlun_training.path(p)
            if tf.exists():
                try:
                    td = json.loads(tf.read_text(encoding='utf-8'))
                    labels = td.get('labels')
                    if isinstance(labels, dict):
                        changed = False
                        for ok, nk in list(pid_map.items()) + list(qid_map.items()):
                            if ok in labels:
                                val = labels.pop(ok)
                                if nk not in labels:
                                    labels[nk] = val
                                changed = True
                        if changed:
                            td['revision'] = int(td.get('revision') or 0) + 1
                            _write(tf, td)
                except (OSError, ValueError):
                    pass
        raw_dir = p.train / '题库原始库'
        if raw_dir.exists():
            shutil.rmtree(raw_dir, ignore_errors=True)
    return {'migrated_questions': len(qid_map), 'removed_papers': removed_papers}


def _safe_md_filename(entry):
    rel = str(entry.get('path') or '')
    pp = PurePosixPath(rel)
    if not rel or rel.startswith('/') or '..' in pp.parts or pp.suffix.lower() != '.md':
        raise BankError('题库目录项路径不安全')
    year = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', str(entry.get('year') or '0000')) or '0000'
    area = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', str(entry.get('area') or '其他')) or '其他'
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', pp.stem).strip(' ._')
    if not stem:
        raise BankError('题库目录项缺少文件名')
    name = '%s-%s-%s.md' % (year, area, stem)
    return name.lstrip('_')


def _fetch_bytes(url, max_bytes, timeout=45):
    req = urllib.request.Request(url, headers={'User-Agent': 'shenlun-rpg'})
    chunks, total = [], 0
    with net.urlopen(req, timeout=timeout) as resp:
        while True:
            buf = resp.read(256 * 1024)
            if not buf:
                break
            total += len(buf)
            if total > max_bytes:
                raise BankError('题库文件长度超出上限')
            chunks.append(buf)
    return b''.join(chunks)


def source_start(p):
    key = str(p.train)
    with _JOB_LOCK:
        if JOBS.get(key, {}).get('running'):
            return dict(JOBS[key])
        JOBS[key] = {'running': True, 'message': '正在读取公开申论题库目录（约33MB）', 'progress': 0}

    def update(**data):
        with _JOB_LOCK:
            JOBS[key].update(data)

    def run():
        try:
            ensure_template(p)
            dest = folder(p)
            dest.mkdir(parents=True, exist_ok=True)
            raw_manifest = _fetch_bytes(GWY_MANIFEST_URL, 16 * 1024 * 1024, timeout=45).decode('utf-8')
            entries = []
            for ln in raw_manifest.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                item = json.loads(ln)
                if item.get('subject') == '申论' and str(item.get('path') or '').endswith('.md'):
                    size = int(item.get('bytes') or 0)
                    sha = str(item.get('sha256') or '').lower()
                    if size <= 0 or size > 4 * 1024 * 1024 or not re.fullmatch(r'[0-9a-f]{64}', sha):
                        raise BankError('题库目录校验信息异常')
                    entries.append((item, _safe_md_filename(item), size, sha))
            if not entries:
                raise BankError('题库目录中没有找到申论试卷')
            total_bytes = sum(x[2] for x in entries)
            done_bytes = 0
            added = skipped = 0
            todo = []
            for item, fname, size, sha in entries:
                target = dest / fname
                if target.exists() and target.stat().st_size == size and _digest(target) == sha:
                    done_bytes += size
                    skipped += 1
                else:
                    todo.append((item, fname, size, sha))
            update(message='准备下载 %d 套申论真题（已有 %d 套保留）' % (len(todo), skipped),
                   progress=round(done_bytes / max(1, total_bytes) * 90))

            def download_one(task):
                item, fname, size, sha = task
                url = GWY_RAW_BASE + urllib.parse.quote(item['path'], safe='/')
                data = _fetch_bytes(url, size, timeout=45)
                if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
                    raise BankError('%s 校验失败，请重试' % fname)
                tmp = dest / ('.' + fname + '.download')
                try:
                    tmp.write_bytes(data)
                    os.replace(tmp, dest / fname)
                finally:
                    if tmp.exists():
                        try:
                            tmp.unlink()
                        except OSError:
                            pass
                return size

            if todo:
                done_count = 0
                with ThreadPoolExecutor(max_workers=8) as pool:
                    futures = [pool.submit(download_one, t) for t in todo]
                    for fut in as_completed(futures):
                        sz = fut.result()
                        done_bytes += sz
                        done_count += 1
                        added += 1
                        if done_count % 10 == 0 or done_count == len(todo):
                            update(
                                message='正在下载申论真题（%d/%d 套）' % (done_count, len(todo)),
                                progress=round(done_bytes / max(1, total_bytes) * 92),
                            )
            update(message='正在整理题库并保留已有作答', progress=96)
            info = reload(p)
            md_papers = [d for d in papers(p) if str(d.get('source') or '').startswith('ProfessorZhi/gwy-zhenti')]
            mig = _migrate_errrc(p, md_papers)
            info = reload(p)
            result = {
                'added': added,
                'skipped': skipped,
                'papers': info['papers'],
                'questions': info['questions'],
                'migrated_questions': mig['migrated_questions'],
                'removed_legacy': mig['removed_papers'],
            }
            update(
                running=False,
                message='录入完成：新增%d套，已有%d套保留（共%d套·%d题，保存于 训练/题库/申论真题/）' % (
                    added, skipped, info['papers'], info['questions']
                ),
                progress=100,
                result=result,
            )
        except Exception as e:
            update(running=False, message='录入未完成：' + str(e), error=True)

    threading.Thread(target=run, daemon=True).start()
    return source_status(p)

