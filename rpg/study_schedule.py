"""两科备考时间线：存档study_schedule保存start/exam，日期覆盖引擎规则而不清空经验。
由Game初始化及设置API调用；首次行测沿用规则开始日，申论使用本机首次启用日期。
"""
import datetime as dt


def install(g):
    d=g.state.get('study_schedule')
    if not d:
        d={'start':g.t if g.subject=='申论' else g.rules.date('开始日期').isoformat(),
           'exam':g.rules.date('目标日').isoformat()}
        if d['exam']<=d['start']:d['exam']=(dt.date.fromisoformat(d['start'])+dt.timedelta(days=365)).isoformat()
        g.state['study_schedule']=d
    g.rules.raw.update({'开始日期':d['start'],'目标日':d['exam']})
    return view(g)


def view(g):
    d=g.state['study_schedule'];start=dt.date.fromisoformat(d['start']);exam=dt.date.fromisoformat(d['exam'])
    return dict(d,days=(exam-start).days,remaining=(exam-g.today).days,elapsed=max(0,(g.today-start).days),
                ideal_total=g.rules.num('每日理想经验')*(exam-start).days)


def save(g,body):
    try:start=dt.date.fromisoformat(body['start']);exam=dt.date.fromisoformat(body['exam'])
    except (ValueError,TypeError,KeyError):raise ValueError('请填写有效的开始学习日期和考试日期')
    if exam<=start:raise ValueError('考试日期必须晚于开始学习日期')
    if start>g.today:raise ValueError('开始学习日期不能晚于今天')
    g.state['study_schedule']={'start':start.isoformat(),'exam':exam.isoformat()}
    return install(g)
