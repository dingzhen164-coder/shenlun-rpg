"""大比横幅日程。API/settings使用，规则保存考试横幅.名称/日期，缺项沿用目标日。

行测周日季号以2026-10-18第39季为锚；与成绩导入、奖励和学习日程无关。
配置使用规则摘要与原子替换，保留用户其他规则；不创建或迁移学习存档。
"""
import datetime as dt
import hashlib
import os
import tempfile

from . import mdconf, task_board

PREFIX = '考试横幅.'


def view(g):
    _, text = task_board._source(g)
    raw = task_board._rules(g, text).raw
    subject = getattr(g, 'subject', '法考')
    name = (raw.get(PREFIX+'名称') or ('法考' if subject == '法考' else '国考'))[:40]
    try:
        exam = dt.date.fromisoformat(raw.get(PREFIX+'日期', ''))
    except (TypeError, ValueError):
        exam = g.rules.date('目标日')
    # 周日当天保留本季，周一才进入下一季。不取已导入的最高季号。
    next_mock = g.today+dt.timedelta(days=(6-g.today.weekday()) % 7)
    mock = None
    if subject == '行测':
        mock = dict(date=next_mock.isoformat(), remaining=(next_mock-g.today).days,
                    season=39+(next_mock-dt.date(2026, 10, 18)).days//7)
    return dict(today=g.t, name=name, exam=exam.isoformat(), remaining=(exam-g.today).days,
                mock=mock, revision=hashlib.sha256(text.encode('utf-8')).hexdigest())


def save(g, body):
    previous = view(g)
    if body.get('revision') != previous['revision']:
        raise ValueError('规则已修改，请重新打开设置；本次未覆盖')
    name = task_board._text(body.get('name'), '考试名称', 40)
    try:
        exam = dt.date.fromisoformat(body['exam'])
    except (ValueError, TypeError, KeyError):
        raise ValueError('请填写有效的考试日期')
    p, text = task_board._source(g)
    lines, in_code = [], False
    for line in text.splitlines(keepends=True):
        if line.strip().startswith('```'):
            in_code = not in_code
        match = None if in_code else mdconf.LINE_RE.match(line)
        if match and match.group(1).strip() in (PREFIX+'名称', PREFIX+'日期'):
            continue
        lines.append(line)
    updated = ''.join(lines).rstrip()+'\n\n- '+PREFIX+'名称: '+name+'\n- '+PREFIX+'日期: '+exam.isoformat()+'\n'
    if hashlib.sha256(text.encode('utf-8')).hexdigest() != previous['revision']:
        raise ValueError('规则已修改，请重新打开设置；本次未覆盖')
    fd, temporary = tempfile.mkstemp(prefix='.exam-calendar-', suffix='.tmp', dir=str(p.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        if hashlib.sha256(task_board._source(g)[1].encode('utf-8')).hexdigest() != previous['revision']:
            raise ValueError('规则刚被外部修改，请重新打开设置；本次未覆盖')
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return view(g)
