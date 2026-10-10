"""申论主题标签，供题库列表和实操筛选；不改变题库原文或评分指纹。
训练/题库/申论主题分类.json={schema:1,revision,labels:{paper/qid:[主题]}}。
只按明确关键词辅助分类；无指定材料的题用题干，必要时回退整卷主题并标明范围。
"""
import json
import re

TOPICS={
    '农村':('农村','乡村','农民','农业','振兴','三农','农田','村庄'),
    '科技':('科技','科研','科学技术','人工智能','数字化','大数据','技术创新','机器人','研发'),
    '基层治理':('基层','社区','网格','居委会','村委会','自治','基层治理'),
    '经济发展':('经济','产业','企业','营商','市场','就业','创业'),
    '生态环保':('生态','环保','污染','环境保护','绿色发展','碳排放'),
    '民生保障':('民生','养老','医疗','社会保障','公共服务','住房'),
    '文化教育':('文化','教育','学校','教师','非遗','传承'),
    '法治建设':('法治','法律','执法','司法','法制','法规')}

def path(p):return p.train/'题库'/'申论主题分类.json'

def read(p):
    from .shenlun_bank import BankError
    f=path(p)
    if not f.exists():return {'schema':1,'revision':0,'labels':{}}
    try:
        d=json.loads(f.read_text(encoding='utf-8'))
        if d.get('schema')!=1 or type(d.get('revision')) is not int or not isinstance(d.get('labels'),dict):raise ValueError()
        if any(not isinstance(k,str) or not isinstance(v,list) or len(v)>8 or any(not isinstance(t,str) or not 1<=len(t.strip())<=24 or re.search(r'[\x00-\x1f]',t) for t in v) for k,v in d['labels'].items()):raise ValueError()
        return d
    except (ValueError,OSError,AttributeError):raise BankError('主题分类文件无法读取，请保留并核对训练/题库/申论主题分类.json')

def infer(text):return [name for name,words in TOPICS.items() if any(w in text for w in words)]

_AUTO={}

def classify(p,source,listing):
    d=read(p);labels=d['labels'];cache=_AUTO.get(str(p.train))
    if not cache or cache[0] is not source:
        inferred={}
        for raw in source:
            alltext=raw['title']+'\n'+'\n'.join(m['text'] for m in raw['materials'])+'\n'+'\n'.join(q['stem'] for q in raw['questions'])
            inferred[raw['id']]=(infer(alltext),'整卷资料')
            for q in raw['questions']:
                mids=q.get('material_ids') or []
                text=q['stem']+'\n'+'\n'.join(m['text'] for m in raw['materials'] if m['id'] in mids)
                inferred[q['qid']]=(infer(text),'本题资料' if mids else '题干')
        if len(_AUTO)>=4:_AUTO.clear()
        cache=(source,inferred);_AUTO[str(p.train)]=cache
    inferred=cache[1]
    for paper in listing:
        paper['topics']=labels.get(paper['id'],inferred[paper['id']][0]) or ['待标注']
        paper['topic_manual']=paper['id'] in labels
        for q in paper['questions']:
            tags,scope=inferred[q['qid']];q['topic_manual']=q['qid'] in labels
            q['topics']=labels.get(q['qid'],tags or paper['topics']) or ['待标注']
            q['topic_scope']='手动标注' if q['topic_manual'] else scope if tags else '整卷主题'
    return d['revision']


def save(p,body):
    from . import shenlun_bank as bank
    with bank._IMPORT_LOCK:
        source=bank.papers(p);keys={x['id'] for x in source}|{q['qid'] for x in source for q in x['questions']}
        key=body.get('id');d=read(p)
        if key not in keys:raise bank.BankError('该题目或试卷不存在')
        if type(body.get('revision')) is not int or body['revision']!=d['revision']:raise bank.BankError('主题标签已在另一处更新，请重新打开分类窗口')
        if body.get('automatic'):d['labels'].pop(key,None)
        else:
            values=body.get('topics')
            if not isinstance(values,list) or len(values)>8:raise bank.BankError('主题最多选择8项')
            clean=[]
            for value in values:
                if not isinstance(value,str) or not 1<=len(value.strip())<=24 or re.search(r'[\x00-\x1f]',value):raise bank.BankError('主题名称需要1至24个字且不能包含控制字符')
                value=value.strip()
                if value not in clean:clean.append(value)
            d['labels'][key]=clean
        d['revision']+=1;bank._write(path(p),d)
        return {'revision':d['revision']}
