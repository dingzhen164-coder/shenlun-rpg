"""学习委托、短主线和收藏；narrative/API展示，原学习模块在落盘前提供证据。

原存档新增journey={schema:1,worlds:{世界id:{revision,tasks:{实例id:
{status,created,kind,task,approach,evidence,proof}},collection:{收藏id:
{title,text,author,date,reason,proof,slot}},placements:{desk|shelf|wall:收藏id}}}}。
实例和收藏用稳定ID；不新建成绩来源，不给经验/学时。领取后才接纳原模块
的真实作答/批改/复习事件，交付幂等、修改有CAS。旧存档缺字段自动补齐。
"""
import copy
import uuid

from .narrative import world_id, _profile

from . import themes

LABELS = themes.JOURNEY_PROFILES
KINDS = ('card', 'bank', 'bank_review', 'recite', 'review', 'speedrun', 'feynman', 'example', 'apply', 'wrong', 'grade')
REVIEW = ('card', 'bank_review', 'review', 'speedrun', 'feynman', 'example', 'apply', 'wrong', 'grade')
SOURCES = {'card': '卡片复习记录', 'bank': '正式题库作答', 'bank_review': '正式题库复练',
           'grade': '正式批改记录'}
SLOTS = ('desk', 'shelf', 'wall')


def _state(g):
    raw = g.state.get('journey')
    if raw is not None and (not isinstance(raw, dict) or raw.get('schema') != 1 or not isinstance(raw.get('worlds'), dict)):
        raise ValueError('委托存档格式不受支持，原记录已保留')
    raw = g.state.setdefault('journey', {'schema': 1, 'worlds': {}})
    wid = world_id(g)
    st = raw['worlds'].setdefault(wid, {'revision': 0, 'tasks': {}, 'collection': {}, 'placements': {}})
    if (not isinstance(st, dict) or type(st.get('revision')) is not int or st['revision'] < 0
            or any(not isinstance(st.get(k), dict) for k in ('tasks', 'collection', 'placements'))):
        raise ValueError('委托记录损坏，原记录已保留')
    for task in st['tasks'].values():
        if (not isinstance(task, dict) or task.get('status') not in ('active', 'completed', 'delivered', 'expired')
                or task.get('kind') not in ('daily', 'study', 'review') or not isinstance(task.get('created'), str)
                or not isinstance(task.get('task'), dict) or not isinstance(task.get('evidence'), dict)
                or not isinstance(task.get('proof'), dict)):
            raise ValueError('委托实例损坏，原记录已保留')
        for key in ('proof', 'evidence'):
            proof = task[key]
            if proof and (any(not isinstance(proof.get(k), str) for k in ('id', 'kind', 'date', 'source', 'board', 'item'))
                          or proof['kind'] not in KINDS):
                raise ValueError('学习证明损坏，原记录已保留')
        if task['status'] in ('completed', 'delivered') and not task['proof']:
            raise ValueError('委托缺少学习证明，原记录已保留')
    for item in st['collection'].values():
        if (not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in
                ('title', 'text', 'author', 'date', 'reason', 'proof', 'slot')) or item['slot'] not in SLOTS):
            raise ValueError('收藏记录损坏，原记录已保留')
    if any(k not in SLOTS or not isinstance(v, str) or v not in st['collection'] or st['collection'][v]['slot'] != k
           for k, v in st['placements'].items()):
        raise ValueError('空间陈列记录损坏，原记录已保留')
    return st


def _daily_id(g):
    return 'daily:' + g.today.isoformat()


def _task_label(g, task):
    if task.get('type') == 'cards':
        return LABELS[world_id(g)]['cards']
    return task.get('board', '') + ' · ' + LABELS[world_id(g)]['exercise']


def _native_done(g, task):
    plan = g.state.get('plan') or {}
    return (plan.get('date') == task['created'] and any(t.get('id') == task['task'].get('id')
            and t.get('done') for t in plan.get('tasks', [])))


def _sync(g, st):
    changed = False
    for task in st['tasks'].values():
        if task['kind'] == 'daily' and task['status'] == 'active' and task['evidence'] and _native_done(g, task):
            task['status'], task['proof'] = 'completed', copy.deepcopy(task['evidence'])
            changed = True
        elif task['kind'] == 'daily' and task['status'] == 'active' and task['created'] < g.today.isoformat():
            task['status'] = 'expired'
            changed = True
    if changed:
        st['revision'] += 1


def record(g, kind, board='', item='', token=None):
    """仅由成功写入原学习记录的服务端调用；未领取、未知/损坏模块不影响学习。"""
    if kind not in KINDS or g.state.get('journey') is None:
        return None
    try:
        st = _state(g)
    except ValueError:
        return None
    token = token or uuid.uuid4().hex
    # 原模块重试同一事件不会被下一阶段再次消费。
    if any(token == t.get(k, {}).get('id') for t in st['tasks'].values() for k in ('proof', 'evidence')):
        return token
    proof = {'id': token, 'kind': kind, 'date': g.today.isoformat(), 'source': SOURCES.get(kind, '训练评阅记录'),
             'board': board, 'item': item}
    changed = False
    for task in st['tasks'].values():
        if task['status'] != 'active':
            continue
        if task['kind'] == 'daily':
            native = task['task']
            matches = (native.get('type') == 'cards' and kind == 'card'
                       or native.get('type') == 'bank' and kind == 'bank'
                       or native.get('type') == kind)
            if matches and (not native.get('board') or native['board'] == board):
                task['evidence'] = copy.deepcopy(proof)
                changed = True
        elif task['kind'] == 'study' or kind in REVIEW:
            task['status'], task['proof'] = 'completed', copy.deepcopy(proof)
            changed = True
    if changed:
        st['revision'] += 1
    return token


def revoke(g, token):
    """撤销卡片评分时撤回未交付证据；已获得的外观纪念保持，不补发成绩。"""
    if not token or g.state.get('journey') is None:
        return
    try:
        st = _state(g)
    except ValueError:
        return
    changed = False
    for task in st['tasks'].values():
        if task['status'] == 'delivered':
            continue
        if token in (task['proof'].get('id'), task['evidence'].get('id')):
            task.update(status='active', proof={}, evidence={})
            changed = True
    if changed:
        st['revision'] += 1


def _row(st, ident, title, kind, unlocked=True, task=None):
    saved = st['tasks'].get(ident)
    return {'id': ident, 'title': title, 'kind': kind, 'unlocked': unlocked,
            'status': saved['status'] if saved else 'available', 'task': copy.deepcopy(task or (saved or {}).get('task', {})),
            'proof': copy.deepcopy((saved or {}).get('proof', {})), 'approach': (saved or {}).get('approach', '')}


def view(g, dashboard):
    st, wid = _state(g), world_id(g)
    _sync(g, st)
    names = LABELS[wid]
    tasks = [_row(st, 'main:study', names['first'], 'study'),
             _row(st, 'main:review', names['second'], 'review',
                  st['tasks'].get('main:study', {}).get('status') == 'delivered')]
    # 每天只领取一项原计划，快照保留；跨日未交付实例仍能交付，未完成旧委托不阻断新日。
    daily = _daily_id(g)
    if daily in st['tasks']:
        tasks.append(_row(st, daily, names['daily'], 'daily'))
    else:
        plan = g.state.get('plan') or {}
        if plan.get('date') == g.today.isoformat():
            for task in plan.get('tasks', []):
                if not task.get('done') and task.get('type') in KINDS + ('cards',):
                    tasks.append(_row(st, daily, names['daily'], 'daily', task=task))
    for ident, task in st['tasks'].items():
        if ident.startswith('daily:') and ident != daily and task['status'] == 'completed':
            tasks.append(_row(st, ident, names['daily'] + ' · ' + task['created'], 'daily'))
    for task in tasks:
        if task['task']:
            task['task']['title'] = _task_label(g, task['task'])
    stage = 2 if st['tasks'].get('main:review', {}).get('status') == 'delivered' else 1 if tasks[0]['status'] == 'delivered' else 0
    # 旧3.0第二批存档懒补称号；同伴纪念需已读支线与真实学习交付双重条件。
    p = themes.WORLD_PROFILES[wid]
    rewards = []
    if stage == 2:
        rewards.append(('main:title', p['honor'], p['finish'], '完成首条学习故事', st['tasks']['main:review'], _profile(g, dashboard)['character']))
    raw = g.state.get('narrative')
    worlds = raw.get('worlds') if isinstance(raw, dict) and raw.get('schema') == 1 else {}
    saved_world = worlds.get(wid) if isinstance(worlds, dict) else {}
    chapters = saved_world.get('chapters', {}) if isinstance(saved_world, dict) else {}
    if not isinstance(chapters, dict):
        chapters = {}
    for person in p['companions']:
        saved = chapters.get(person['id'], {})
        if stage >= 1 and isinstance(saved, dict) and saved.get('read'):
            history = saved.get('record') or saved.get('trail') or []
            direction = next((x.get('choice_id', x.get('choice')) for x in history if isinstance(x, dict) and x.get('choice_id', x.get('choice')) in ('method', 'practice')), '') if isinstance(history, list) else ''
            text = person.get('echo_' + direction, person['greeting'])
            rewards.append((person['id'] + ':keepsake', person['keepsake'], text, '同伴交谈与真实学习交付', st['tasks']['main:study'], person['name']))
    for ident, title, text, reason, task, author in rewards:
        if ident not in st['collection']:
            st['collection'][ident] = {'title': title, 'text': text, 'author': author,
                'date': g.today.isoformat(), 'reason': reason, 'proof': task['proof']['id'], 'slot': 'wall'}
            st['revision'] += 1
    return {'world': wid, 'revision': st['revision'], 'title': names['title'], 'stage': stage,
            'text': names[('intro', 'echo', 'end')[stage]], 'tasks': tasks,
            'collection': [dict(id=k, **copy.deepcopy(v)) for k, v in st['collection'].items()],
            'placements': copy.deepcopy(st['placements']), 'error': ''}


def safe_view(g, dashboard):
    try:
        return view(g, dashboard)
    except ValueError as e:
        return {'error': str(e)}


def act(g, dashboard, body):
    if not isinstance(body, dict) or body.get('world') != world_id(g):
        raise ValueError('科目已经改变，请重新打开委托')
    st = _state(g)
    _sync(g, st)
    action, ident = body.get('action'), body.get('id')
    if not isinstance(ident, str):
        raise ValueError('请选择一项委托或收藏')
    task = st['tasks'].get(ident)
    # 重复领取/交付同实例幂等；只返回已存在结果，不修改新状态或重复发收藏。
    if (action == 'claim' and task) or (action == 'deliver' and task and task['status'] == 'delivered'):
        return view(g, dashboard)
    if type(body.get('revision')) is not int or body['revision'] != st['revision']:
        raise ValueError('委托已在另一窗口更新，请刷新后继续，不会覆盖新记录')
    if action == 'claim':
        offered = next((t for t in view(g, dashboard)['tasks'] if t['id'] == ident and t['unlocked']
                        and (t['kind'] != 'daily' or t['task'].get('id') == body.get('task_id'))), None)
        if not offered or offered['status'] != 'available':
            raise ValueError('这项委托尚不可领取，请先完成上一段学习或刷新今日计划')
        approach = body.get('approach', 'study')
        if approach not in ('study', 'practice'):
            raise ValueError('请选择课程研习或以题检验')
        st['tasks'][ident] = {'status': 'active', 'created': g.today.isoformat(), 'kind': offered['kind'],
                              'task': offered['task'], 'approach': approach, 'evidence': {}, 'proof': {}}
    elif action == 'deliver':
        if not task or task['status'] != 'completed' or not task['proof']:
            raise ValueError('还没有领取后的真实学习成果，不能交付')
        names, profile = LABELS[world_id(g)], _profile(g, dashboard)
        first = task['kind'] == 'study'
        reward = names['letter'] if first else names['badge'] if task['kind'] == 'review' else names['daily'] + '纪念'
        author = profile['character']
        direction = '从课程梳理入手' if task['approach'] == 'study' else '从题目检验入手'
        text = '%s：你%s，已经留下%s。这份纪念记录你的行动，不替代正确率或掌握程度。' % (author, direction, task['proof']['source'])
        key = ident + ':reward'
        st['collection'].setdefault(key, {'title': reward, 'text': text, 'author': author, 'date': g.today.isoformat(),
            'reason': '交付' + names['first' if first else 'second' if task['kind'] == 'review' else 'daily'],
            'proof': task['proof']['id'], 'slot': 'desk' if first else 'wall'})
        if task['kind'] == 'review':
            st['collection'].setdefault('main:ornament', {'title': names['ornament'], 'text': names['end'], 'author': author,
                'date': g.today.isoformat(), 'reason': '完成首条学习故事', 'proof': task['proof']['id'], 'slot': 'shelf'})
        task['status'] = 'delivered'
    elif action == 'place':
        slot = body.get('slot')
        if slot not in SLOTS:
            raise ValueError('没有这个陈列位置')
        if ident:
            item = st['collection'].get(ident)
            if not item or item['slot'] != slot:
                raise ValueError('只能陈列已获得且适合这个位置的收藏')
            st['placements'][slot] = ident
        else:
            st['placements'].pop(slot, None)
    else:
        raise ValueError('不认识的委托操作')
    st['revision'] += 1
    return view(g, dashboard)
