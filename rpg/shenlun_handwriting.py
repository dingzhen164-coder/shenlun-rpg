"""申论红格答题卡：草稿card={pages:[{strokes:[{points:[[x,y]],erase,width}]}]}。
笔迹/文字共享草稿revision；OCR只转录原文，确认后的card哈希随草稿及报告保存。
计时使用服务端时间及独占会话，闲置/暂停不计分不奖励，仅统计作答秒数。
"""
import hashlib
import json
import math
import time
from . import shenlun_bank as bank
from . import ai, notes, report


def card(value):
    if value is None:return {'pages':[]}
    if not isinstance(value,dict) or not isinstance(value.get('pages'),list) or len(value['pages'])>10:
        raise bank.BankError('答题卡页数不正确（最多10页）')
    layout=value.get('layout',1)
    if type(layout) is not int or layout not in (1,2):raise bank.BankError('答题卡排版版本不正确')
    max_height=1360 if layout==2 else 900
    count=0;out=[]
    for page in value['pages']:
        if not isinstance(page,dict) or not isinstance(page.get('strokes'),list):raise bank.BankError('答题卡笔迹格式不正确')
        strokes=[]
        for stroke in page['strokes']:
            if not isinstance(stroke,dict) or not isinstance(stroke.get('points'),list):raise bank.BankError('笔画格式不正确')
            pts=[]
            for xy in stroke['points']:
                if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in xy):raise bank.BankError('笔迹坐标不正确')
                if not (0<=xy[0]<=1040 and 0<=xy[1]<=max_height):raise bank.BankError('笔迹超出答题区域')
                pts.append(xy)
            count+=len(pts)
            if count>100000:raise bank.BankError('答题卡笔迹太多，请分题练习')
            w=stroke.get('width',3)
            if type(w) not in (int,float) or not 1<=w<=30:raise bank.BankError('笔宽不正确')
            strokes.append({'points':pts,'erase':bool(stroke.get('erase')),'width':w})
        out.append({'strokes':strokes})
    return {'pages':out,'layout':2} if layout==2 else {'pages':out}


def digest(c):return hashlib.sha256(json.dumps(c,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()

def has_ink(c):return any(s['points'] and not s['erase'] for p in c.get('pages',[]) for s in p['strokes'])


def clock(p,body):
    qid=body.get('qid');bank.question(p,qid);session=str(body.get('session') or '')
    if len(session)!=32 or any(c not in '0123456789abcdef' for c in session):raise bank.BankError('计时会话不正确')
    with bank._IMPORT_LOCK:
        d=bank.answer_get(p,qid);now=time.time();old=d.get('clock') or {};last=old.get('last',now)
        if old.get('running') and old.get('session')!=session and 0<=now-last<30:raise bank.BankError('另一页面正在计时，请先暂停或关闭它')
        if old.get('session')==session and old.get('running') and 0<=now-last<=25:
            d['seconds']=d.get('seconds',0)+round(now-last)
        d['clock']={'session':session,'last':now,'running':bool(body.get('active'))}
        bank._write(bank.answer_file(p,qid),d)
        return {'seconds':d['seconds'],'running':d['clock']['running']}


def recognize(p,body):
    qid=body.get('qid');before=bank.answer_get(p,qid);bank.question(p,qid)
    if before['revision']!=body.get('revision'):raise bank.BankError('答题卡已更新，请保存最新笔迹再识别')
    images=body.get('images')
    if not isinstance(images,list) or not 1<=len(images)<=10 or any(not isinstance(x,str) or len(x)>2800000 for x in images):raise bank.BankError('识别图片过大或页数不正确')
    pngs=[]
    for x in images:
        try:b=notes._png(x)
        except Exception:raise bank.BankError('识别图片格式不正确')
        if not b.startswith(b'\x89PNG\r\n\x1a\n') or len(b)<24:raise bank.BankError('请使用PNG答题卡图片')
        w=int.from_bytes(b[16:20],'big');h=int.from_bytes(b[20:24],'big')
        if not 0<w<=1500 or not 0<h<=(1360 if before.get('card',{}).get('layout')==2 else 1200):raise bank.BankError('识别图片尺寸过大')
        pngs.append(b)
    if ai.vision_available():
        content=[{'type':'text','text':'逐页忠实转录这份申论手写答案，只输出原文字，不润色、不补充、不修正内容。保留段落及标点，忽略格线，认不清的字写［?］。'}]
        content.extend({'type':'image_url','image_url':{'url':x}} for x in images)
        text=ai.chat([{'role':'user','content':content}],vision=True,temperature=0,max_tokens=6000,timeout=240);engine='识图模型'
    else:
        try:text='\n'.join(report.ocr(b).strip() for b in pngs);engine='系统OCR'
        except report.ReportError as e:raise bank.BankError(str(e))
    text=str(text).strip()
    if not text:raise bank.BankError('未识别出文字，请检查笔迹或在核对框手动录入')
    if len(text)>30000:raise bank.BankError('识别文字过长')
    if bank.answer_get(p,qid)['revision']!=before['revision']:raise bank.BankError('识别期间答题卡已修改，请重新识别')
    return {'text':text,'engine':engine,'revision':before['revision'],'card_hash':digest(before.get('card') or card(None))}
