"""离线纪事与人物互动，api.dashboard及/api/narrative调用。

故事定义只读rpg/data/narrative.json；存档narrative={schema:1,worlds:{世界id:
{revision,chapters:{章节id:{node,trail:[{node,choice}],read,skipped,record}},memories:{事件id:{date,text,source}}}}}。
节点/选项均由服务端校验，revision阻止并发覆盖；Ink只负责文字、分支呈现，
不信任浏览器上报的学习事实，不授予经验/成绩/时间。沿用Store原子写入与每日备份。
"""
import copy
import json
import math
from pathlib import Path

from . import art, themes

DEFINITIONS = json.loads((Path(__file__).parent / 'data/narrative.json').read_text(encoding='utf-8'))


def world_id(g):
    subject = getattr(g, 'subject', '法考')
    return {'行测': 'xingce', '申论': 'office', '法考': 'mage'}[subject]


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def facts(g, dashboard):
    """只依据原引擎中的学习记录；初始化空项目/总经验不是学习证据。"""
    st = g.state
    learned = (any(t.get('done') for t in (st.get('plan') or {}).get('tasks', []))
               or any(_positive(v) for v in st.get('seconds', {}).values())
               or any(v.get('last') or _positive(v.get('level')) or _positive(v.get('l1'))
                      for v in st.get('items', {}).values())
               or any(r.get('history') for r in (st.get('bank') or {}).get('records', {}).values())
               or any(e.get('type') == 'grade' for e in st.get('events', [])))
    return {'learned': bool(learned), 'tower': bool((dashboard.get('tower') or {}).get('completed', 0)),
            'boss': bool(st.get('boss'))}


def _chapter(world, ident):
    if not isinstance(ident, str):
        raise ValueError('没有这段纪事')
    for c in DEFINITIONS[world]['chapters']:
        if c['id'] == ident:
            return c
    raise ValueError('没有这段纪事')


def _state(g):
    raw = g.state.get('narrative')
    if raw is not None and (not isinstance(raw, dict) or raw.get('schema') != 1 or not isinstance(raw.get('worlds'), dict)):
        raise ValueError('纪事存档格式不受支持，请保留原存档并检查版本')
    st = g.state.setdefault('narrative', {'schema': 1, 'worlds': {}})
    wid = world_id(g)
    if wid not in DEFINITIONS:
        raise ValueError('当前科目不支持这套纪事')
    if wid not in st['worlds']:
        st['worlds'][wid] = {'revision': 0, 'chapters': {}, 'memories': {}}
        # 行测原五章保持原接口；映射入门与学习章的已读状态，不重发任何奖励。
        if wid == 'xingce':
            legacy = g.state.get('sect_story') or {}
            for cid, oldid in [('prologue', 'arrival'), ('study_echo', 'five_paths')]:
                if oldid in (legacy.get('read') or []):
                    c = _chapter(wid, cid)
                    st['worlds'][wid]['chapters'][cid] = {'node': c['end'], 'trail': [], 'read': True,
                                                          'skipped': False, 'record': []}
    current = st['worlds'][wid]
    if (not isinstance(current, dict) or type(current.get('revision')) is not int or current['revision'] < 0
            or not isinstance(current.get('chapters'), dict) or not isinstance(current.get('memories'), dict)):
        raise ValueError('纪事记录损坏，请保留原存档并从备份核对')
    for entry in current['chapters'].values():
        if (not isinstance(entry, dict) or not isinstance(entry.get('node'), str)
                or type(entry.get('read')) is not bool or not isinstance(entry.get('trail'), list)
                or len(entry['trail']) > 64 or any(not isinstance(x, dict) or not isinstance(x.get('node'), str)
                                                  or not isinstance(x.get('choice'), str) for x in entry['trail'])):
            raise ValueError('纪事章节记录损坏，请保留原存档并从备份核对')
    for entry in current['chapters'].values():
        record = entry.get('record', [])
        if (not isinstance(record, list) or len(record) > 64
                or any(not isinstance(x, dict) or not isinstance(x.get('choice'), str)
                       or not isinstance(x.get('lines'), list) or any(not isinstance(line, str) for line in x['lines'])
                       for x in record)):
            raise ValueError('对话记录损坏，原记录已保留')
    if any(not isinstance(v, dict) or any(not isinstance(v.get(k), str) for k in ('date', 'text', 'source'))
           for v in current['memories'].values()):
        raise ValueError('人物记忆损坏，原记录已保留')
    return current


def _allowed(chapter, saved, fs):
    return bool(saved.get('unlocked') or saved.get('read') or chapter['condition'] == 'always' or fs.get(chapter['condition']))


def _entry(chapter):
    return {'node': chapter['start'], 'trail': [], 'read': False, 'skipped': False, 'record': [], 'unlocked': True}


def _profile(g, dashboard):
    p = copy.deepcopy(themes.NARRATIVE_PROFILES[world_id(g)])
    if world_id(g) == 'office':
        leader = (dashboard.get('career') or {}).get('leader') or {}
        p['character'] = leader.get('name') or g.persona['导师名'] or p['character']
        p['role'] = leader.get('title') or p['role']
        cid = dict(art.SL_CHARS).get(p['character'])            # 美术文件夹里有这位领导的立绘就用（rpg/art.py）
        por = art.character_portraits(getattr(g, 'paths', None), '申论', cid) if cid else None
        custom_avatar = (dashboard.get('persona') or {}).get('tutor_avatar') or ''
        user_portrait = art.lookup(getattr(g, 'paths', None), '申论', 'beauty/portrait/sl-%s-calm.webp' % cid) if cid else None
        if por and (user_portrait or not custom_avatar):
            p['portraits'], p['portrait'], p['art_portraits'] = por, por['calm'], True
    if world_id(g) != 'xingce':
        custom = (dashboard.get('persona') or {}).get('tutor_avatar') or ''
        if (custom or not p.get('portraits')) and not p.get('art_portraits'):
            p['portrait'] = custom          # 用户自定义导师头像优先，此时不用内置表情立绘（美术文件夹里按姓名放的申论人物立绘除外）
            p.pop('portraits', None)
    p.pop('art_portraits', None)
    return p


def view(g, dashboard):
    wid = world_id(g)
    state, fs = _state(g), facts(g, dashboard)
    memories = state['memories']
    # 人物只记真实来源摘要，不复制作答正文、原题、答案或密钥。
    for key, text, source in [('learned', '已经留下真实学习记录', '学习存档'),
                              ('tower', '已有正式题库作答记录', '题库练习历史'),
                              ('boss', '已有模考或考试成绩记录', '考试录分')]:
        if fs[key] and key not in memories:
            memories[key] = {'date': g.today.isoformat(), 'text': text, 'source': source}
    chapters = []
    for c in DEFINITIONS[wid]['chapters']:
        saved = state['chapters'].get(c['id'], {})
        unlocked = _allowed(c, saved, fs)
        if unlocked and not saved:
            saved = state['chapters'][c['id']] = _entry(c)
        elif unlocked:
            saved['unlocked'] = True
        chapters.append({'id': c['id'], 'title': c['title'], 'unlocked': unlocked,
                         'condition': '已有有效学习记录' if c['condition'] == 'learned' else '随时可读',
                         'read': bool(saved.get('read')), 'skipped': bool(saved.get('skipped')),
                         'started': bool(saved.get('trail')), 'character': c.get('character', '')})
    profile = _profile(g, dashboard)
    if fs['learned']:
        profile['greeting'] = profile['echo']
    companions = []
    for person in themes.WORLD_PROFILES[wid]['companions']:
        p = copy.deepcopy(person)
        saved = state['chapters'].get(p['id'], {})
        history = saved.get('record') or saved.get('trail') or []
        direction = next((x.get('choice_id', x['choice']) for x in history if x.get('choice_id', x['choice']) in ('method', 'practice')), '')
        p['feedback'] = p.get('echo_' + direction, p['greeting'])
        p['read'] = bool(saved.get('read'))
        p['familiar'] = '已交谈 · 依据对话记录' if p['read'] else '初次相遇'
        companions.append(p)
    from . import journey, world
    j = journey.safe_view(g, dashboard)
    return {'journey': j, 'world_progress': world.safe_view(g, dashboard, j, fs['learned']),
            'companions': companions, 'guide_profile': profile, 'world': wid, 'revision': state['revision'], 'version': DEFINITIONS[wid]['version'],
            'profile': profile, 'facts': fs, 'chapters': chapters,
            'memories': list(memories.values()),
            'unread': sum(c['unlocked'] and not c['read'] for c in chapters)}


def _scene(g, dashboard, cid):
    out = view(g, dashboard)
    c = _chapter(out['world'], cid)
    saved = _state(g)['chapters'].get(cid, {})
    if not _allowed(c, saved, out['facts']):
        raise ValueError('这段纪事需先留下有效学习记录')
    node = saved['node']
    if node not in c['nodes']:
        raise ValueError('纪事节点已更新，请重读本章；原阅读记录仍保留')
    n = c['nodes'][node]
    if c.get('character'):
        person = next(p for p in out['companions'] if p['id'] == c['character'])
        pid = dict(art.SL_CHARS).get(person['name']) if out['world'] == 'office' else None
        por = art.character_portraits(getattr(g, 'paths', None), '申论', pid) if pid else None
        out['profile'] = dict(out['guide_profile'], character=person['name'], role=person['role'],
                              intro=person['intro'], greeting=person['feedback'], mark=person['mark'],
                              portrait=por['calm'] if por else '', portraits=por)
    choices = [x for x in n['choices'] if not x.get('when') or out['facts'].get(x['when'])]
    trail = saved.get('trail', [])
    transcript = []
    for step in trail:
        old = c['nodes'].get(step['node'])
        if not old: continue
        selected = next((v for v in old['choices'] if v['id'] == step['choice']), None)
        if selected:
            transcript.append({'lines': old['lines'], 'choice': selected['text'], 'choice_id': selected['id']})
    out['scene'] = {'chapter': cid, 'title': c['title'], 'node': node, 'lines': n['lines'],
                    'choices': choices, 'end': node == c['end'], 'read': saved['read'],
                    'transcript': transcript, 'record': saved.get('record', [])}
    return out


def act(g, dashboard, body):
    if not isinstance(body, dict) or body.get('world') != world_id(g):
        raise ValueError('科目已经改变，请重新打开纪事')
    action = body.get('action', 'open')
    if action not in ('open', 'choose', 'finish', 'skip', 'replay'):
        raise ValueError('不认识的纪事操作')
    cid = body.get('chapter')
    c = _chapter(world_id(g), cid)
    if action == 'open':
        return _scene(g, dashboard, cid)
    # 版本先检查；失败不修改节点/选择/阅读记录，也不清除重读前历史。
    state = _state(g)
    if type(body.get('revision')) is not int or body['revision'] != state['revision']:
        raise ValueError('纪事已在另一窗口更新，请关闭后重新打开，不会覆盖新记录')
    fs = facts(g, dashboard)
    saved = state['chapters'].get(cid, {})
    if not _allowed(c, saved, fs):
        raise ValueError('这段纪事尚未解锁')
    if action != 'replay' and body.get('node') != saved.get('node'):
        raise ValueError('纪事节点已经改变，请重新打开')
    if action == 'replay':
        old = saved
        saved = _entry(c)
        saved.update(read=bool(old.get('read')), record=old.get('record', []))
        state['chapters'][cid] = saved
    elif action == 'choose':
        n = c['nodes'].get(saved['node'])
        choice = next((x for x in (n or {}).get('choices', []) if x['id'] == body.get('choice')), None)
        if not choice or (choice.get('when') and not fs.get(choice['when'])):
            raise ValueError('这个选项当前不可用')
        saved['trail'].append({'node': saved['node'], 'choice': choice['id']})
        saved['node'] = choice['target']
    else:
        if action == 'finish' and saved['node'] != c['end']:
            raise ValueError('请读到本章结尾，或使用跳过')
        if not saved['read']:
            saved['record'] = _scene(g, dashboard, cid)['scene']['transcript']
        saved.update(node=c['end'], read=True, skipped=action == 'skip')
        # 原接口仍能看到映射的已读章节；只更新已读，不删原五章。
        if world_id(g) == 'xingce' and cid in ('prologue', 'study_echo'):
            oldid = {'prologue': 'arrival', 'study_echo': 'five_paths'}[cid]
            legacy = g.state.setdefault('sect_story', {'schema': 1, 'unlocked': [], 'read': []})
            for key in ('unlocked', 'read'):
                if oldid not in legacy[key]: legacy[key].append(oldid)
    state['revision'] += 1
    return _scene(g, dashboard, cid)
