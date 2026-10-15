"""阶段世界：narrative.view读取真实委托、模考和考试日程，沿用原Store落盘。
存档world_progress={schema:1,worlds:{世界id:{unlocked:{阶段id:{date,reason}}}}}。
只保存解锁来源摘要；既得阶段不随调日程回收，不阻断原学习、不改成绩或学时。
未知schema/损坏记录保留并提示。场景及同伴名词来自themes.WORLD_PROFILES。
"""
import copy
import datetime as dt
import math
from . import themes
from .narrative import world_id

IDS = ('arrival', 'foundation', 'restored', 'assembly', 'departure')


def _state(g):
    raw = g.state.get('world_progress')
    if raw is not None and (not isinstance(raw, dict) or raw.get('schema') != 1 or not isinstance(raw.get('worlds'), dict)):
        raise ValueError('世界阶段存档格式不受支持，原记录已保留')
    raw = g.state.setdefault('world_progress', {'schema': 1, 'worlds': {}})
    st = raw['worlds'].setdefault(world_id(g), {'unlocked': {}})
    if not isinstance(st, dict) or not isinstance(st.get('unlocked'), dict):
        raise ValueError('世界阶段记录损坏，原记录已保留')
    if any(not isinstance(k, str) or not isinstance(v, dict) or not isinstance(v.get('date'), str)
           or not isinstance(v.get('reason'), str) for k, v in st['unlocked'].items()):
        raise ValueError('世界阶段来源损坏，原记录已保留')
    return st


def view(g, dashboard, journey, learned):
    st = _state(g)
    p = themes.WORLD_PROFILES[world_id(g)]
    schedule = g.state.get('study_schedule') or {}
    exam = schedule.get('exam')
    if not exam and hasattr(g, 'rules'):
        exam = g.rules.date('目标日').isoformat()
    try:
        remaining = (dt.date.fromisoformat(exam) - g.today).days
    except (TypeError, ValueError):
        remaining = None
    limit = max(0, g.rules.num('世界考前提醒天数')) if hasattr(g, 'rules') else 30
    bosses = [b for b in g.state.get('boss', []) if isinstance(b, dict)
              and isinstance(b.get('score'), (int, float)) and not isinstance(b.get('score'), bool)
              and math.isfinite(b['score']) and 0 <= b['score'] <= 100
              and isinstance(b.get('d'), str) and isinstance(b.get('name'), str)]
    tasks = {t['id']: t for t in journey.get('tasks', [])} if not journey.get('error') else {}
    conditions = {'arrival': (True, '初次进入世界'),
                  'foundation': (tasks.get('main:study', {}).get('status') == 'delivered', '已交付首段真实学习成果'),
                  'restored': (tasks.get('main:review', {}).get('status') == 'delivered', '已交付新的一次复习或复练成果'),
                  'assembly': (bool(bosses), '原模考/考试录分记录'),
                  'departure': (bool(learned and remaining is not None and 0 <= remaining <= limit), '已有学习记录，考试进入准备日程')}
    for ident, (ok, reason) in conditions.items():
        if ok:
            st['unlocked'].setdefault(ident, {'date': g.today.isoformat(), 'reason': reason})
    stage = max((i for i, ident in enumerate(IDS) if ident in st['unlocked']), default=0)
    milestones = [dict(id=ident, title=p['stages'][i], unlocked=ident in st['unlocked'],
                       **copy.deepcopy(st['unlocked'].get(ident, {}))) for i, ident in enumerate(IDS)]
    regions = [dict(id=ident, title=p['regions'][i], unlocked=ident in st['unlocked'], view=route,
                    reason=st['unlocked'].get(ident, {}).get('reason', requirement))
               for i, (ident, route, requirement) in enumerate((('foundation', 'skeleton', '交付首段学习成果'),
                    ('restored', 'dwelling' if world_id(g) == 'xingce' else 'log', '交付复习或复练成果'), ('assembly', 'contest', '原页面记录一次模考/考试成绩')))]
    return {'error': '', 'title': p['title'], 'stage': stage, 'phase': p['stages'][stage],
            'milestones': milestones, 'regions': regions, 'exam': exam or '', 'remaining': remaining,
            'note': '解锁记录保留；修改考试日程不会收回阶段或收藏。原学习入口始终可用。'}


def safe_view(g, dashboard, journey, learned):
    try:
        return view(g, dashboard, journey, learned)
    except ValueError as error:
        return {'error': str(error)}
