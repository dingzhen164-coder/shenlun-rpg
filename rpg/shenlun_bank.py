"""完整申论真题的本地题库（标准库，shenlun/api调用）。
训练/题库/申论真题/<paper-id>.json 保存试卷、材料、题目、参考资料。
训练/作答/草稿/<qid>.json 保存答案、revision、累计有效编辑秒数；不混入真题。
导入幂等、不覆盖；题干/材料原文只读。源SQLite只读，公开数据库只下载到训练目录。
"""
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import sqlite3
import threading
import urllib.request
from pathlib import Path
from contextlib import closing
from . import net


class BankError(Exception):
    pass

TYPES = ('归纳概括', '综合分析', '提出对策', '贯彻执行', '大作文')
SOURCE_COMMIT = '12cf8e73be8fd18f615782e7a5748b0ca7f39ce2'
SOURCE_FILES = [
 ('tiku.db.part-00',94371840,'6b74379677459d9c6593e97e0e3146137b94df21949c48a12e8ce9046db8d055'),
 ('tiku.db.part-01',94371840,'86ada256e4582f851f0a6219eb91b5886687fe20fa1ab1a311df01e100fa3fed'),
 ('tiku.db.part-02',94371840,'aaf0ef67dd80212efeae9ce029faa33e88e117bf8bf9dc7983c7ec8932d32c58'),
 ('tiku.db.part-03',35622912,'f912de24c492673892f843dbda8afe108bb769a8785768efb0c5dccd6c2e1644'),
 ('materials.db',27873280,'8d7d525183829cd0546bfb44c7155bf6ead9a0a3bdc240c1bcce8eb83d2e6d48')]
_JOB_LOCK = threading.Lock()
_IMPORT_LOCK = threading.RLock()
JOBS = {}
_CACHE = {}


def folder(p):
    return p.train / '题库' / '申论真题'


def _id(prefix, value):
    return prefix + hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:20]


def _safe(value):
    if not re.fullmatch(r'sl[pq]-[0-9a-f]{20}', str(value)):
        raise BankError('题目或试卷编号不正确')
    return value


def _write(f, d):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix('.tmp')
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(f)


def text(value):
    s = str(value or '')
    s = re.sub(r'<(?:br\s*/?|/p|/div|/li)>', '\n', s, flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ').strip()


def infer_type(stem):
    if re.search(r'自拟题目|自拟标题|议论文|写.{0,12}(?:文章|作文)', stem):
        return '大作文'
    if re.search(r'报告|讲话|发言|提纲|倡议|通知|公开信|宣传稿|工作方案|建议书|简报|短评|编者按|推介', stem):
        return '贯彻执行'
    if re.search(r'建议|对策|措施|解决', stem):
        return '提出对策'
    if re.search(r'理解|分析|评价|评析|谈谈|看法|解释', stem):
        return '综合分析'
    return '归纳概括'


def normalize(raw, origin='用户导入'):
    if not isinstance(raw, dict):
        raise BankError('每套试卷必须是一个对象')
    title = str(raw.get('title') or raw.get('name') or '').strip()
    if not title:
        raise BankError('试卷缺少标题')
    source = str(raw.get('sourceName') or raw.get('source') or origin)
    pid = _id('slp-', raw.get('source_id') or source + '|' + title)
    mats = []
    for i, m in enumerate(raw.get('materials') or []):
        if not isinstance(m, dict):
            raise BankError('材料格式不正确')
        body = str(m.get('text') or '').strip()
        if body:
            mats.append({'id': str(m.get('id') or i+1), 'label': str(m.get('label') or '材料%d' % (i+1)), 'text': body})
    if len({m['id'] for m in mats})!=len(mats):
        raise BankError('材料编号重复')
    qs = []
    for i, q in enumerate(raw.get('questions') or []):
        if not isinstance(q, dict):
            raise BankError('题目格式不正确')
        stem = str(q.get('text') or q.get('stem') or '').strip()
        if not stem:
            raise BankError('第%d题缺少题干' % (i+1))
        try:
            score, words = float(q.get('score') or q.get('total') or 0), int(q.get('limit') or q.get('words') or 0)
        except (ValueError, TypeError):
            raise BankError('分值或字数必须是数字')
        if not 0 <= score <= 150 or not 0 <= words <= 5000:
            raise BankError('分值或字数超出范围')
        typ = q.get('type') or infer_type(stem)
        if typ not in TYPES:
            raise BankError('题型必须是五种申论题型之一')
        mids = [str(x) for x in q.get('material_ids') or []]
        if any(x not in [m['id'] for m in mats] for x in mids):
            raise BankError('题目引用了不存在的材料')
        refs = [{'source': str(x.get('organization') or x.get('source') or '用户参考资料'),
                 'answer': str(x.get('answer') or '').strip()} for x in q.get('references') or [] if isinstance(x, dict) and x.get('answer')]
        qs.append({'qid': _id('slq-', pid+'|'+str(q.get('source_id') or i+1)), 'no': i+1, 'type': typ,
                   'stem': stem, 'requirement': str(q.get('requirement') or ''), 'total': score, 'words': words or None,
                   'material_ids': mids, 'references': refs, 'analysis': str(q.get('analysis') or '')})
    if len({q['qid'] for q in qs})!=len(qs):
        raise BankError('题目编号重复')
    if not qs:
        raise BankError('试卷至少需要一道题')
    year = str(raw.get('year') or (re.search(r'(20\d{2}|19\d{2})', title) or [''])[0])
    return {'id':pid, 'title':title, 'year':year, 'region':str(raw.get('region') or raw.get('category') or '其他'),
            'source':source, 'source_url':str(raw.get('source_url') or ''), 'edition':str(raw.get('edition') or '来源未注明版本'),
            'materials':mats, 'questions':qs, 'schema':1}


def import_packages(p, raw):
    raws = raw if isinstance(raw, list) else [raw]
    if not raws or len(raws)>1000:
        raise BankError('一次导入1至1000套试卷')
    # 先全部校验，再写入；不因后面的坏题导致前面半途入库。
    papers = [normalize(x) for x in raws]
    added = skipped = 0
    with _IMPORT_LOCK:
        for paper in papers:
            f = folder(p)/(paper['id']+'.json')
            if f.exists():
                skipped += 1
                continue
            _write(f,paper); added += 1
    return {'added':added,'skipped':skipped,'questions':sum(len(x['questions']) for x in papers)}


def papers(p):
    files=sorted(folder(p).glob('*.json'))
    sig=tuple((f.name,f.stat().st_mtime_ns,f.stat().st_size) for f in files)
    key=str(folder(p))
    if key in _CACHE and _CACHE[key][0]==sig: return _CACHE[key][1]
    out=[]
    for f in files:
        try:
            d=json.loads(f.read_text(encoding='utf-8'))
            if d.get('schema')==1: out.append(d)
        except (OSError,ValueError):
            continue
    if len(_CACHE)>4: _CACHE.clear()
    _CACHE[key]=(sig,out)
    return out


def listing(p):
    out=[]
    for d in papers(p):
        out.append({k:d[k] for k in ('id','title','year','region','source','edition')})
        out[-1].update(count=len(d['questions']), materials=len(d['materials']), questions=[
            {'qid':q['qid'],'no':q['no'],'type':q['type'],'total':q['total'],'words':q['words'],
             'stem':q['stem'],'complete':bool(d['materials']) and q['total']>0} for q in d['questions']])
    return sorted(out,key=lambda x:(x['year'],x['region'],x['title']),reverse=True)


def question(p,qid, reveal=False):
    _safe(qid)
    for paper in papers(p):
        for q in paper['questions']:
            if q['qid']==qid:
                d=dict(q, paper_id=paper['id'],paper_title=paper['title'],source=paper['source'],edition=paper['edition'])
                d['materials']=[m for m in paper['materials'] if not q['material_ids'] or m['id'] in q['material_ids']]
                d['complete']=bool(d['materials']) and d['total']>0
                if not reveal:
                    d.pop('references',None); d.pop('analysis',None)
                return d
    raise BankError('题目不存在')


def answer_file(p,qid):
    return p.reviews / '草稿' / (_safe(qid)+'.json')


def answer_get(p,qid):
    f=answer_file(p,qid)
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'qid':qid,'text':'','revision':0,'seconds':0}


def answer_save(p,body):
    # revision检查和原子替换作为一个临界区，两个标签页不能同时写入旧版本。
    with _IMPORT_LOCK:
        return _answer_save(p,body)


def _answer_save(p,body):
    qid=body.get('qid'); question(p,qid)
    old=answer_get(p,qid)
    if type(body.get('revision')) is not int or body.get('revision')!=old['revision']:
        raise BankError('答案已在另一处更新，请保留当前文字，再重新打开题目')
    value=str(body.get('text') or '')
    if len(value)>30000: raise BankError('答案太长')
    d={'qid':qid,'text':value,'revision':old['revision']+1,'seconds':old['seconds'],
       'updated':dt.datetime.now().isoformat(timespec='seconds')}
    # 用两次真实编辑之间的服务端时间记录有效用时，长时间离开不计。
    if old.get('updated') and value!=old['text']:
        elapsed=(dt.datetime.now()-dt.datetime.fromisoformat(old['updated'])).total_seconds()
        if 0<elapsed<=120: d['seconds']+=round(elapsed)
    _write(answer_file(p,qid),d)
    return d


def import_sqlite(p, dbfile, matfile):
    added=skipped=questions=0
    with closing(sqlite3.connect(Path(dbfile).resolve().as_uri()+'?mode=ro',uri=True)) as db, closing(sqlite3.connect(Path(matfile).resolve().as_uri()+'?mode=ro',uri=True)) as md:
        db.row_factory=md.row_factory=sqlite3.Row
        for row in db.execute("SELECT * FROM papers WHERE subjectName IN ('公务员·申论','申论') ORDER BY id"):
            r=dict(row)
            mats=[{'id':str(m['idx']),'label':m['title'] or '材料%s'%m['idx'],'text':m['text']} for m in md.execute('SELECT * FROM materials WHERE paperId=? ORDER BY idx',(r['id'],))]
            qs=[]
            for qrow in db.execute('SELECT * FROM questions WHERE paperId=? ORDER BY id',(r['id'],)):
                q=dict(qrow); stem=text(q['content'] or q.get('contentHtml'))
                if not stem: continue
                sm=re.search(r'[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]',stem)
                if not sm: sm=re.search(r'(?:本题|满分|分值|计)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*分',stem)
                if not sm: sm=re.search(r'(\d+(?:\.\d+)?)\s*分',stem)
                wm=re.search(r'(?:不超过|不多于|最多|以内|限)\s*(\d+)\s*字',stem)
                if not wm: wm=re.search(r'(?:\d+\s*[-—～~至到]\s*)?(\d+)\s*字',stem)
                if re.search(r'不少于\s*\d+\s*字',stem) and not re.search(r'不超过|不多于|最多|[-—～~至到]',stem): wm=None
                refs=[{'source':'来源库参考资料（非官方细则）','answer':text(q.get('answer'))}] if q.get('answer') else []
                qs.append({'source_id':'errrc-question-'+str(q['questionId']),'text':stem,'score':float(sm.group(1)) if sm else 0,
                           'limit':int(wm.group(1)) if wm else 0,'references':refs,'analysis':text(q.get('analysis'))})
            if not qs: continue
            data={'source_id':'errrc-paper-'+str(r['id']),'title':r['name'],'region':r['category'],'materials':mats,'questions':qs,
                  'sourceName':'ERRRC/kaogong-shuati','source_url':'https://github.com/ERRRC/kaogong-shuati',
                  'edition':'网友回忆版' if '回忆' in r['name'] else '来源库真题（未核验官方原卷）'}
            result=import_packages(p,data); added+=result['added'];skipped+=result['skipped'];questions+=result['questions']
    return {'added':added,'skipped':skipped,'questions':questions}


def _digest(f):
    h=hashlib.sha256()
    with f.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def source_status(p):
    with _JOB_LOCK:
        return dict(JOBS.get(str(p.train),{'running':False,'message':'尚未下载','progress':0}))


def source_start(p):
    key=str(p.train)
    with _JOB_LOCK:
        if JOBS.get(key,{}).get('running'): return dict(JOBS[key])
        JOBS[key]={'running':True,'message':'准备下载题库（约330MB）','progress':0}
    def update(**data):
        with _JOB_LOCK: JOBS[key].update(data)
    def run():
        try:
            dest=p.train/'题库原始库'; dest.mkdir(parents=True,exist_ok=True)
            total=sum(x[1] for x in SOURCE_FILES);done=0
            for name,size,sha in SOURCE_FILES:
                f=dest/name
                if f.exists() and f.stat().st_size==size and _digest(f)==sha:
                    done+=size;continue
                tmp=f.with_suffix('.download')
                url='https://raw.githubusercontent.com/ERRRC/kaogong-shuati/'+SOURCE_COMMIT+'/'+name
                update(message='正在下载 '+name)
                req=urllib.request.Request(url,headers={'User-Agent':'shenlun-rpg'})
                with net.urlopen(req,timeout=60) as response, tmp.open('wb') as out:
                    n=0
                    while True:
                        chunk=response.read(1024*1024)
                        if not chunk:break
                        out.write(chunk);n+=len(chunk)
                        if n>size:raise BankError('题库文件长度异常')
                        update(progress=round((done+n)/total*90))
                if tmp.stat().st_size!=size or _digest(tmp)!=sha:
                    tmp.unlink();raise BankError('题库校验失败，请重新下载')
                tmp.replace(f);done+=size
            dbfile=dest/'tiku.db';temp=dbfile.with_suffix('.tmp')
            if not dbfile.exists() or dbfile.stat().st_size!=sum(x[1] for x in SOURCE_FILES[:-1]):
                with temp.open('wb') as out:
                    for name,_,_ in SOURCE_FILES[:-1]:
                        with (dest/name).open('rb') as src: shutil.copyfileobj(src,out)
                temp.replace(dbfile)
            update(message='下载校验完成，正在录入真题',progress=95)
            result=import_sqlite(p,dbfile,dest/'materials.db')
            update(running=False,message='录入完成：新增%d套，已有%d套保留'%(result['added'],result['skipped']),progress=100,result=result)
        except Exception as e:
            update(running=False,message='录入未完成：'+str(e),error=True)
    threading.Thread(target=run,daemon=True).start()
    return source_status(p)
