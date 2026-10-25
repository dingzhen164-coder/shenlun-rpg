"""独立消化清单PDF：按原空位展示，答案仅取显式答案或配套原文的唯一匹配。

wanxiang_journal注册API；训练/时政消化/<目标摘要>.json存PDF模板，原文/<PDF摘要>.pdf留原件，
进度/<目标摘要>.json单独保存。标红不决定空位；不调用AI，不改讲义、批注或修为。

导入不再选择配套讲义（3.7.4）：每一段清单用它的上下文文字去所有已导入的冲刺讲义、月半、专题里找出处，
找到的段落分配到对应资料（同一份PDF拆出的几篇讲义共用时归到“整份讲义”），分段保存在各资料的清单里，
每段记src（在PDF里的序号）以便重复导入不叠加；找不到出处的段落不导入、不猜，导入结果里如实告知。
"""
import base64
import hashlib
import re
import unicodedata
from pathlib import Path

from . import politics

BLANK = re.compile(r'(?:[_＿﹍﹎][ \t]*){2,}|（[ \u3000]*）|\([ \u3000]{2,}\)')
NUMBER = re.compile(r'^\s*(\d+)[.．、]\s*')


RV = 3          # 识别规则版本（3：整份保留全文——标题、没有空的段落、加粗都留下）：同一份PDF在旧版本导入的，再次导入时按新规则重新识别（见import_pdf）
_ASCII_PUNCT = {'(': '（', ')': '）', ',': '，', ';': '；', ':': '：', '!': '！', '?': '？'}


def _fold(ch):
    """比对用的字符折叠：全角字母数字、％等折成半角；半角标点折成中文全角标点（PDF与原文常在这两种写法间不一致）。"""
    if ch in _ASCII_PUNCT:return _ASCII_PUNCT[ch]
    one=unicodedata.normalize('NFKC',ch)
    return one if len(one)==1 and one not in _ASCII_PUNCT else ch


def norm(text):
    return ''.join(_fold(c) for c in re.sub(r'\s+', '', text))


def resolve(g, target):
    """只接受资料身份，不能由客户端指定文件路径或匹配原文。"""
    from . import wanxiang_journal as journal
    if not isinstance(target, dict):
        raise politics.PoliticsError('请选择配套研读讲义')
    if target.get('source') == 'atlas':
        exam = politics.exam_id(target.get('exam'))
        materials = politics.atlas(g.paths, exam)['materials']
        if target.get('bundle'):
            bundle = str(target['bundle'])
            if not re.fullmatch(r'[0-9a-f]{64}', bundle):
                raise politics.PoliticsError('配套讲义编号无效')
            chosen = [m for m in materials if Path(m.get('pdf', '')).stem == bundle and not m.get('practice_only')]
            desc = {'source': 'atlas', 'exam': exam, 'bundle': bundle}
        else:
            chosen = [m for m in materials if m['id'] == target.get('material') and not m.get('practice_only')]
            desc = {'source': 'atlas', 'exam': exam, 'material': target.get('material')}
        if not chosen:
            raise politics.PoliticsError('配套研读讲义不存在，请重新选择')
        return desc, chosen, chosen[0].get('pdf_name') or chosen[0]['title']
    if target.get('source') == 'wanxiang_journal':
        data = journal.load(g.paths, target.get('kind'), target.get('id'))
        desc = {'source': 'wanxiang_journal', 'kind': target['kind'], 'id': target['id']}
        return desc, data, data['title']
    raise politics.PoliticsError('配套讲义来源无效')


def _underlines(page):
    """页上所有水平线段（线、细长矩形、细长四边形都算，Word/WPS导出的下划线写法不同），首尾相接的合并成一条。"""
    segs=[]
    for drawing in page.get_drawings():
        for item in drawing['items']:
            kind=item[0]
            if kind=='l':
                a,b=item[1],item[2]
                if abs(a.y-b.y)<=.7:segs.append([min(a.x,b.x),max(a.x,b.x),(a.y+b.y)/2])
            elif kind in ('re','qu'):
                r=item[1] if kind=='re' else item[1].rect
                if r.height<=1.8 and r.width>=4:segs.append([r.x0,r.x1,(r.y0+r.y1)/2])
    segs.sort(key=lambda s:(round(s[2]),s[0]))
    merged=[]
    for seg in segs:
        if merged and abs(merged[-1][2]-seg[2])<=.8 and seg[0]-merged[-1][1]<=1.5:merged[-1][1]=max(merged[-1][1],seg[1])
        else:merged.append(seg)
    return [m for m in merged if m[1]-m[0]>=10]


def _bold(span):
    return bool(span['flags']&16) or bool(re.search(r'bold|black|heavy|黑体|粗',span.get('font',''),re.I))


def _pdf_lines(doc):
    """逐字提取，返回 [(这一行的文字, 加粗字符占比)]；绘制下划线按下面的规则认成空：
    贴着基线下方，不压在有字的地方（空格不算有字，被下划线盖住的空格整段换成一个空）；
    左右至少一侧紧挨着文字——所以行首、行尾、字中间的空都认，页眉线、表格线、字下面的强调下划线不会被当成空。"""
    from .wanxiang_journal import NOISE
    result=[]
    for page in doc:
        rows={}
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    chars=span.get('chars',[])
                    if ''.join(c['c'] for c in chars).strip() in NOISE:
                        continue
                    row=rows.setdefault(round(span['origin'][1],1),[]);bold=_bold(span)
                    for c in chars:row.append([c['bbox'][0],c['bbox'][2],c['c'],bold,False])     # x0,x1,字,加粗,是否被下划线盖住的空格
        for left,right,line_y in _underlines(page):
            candidates=[y for y in rows if -1<=line_y-y<=5.5]
            if not candidates:continue
            row=rows[min(candidates,key=lambda y:abs(line_y-y))]
            solid=[c for c in row if c[2].strip() and c[4] is False]
            if any(c[0]<right-2 and c[1]>left+2 for c in solid):continue
            if not (any(0<=left-c[1]<=8 for c in solid) or any(0<=c[0]-right<=8 for c in solid)):continue
            covered=[c for c in row if not c[2].strip() and left-1<=(c[0]+c[1])/2<=right+1]
            if covered:
                for c in covered:c[4]=True
            else:row.append([left,right,'',False,True])
        for y,row in sorted(rows.items()):
            cells=[];gap=False                                  # [(字, 是否加粗)]：留着逐字的加粗信息，段落里的加粗重点才能原样显示
            for c in sorted(row,key=lambda c:(c[0],c[1])):
                if c[4]:
                    if not gap:cells+=[('_',False)]*4;gap=True
                else:cells+=[(ch,bool(c[3])) for ch in c[2]];gap=False
            text=''.join(ch for ch,_ in cells)
            drop={i for m in re.finditer(r'(?<=[^\x00-\x7f])[ \t]+(?=[^\x00-\x7f])',text) for i in range(m.start(),m.end())}      # 中文字符之间的空格是排版留下的，不是内容
            cells=[c for i,c in enumerate(cells) if i not in drop]
            while cells and not cells[0][0].strip():cells.pop(0)
            while cells and not cells[-1][0].strip():cells.pop()
            text=''.join(ch for ch,_ in cells)
            letters=[c for c in row if c[2].strip()]
            weight=sum(c[3] for c in letters)/max(1,len(letters))
            if not text.strip() or (y>page.rect.height*.9 and re.fullmatch(r'\s*\d{1,3}\s*',text)):continue
            result.append((text,weight,''.join('1' if b else '0' for _,b in cells)))
    return result


HEADING = re.compile(r'^(?:[一二三四五六七八九十]+[、．]|[（(][一二三四五六七八九十]+[）)]|第[一二三四五六七八九十]+[部章节篇])')


def _is_heading(line,weight,current):
    """标题：独占一行、没有空、不带句内标点；整行加粗或以“一、”“（一）”“第一部分”开头。标题自成一段，不并进下面的正文。"""
    if BLANK.search(line) or len(line)>40 or re.search(r'[，。；！？：]',line):return False
    if current and not re.search(r'[。！？；]$',current):return False       # 上一段还没写完，这一行是它的续行
    return bool(HEADING.match(line)) or weight>=.9


def parse_pdf(content):
    try:
        import pymupdf as fitz
    except ImportError:
        raise politics.PoliticsError('缺少PDF组件，请使用完整电脑安装包')
    try:
        with fitz.open(stream=content,filetype='pdf') as doc:
            if doc.needs_pass:raise politics.PoliticsError('请先解密PDF')
            lines=_pdf_lines(doc)
    except (RuntimeError, ValueError) as error:
        raise politics.PoliticsError('PDF无法读取：'+str(error))
    if not lines:raise politics.PoliticsError('PDF没有可提取文字，请先做OCR')
    blocks,answers,current,cmask=[],{},'',''
    in_answers=False
    def flush():
        nonlocal current,cmask
        if current.strip():blocks.append({'text':current,'mask':cmask,'kind':'p'})
        current=cmask=''
    for line,weight,mask in lines:
        if re.fullmatch(r'(?:参考)?答案(?:与解析)?[：:]?',line) or line.endswith('·答案与解析'):
            flush();in_answers=True;continue
        if not BLANK.search(line) and re.search(r'消化清单|填空练习',line):
            flush();continue
        if in_answers:
            m=NUMBER.match(line)
            if m:answers[m.group(1)]=re.sub(r'^(?:【答案】|答案[：:])','',line[m.end():]).split('解析：')[0].strip('。 ')
            continue
        heading=_is_heading(line,weight,current)
        if NUMBER.match(line) or heading or (current and re.search(r'[。！？；]$',current)):
            flush()
        if heading:blocks.append({'text':line,'mask':mask,'kind':'h'});continue     # 3.7.6：小标题单独成块保留，让每一段都找得到位置
        if current and re.search(r'[A-Za-z]$',current) and re.match(r'[A-Za-z]',line):current+=' ';cmask+='0'
        current+=line;cmask+=mask
    flush()
    blanked=[b for b in blocks if BLANK.search(b['text'])]
    if not blanked:raise politics.PoliticsError('未识别到清单空位；支持文字下划线、空括号和文字行中的空白下划线，扫描版请先OCR')
    numbers=[NUMBER.match(b['text']).group(1) if NUMBER.match(b['text']) else None for b in blanked]      # 题号只在有空的段里数，没有空的段（小标题、普通句子）不参与
    out=[]
    for b in blocks:
        text=b['text'];count=len(BLANK.findall(text));provided=[]
        no=NUMBER.match(text).group(1) if count and NUMBER.match(text) else None
        if no and numbers.count(no)==1 and no in answers:
            value=answers[no]
            provided=[value] if count==1 else [v.strip() for v in re.split(r'[、；;|｜]',value)]
            if len(provided)!=count:provided=[]
        row={'text':text,'provided':provided,'kind':b['kind']}
        runs=[[m.start(),m.end()] for m in re.finditer('1+',b['mask'])] if b['kind']=='p' else []
        if runs:row['bold']=runs
        out.append(row)
    return out


_SEP='，。；：！？、'


def match_answers(template, sources):
    """枚举明确上下文的所有匹配；有歧义、无上下文或复杂度超限均不填。
    空在整段开头/结尾时（3.7.6）：按“一个分句”取答案——开头的空从上一个逗号/句号之后到后面的固定文字，
    结尾的空从前面的固定文字到下一个逗号/句号；只在原文单句里找，仍须唯一才填。"""
    stripped=NUMBER.sub('',template)
    pieces=[norm(s) for s in BLANK.split(stripped)]
    count=len(pieces)-1
    lead,trail=not pieces[0],not pieces[-1]
    if not count or sum(map(len,pieces))<4 or any(not x for x in pieces[1:-1]) or (count==1 and (lead or trail) and len(pieces[0]+pieces[1])<4):
        return [None]*count
    candidates=[];budget=[0]
    def clause_end(text,cursor):
        ends=[i for i in (text.find(c,cursor) for c in _SEP) if i>=0]
        return min(ends) if ends else len(text)
    def walk(text,k,cursor,values):
        budget[0]+=1
        if budget[0]>2000:return
        literal=pieces[k+1]
        if not literal:
            answer=text[cursor:clause_end(text,cursor)]
            if 0<len(answer)<=40:candidates.append(values+[answer])
            return
        at=text.find(literal,cursor+1)
        while at>=0 and at-cursor<=120:
            answer=text[cursor:at]
            if not re.search(r'[。！？；]',answer):
                if k+1==count:candidates.append(values+[answer])
                else:walk(text,k+1,at+len(literal),values+[answer])
            at=text.find(literal,at+1)
    for n,source in enumerate(sources):
        for m,raw in enumerate([source]+re.split(r'\n\s*\n|(?<=[。！？；])',source)):
            if m==0 and (lead or trail):continue         # 分句边界只在单句里可靠：整篇原文拼起来会把标题、前一段的字算进答案
            text=norm(raw)
            if not text:continue
            if lead:
                for found in re.finditer(re.escape(pieces[1]),text):
                    start=max([text.rfind(c,0,found.start()) for c in _SEP]+[-1])+1
                    answer=text[start:found.start()]
                    if not 0<len(answer)<=40:continue
                    if count==1:candidates.append([answer])
                    else:walk(text,1,found.end(),[answer])
                    if budget[0]>2000:return [None]*count
                continue
            starts=[m2.start()+len(pieces[0]) for m2 in re.finditer('(?='+re.escape(pieces[0])+')',text)]
            for start in starts:
                walk(text,0,start,[])
                if budget[0]>2000:return [None]*count
    return [next(iter(values)) if len(values)==1 else None for values in [{row[i] for row in candidates} for i in range(count)]]


def _store(g, desc):
    return g.paths.train/'时政消化'/(politics.digest(desc)+'.json')


def _pool(chosen,desc):
    return [m['original'] for m in chosen] if desc['source']=='atlas' else ['\n'.join(n['paras']) for n in chosen['news']]


def _legacy(g,desc,chosen):
    if desc['source']=='atlas':
        m=chosen[0]
        progress=politics.progress(g.paths,desc['exam']).get('digest',{})
        return [(m.get('cloze',[]),m['title'],m['id'],progress)]
    from . import wanxiang_journal as journal
    progress=journal.progress_of(g,desc['kind'],desc['id'])['cloze']
    return [(chosen['cloze'],chosen['title'],'',progress)]


def _fill_file(g,key):
    return g.paths.train/'时政消化/补全'/(key+'.json')


def _literals(text,a,b,bold,whole):
    """text[a:b]这一段普通文字 → [{'t':文字,'b':是否加粗}]；整段加粗（小标题）直接标成粗体。"""
    if a>=b:return []
    if whole:return [{'t':text[a:b],'b':True}]
    cuts=sorted({a,b}|{x for run in bold for x in run if a<x<b});out=[]
    for x,y in zip(cuts,cuts[1:]):
        out.append({'t':text[x:y],'b':True} if any(s<=x and y<=e for s,e in bold) else {'t':text[x:y]})
    return out


def get(g, target):
    desc,chosen,label=resolve(g,target)
    descriptors=[(desc,chosen)]
    if desc['source']=='atlas' and desc.get('material'):
        stem=Path(chosen[0].get('pdf','')).stem
        if re.fullmatch(r'[0-9a-f]{64}',stem):
            bundle={'source':'atlas','exam':desc['exam'],'bundle':stem}
            _,all_materials,_=resolve(g,bundle);descriptors.append((bundle,all_materials))
    rows=[];progress={};items=[];documents=[]
    for owner,readings in descriptors:
        key=politics.digest(owner)
        saved=politics.read_json(_store(g,owner),{'documents':[]})
        memory=politics.read_json(g.paths.train/'时政消化/进度'/(key+'.json'),{})
        fills=politics.read_json(_fill_file(g,key),{})
        for document in saved['documents']:
            documents.append(document['name'])
            for i,row in enumerate(document['paragraphs']):
                text=row['text'];kind=row.get('kind','p')
                if not BLANK.search(text):          # 3.7.6：没有空的句子和小标题照样保留，保持PDF原来的上下文
                    rows.append({'title':document['name'],'kind':kind,'parts':_literals(text,0,len(text),row.get('bold',[]),kind=='h')})
                    continue
                answers=match_answers(text,_pool(readings,owner))
                parts=[];at=0;spans=list(BLANK.finditer(text))
                for k,m in enumerate(spans):
                    parts+=_literals(text,at,m.start(),row.get('bold',[]),False);at=m.end()
                    explicit=row['provided'][k] if k<len(row.get('provided',[])) else None
                    bkey=politics.digest([document['hash'],i,k]);fill=fills.get(bkey)
                    answer=explicit or answers[k] or fill
                    # 手动补全的空编号不含答案：改答案不丢核对记号
                    ident=(key+':f'+bkey[:22]) if fill and not (explicit or answers[k]) else key+':'+politics.digest([document['hash'],i,k,answer])[:24]
                    status='provided' if explicit else 'matched' if answers[k] else 'filled' if fill else 'pending'
                    part={'id':ident,'a':answer,'status':status,'owner':owner,'bkey':bkey}
                    parts.append(part);items.append(part);progress[ident]=memory.get(ident)
                parts+=_literals(text,at,len(text),row.get('bold',[]),False)
                rows.append({'title':document['name'],'kind':kind,'parts':parts})
    # 兼容原PDF内已有消化清单，但不从红字/独立回忆问答生成空位。
    if not documents:
        for old_rows,title,mid,old_progress in _legacy(g,desc,chosen):
            for i,row in enumerate(old_rows):
                parts=[]
                for k,p in enumerate(row['parts']):
                    if 'a' not in p:parts.append({'t':p.get('t','')});continue
                    legacy=('%s:blank:%s:%s'%(mid,i,k)) if mid else '%s-%s'%(i,k)
                    ident='legacy:'+politics.digest([desc,legacy])[:24]
                    part={'id':ident,'a':p.get('a') or None,'status':'matched' if p.get('a') else 'pending','legacy':legacy,'owner':desc}
                    parts.append(part);items.append(part)
                    value=old_progress.get(legacy)
                    progress[ident]=('remember' if value==1 else 'forgot' if value==0 else value)
                if any('id' in p for p in parts):rows.append({'title':title,'parts':parts})
    counts={'blanks':len(items),'ready':sum(bool(p['a']) for p in items),'pending':sum(not p['a'] for p in items),
            'seen':sum(p['a'] is not None and progress.get(p['id']) in ('remember','forgot') for p in items),
            'forgot':sum(p['a'] is not None and progress.get(p['id'])=='forgot' for p in items)}
    return {'target':desc,'label':label,'paragraphs':rows,'items':items,'progress':progress,'counts':counts,'documents':documents}


def fill(g, body):
    """待补全的空由用户自己填答案：只存在补全文件里（按空位置，不改清单模板与讲义）；填空文字为空＝取消补全。"""
    data=get(g,body.get('target'))
    item=next((p for p in data['items'] if p['id']==body.get('id')),None)
    if not item or item['status'] not in ('pending','filled'):raise politics.PoliticsError('这个空已有明确答案，或不属于此清单，不能补全')
    text=re.sub(r'\s+',' ',str(body.get('text') or '')).strip()
    if len(text)>80:raise politics.PoliticsError('补全的答案太长，请精简到80字以内')
    with politics._LOCK:
        file=_fill_file(g,politics.digest(item['owner']));fills=politics.read_json(file,{})
        if text:fills[item['bkey']]=text
        else:fills.pop(item['bkey'],None)
        file.parent.mkdir(parents=True,exist_ok=True);politics.atomic_json(file,fills)
    return get(g,body['target'])


def mark(g, body):
    data=get(g,body.get('target'));value=body.get('value')
    if value not in ('remember','forgot',None):raise politics.PoliticsError('消化状态无效')
    item=next((p for p in data['items'] if p['id']==body.get('id') and p['a']),None)
    if not item:raise politics.PoliticsError('该空待补全或不属于此清单，不能记录核对结果')
    owner=item['owner']
    if item.get('legacy') and owner['source']=='atlas':
        politics.set_progress(g.paths,dict(exam=owner['exam'],field='digest',id=item['legacy'],value=value))
    elif item.get('legacy'):
        from . import wanxiang_journal as journal
        memory=journal.progress_of(g,owner['kind'],owner['id'])['cloze']
        if value is None:memory.pop(item['legacy'],None)
        else:memory[item['legacy']]=1 if value=='remember' else 0
    else:
        file=g.paths.train/'时政消化/进度'/(politics.digest(owner)+'.json')
        memory=politics.read_json(file,{})
        if value is None:memory.pop(item['id'],None)
        else:memory[item['id']]=value
        politics.atomic_json(file,memory)
    return get(g,body['target'])


def _candidates(g):
    """所有可作为出处的资料：[(资料身份, 文本列表, 同一份讲义PDF的摘要)]；练习占位材料不算。"""
    from . import wanxiang_journal as journal
    out=[]
    for exam in politics.EXAMS:
        for m in politics.atlas(g.paths,exam['id'])['materials']:
            if m.get('practice_only'):continue
            stem=Path(m.get('pdf','')).stem
            out.append(({'source':'atlas','exam':exam['id'],'material':m['id']},[m['original']],stem if re.fullmatch(r'[0-9a-f]{64}',stem) else ''))
    listing=journal.listing(g)
    for kind in journal.KINDS:
        for item in listing[kind]:
            data=journal.load(g.paths,kind,item['id'])
            out.append(({'source':'wanxiang_journal','kind':kind,'id':item['id']},['\n'.join(n['paras']) for n in data['news']],''))
    return out


def _located(template,texts):
    """清单这一段的各段固定文字是否按顺序出现在某份资料里（相邻不超过240字）；文字太少不足以认定出处。"""
    lits=[norm(x) for x in BLANK.split(NUMBER.sub('',template))]
    lits=[x for x in lits if x]
    if not lits or sum(map(len,lits))<6:return False
    for raw in texts:
        text=norm(raw);start=text.find(lits[0]);tries=0
        while start>=0 and tries<400:
            at=start+len(lits[0]);ok=True
            for lit in lits[1:]:
                i=text.find(lit,at)
                if i<0 or i-at>240:ok=False;break
                at=i+len(lit)
            if ok:return True
            start=text.find(lits[0],start+1);tries+=1
    return False


def _owners(matches):
    """出处资料 → 保存位置：同一份讲义PDF拆出的多篇共用一份“整份讲义”清单；其余各自保存（同样原文出现在多份资料就都保存）。"""
    stems={m[2] for m in matches}
    if len(matches)>1 and len(stems)==1 and next(iter(stems)) and len({m[0]['exam'] for m in matches})==1:
        stem=next(iter(stems));return [({'source':'atlas','exam':matches[0][0]['exam'],'bundle':stem},[t for m in matches for t in m[1]])]
    return [(m[0],m[1]) for m in matches]


def _row_ids(key,doc_hash,i,row,pool):
    """与get()相同的空位编号：[(编号, 答案)]；用来在重新识别后把旧的核对记号搬到新编号上。"""
    answers=match_answers(row['text'],pool);out=[]
    for k in range(len(BLANK.findall(row['text']))):
        explicit=row['provided'][k] if k<len(row.get('provided',[])) else None
        answer=explicit or answers[k]
        out.append((key+':'+politics.digest([doc_hash,i,k,answer])[:24],answer))
    return out


def _carry_marks(g,key,doc_hash,old_rows,new_rows,pool):
    """新规则重新识别同一份PDF：段落文字相同（或新段落是旧段落去掉标题等多余前缀后的一部分）且空数相同的，核对记号随之迁移。"""
    file=g.paths.train/'时政消化/进度'/(key+'.json')
    memory=politics.read_json(file,{})
    fill_file=_fill_file(g,key);fills=politics.read_json(fill_file,{})
    if not memory and not fills:return 0
    old=[(norm(r['text']),len(BLANK.findall(r['text'])),_row_ids(key,doc_hash,i,r,pool)) for i,r in enumerate(old_rows)]
    moved=0
    for j,row in enumerate(new_rows):
        text=norm(row['text']);blanks=len(BLANK.findall(row['text']));new_ids=None
        for old_index,(old_text,old_blanks,old_ids) in enumerate(old):
            if old_blanks!=blanks or not blanks or text not in old_text:continue
            new_ids=new_ids or _row_ids(key,doc_hash,j,row,pool)
            for k,((oid,_),(nid,answer)) in enumerate(zip(old_ids,new_ids)):
                if answer and oid in memory and nid not in memory:memory[nid]=memory[oid];moved+=1
            for k in range(blanks):                  # 手动补全的答案和它们的核对记号跟着空位一起搬
                old_key=politics.digest([doc_hash,old_index,k]);new_key=politics.digest([doc_hash,j,k])
                if old_key in fills and new_key not in fills:fills[new_key]=fills[old_key];moved+=1
                old_id,new_id=key+':f'+old_key[:22],key+':f'+new_key[:22]
                if old_id in memory and new_id not in memory:memory[new_id]=memory[old_id]
            break
    if moved:
        politics.atomic_json(file,memory)
        if fills:fill_file.parent.mkdir(parents=True,exist_ok=True);politics.atomic_json(fill_file,fills)
    return moved


def import_pdf(g, body):
    raw=str(body.get('data') or '').split(',',1)[-1]
    if len(raw)>56*1024*1024:raise politics.PoliticsError('请拆成40MB以内的PDF')
    try:content=base64.b64decode(raw,validate=True)
    except (ValueError,TypeError):raise politics.PoliticsError('PDF数据无效')
    if len(content)>40*1024*1024 or not content.startswith(b'%PDF'):raise politics.PoliticsError('请选择40MB以内的PDF')
    paragraphs=parse_pdf(content)
    ident=hashlib.sha256(content).hexdigest()
    name=Path(str(body.get('name') or '消化清单.pdf')).name[:200]
    candidates=_candidates(g)
    lost=[]
    placed={};unmatched=0       # placed：保存位置摘要 → [资料身份, 文本池, 本次新增的段落]
    own=[]
    for row in paragraphs:      # 先各自在资料里找出处；找不到的（小标题、太短的句子、原文有出入的）稍后按前后文归位
        matches=[c for c in candidates if _located(row['text'],c[1])]
        own.append(_owners(matches) if matches else None)
    if not any(own):
        raise politics.PoliticsError('没有在已导入的讲义、月半或专题里找到这份清单的出处，未导入；请先导入对应资料，或检查清单文字与原文是否一致')
    loose=[o is None for o in own]
    names=lambda o:{politics.digest(d) for d,_ in o}
    i=0
    while i<len(own):
        if own[i] is not None:i+=1;continue
        j=i
        while j<len(own) and own[j] is None:j+=1
        before=own[i-1] if i>0 else None;after=own[j] if j<len(own) else None
        cut=j                   # 这一段空档里 cut 之前归前一份资料，cut 起归后一份
        if before is None:cut=i
        elif after is not None and names(before)!=names(after):
            heads=[k for k in range(i,j) if paragraphs[k]['kind']=='h']
            cut=heads[-1] if heads else j
        for k in range(i,j):own[k]=before if k<cut else after
        i=j
    for src,row in enumerate(paragraphs):
        if loose[src] and BLANK.search(row['text']):unmatched+=1;lost.append(re.sub(r'(?:_\s*){2,}','＿＿',row['text'])[:28])
        for desc,pool in own[src]:
            key=politics.digest(desc)
            slot=placed.setdefault(key,[desc,pool,[]]);slot[2].append(dict(row,src=src,**({'loose':True} if loose[src] and BLANK.search(row['text']) else {})))
    added=existing=ready=pending=0;targets=0;moved=redone=0
    with politics._LOCK:
        for key,(desc,pool,rows) in placed.items():
            file=_store(g,desc);saved=politics.read_json(file,{'schema':1,'target':desc,'documents':[]})
            doc=next((d for d in saved['documents'] if d['hash']==ident),None)
            if doc is None:doc={'hash':ident,'name':name,'paragraphs':[],'rv':RV};saved['documents'].append(doc)
            elif doc.get('rv',1)<RV and any('src' in r for r in doc['paragraphs']):
                # 识别规则升级：同一份PDF按新规则整份重新识别（标题不再并进正文、行首行尾的空不再漏），核对记号尽量搬过去
                moved+=_carry_marks(g,key,ident,doc['paragraphs'],[dict(r) for r in rows],pool)
                doc['paragraphs']=[];doc['rv']=RV;redone+=1
            if any('src' not in r for r in doc['paragraphs']):existing+=len(rows);continue     # 旧版整份导入过的同一份PDF：不叠加
            have={r['src'] for r in doc['paragraphs']}
            fresh=[r for r in rows if r['src'] not in have]
            existing+=len(rows)-len(fresh)
            if not fresh:continue
            doc['paragraphs'].extend(fresh);targets+=1
            politics.atomic_json(file,saved)
            for r in fresh:
                answers=match_answers(r['text'],pool);explicit=r.get('provided',[])
                for k in range(len(BLANK.findall(r['text']))):
                    added+=1
                    if (explicit[k] if k<len(explicit) else None) or answers[k]:ready+=1
                    else:pending+=1
        original=g.paths.train/'时政消化/原文'/(ident+'.pdf')
        if not original.exists():
            original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(content)
    return dict(channel='digest',duplicate=not added and bool(existing),title=name,blanks=added,ready=ready,pending=pending,
                rows=sum(1 for r in paragraphs if BLANK.search(r['text'])),blocks=len(paragraphs),unmatched=unmatched,targets=targets,redone=redone,moved=moved,
                pdf_blanks=sum(len(BLANK.findall(r['text'])) for r in paragraphs),lost=lost[:5])
