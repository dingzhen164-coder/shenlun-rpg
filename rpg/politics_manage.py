"""万象峰“导入时政PDF”区的已导入文件管理：列出并批量删除。

数据落点：月半/专题期刊（训练/万象时政/<栏目>/<id>.json，原PDF在 万象时政/原文）；
冲刺学习/刷题资料（训练/时政知识地图[/考试/<考试>]/补充.json，原PDF按摘要在 时政知识地图/原文）；
消化清单（训练/时政消化/<资料摘要>.json 的 documents，原PDF在 时政消化/原文）。

删除只动程序自己保存的导入数据：先把将被改动或删除的文件整份复制到 训练/时政回收/<时间>/（保持原相对路径，要恢复就复制回去），
学习进度、批注、AI解释等单独保存的记录一律不动，重新导入同一份PDF后自动对上。
客户端只能传列表里出现过的编号，不能指定任何文件路径。
"""
import datetime as dt
import json
import re
import shutil
from pathlib import Path

from . import politics, politics_digest, wanxiang_journal as journal

HASH = re.compile(r'[0-9a-f]{64}')


def _stem(rel):
    stem = Path(str(rel or '')).stem
    return stem if HASH.fullmatch(stem) else ''


def _journals(g):
    root = journal.folder(g.paths)
    rows = []
    for kind, name in journal.KINDS.items():
        d = root / name
        for f in sorted(d.glob('*.json')) if d.is_dir() else []:
            data = politics.read_json(f, None)
            if not isinstance(data, dict):
                continue
            rows.append(dict(id='journal:%s:%s' % (kind, f.stem), channel=kind, label=data.get('title') or f.stem,
                             detail='%s条新闻 · %s道精卷题' % (len(data.get('news', [])), len(data.get('questions', []))),
                             kind=kind, iid=f.stem, file=f, pdf=data.get('pdf')))
    return rows


def _sprint(g):
    rows = []
    for exam in politics.EXAMS:
        file = politics.exam_folder(g.paths, exam['id']) / '补充.json'
        extra = politics.read_json(file, None)
        if not isinstance(extra, dict):
            continue
        groups = {}
        for m in extra.get('materials', []):
            stem = _stem(m.get('pdf'))
            if stem:
                groups.setdefault(stem, []).append(m)
        for stem, ms in groups.items():
            ids = {m['id'] for m in ms}
            questions = [q for q in extra.get('questions', []) if _stem(q.get('pdf')) == stem or q.get('material') in ids]
            study = [m for m in ms if not m.get('practice_only')]
            label = (study[0]['title'] + ('等%s份资料' % len(study) if len(study) > 1 else '')) if study else ms[0]['title']
            rows.append(dict(id='sprint:%s:%s' % (exam['id'], stem), channel='sprint', label=label,
                             detail='%s · %s份资料 · %s道题' % (exam['title'], len(study), len(questions)),
                             exam=exam['id'], stem=stem, file=file))
    return rows


def _digest(g):
    folder = g.paths.train / '时政消化'
    docs = {}
    for f in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        saved = politics.read_json(f, None)
        if not isinstance(saved, dict):
            continue
        for d in saved.get('documents', []):
            if not HASH.fullmatch(str(d.get('hash', ''))):
                continue
            row = docs.setdefault(d['hash'], dict(name=d.get('name') or '消化清单.pdf', blanks=0, targets=0, files=[]))
            row['blanks'] += sum(len(politics_digest.BLANK.findall(p.get('text', ''))) for p in d.get('paragraphs', []))
            row['targets'] += 1
            row['files'].append(f)
    return [dict(id='digest:' + h, channel='digest', label=r['name'], detail='%s空 · 分到%s份资料' % (r['blanks'], r['targets']),
                 hash=h, files=r['files']) for h, r in docs.items()]


TITLES = {'month': '月半时政', 'topic': '专题时政', 'sprint': '冲刺学习 / 冲刺刷题', 'digest': '消化清单'}


def _all(g):
    return _journals(g) + _sprint(g) + _digest(g)


def listing(g):
    items = _all(g)
    groups = []
    for channel, title in TITLES.items():
        rows = [dict(id=i['id'], label=i['label'], detail=i['detail']) for i in items if i['channel'] == channel]
        if rows:
            groups.append({'channel': channel, 'title': title, 'items': rows})
    return {'groups': groups, 'total': sum(len(x['items']) for x in groups)}


def _backup(g, stamp, *files):
    """把文件整份复制到 训练/时政回收/<时间>/ 下（保持相对路径）。"""
    base = g.paths.train / '时政回收' / stamp
    for f in files:
        f = Path(f)
        if f.is_file():
            dst = base / f.relative_to(g.paths.train)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(str(f), str(dst))
    return base


def _referenced(g, rel):
    """其他导入数据是否还引用这份原PDF（相对资料库的路径）。"""
    rel = str(rel)
    for exam in politics.EXAMS:
        text = (politics.exam_folder(g.paths, exam['id']) / '补充.json')
        if text.is_file() and rel in text.read_text(encoding='utf-8'):
            return True
    root = journal.folder(g.paths)
    for f in root.glob('*/*.json') if root.is_dir() else []:
        if rel in f.read_text(encoding='utf-8'):
            return True
    return False


def delete(g, ids):
    if not isinstance(ids, list) or not ids or len(ids) > 500:
        raise politics.PoliticsError('请先选择要删除的文件')
    items = {i['id']: i for i in _all(g)}
    picked = []
    for ident in ids:
        if not isinstance(ident, str) or ident not in items:
            raise politics.PoliticsError('所选文件已不存在，请刷新列表后重试')
        if ident not in [p['id'] for p in picked]:
            picked.append(items[ident])
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    base = g.paths.train / '时政回收' / stamp
    n = 1
    while base.exists():
        n += 1
        base = g.paths.train / '时政回收' / ('%s-%s' % (stamp, n))
    stamp = base.name
    with politics._LOCK:
        for item in picked:
            if item['channel'] in journal.KINDS:
                pdf = g.paths.vault / item['pdf'] if item.get('pdf') else None
                _backup(g, stamp, item['file'], *( [pdf] if pdf and journal.folder(g.paths) in pdf.resolve().parents else []))
                item['file'].unlink(missing_ok=True)
                if pdf and pdf.is_file() and journal.folder(g.paths) in pdf.resolve().parents and not _referenced(g, item['pdf']):
                    pdf.unlink()
            elif item['channel'] == 'sprint':
                _delete_sprint(g, stamp, item)
            else:
                _delete_digest(g, stamp, item)
    return {'deleted': len(picked), 'recycle': (g.paths.train / '时政回收' / stamp).relative_to(g.paths.vault).as_posix()}


def _delete_sprint(g, stamp, item):
    file = item['file']
    extra = politics.read_json(file, {})
    stem = item['stem']
    ids = {m['id'] for m in extra.get('materials', []) if _stem(m.get('pdf')) == stem}
    pdfs = {m['pdf'] for m in extra.get('materials', []) if _stem(m.get('pdf')) == stem}
    pdf_files = [g.paths.vault / p for p in pdfs]
    _backup(g, stamp, file, *pdf_files)
    extra['materials'] = [m for m in extra.get('materials', []) if m['id'] not in ids]
    extra['questions'] = [q for q in extra.get('questions', []) if _stem(q.get('pdf')) != stem and q.get('material') not in ids]
    extra['links'] = {k: v for k, v in extra.get('links', {}).items() if k not in ids}
    extra['imports'] = [h for h in extra.get('imports', []) if h != stem]
    kept = {q['id'] for q in extra['questions']}
    for m in extra['materials']:
        m['questions'] = [i for i in m.get('questions', []) if i in kept]
    politics.atomic_json(file, extra)
    for p in pdfs:
        if not _referenced(g, p) and (g.paths.vault / p).is_file():
            (g.paths.vault / p).unlink()


def _delete_digest(g, stamp, item):
    original = g.paths.train / '时政消化/原文' / (item['hash'] + '.pdf')
    _backup(g, stamp, original, *item['files'])
    for f in item['files']:
        saved = politics.read_json(f, {})
        saved['documents'] = [d for d in saved.get('documents', []) if d.get('hash') != item['hash']]
        if saved['documents']:
            politics.atomic_json(f, saved)
        else:
            f.unlink(missing_ok=True)
    original.unlink(missing_ok=True)
