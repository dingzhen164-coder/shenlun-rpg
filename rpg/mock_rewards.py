"""3.0.6模考悟道：成绩超出录入时预估分，登记一次可手动领取的阶段奖励。
state.mock_rewards={schema:1,legacy_corrected:bool,records:{考试键:{name,date,score,baseline,status,...}}}。
API在原存档锁内调用；旧直接补经验记录保留，另记负向修正，匹配该次成绩生成待领取奖励。
"""
import datetime as dt
import hashlib
import math
import re

SCHEMA = 1
MODEL = 'stage-manual-v1'


def exam_key(name, kind='大比'):
    return hashlib.sha256((kind + '\0' + str(name).strip()).encode('utf-8')).hexdigest()[:20]


def ledger(g):
    return g.state.setdefault('mock_rewards', {'schema': SCHEMA, 'legacy_corrected': False, 'records': {}})


def legacy_events(g):
    return [e for e in g.state.get('events', []) if e.get('type') == 'insight' and e.get('xp', 0) > 0 and not e.get('reward_model')]


def migrate(g):
    data = ledger(g)
    if data.get('legacy_corrected'):
        return []
    records = data.setdefault('records', {})
    bosses = [b for b in g.state.get('boss', []) if b.get('kind', '大比') == '大比']
    for b in bosses:
        records.setdefault(exam_key(b['name']), dict(name=b['name'], date=b['d'], score=b['score'], status='historical'))
    old = legacy_events(g)
    events = list(g.state.get('events', []))
    gained = sum(e['xp'] for e in old)
    for event in old:
        pos = next((i for i, e in enumerate(events) if e is event), -1)
        prior = next((e for e in reversed(events[:pos]) if e.get('type') == 'boss'), None)
        name_match = re.search(r'「(.+?)」', prior.get('note', '')) if prior else None
        name = name_match.group(1) if name_match else None
        match = next((b for b in reversed(bosses) if b.get('name') == name and b.get('d') == event.get('d')), None)
        if match:
            records[exam_key(name)].update(status='pending', baseline=None, migrated=True, legacy_xp=event['xp'])
    data['legacy_corrected'] = True
    if not gained:
        return []
    removed = min(gained, max(0, g.state['xp']))
    g.state['xp'] -= removed
    # 已被旧奖励推高并点过的境界也归回真实可达阶段，避免日后不点突破却自动恢复。
    if g.state.get('claimed') is not None:
        g.state['claimed'] = min(g.state['claimed'], int(math.floor(g.raw_score() + 1e-9)))
    # 同类型负向记账抵消旧悟道，天道进度仍只统计真实积累；原记录保留便于审计。
    g.state['events'].append(dict(t=dt.datetime.now().isoformat(timespec='seconds'), d=g.t,
                                 type='insight', board='', item='', ok=True, xp=-gained,
                                 reward_model='legacy-rollback', note='3.0.6纠正：撤回旧模考直接补足修为 %s' % removed))
    data['legacy_removed'] = removed
    return [dict(kind='xp', v=-removed, msg='撤回旧模考悟道 %s，新的阶段奖励请手动领取' % removed)]


def offer(g, name, score, baseline):
    migrate(g)
    data = ledger(g)['records']
    key = exam_key(name)
    if key in data:
        return []
    pending = score > baseline
    data[key] = dict(name=name, date=g.t, score=score, baseline=round(baseline, 2),
                     status='pending' if pending else 'ineligible')
    return [dict(kind='info', msg='模考成绩超过预估分，已获得待领取悟道奖励；前往成长或模考界面领取')] if pending else []


def amount(g):
    info = g.realm_info()
    at_max = info['raw'] >= info['max_score'] and g.claimed() >= info['max_score']
    cost = 0 if at_max else max(0, int(info['need']))
    rate_key = '模考悟道.入门倍率' if info['big'] < 2 else '模考悟道.进阶倍率'
    rate = max(0, float(g.rules.num(rate_key)))
    return dict(amount=int(math.ceil(cost * rate)), cost=cost, rate=rate,
                realm=info['name'], next=info['next'] or info.get('gate_realm', ''),
                available=cost > 0 and rate > 0)


def view(g):
    preview = amount(g)
    return [dict(r, key=key, preview=preview if r['status'] == 'pending' else None)
            for key, r in reversed(list(ledger(g)['records'].items())) if r['status'] in ('pending', 'claimed')]


def claim(g, key):
    migrate(g)
    record = ledger(g)['records'].get(key)
    if not record or record['status'] not in ('pending', 'claimed'):
        raise ValueError('没有这份待领取模考奖励')
    if record['status'] == 'claimed':
        return []
    preview = amount(g)
    if not preview['available']:
        raise ValueError('当前阶段没有可领取的突破修为')
    reward = preview['amount']
    events = g._award(reward, 'insight', note='模考悟道「%s」：按%s突破所需修为的%s%%奖励，手动领取' %
                      (record['name'], preview['realm'], int(preview['rate'] * 100)), bonus=False)
    # _award同时可能生成境界提醒；只为这笔悟道经验添加规则标记。
    event = next(e for e in reversed(g.state['events']) if e['type'] == 'insight' and e['xp'] == reward)
    event.update(reward_model=MODEL, exam_key=key)
    record.update(status='claimed', claimed_at=g.t, reward=reward, realm=preview['realm'], rate=preview['rate'])
    return events
