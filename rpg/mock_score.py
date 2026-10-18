"""行测模考参考估分，供mock.summary与导入回执调用，不保存成绩/发奖。

规则键模考参考.题量/分值.<题型>可在训练/规则.md修改；默认是用户提供的
130题地市级/行政执法参考表。Decimal逐项相加，保留两位小数。完整题量、
分值合计100且对错明确才给总估分；HTML明确未作答算0，PDF未知对错不算错。
与HTML报告原分数独立，法考/申论不使用此表。
"""
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ROWS = (("政治理论",20,"0.5"), ("常识判断",15,"0.5"), ("言语理解",30,"0.8"),
        ("图形推理",10,"0.8"), ("定义判断",10,"0.8"), ("类比推理",5,"0.8"),
        ("逻辑判断",10,"0.85"), ("数量关系",10,"1"), ("资料分析",20,"1"))
JUDGMENT = {"论证逻辑":"逻辑判断","形式逻辑":"逻辑判断","一拖五":"逻辑判断","类比关系":"类比推理"}


def estimate(g, directory, counts, rec):
    from . import vault
    if g.subject != '行测':return None
    reasons, profile = [], {}
    try:
        for name, number, point in ROWS:
            n=Decimal(str(g.rules.get('模考参考.题量.'+name)))
            w=Decimal(str(g.rules.get('模考参考.分值.'+name)))
            if not n.is_finite() or n!=int(n) or not 0<=n<=500 or not w.is_finite() or not 0<w<=10:raise ValueError()
            profile[name]=(int(n),w)
        if sum(n*w for n,w in profile.values())!=100:reasons.append('参考分值合计须为100分，请核对规则')
    except (ValueError,TypeError,InvalidOperation,OverflowError):
        return dict(ready=False,score=None,known_score=None,reason='参考题量或分值无效，请核对训练/规则.md',modules={},unknown=0)
    metadata=rec.get('html_import') or {}
    known=set(metadata.get('known_numbers') or [])
    numbers,unknown,duplicate=set(),0,False
    for f in directory.glob('[0-9][0-9]-*.md'):
        for q in vault.parse_board_file(f):
            if q['num'] in numbers:duplicate=True
            numbers.add(q['num'])
            if q['icon'] not in ('✅','❌') and q['num'] not in known:unknown+=1
    if duplicate:reasons.append('复盘题号重复，需先核对')
    if unknown:reasons.append('%d题对错未知，请补答题卡或HTML' % unknown)
    rows=Counter();right=Counter();modules={};total=Decimal(0)
    for module,c in counts.items():
        mod=Decimal(0)
        if module=='判断推理':
            parts=[(JUDGMENT.get(b,b),v[0],v[3]) for b,v in c['boards'].items()]
        else:parts=[(module,c['ok'],c['total'])]
        for name,ok,n in parts:
            if name not in profile:
                if n:reasons.append('未配置题型分值：'+name)
                continue
            rows[name]+=n;right[name]+=ok
            mod+=profile[name][1]*ok
        modules[module]=float(mod.quantize(Decimal('.01'),rounding=ROUND_HALF_UP));total+=mod
    for name,(n,w) in profile.items():
        if rows[name]!=n:reasons.append('%s题量%d/%d' % (name,rows[name],n))
    score=float(total.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    return dict(ready=not reasons,score=score if not reasons else None,known_score=score,
                reason='；'.join(dict.fromkeys(reasons)),modules=modules,unknown=unknown,
                profile='规则内参考表（默认地市级/行政执法130题）',
                rows=[dict(name=n,total=rows[n],ok=right[n],points=float(w)) for n,(_,w) in profile.items()])
