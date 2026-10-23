"""行测宗剧情：api.dashboard 传入已计算的面板；POST /api/sect/story 记录阅读。
存档 sect_story={schema:1,unlocked:[章节id],read:[章节id]}，只写现有原子存档，
不改经验/成绩/任务；章节由实际学习记录解锁，旧存档自动补字段，申论不启用。
"""
CHAPTERS = (
    {'id': 'arrival', 'title': '初入山门', 'condition': '入宗即可阅读', 'lines': [
        '行测宗坐落在群山之间。昔日门人以辨理、推演、识势立道，五脉典籍曾汇成一部《万象经》。后来典籍散失，宗门渐渐沉寂。',
        '山门前，沈清禾将一卷竹简交到你手中：“徒儿，入我宗门，无须争一时之快。先明理，再举例，最后用实战验之。”',
        '你将在五脉修行，登试炼塔、照见心魔、参加宗门会试。设置中的考试日期，便是你的仙门大选之日。已有的学习记录，也都算作这段修行。']},
    {'id': 'five_paths', 'title': '五脉寻道', 'condition': '完成一项功课或已有有效学习记录', 'lines': [
        '辨言峰、演数峰、明理峰、观星峰、万象峰，五脉通往不同的山峰，却都在追问同一件事：你是否真正理解眼前的问题？',
        '清禾说道：“知识不是背出名字便算掌握。试着用自己的话讲清它，再举一例；面对选项时，说出你判断的依据。”']},
    {'id': 'tower', 'title': '登塔炼心', 'condition': '完成至少一道题库真题', 'lines': [
        '试炼塔的灯火逐层向上。塔中每道题都留下你的实战记录；再次练习可以巩固，却不会重复增加登塔题数。',
        '清禾轻叩竹卷：“层数记历练，正确率看成效。若遇错题，去照心台弄清失误，再回来走下一程。”']},
    {'id': 'assembly', 'title': '宗门会试', 'condition': '已有宗门大比（模考）成绩', 'lines': [
        '宗门大比的钟声响起。宗门会试将五脉所学放在同一张试卷中，也让时间安排与取舍有了重量。',
        '清禾说道：“成绩已记入修仙录。复盘时，先看真实失分与耗时，再决定下一轮练什么。不要凭一时心情给自己下定论。”']},
    {'id': 'departure', 'title': '赴选之前', 'condition': '距考试不超过30天，且已有学习记录', 'lines': [
        '仙门大选临近，山门外的路渐渐清晰。藏经阁的卷轴、照心台的记录，都是你一路走来的凭据。',
        '清禾将竹简合拢：“此时不必追求把所有东西重学一遍。巩固已会的，查清还错的，按你的考试时间练一练。赴选之日，带着明白与从容下山。”']},
)
IDS = {c['id'] for c in CHAPTERS}


def view(g, dashboard):
    if g.subject != '行测':
        return None
    old = g.state.get('sect_story')
    old = old if isinstance(old, dict) else {}
    def clean(key):
        values = old.get(key, [])
        return [x for x in values if isinstance(x, str) and x in IDS] if isinstance(values, list) else []
    unlocked = set(clean('unlocked'))
    tasks = (dashboard.get('plan') or {}).get('tasks', [])
    learned = (any(t.get('done') for t in tasks) or any(v.get('last') or v.get('level', 0) > 0 or v.get('l1', 0) > 0
                   for v in g.state.get('items', {}).values())
               or any(float(s or 0) > 0 for s in g.state.get('seconds', {}).values())
               or any(e.get('xp', 0) > 0 for e in g.state.get('events', [])) or bool(dashboard.get('boss_all'))
               or (dashboard.get('tower') or {}).get('completed', 0) > 0)
    schedule = g.state.get('study_schedule', {})
    import datetime as dt
    try:
        remaining = (dt.date.fromisoformat(schedule['exam']) - g.today).days
    except (KeyError, TypeError, ValueError):
        remaining = None
    conditions = {'arrival': True, 'five_paths': learned,
                  'tower': (dashboard.get('tower') or {}).get('completed', 0) > 0,
                  'assembly': bool(dashboard.get('boss_all')),
                  'departure': learned and remaining is not None and 0 <= remaining <= 30}
    unlocked.update(k for k, ok in conditions.items() if ok)
    # 解锁后不会因日程调整、重新生成今日任务而收回；已读章节也保留解锁。
    unlocked.update(clean('read'))
    saved = {'schema': 1, 'unlocked': [c['id'] for c in CHAPTERS if c['id'] in unlocked],
             'read': [c['id'] for c in CHAPTERS if c['id'] in set(clean('read'))]}
    g.state['sect_story'] = saved
    chapters = [dict(c, unlocked=c['id'] in unlocked, read=c['id'] in saved['read']) for c in CHAPTERS]
    return {'name': '行测宗', 'chapters': chapters, 'remaining': remaining,
            'unread': sum(c['unlocked'] and not c['read'] for c in chapters)}


def mark_read(g, dashboard, chapter_id):
    if g.subject != '行测':
        raise ValueError('宗门剧情仅用于行测')
    result = view(g, dashboard)
    if not isinstance(chapter_id, str) or chapter_id not in IDS:
        raise ValueError('没有这段宗门剧情')
    chapter = next(c for c in result['chapters'] if c['id'] == chapter_id)
    if not chapter['unlocked']:
        raise ValueError('这段剧情尚未解锁')
    if chapter_id not in g.state['sect_story']['read']:
        g.state['sect_story']['read'].append(chapter_id)
    return view(g, dashboard)
