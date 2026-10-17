"""可配置任务板：API返回每日/每周主线及支线纸签，学习证据沿用原存档。
规则.md保存任务板.每日内容/每周内容/支线.<稳定ID>.{内容,板块,分钟}；
每日时长复用每日目标分钟，每周次数复用周常.宗门大比。无新奖励/新成绩。
支线补记调用原add_selfstudy，记录附task_board_id/op；幂等重试不重复记时。
配置用规则文件摘要防覆盖，原子替换；不改原journey/collection与存档版本。
"""
import datetime as dt
import hashlib
import math
import os
import re
import tempfile

from . import config, mdconf

def _rules(g, text):
    return config.Rules(text, g.subject) if hasattr(config, 'canon_key') else config.Rules(text)


def _boards(g):
    return list(g.all_boards()) if hasattr(g, 'all_boards') else list(dict.fromkeys(list(g.boards)+list(g.rules.side)))


PREFIX = '任务板.'
IDENT = re.compile(r'^[a-z0-9_-]{1,40}$')


def _text(value, label, limit=100):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit or any(c in value for c in '\r\n\x00') or mdconf.COMMENT_RE.search(value):
        raise ValueError('%s请填写1—%d字的单行文字' % (label, limit))
    return value.strip()


def _integer(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('%s须为%d—%d之间的整数' % (label, lo, hi))
    return value


def _source(g):
    if not g.paths.vault:
        raise ValueError('请先选择学习库，再配置任务板')
    p = g.paths.rules
    return p, p.read_text(encoding='utf-8') if p.exists() else ''


def settings(g):
    _, text = _source(g)
    rules = _rules(g, text)
    raw = rules.raw
    tasks = []
    for key, value in raw.items():
        m = re.fullmatch(r'任务板\.支线\.([a-z0-9_-]{1,40})\.内容', key)
        if not m or not value.strip():
            continue
        ident = m.group(1)
        minutes = mdconf.to_num(raw.get(PREFIX+'支线.'+ident+'.分钟'), 30)
        tasks.append(dict(id=ident, title=value[:100], board=raw.get(PREFIX+'支线.'+ident+'.板块', ''),
                          minutes=max(1, min(600, int(minutes)))))
    return dict(revision=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                daily_minutes=max(1, int(rules.num('每日目标分钟'))),
                daily_title=raw.get(PREFIX+'每日内容') or ('每日精进' if getattr(g, 'subject', '法考') != '申论' else '每日研习'),
                weekly_title=raw.get(PREFIX+'每周内容') or '每周模考',
                weekly_count=max(1, int(rules.num('周常.宗门大比'))),
                tasks=tasks[:24], boards=_boards(g))


def save(g, body):
    previous = settings(g)
    if body.get('revision') != previous['revision']:
        raise ValueError('任务设置已在别处修改，请重新打开设置后再保存；本次未覆盖')
    minutes = _integer(body.get('daily_minutes'), 1, 1440, '每日目标分钟')
    weekly = _integer(body.get('weekly_count'), 1, 7, '每周模考次数')
    daily_title = _text(body.get('daily_title'), '每日内容')
    weekly_title = _text(body.get('weekly_title'), '每周内容')
    tasks = body.get('tasks')
    if not isinstance(tasks, list) or len(tasks) > 24:
        raise ValueError('支线任务最多24项')
    clean, seen = [], set()
    for t in tasks:
        if not isinstance(t, dict) or not IDENT.fullmatch(str(t.get('id', ''))) or t['id'] in seen:
            raise ValueError('任务编号无效或重复，请重新打开设置')
        seen.add(t['id'])
        board = t.get('board', '')
        if board and board not in _boards(g):
            raise ValueError('请选择当前科目的板块')
        clean.append(dict(id=t['id'], title=_text(t.get('title'), '支线内容'), board=board,
                          minutes=_integer(t.get('minutes'), 1, 600, '支线目标分钟')))
    p, text = _source(g)
    # 修改目标时保留其他规则、注释和代码块。别名按当前科目规范化。
    lines, in_code = [], False
    for ln in text.splitlines(keepends=True):
        if ln.strip().startswith('```'):
            in_code = not in_code
        m = None if in_code else mdconf.LINE_RE.match(ln)
        key = getattr(config, 'canon_key', lambda key, subject: key)(m.group(1).strip(), getattr(g, 'subject', '法考')) if m else ''
        if key.startswith(PREFIX) or key in ('每日目标分钟', '周常.宗门大比'):
            continue
        lines.append(ln)
    extra = ['- 每日目标分钟: %d' % minutes, '- 周常.宗门大比: %d' % weekly,
             '- 任务板.每日内容: '+daily_title, '- 任务板.每周内容: '+weekly_title]
    for t in clean:
        for field, value in (('内容', t['title']), ('板块', t['board']), ('分钟', t['minutes'])):
            extra.append('- 任务板.支线.%s.%s: %s' % (t['id'], field, value))
    updated = ''.join(lines).rstrip()+'\n\n'+'\n'.join(extra)+'\n'
    # 同锁内读写，摘要再校验外部编辑；失败不触碰旧规则。
    if hashlib.sha256(_source(g)[1].encode('utf-8')).hexdigest() != previous['revision']:
        raise ValueError('规则文件刚被修改，请重新载入设置')
    fd, name = tempfile.mkstemp(prefix='.task-board-', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(updated)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    g.rules.raw.update(_rules(g, updated).raw)
    return view(g)


def view(g):
    conf = settings(g)
    start = g.today-dt.timedelta(days=g.today.weekday())
    end = start+dt.timedelta(days=6)
    # 成绩单与boss是同一次录分的两个视图；有成绩单时，以其日期/删除结果为准。
    exams = set()
    mocks = g.state.get('mocks', {})
    for ident, rec in mocks.items():
        score, date = rec.get('score'), str(rec.get('date', ''))
        if type(score) in (int, float) and math.isfinite(score) and start.isoformat() <= date <= min(g.t, end.isoformat()):
            exams.add('season:'+ident)
    for i, rec in enumerate(g.state.get('boss', [])):
        if rec.get('kind') == '飞升':
            continue
        match = re.fullmatch(r'第(\d+)季', str(rec.get('name', '')))
        if match and match.group(1) in mocks:
            continue
        score, date = rec.get('score'), str(rec.get('d', ''))
        if type(score) in (int, float) and math.isfinite(score) and start.isoformat() <= date <= min(g.t, end.isoformat()):
            exams.add('boss:'+str(i))
    rows = []
    for t in conf['tasks']:
        records = [r for r in g.state.get('selfstudy', []) if r.get('task_board_id') == t['id'] and r.get('d') == g.t]
        rows.append(dict(t, current=sum(r['minutes'] for r in records),
                         records=[dict(minutes=r['minutes'], note=r.get('note', '')) for r in records]))
    return dict(config=conf, date=g.t, week=start.isoformat()+' — '+end.isoformat(),
                daily_current=round(g.minutes(g.t), 1), weekly_current=len(exams), tasks=rows)


def record(g, body):
    conf = settings(g)
    if body.get('revision') != conf['revision']:
        raise ValueError('任务内容已修改，请刷新任务板后再记一笔')
    ident, op = body.get('id'), body.get('op')
    if not isinstance(op, str) or not IDENT.fullmatch(op):
        raise ValueError('记录标识无效，请重新打开任务板')
    minutes = _integer(body.get('minutes'), 1, int(g.rules.num('听道单次上限') or 600), '本次学习分钟')
    note = body.get('note', '')
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError('学习备注最多2000字')
    previous = next((r for r in g.state.get('selfstudy', []) if r.get('task_board_op') == op), None)
    if previous:
        if previous.get('task_board_id') != ident or previous['minutes'] != minutes or previous.get('note', '') != note:
            raise ValueError('同一记录标识的内容发生变化，请重新打开任务板')
        return view(g)
    task = next((t for t in conf['tasks'] if t['id'] == ident), None)
    if not task:
        raise ValueError('这张支线任务签已移除，请刷新任务板')
    g.add_selfstudy(task['board'], minutes, task['title'], note)
    g.state['selfstudy'][-1].update(task_board_id=ident, task_board_op=op)
    return view(g)
