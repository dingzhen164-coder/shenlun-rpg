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
from pathlib import Path

from . import politics

BLANK = re.compile(r'(?:[_＿﹍﹎][ \t]*){2,}|（[ \u3000]*）|\([ \u3000]{2,}\)')
NUMBER = re.compile(r'^\s*(\d+)[.．、]\s*')


def norm(text):
    return re.sub(r'\s+', '', text)


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


def _pdf_lines(doc):
    """提取文字与真正空白处的绘制下划线；正文已有字的下划线不算空。"""
    from .wanxiang_journal import NOISE
    result=[]
    for page in doc:
        rows={}
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    if span['text'].strip() in NOISE:
                        continue
                    baseline=round(span['origin'][1],1)
                    rows.setdefault(baseline,[]).append((span['bbox'][0],span['bbox'][2],span['text'],False))
        for drawing in page.get_drawings():
            for item in drawing['items']:
                if item[0]!='l':continue
                a,b=item[1],item[2]
                if abs(a.y-b.y)>.7 or abs(a.x-b.x)<12:continue
                left,right=sorted((a.x,b.x))
                candidates=[y for y in rows if -1<=a.y-y<=5]
                if not candidates:continue
                y=min(candidates,key=lambda y:abs(a.y-y))
                spans=rows[y]
                if not any(x2<=left+2 for x1,x2,_,_ in spans):continue
                if any(x1<right-1 and x2>left+1 for x1,x2,_,_ in spans):continue
                spans.append((left,right,'____',True))
        for y,spans in sorted(rows.items()):
            text=''.join(s[2] for s in sorted(spans))
            if not text.strip() or (y>page.rect.height*.9 and re.fullmatch(r'\s*\d{1,3}\s*',text)):continue
            result.append(text.strip())
    return result


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
    paragraphs,answers,current=[],{},''
    in_answers=False
    def flush():
        nonlocal current
        if BLANK.search(current):paragraphs.append(current)
        current=''
    for line in lines:
        if re.fullmatch(r'(?:参考)?答案(?:与解析)?[：:]?',line) or line.endswith('·答案与解析'):
            flush();in_answers=True;continue
        if not BLANK.search(line) and re.search(r'消化清单|填空练习',line):
            flush();continue
        if in_answers:
            m=NUMBER.match(line)
            if m:answers[m.group(1)]=re.sub(r'^(?:【答案】|答案[：:])','',line[m.end():]).split('解析：')[0].strip('。 ')
            continue
        heading=re.match(r'^[一二三四五六七八九十]+[、．]',line)
        if NUMBER.match(line) or heading or (current and re.search(r'[。！？；]$',current)):
            flush()
        if heading and not BLANK.search(line):continue
        if current and re.search(r'[A-Za-z]$',current) and re.match(r'[A-Za-z]',line):current+=' '
        current+=line
    flush()
    if not paragraphs:raise politics.PoliticsError('未识别到清单空位；支持文字下划线、空括号和文字行中的空白下划线，扫描版请先OCR')
    numbers=[NUMBER.match(p).group(1) if NUMBER.match(p) else None for p in paragraphs]
    out=[]
    for text,no in zip(paragraphs,numbers):
        count=len(BLANK.findall(text));provided=[]
        if no and numbers.count(no)==1 and no in answers:
            value=answers[no]
            provided=[value] if count==1 else [v.strip() for v in re.split(r'[、；;|｜]',value)]
            if len(provided)!=count:provided=[]
        out.append({'text':text,'provided':provided})
    return out


def match_answers(template, sources):
    """枚举明确上下文的所有匹配；有歧义、无上下文或复杂度超限均不填。"""
    stripped=NUMBER.sub('',template)
    pieces=[norm(s) for s in BLANK.split(stripped)]
    count=len(pieces)-1
    if not count or sum(map(len,pieces))<4 or any(not s for s in pieces):return [None]*count
    candidates=[];budget=[0]
    def walk(text,k,cursor,values):
        budget[0]+=1
        if budget[0]>2000:return
        literal=pieces[k+1]
        if not literal:
            answer=text[cursor:].rstrip('。！？；')
            if 0<len(answer)<=120:candidates.append(values+[answer])
            return
        at=text.find(literal,cursor+1)
        while at>=0 and at-cursor<=120:
            answer=text[cursor:at]
            if not re.search(r'[。！？；]',answer):
                if k+1==count:candidates.append(values+[answer])
                else:walk(text,k+1,at+len(literal),values+[answer])
            at=text.find(literal,at+1)
    for source in sources:
        for raw in [source]+re.split(r'\n\s*\n|(?<=[。！？；])',source):
            text=norm(raw)
            if not text:continue
            starts=[0] if not pieces[0] else [m.start()+len(pieces[0]) for m in re.finditer('(?='+re.escape(pieces[0])+')',text)]
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
        for document in saved['documents']:
            documents.append(document['name'])
            for i,row in enumerate(document['paragraphs']):
                answers=match_answers(row['text'],_pool(readings,owner))
                literals=BLANK.split(row['text']);parts=[]
                for k,literal in enumerate(literals):
                    if literal:parts.append({'t':literal})
                    if k==len(literals)-1:continue
                    explicit=row['provided'][k] if k<len(row.get('provided',[])) else None
                    answer=explicit or answers[k]
                    ident=key+':'+politics.digest([document['hash'],i,k,answer])[:24]
                    part={'id':ident,'a':answer,'status':'provided' if explicit else 'matched' if answer else 'pending','owner':owner}
                    parts.append(part);items.append(part);progress[ident]=memory.get(ident)
                rows.append({'title':document['name'],'parts':parts})
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
    placed={};unmatched=0       # placed：保存位置摘要 → [资料身份, 文本池, 本次新增的段落]
    for src,row in enumerate(paragraphs):
        matches=[c for c in candidates if _located(row['text'],c[1])]
        if not matches:unmatched+=1;continue
        for desc,pool in _owners(matches):
            key=politics.digest(desc)
            slot=placed.setdefault(key,[desc,pool,[]]);slot[2].append(dict(row,src=src))
    if not placed:
        raise politics.PoliticsError('没有在已导入的讲义、月半或专题里找到这份清单的出处，未导入；请先导入对应资料，或检查清单文字与原文是否一致')
    added=existing=ready=pending=0;targets=0
    with politics._LOCK:
        for key,(desc,pool,rows) in placed.items():
            file=_store(g,desc);saved=politics.read_json(file,{'schema':1,'target':desc,'documents':[]})
            doc=next((d for d in saved['documents'] if d['hash']==ident),None)
            if doc is None:doc={'hash':ident,'name':name,'paragraphs':[]};saved['documents'].append(doc)
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
                rows=len(paragraphs),unmatched=unmatched,targets=targets)
