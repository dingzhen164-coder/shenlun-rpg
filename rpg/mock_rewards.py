"""3.6.5模考悟道：行测以录分前高峰分差登记机缘/即时扣进度，其余科目沿预估分奖励。
新记录增加model/best/gap/stage_line/penalty字段；新录分才结算，旧账本不追罚。
state.mock_rewards={schema:1,legacy_corrected:bool,records:{考试键:{name,date,score,baseline,status,...}}}。
API在原存档锁内调用；旧直接补经验记录保留，另记负向修正，匹配该次成绩生成待领取奖励。
"""
import datetime as dt
import hashlib
import math
import re
from . import themes

SCHEMA = 1
MODEL = 'stage-manual-v2'


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


def policy(g):
    """行测高分维持规则，程序与考情同源；规则缺项沿默认。"""
    keep = max(0, float(g.rules.num('模考悟道.维持分差')))
    normal = max(keep, float(g.rules.num('模考悟道.正常分差')))
    collapse = max(normal + 1, float(g.rules.num('模考悟道.入魔分差')))
    rates = g.rules.nums('模考悟道.退步扣除比例') or [.1, .2, .4, .6, .8]
    rates = sorted(min(1, max(0, float(r))) for r in rates[:20])
    step = (collapse - normal) / len(rates)
    return dict(keep=keep, normal=normal, collapse=collapse,
                tiers=[dict(lower=round(normal+i*step, 4), upper=round(normal+(i+1)*step, 4), rate=r)
                       for i, r in enumerate(rates)])


def prior_best(g, name):
    """排除本场，历次已编辑的成绩单优先于旧boss快照；飞升成绩不参与。"""
    mocks = g.state.get('mocks', {})
    scores = []
    seen = set()
    for entry in g.state.get('boss', []):
        if entry.get('kind', '大比') != '大比' or entry.get('name') == name:
            continue
        label = entry.get('name', '')
        m = re.fullmatch(r'第(\d+)季', label)
        value = mocks.get(m.group(1), {}).get('score') if m else None
        if value is None:
            value = entry.get('score')
        if m:
            seen.add(m.group(1))
        if isinstance(value, (int, float)) and math.isfinite(value):
            scores.append(value)
    for n, entry in mocks.items():
        if n in seen or '第%s季' % n == name:
            continue
        value = entry.get('score')
        if isinstance(value, (int, float)) and math.isfinite(value):
            scores.append(value)
    return max(scores) if scores else None


def stage_progress(g):
    """已踏入小境界的起点与未固化进度；清空进度不回收已突破境界。"""
    line = themes.sub_stage(min(g.claimed(), int(math.floor(g.raw_score()+1e-9))), g.theme)[2]
    base = min(g.state['xp'], int(math.ceil(g.xp_at(line))))
    return line, base, max(0, int(g.state['xp']-base))


def offer(g, name, score, baseline):
    migrate(g)
    data = ledger(g)['records']
    key = exam_key(name)
    if key in data:
        return []
    if getattr(g, 'subject', '法考') == '行测':
        best, rules = prior_best(g, name), policy(g)
        line, base, progress = stage_progress(g)
        gap = round(best-score, 4) if best is not None else 0
        pending = score > line and (best is None or gap <= rules['keep'])
        record = dict(name=name, date=g.t, score=score, baseline=round(baseline, 2), best=best,
                      gap=gap, stage_line=line, model='best-score-v1', status='pending' if pending else 'neutral')
        data[key] = record
        if best is not None and gap > rules['normal']:
            rate = 1 if gap >= rules['collapse'] else next(t['rate'] for t in reversed(rules['tiers']) if gap >= t['lower'])
            loss = min(progress, int(math.ceil(progress*rate)))
            g.state['xp'] = max(base, g.state['xp']-loss)
            label = '走火入魔' if rate == 1 else '道心失守'
            note = '%s：大比「%s」较此前最高%s分低%g分，本次扣除当前小境界进度%s%%（%s修为）' % (label, name, best, gap, round(rate*100), loss)
            g.state['events'].append(dict(t=dt.datetime.now().isoformat(timespec='seconds'), d=g.t,
                                         type='insight', board='', item='', ok=False, xp=-loss,
                                         reward_model='best-score-penalty-v1', exam_key=key, note=note))
            record.update(status='penalized', penalty=loss, penalty_rate=rate, progress_before=progress,
                          progress_after=progress-loss, realm=g.realm_info()['name'], settled_at=g.t)
            return [dict(kind='xp', v=-loss, msg=note)]
        return [dict(kind='info', msg='大比保持高峰且胜过当前境界分数线，已获得待领取悟道机缘')] if pending else []
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
    # 行测按实际境界分配；申论、法考保留各自原奖励，不回收已领取修为。
    divisor = 1
    if getattr(g, 'subject', '法考') == '行测' and info['big'] >= 2:
        divisor = max(1, int(g.rules.num('模考悟道.筑基分母' if info['big'] == 2 else '模考悟道.金丹及以后分母')))
        rate = 1.0 / divisor
    # 3.7.5：奖励只补满当前小境界（本阶段还差多少就最多领多少），不会溢出，也不会自己突破——突破仍由自己点。
    target = info['next_xp']        # 下一小境界的修为门槛（向上取整），补到这里正好圆满
    remaining = 0 if at_max or info['ready'] or not target else max(0, target - g.state['xp'])
    full = int(math.ceil(cost * rate))
    reward = min(full, remaining)
    return dict(amount=reward, cost=cost, rate=rate, divisor=divisor, remaining=remaining, capped=reward < full,
                realm=info['name'], next=info['next'] or info.get('gate_realm', ''),
                available=reward > 0 and rate > 0)


def view(g):
    preview = amount(g)
    return [dict(r, key=key, preview=preview if r['status'] == 'pending' else None)
            for key, r in reversed(list(ledger(g)['records'].items())) if r['status'] in ('pending', 'claimed', 'penalized')]


def claim(g, key):
    migrate(g)
    record = ledger(g)['records'].get(key)
    if not record or record['status'] not in ('pending', 'claimed'):
        raise ValueError('没有这份待领取模考奖励')
    if record['status'] == 'claimed':
        return []
    preview = amount(g)
    if not preview['available']:
        info = g.realm_info()
        if info['ready']:
            raise ValueError('当前小境界修为已圆满，不再有可领取的修为；请先去洞府点「突破」，进入下一阶段后再领取')
        if info['bottleneck']:
            raise ValueError('已到大境界瓶颈，修为已补满，请先渡劫')
        raise ValueError('当前阶段没有可领取的突破修为')
    reward = preview['amount']
    ratio = '1/%d' % preview['divisor'] if preview['divisor'] > 1 else '%g%%' % (preview['rate'] * 100)
    suffix = '，已补满本阶段（不溢出）' if preview['capped'] else ''
    events = g._award(reward, 'insight', note='模考悟道「%s」：按%s突破所需修为的%s奖励，手动领取%s' %
                      (record['name'], preview['realm'], ratio, suffix), bonus=False)
    # _award同时可能生成境界提醒；只为这笔悟道经验添加规则标记。
    event = next(e for e in reversed(g.state['events']) if e['type'] == 'insight' and e['xp'] == reward)
    event.update(reward_model=MODEL, exam_key=key)
    record.update(status='claimed', claimed_at=g.t, reward=reward, realm=preview['realm'], rate=preview['rate'])
    return events
