"""实操领取目录，由申论API调用；只保存题号，不复制真题或另记成绩。
训练/题库/申论领取目录.json={schema:1,qids:[qid]}，同导入锁原子追加、重复领取幂等。
作答和批改状态实时读取原草稿/综合报告，旧版已有作答自动收录。
"""
import json
from . import shenlun_bank as bank, shenlun_review as review, shenlun_handwriting as hw

def path(p):return p.train/'题库'/'申论领取目录.json'

def read(p):
    if not path(p).exists():return {'schema':1,'qids':[]}
    try:
        d=json.loads(path(p).read_text(encoding='utf-8'))
        if not isinstance(d,dict) or d.get('schema')!=1 or not isinstance(d.get('qids'),list):raise ValueError()
        for qid in d['qids']:bank._safe(qid)
        return d
    except (OSError,ValueError,bank.BankError):raise bank.BankError('领取目录无法读取，请保留并核对训练/题库/申论领取目录.json')

def claim(p,body):
    with bank._IMPORT_LOCK:
        qids=body.get('qids')
        if not isinstance(qids,list) or not qids or len(qids)>100:raise bank.BankError('请选择1至100道题领取')
        known={q['qid'] for paper in bank.papers(p) for q in paper['questions']}
        for qid in qids:
            bank._safe(qid)
            if qid not in known:raise bank.BankError('领取的题目不存在，请刷新题库')
        d=read(p);added=0
        for qid in qids:
            if qid not in d['qids']:d['qids'].append(qid);added+=1
        if added:bank._write(path(p),d)
        return {'added':added,'count':len(d['qids'])}

def listing(p):
    with bank._IMPORT_LOCK:
        known={q['qid'] for paper in bank.papers(p) for q in paper['questions']}
        d=read(p);qids=list(dict.fromkeys(d['qids']));before=list(qids)
        # 旧版本没有领取日志；只收录实际有答案/笔迹/批改的题，空白计时草稿不算领取。
        for f in sorted((p.reviews/'草稿').glob('*.json')):
            if f.stem in known and f.stem not in qids:
                draft=bank.answer_get(p,f.stem)
                if str(draft.get('text') or '').strip() or hw.has_ink(draft.get('card') or {'pages':[]}):qids.append(f.stem)
        for f in sorted((p.reviews/'综合').glob('*')):
            if f.is_dir() and f.name in known and f.name not in qids and review.history(p,f.name):qids.append(f.name)
        if before!=qids:bank._write(path(p),{'schema':1,'qids':qids})
        out=[]
        for qid in qids:
            if qid not in known:continue
            draft=bank.answer_get(p,qid);history=review.history(p,qid);last=history[-1] if history else None
            has_draft=bank.answer_file(p,qid).exists()
            text=str(draft.get('text') or '').strip();card=draft.get('card') or {'pages':[]};ink=hw.has_ink(card)
            answered=bool(text or ink or (last and not has_draft))
            current=bool(last)
            if last and has_draft:
                oldcard=last['result'].get('answer_card') or {'pages':[]}
                current=text==str(last.get('answer') or '').strip() and (not (ink or hw.has_ink(oldcard)) or hw.digest(card)==hw.digest(oldcard))
            status='已批改' if current else '待批改' if answered else '未做'
            out.append({'qid':qid,'answered':answered,'status':status,
                        'score':last['result']['total'] if current else None,
                        'full':last['result']['full'] if current else None})
        return {'items':out}
