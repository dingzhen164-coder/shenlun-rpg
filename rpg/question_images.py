"""3.1.1行测截图净化：保留图形/几何/统计图表，复用本地拆卷器的题目坐标，只截有用区域。

vault/trainer/importer调用clean_text；旧题及历史题目快照即时应用，不改原文、编号或复盘笔记。
原PDF和skill只读；索引与合并后的图片写训练/题库/图片/_净化。原图缺少PDF时保留必要图作回退。
新拆卷由app.run_script调用run_splitter，覆写截图函数而不改用户skill；输出仍保留原解析与答案。
"""
import ast
import hashlib
import importlib.util
import json
import re
import sys
import threading
from pathlib import Path

VERSION = 2
GRAPH_BOARDS = {'图形推理', '资料分析', '数量关系'}
_CACHE = {}
_MODULES = {}
_LOCK = threading.RLock()
IMG = re.compile(r'!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]|!\[[^\]]*\]\(([^)]+)\)')
AUTO = re.compile(r'(?:S|粉笔)(\d+)(?:季)?-(?:Q)?(\d{3})(?:-(\d+))?', re.I)
MATERIAL = re.compile(r'(?:S|粉笔)(\d+)(?:季)?-(M\d+-\d+)', re.I)
PLACEHOLDER = re.compile(r'^\s*(?:-\s*)?(?:\*\*)?([A-D])[.．、](?:\*\*)?\s*(?:\1|（(?:见图|见截图|选项见图)）)\s*$', re.M)


def enabled(paths):
    return getattr(paths, 'subject', '') == '行测' and bool(paths.vault)


def _pm():
    from .imgtrim import _pm as get
    return get()


def _folder(paths):
    folder = paths.train / '题库' / '图片' / '_净化'
    if paths.train.resolve() not in folder.resolve().parents or paths.vault.resolve() not in folder.resolve().parents:
        raise ValueError('截图缓存必须在当前库的训练目录内')
    return folder


def _script(paths):
    for base in ('copilot/skills', '.opencode/skills'):
        f = paths.vault / base / 'xingce-mokao-split/scripts/split_mokao.py'
        if f.is_file():
            return f
    return None


def _module(script):
    key = (str(script.resolve()), script.stat().st_mtime_ns)
    if key not in _MODULES:
        name = '_xingce_split_' + hashlib.sha256(repr(key).encode()).hexdigest()[:16]
        spec = importlib.util.spec_from_file_location(name, str(script))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        # 用户已安装、原导入流程也会运行的拆卷器；这里只调用读取函数，不调用main、不写skill。
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
        _MODULES[key] = module
    return _MODULES[key]


def pdf_files(paths):
    roots = (paths.train / '模考试卷', paths.vault / 'FB模考试卷复盘' / '模考试卷')
    return [f for root in roots if root.is_dir() for f in sorted(root.glob('*.pdf'))]


def _season(pdf):
    from .importer import SEASON_RE, _cn2int
    match = SEASON_RE.search(pdf.stem)
    return _cn2int(match.group(1)) if match else None


def _pdf(paths, season):
    return next((f for f in pdf_files(paths) if _season(f) == season), None)


def _visible_rect(rect, page, y0, y1):
    # 页背景/水印不是题图；按整张页面判断，不能用当前题目的小区域比例判断。
    area = max(0, rect.width) * max(0, rect.height)
    if area > page.rect.width * page.rect.height * .7:
        return False
    return rect.y0 >= y0 - 3 and rect.y1 <= y1 + 3 and rect.width >= 24 and rect.height >= 24 and area >= 1000


def _tables(page, y0, y1):
    """资料分析的无边框统计表：三行以上、两列以上数值对齐才截，普通文字/选项不当成表。"""
    pm = _pm()
    rows = []
    words = sorted((w for w in page.get_text('words') if y0 <= w[1] and w[3] <= y1), key=lambda w:(w[1],w[0]))
    for word in words:
        if rows and abs(rows[-1][0] - word[1]) < 4:
            rows[-1][1].append(word)
        else:
            rows.append([word[1], [word]])
    candidates = []
    for _, row in rows:
        numeric = [w for w in row if re.fullmatch(r'[\d,，.+%％−—-]+',w[4])]
        if len(numeric) >= 2:
            candidates.append((row,numeric))
    if len(candidates) < 3:
        return []
    out = []
    for i, (row, numeric) in enumerate(candidates):
        aligned = [(other,nums) for other,nums in candidates[i:] if sum(any(abs(a[0]-b[0])<9 for b in nums) for a in numeric)>=2]
        if len(aligned)<3:
            continue
        selected = [w for group,_ in aligned for w in group]
        box = pm.Rect(selected[0][:4])
        for word in selected[1:]:
            box |= pm.Rect(word[:4])
        # 补表头；不连带上方整段材料说明。
        for yy, group in rows:
            if box.y0-35 <= yy < box.y0 and len(group)>=2:
                for word in group:
                    if box.x0-10 <= word[0] <= box.x1+10:
                        box |= pm.Rect(word[:4])
        out.append(box)
        break
    return out


def graphics(doc, segments, labels=False, table=False):
    """按PDF对象坐标选实际图；小数字/字母/分数位图、空白页、页底水印不触发整题截图。"""
    pm = _pm()
    clips = []
    for pno, y0, y1 in segments:
        page = doc[pno]
        rects = []
        for info in page.get_image_info():
            rect = pm.Rect(info['bbox'])
            inline = rect.width<80 and rect.height<=36 and rect.width*rect.height<1200 and any(
                w[3]>=rect.y0 and w[1]<=rect.y1 and (0<=rect.x0-w[2]<45 or 0<=w[0]-rect.x1<45)
                for w in page.get_text('words'))
            if _visible_rect(rect, page, y0, y1) and not inline:
                rects.append(rect)
        lines = []
        for drawing in page.get_drawings():
            rect = drawing['rect']
            # 灰白水印与纸底、填空横线及分数横线都不是图形。
            colors = [c for c in (drawing.get('color'), drawing.get('fill')) if c is not None]
            if colors and min(sum(c) / len(c) for c in colors) > .82:
                continue
            if max([drawing[k] for k in ('fill_opacity','stroke_opacity') if drawing.get(k) is not None] or [1]) < .35:
                continue
            if _visible_rect(rect, page, y0, y1):
                rects.append(pm.Rect(rect))
            elif y0 <= rect.y0 <= rect.y1 <= y1 and (rect.width >= 35 or rect.height >= 35) and rect.width * rect.height < page.rect.width * page.rect.height * .5:
                lines.append(pm.Rect(rect))
        # 坐标轴/几何/表格可能由许多独立线段构成；只合并邻接的线，孤立下划线不成为图片。
        clusters = []
        for rect in lines:
            touched = [c for c in clusters if (c + (-5, -5, 5, 5)).intersects(rect)]
            for c in touched:
                rect |= c
                clusters.remove(c)
            clusters.append(rect)
        rects += [r for r in clusters if _visible_rect(r, page, y0, y1)]
        if table:
            rects += _tables(page, y0, y1)
        if not rects:
            continue
        box = pm.Rect(rects[0])
        for rect in rects[1:]:
            box |= rect
        if labels:
            # 图形选项的字母可能不在位图里，补入邻近A/B/C/D；不重复截A.A等文字占位选项。
            for word in page.get_text('words'):
                if re.fullmatch(r'[A-D][.．]?', word[4]) and y0 <= word[1] and word[3] <= y1:
                    r = pm.Rect(word[:4])
                    if box.x0 - 15 <= r.x0 <= box.x1 + 15 and box.y0 - 18 <= r.y0 <= box.y1 + 28:
                        box |= r
        box = (box + (-4, -4, 4, 4)) & page.rect
        clips.append([pno, *[round(float(v), 3) for v in box]])
    return clips


def _symbol_lines(paths, doc, lines, segments, clips, fingerprint, persist, normalize=lambda s:s, only=None):
    """PDF的小公式可能没有文字层：按原坐标插入行内符号，不猜分子/分母，不截整题。"""
    pm = _pm()
    changed, recipes = {}, []
    for pno,y0,y1 in segments:
        page=doc[pno]
        candidates=[]
        for i,info in enumerate(page.get_image_info()):
            rect=pm.Rect(info['bbox'])
            if only is not None and (pno,*[round(float(v),3) for v in rect]) not in only:continue
            native=[w for w in page.get_text('words') if rect.contains(pm.Rect(w[:4]).tl) or rect.contains(pm.Rect(w[:4]).br)]
            if any(re.fullmatch(r'[-+]?\d+/\d+|[½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]',w[4]) for w in native):
                continue  # 文字层已经有完整分数时直接用文字。
            if not (3 <= rect.width < 80 and 5 <= rect.height <= 36 and rect.width*rect.height<1200 and y0-3 <= rect.y0 and rect.y1 <= y1+3):
                continue
            if any(c[0]==pno and pm.Rect(c[1:]).contains(rect) for c in clips):
                continue  # 题图里的数字已随图保留，不塞入题干。
            available=[(j,l) for j,l in enumerate(lines) if getattr(l,'page',-1)==pno and l.text!='\x00IMG' and l.y1>=rect.y0-4 and l.y0<=rect.y1+4]
            if not available:
                continue
            j,line=min(available,key=lambda item:abs((item[1].y0+item[1].y1)/2-(rect.y0+rect.y1)/2))
            file=_folder(paths)/'符号'/('%s-p%d-%d.png'%(fingerprint,pno,i))
            rel=file.relative_to(paths.vault).as_posix()
            recipe=dict(path=rel,clip=[pno,*[float(v) for v in rect]])
            if persist:
                _write_symbol(doc,recipe,paths)
            candidates.append((j,rect,'![[%s]]'%rel));recipes.append(recipe)
        for j in set(x[0] for x in candidates):
            line=lines[j]
            boxes=[r for jj,r,_ in candidates if jj==j]
            words=[w for w in page.get_text('words') if abs(w[3]-line.y1)<4 and w[0]>=line.x0-3 and not any(r.contains(pm.Point((w[0]+w[2])/2,(w[1]+w[3])/2)) for r in boxes)]
            tokens=[(w[0],w[4],w[2]) for w in words]
            if '____' in line.text:
                for drawing in page.get_drawings():
                    r=drawing['rect']
                    if r.height<1.5 and 12<r.width<60 and abs(r.y0-line.y1)<5:tokens.append((r.x0,'____',r.x1))
            tokens += [(r.x0,text,r.x1) for jj,r,text in candidates if jj==j]
            if not words:
                continue  # 不重建无法核对的文本行。
            tokens.sort(key=lambda item:item[0]);text='';last=None;previous=''
            for x,value,right in tokens:
                if last is not None and (x-last>4 or (previous and value and previous[-1].isascii() and previous[-1].isalpha() and value[0].isascii() and value[0].isalpha())):text+=' '
                text+=value;last=right;previous=value
            import copy
            new=copy.copy(line);new.text=normalize(text);changed[j]=new
    return [changed.get(i,line) for i,line in enumerate(lines)],recipes


def _write_symbol(doc,recipe,paths):
    file=(paths.vault/recipe['path']).resolve()
    if _folder(paths).resolve() not in file.parents:
        raise ValueError('行内符号路径越界')
    if file.is_file():return
    file.parent.mkdir(parents=True,exist_ok=True)
    clip=recipe['clip'];pm=_pm()
    raw=doc[clip[0]].get_pixmap(clip=pm.Rect(clip[1:]),matrix=pm.Matrix(2,2),colorspace=pm.csRGB,alpha=False).tobytes('png')
    tmp=file.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(file)


def _repair(paths,pdf,meta,info,text):
    repair=info.get('repair')
    if not repair:return text
    before=text
    old,new=repair['stem']
    if len(old)>=10 and old in text:text=text.replace(old,new,1)
    for label,pair in repair['options'].items():
        old,new=pair
        pattern=r'(?m)^([ \t]*(?:-\s*)?(?:\*\*)?'+label+r'[.．](?:\*\*)?\s*)([^\n]*)$'
        text=re.sub(pattern,lambda m:m.group(1)+new if m.group(2).strip()==old or (not old and m.group(2).strip() in ('（见图）','（见截图）','（选项见图）',label)) else m.group(0),text)
    if text!=before:
        missing=[r for r in meta.get('symbols',[]) if '![[%s]]'%r['path'] in text and not (paths.vault/r['path']).is_file()]
        if missing:
            with _pm().open(str(pdf)) as doc:
                for recipe in missing:_write_symbol(doc,recipe,paths)
    return text


def _fingerprint(pdf, script):
    return hashlib.sha256(repr((VERSION, str(pdf.resolve()), pdf.stat().st_mtime_ns, pdf.stat().st_size,
                                str(script.resolve()), script.stat().st_mtime_ns)).encode()).hexdigest()[:20]


def prepare(paths, pdf, persist=True):
    """每份PDF只索引一次；缓存只含题号/板块/矩形，不复制题干、答案或笔记。"""
    script, pm = _script(paths), _pm()
    if not script or not pm:
        return None
    names={n.name for n in ast.parse(script.read_text(encoding='utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if not {'extract_lines','parse','classify','split_options','join_stem','region_segments'}.issubset(names):
        return None
    key = _fingerprint(pdf, script)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        file = _folder(paths) / ('index-' + key + '.json')
        if file.is_file():
            try:
                data = json.loads(file.read_text(encoding='utf-8'))
                if data.get('fingerprint') == key:
                    _CACHE[key] = data
                    return data
            except (OSError, ValueError):
                pass
        module = _module(script)
        with pm.open(str(pdf)) as doc:
            lines = module.extract_lines(doc)
            left = sorted(l.x0 for l in lines)[len(lines) // 2] if lines else 43
            questions, materials = module.parse(lines, left)
            data = dict(fingerprint=key, questions={}, materials={}, symbols=[])
            symbol_lines=list(lines)
            for i, q in enumerate(questions):
                q.options = module.split_options(q.opt_lines)
                board = module.classify(q, module.join_stem(q.stem_lines, left))
                end = q.ans_line or (questions[i+1].start if i+1 < len(questions) else None)
                if not end:
                    continue  # 边界不完整时保留原图，不伪造“无需图”。
                segs = module.region_segments(doc, q.start, end.page, end.y0)
                data['questions']['Q%03d' % q.num] = dict(board=board, clips=graphics(doc, segs, board == '图形推理', board == '资料分析') if board in GRAPH_BOARDS else [])
                info=data['questions']['Q%03d'%q.num]
                symbol_lines,recipes=_symbol_lines(paths,doc,symbol_lines,segs,info['clips'],key,persist,getattr(module,'norm',lambda s:s))
                data['symbols']+=recipes
            for material in materials:
                if material.lines and material.qnums and material.end:
                    segs = module.region_segments(doc, material.lines[0], material.end.page, material.end.y0)
                    first = next((q for q in questions if q.num == material.qnums[0]), None)
                    allowed = first and first.section == '资料分析'
                    owner = 'M%03d-%03d' % (material.qnums[0], material.qnums[-1])
                    data['materials'][owner] = dict(board='资料分析' if allowed else '一拖五', clips=graphics(doc, segs, table=True) if allowed else [])
                    info=data['materials'][owner]
                    symbol_lines,recipes=_symbol_lines(paths,doc,symbol_lines,segs,info['clips'],key,persist,getattr(module,'norm',lambda s:s))
                    data['symbols']+=recipes
            if data['symbols']:
                amended,amended_mats=module.parse(symbol_lines,left)
                originals={q.num:q for q in questions}
                for fixed in amended:
                    original=originals.get(fixed.num);info=data['questions'].get('Q%03d'%fixed.num)
                    if not original or not info:continue
                    old_stem=module.join_stem(original.stem_lines,left);new_stem=module.join_stem(fixed.stem_lines,left)
                    if original.section!='言语理解与表达':old_stem=old_stem.replace('____','');new_stem=new_stem.replace('____','')
                    old_opts=module.split_options(original.opt_lines);new_opts=module.split_options(fixed.opt_lines)
                    changed={k:[v,new_opts.get(k,v)] for k,v in old_opts.items() if new_opts.get(k,v)!=v}
                    if old_stem!=new_stem or changed:info['repair']=dict(stem=[old_stem,new_stem],options=changed)
                for fixed in amended_mats:
                    if not fixed.qnums:continue
                    original=next((m for m in materials if m.qnums==fixed.qnums),None)
                    owner='M%03d-%03d'%(fixed.qnums[0],fixed.qnums[-1]);info=data['materials'].get(owner)
                    if not original or not info:continue
                    old=module.join_stem([(l.text,l.x0) for l in original.lines if l.text!='\x00IMG'],left)
                    new=module.join_stem([(l.text,l.x0) for l in fixed.lines if l.text!='\x00IMG'],left)
                    if old!=new:info['repair']=dict(stem=[old,new],options={})

        if not data['questions']:
            return None
        if persist:
            file.parent.mkdir(parents=True, exist_ok=True)
            tmp = file.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            tmp.replace(file)
        if len(_CACHE) >= 32:
            _CACHE.clear()
        _CACHE[key] = data
        return data


def _capture(doc, clips):
    """跨页只拼接实际图，合为一张PNG；不带上一页纯题干或巨大的页边空白。"""
    pm = _pm()
    pixmaps = [doc[c[0]].get_pixmap(clip=pm.Rect(c[1:]), matrix=pm.Matrix(2, 2), colorspace=pm.csRGB, alpha=False) for c in clips]
    if not pixmaps:
        return None
    if len(pixmaps) == 1:
        return pixmaps[0].tobytes('png')
    width, height = max(p.width for p in pixmaps), sum(p.height for p in pixmaps) + 12 * (len(pixmaps) - 1)
    canvas = pm.Pixmap(pm.csRGB, pm.IRect(0, 0, width, height), False)
    canvas.clear_with(255)
    y = 0
    for pix in pixmaps:
        x = (width - pix.width) // 2
        # copy使用页面坐标，先设原点再合并；不缩放任何图形。
        pix.set_origin(x, y)
        canvas.copy(pix, pm.IRect(x, y, x + pix.width, y + pix.height))
        y += pix.height + 12
    return canvas.tobytes('png')


def _identity(name):
    base = Path(name.replace('\\', '/')).name
    m = MATERIAL.search(base)
    if m:
        a, b = map(int, re.findall(r'\d+', m.group(2)))
        return int(m.group(1)), 'M%03d-%03d' % (a, b)
    m = AUTO.search(base)
    return (int(m.group(1)), 'Q%03d' % int(m.group(2))) if m else None


def clean_text(paths, board, text):
    if not enabled(paths) or not board or not IMG.search(text):
        return text
    source = str(text)
    repaired=set()
    for match in IMG.finditer(source):
        identity=_identity((match.group(1) or match.group(2)).strip())
        if not identity or identity in repaired:continue
        season,owner=identity
        try:
            pdf=_pdf(paths,season);meta=prepare(paths,pdf) if pdf else None
            info=meta.get('materials' if owner.startswith('M') else 'questions',{}).get(owner) if meta else None
            if info:source=_repair(paths,pdf,meta,info,source)
        except (OSError,ValueError,RuntimeError,ImportError,AttributeError,TypeError,KeyError,SyntaxError):
            pass
        repaired.add(identity)
    plain = IMG.sub('', source)
    plain = re.sub(r'^\s*（[^）\n]{1,80}）\s*', '', plain)  # 导入来源不能算题干文字。
    plain = PLACEHOLDER.sub('', plain)
    plain = re.sub(r'^\s*>?\s*\[![^\]]+\].*$', '', plain, flags=re.M)
    complete_text = len(re.sub(r'\s|[ABCD.．*\->]', '', plain)) >= 12
    used, replaced_graph = set(), False
    def replace(match):
        nonlocal replaced_graph
        name = (match.group(1) or match.group(2)).strip()
        if '/_净化/符号/' in name.replace('\\','/'):
            return match.group(0)
        identity = _identity(name)
        # 文字题有完整文字时取消截图；只有图片没有文本时保留，避免丢题。
        if board not in GRAPH_BOARDS and complete_text:
            return ''
        if not identity:
            return match.group(0)
        season, owner = identity
        try:
            pdf = _pdf(paths, season)
            meta = prepare(paths, pdf) if pdf else None
            info = meta.get('materials' if owner.startswith('M') else 'questions', {}).get(owner) if meta else None
            if info is None:
                return match.group(0)
            if not info['clips']:
                return '' if complete_text else match.group(0)
            if identity in used:
                return ''
            folder = _folder(paths)
            target = folder / ('S%d-%s-%s.png' % (season, owner, meta['fingerprint']))
            with _LOCK:
                if not target.is_file():
                    with _pm().open(str(pdf)) as doc:
                        raw = _capture(doc, info['clips'])
                    if not raw:
                        return match.group(0)
                    folder.mkdir(parents=True, exist_ok=True)
                    tmp = target.with_suffix('.tmp')
                    tmp.write_bytes(raw)
                    tmp.replace(target)
            used.add(identity)
            replaced_graph = board == '图形推理'
            return '![[%s]]' % target.relative_to(paths.vault).as_posix()
        except (OSError, ValueError, RuntimeError, ImportError, AttributeError, TypeError, KeyError, SyntaxError):
            return match.group(0)  # 没有解析器/组件/原PDF时仍能做旧题。
    result = IMG.sub(replace, source)
    if replaced_graph:
        result = PLACEHOLDER.sub('', result)
        prefix=re.match(r'^\s*(（[^）\n]+）)\s*',result)
        front=prefix.group(1)+'\n' if prefix else ''
        rest=result[prefix.end():] if prefix else result
        lead=re.match(r'^(?:\s*!\[\[[^\]]+\]\])+\s*',rest)
        if lead and rest[lead.end():].strip():result=front+rest[lead.end():].strip()+'\n\n'+lead.group(0).strip()

    return re.sub(r'\n{3,}', '\n\n', result).strip()


def run_splitter(script, args):
    """新导入仍用原题文和答案解析，替换旧“数量一律截图/任意小图截图”的策略。"""
    from .paths import Paths
    import os
    paths = Paths(Path(os.environ['XINGCE_CLEAN_VAULT']), '行测')
    pdf = Path(args[0])
    meta = prepare(paths, pdf)
    if not meta:
        import runpy
        sys.argv=[str(script)]+list(args)
        return runpy.run_path(str(script),run_name='__main__')
    module = _module(Path(script))
    def snap(doc, segs, folder, stem):
        identity = _identity(stem)
        owner = identity[1] if identity else ''
        info = meta.get('materials' if owner.startswith('M') else 'questions', {}).get(owner)
        if not info or not info['clips']:
            return []
        raw = _capture(doc, info['clips'])
        name = stem + '.png'
        (folder / name).write_bytes(raw)
        return [name]
    # 截图函数本身按板块及实际图形过滤；确保所有题和材料都经过同一规则。
    original_extract=module.extract_lines
    def extract(doc):
        lines=original_extract(doc)
        ranges={}
        for recipe in meta.get('symbols',[]):
            c=recipe['clip'];old=ranges.get(c[0],[c[2],c[4]]);ranges[c[0]]=[min(old[0],c[2]),max(old[1],c[4])]
        only={(r['clip'][0],*[round(float(v),3) for v in r['clip'][1:]]) for r in meta.get('symbols',[])}
        lines,_=_symbol_lines(paths,doc,lines,[(page,a-1,b+1) for page,(a,b) in ranges.items()],[],meta['fingerprint'],True,getattr(module,'norm',lambda s:s),only)
        return lines
    module.extract_lines=extract
    module.ALWAYS_SNAP = set()
    module.has_images = lambda doc, segs: True
    module.snap = snap
    sys.argv = [str(script)] + list(args)
    module.main()
