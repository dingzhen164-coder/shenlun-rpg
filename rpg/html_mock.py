"""粉笔已保存HTML/ZIP模考导入（仅行测），由/api/import/html调用。
HTMLParser只读取已渲染节点，不执行脚本、不访问外链。支持主HTML+资源ZIP或整包ZIP。
预览不写盘；缺图/结构不完整拒绝提交。图片仅接收有签名的PNG/JPEG/GIF/WebP。
题号沿用粉笔N季-xxx；复盘/解析/原作答保留，已有季复盘不覆盖；重复不追加题/计时。
"""
import base64
import hashlib
import io
import os
import tempfile
import posixpath
import re
import threading
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from . import importer, vault

LOCK = threading.Lock()
MAX_FILE = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
VOID = {'img','br','input','meta','link','hr','base','source','wbr','area','embed','param','col'}
IGNORE = {'script','style','iframe','object','svg','canvas','noscript','button','input'}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
        self.depth = parent.depth+1 if parent else 0
        if self.depth > 180: raise importer.ImportError_('HTML嵌套过深')

    def walk(self, tag=None, cls=None):
        for child in self.children:
            if isinstance(child, Node):
                if (not tag or child.tag == tag) and (not cls or cls in child.attrs.get('class','').split()):
                    yield child
                yield from child.walk(tag, cls)

    def one(self, tag=None, cls=None):
        return next(self.walk(tag, cls), None)

    def text(self):
        if self.tag in IGNORE-{'button','input'}:
            return ''
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.nodes = 0
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > 150000:
            raise importer.ImportError_('HTML节点过多，请选择单份模考报告')
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                break
            node = node.parent

    def handle_data(self, text):
        self.current.children.append(text)


def _decode(value):
    if not isinstance(value, str) or len(value) > MAX_FILE*4//3+10:
        raise importer.ImportError_('单个文件最多32MB')
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise importer.ImportError_('文件读取失败，请重新选择')
    if len(data) > MAX_FILE:
        raise importer.ImportError_('单个文件最多32MB')
    return data


def _zip(data):
    result, total = {}, 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 2500:
                raise importer.ImportError_('ZIP文件数量过多')
            for entry in archive.infolist():
                name = entry.filename
                if '\\' in name or name.startswith('/') or '..' in PurePosixPath(name).parts or entry.flag_bits & 1 or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise importer.ImportError_('ZIP含不安全路径、链接或加密文件')
                total += entry.file_size
                if total > MAX_EXPANDED or entry.file_size > MAX_FILE:
                    raise importer.ImportError_('ZIP解压内容过大，最多64MB')
                if entry.is_dir():
                    continue
                # 脚本/样式无需读取，不会解压或执行。
                if name.lower().endswith(('.js','.css','.exe','.dll','.下载')):
                    continue
                if name in result:
                    raise importer.ImportError_('ZIP含重复路径')
                result[name] = archive.read(entry)
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError):
        raise importer.ImportError_('无法读取ZIP，请选择未加密的完整压缩包')
    return result


def _image_type(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return '.png'
    if data.startswith(b'\xff\xd8\xff'): return '.jpg'
    if data.startswith((b'GIF87a', b'GIF89a')): return '.gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP': return '.webp'
    return ''


def extract(body):
    name = str(body.get('name') or '')
    data = _decode(body.get('data'))
    files = _zip(data) if name.lower().endswith('.zip') else {}
    if files:
        htmls = [n for n in files if n.lower().endswith(('.html','.htm')) and not n.startswith('__MACOSX/') and not any(part.endswith('_files') for part in PurePosixPath(n).parts[:-1])]
        if len(htmls) != 1:
            raise importer.ImportError_('整包ZIP中须有且仅有一份HTML；只有资源包时请把HTML选在上方、ZIP选在配套资源')
        name, data = htmls[0], files[htmls[0]]
    elif not name.lower().endswith(('.html','.htm')):
        raise importer.ImportError_('请选择HTML、HTM或包含HTML的ZIP')
    resources = body.get('resources')
    if resources:
        if not isinstance(resources, dict) or not str(resources.get('name','')).lower().endswith('.zip'):
            raise importer.ImportError_('配套资源请选择ZIP')
        files.update(_zip(_decode(resources.get('data'))))
    digest = hashlib.sha256(data+b'\0'+b''.join(n.encode('utf-8')+hashlib.sha256(v).digest() for n,v in sorted(files.items()))).hexdigest()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        try: text = data.decode('gb18030')
        except UnicodeDecodeError: raise importer.ImportError_('无法识别HTML编码，请另存为UTF-8')
    root = Document(text).root
    title = root.one('title')
    title = title.text().strip()[:160] if title else PurePosixPath(name).stem
    match = importer.SEASON_RE.search(title+' '+name)
    season = body.get('season') or (importer._cn2int(match.group(1)) if match else None)
    if type(season) is not int or not 1 <= season <= 9999:
        raise importer.ImportError_('未识别季号，请填写正确的第几季')
    digest = hashlib.sha256((digest+':'+str(season)).encode('ascii')).hexdigest()
    images, missing = {}, set()

    def render(node):
        if node is None: return ''
        if isinstance(node, str): return node
        if node.tag in IGNORE: return ''
        if node.tag == 'img':
            ref = node.attrs.get('src','')
            payload = b''
            if ref.startswith('data:image/') and ';base64,' in ref:
                try: payload = _decode(ref.split(';base64,',1)[1])
                except importer.ImportError_: pass
            elif not urlsplit(ref).scheme and not ref.startswith('//'):
                local = unquote(urlsplit(ref).path)
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name),local))
                if not target.startswith('/') and '..' not in PurePosixPath(target).parts:
                    payload = files.get(target,files.get(posixpath.normpath(local),b''))
                    if not payload:
                        # 资源ZIP常只压_files内的文件，允许唯一的尾路径匹配。
                        hits = [v for n,v in files.items() if n.endswith('/'+target) or target.endswith('/'+n)]
                        if len(hits) == 1: payload = hits[0]
            ext = _image_type(payload)
            if not ext:
                missing.add(ref[:200] or '无图片地址')
                return '【缺少图片】'
            rel = '训练/题库/图片/HTML/'+hashlib.sha256(payload).hexdigest()+ext
            images[rel] = payload
            return '![[%s]]' % rel
        out = ''.join(render(child) for child in node.children)
        if node.tag in ('p','div','section','br','tr','li'):out += '\n'
        if node.tag in ('td','th'):out += ' | '
        if node.tag == 'u':out = '____' if not out.strip() else out
        return out

    def plain(node):
        value = re.sub(r'\n[ \t]*\n+', '\n\n', render(node)).strip()
        return re.sub(r'(?m)^(?=#{1,6}\s|---\s*$)', r'\\', value)

    modules = {}
    card = root.one('app-answer-card')
    current = ''
    if card:
        for node in card.walk():
            classes = node.attrs.get('class','').split()
            if 'chapter-title' in classes: current = node.text().strip()
            if 'answer-btn' in classes and node.text().strip().isdigit(): modules[int(node.text().strip())] = current
    materials = {}
    for mat in root.walk('app-materials'):
        parent = mat.parent
        while parent.parent and not list(parent.walk('nav')): parent = parent.parent
        nav = parent.one('nav')
        nums = [int(n) for n in re.findall(r'(\d+)\s*题',nav.text())] if nav else []
        content = mat.one(cls='material-content')
        value = plain(content)
        for number in nums: materials[number] = (tuple(nums),value)
    questions, seen = [], set()
    for node in root.walk('app-ti'):
        index = node.one(cls='title-index')
        found = re.search(r'\d+',index.text() if index else '')
        if not found: raise importer.ImportError_('部分题目缺少题号，未导入')
        number = int(found.group())
        if number in seen: raise importer.ImportError_('HTML题号重复，未导入')
        seen.add(number)
        question = node.one('app-question-choice')
        stem_node = question.one('app-format-html') if question else None
        stem = plain(stem_node)
        options = {}
        mine = ''
        for option in node.walk('li','choice-radio'):
            radio = option.one(cls='input-radio')
            letter = radio.text().strip() if radio else ''
            if letter not in 'ABCD' or len(letter) != 1: continue
            options[letter] = plain(option.one(cls='input-text') or option.one('app-format-html'))
            if set(radio.attrs.get('class','').split()) & {'wrong','correct'}: mine = letter
        answer = node.one(cls='correct-answer')
        answer = answer.text().strip() if answer else ''
        analysis_node = node.one('app-result-common')
        analysis = '\n\n'.join(plain(n) for n in analysis_node.walk('app-format-html')) if analysis_node else ''
        topic_node = node.one('app-solution-keypoint')
        topic = re.sub(r'\s+', ' ', topic_node.text()).strip()[:200] if topic_node else importer.UNSORTED
        material = materials.get(number, ((),''))
        module = modules.get(number, '')
        board = importer.guess_board(module,stem,options)
        if module == '判断推理' and material[0]: board = '一拖五'
        if not board and module == '判断推理':
            if '定义' in topic: board = '定义判断'
            elif '削弱' in topic or '加强' in topic: board = '论证逻辑'
            elif '图形' in topic or '数量规律' in topic: board = '图形推理'
        problems = []
        if not stem: problems.append('题干缺失')
        if set(options) != set('ABCD') or not all(options.values()): problems.append('选项不完整')
        if answer not in ('A','B','C','D'): problems.append('标准答案缺失或非单选题')
        if board not in importer.BOARDS: problems.append('板块未识别')
        questions.append(dict(num=number,id='粉笔%d季-%03d' % (season,number),board=board,module=module,topic=topic,
            stem=(material[1]+'\n\n' if material[1] else '')+stem,question=stem,material=material[1],material_nums=material[0],
            options=options,answer=answer,analysis=analysis,mine=mine,source='粉笔第%d季模考' % season,problems=problems))
    # 与原mock.FIXED共用粉笔35题判断分布，仅在图形/类比/材料结构吻合时采用。
    from . import mock
    judgments = [q for q in questions if q['module'] == '判断推理']
    fixed = mock.FIXED['判断推理']
    if len(judgments) == sum(n for _,n in fixed) and all(q['board'] == '图形推理' for q in judgments[:10]) and all(q['board'] == '类比推理' for q in judgments[20:25]) and all(q['material_nums'] for q in judgments[-5:]):
        offset = 0
        for board, count in fixed:
            for q in judgments[offset:offset+count]:
                q['board'] = board
                q['problems'] = [x for x in q['problems'] if x != '板块未识别']
            offset += count
    if set(modules)-seen: raise importer.ImportError_('网页仅保存了部分题目（%d/%d），请展开全部解析后重新保存完整HTML' % (len(seen),len(modules)))
    if not questions: raise importer.ImportError_('没有找到已保存的粉笔题目内容；请保存已展开解析的完整网页')
    if len(questions) > 500: raise importer.ImportError_('请一次导入一份模考试卷')
    return dict(title=title,season=season,questions=questions,images=images,missing=sorted(missing),digest=digest)


def import_file(paths, body):
    with LOCK:
        return _import_file(paths, body)


def _import_file(paths, body):
    if getattr(paths,'subject','') != '行测': raise importer.ImportError_('粉笔行测HTML导入仅用于行测科目')
    if 'commit' in body and type(body['commit']) is not bool: raise importer.ImportError_('导入确认须为布尔值')
    result = extract(body)
    qs, season = result['questions'], result['season']
    known, _ = importer.existing(paths.train/'题库')
    duplicate = [q for q in qs if q['id'] in known]
    ready = [q for q in qs if q['id'] not in known]
    blocked = [q for q in qs if q['problems']]
    report = dict(title=result['title'],season=season,total=len(qs),ready=0 if blocked or result['missing'] else len(ready),dup=len(duplicate),
        images=len(result['images']),missing_images=len(result['missing']),missing=result['missing'][:20],
        problems=[dict(num=q['num'],reasons=q['problems']) for q in blocked[:20]],blocked=len(blocked),digest=result['digest'],
        boards=Counter(q['board'] or '待识别' for q in qs).most_common(),dry=not body.get('commit'))
    if not body.get('commit'): return report
    if body.get('digest') != result['digest']: raise importer.ImportError_('文件或资源已变化，请重新检查后导入')
    if blocked or result['missing']: raise importer.ImportError_('题目结构或图片不完整，请补齐HTML与_files资源后重新检查；未写入题库')
    # 先生成全部输出，再按原模块原子写文件；只补缺图，不覆盖任何已有美术。
    for rel, data in result['images'].items():
        file = paths.vault/rel
        file.parent.mkdir(parents=True,exist_ok=True)
        if not file.exists():
            fd, temporary = tempfile.mkstemp(prefix='.html-image-',dir=str(file.parent))
            try:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(data);stream.flush();os.fsync(stream.fileno())
                if not file.exists():os.replace(temporary,file)
            finally:
                if os.path.exists(temporary):os.unlink(temporary)
    by = {}
    for q in ready:
        block = importer.bank_block(q).replace('### 解析\n'+importer.TODO+'\n','### 解析\n'+(q['analysis'] or importer.TODO)+'\n')
        by.setdefault(q['board'],[]).append(block)
    for board, blocks in by.items():
        file = paths.train/'题库'/(board+'真题.md')
        old = file.read_text(encoding='utf-8-sig') if file.exists() else '# '+board+'真题\n'
        importer._write(file,old.rstrip()+'\n\n'+''.join(blocks))
    # 已有PDF/HTML复盘优先，用户笔记和对错一字不改。
    prior = next((d for n,d in vault.seasons(paths) if n == season and any(d.glob('[0-9][0-9]-*.md'))),None)
    writable_prior = False
    if prior:
        try: prior.resolve().relative_to(paths.train.resolve());writable_prior=True
        except ValueError: pass
    if not prior or writable_prior:
        folder = prior or paths.train/'模考复盘'/('第%d季' % season)
        existing_boards = {f.stem[3:] for f in folder.glob('[0-9][0-9]-*.md')}
        for board in dict.fromkeys(q['board'] for q in qs):
            if board in existing_boards:continue
            lines, groups = [], set()
            for q in (q for q in qs if q['board'] == board):
                group = q['material_nums']
                if group and group not in groups:
                    groups.add(group)
                    lines.append('## 材料（第%d-%d题）\n%s\n---\n' % (min(group),max(group),q['material']))
                icon = '✅' if q['mine'] and q['mine'] == q['answer'] else '❌' if q['mine'] else '⚪'
                lines.append('### %d. %s\n%s\n%s\n> [!check]- 答案\n> 正确答案：**%s**　我的答案：**%s**\n> [!note] 复盘\n%s\n---\n' % (
                    q['num'],icon,q['question'],'\n'.join('- **%s.** %s' % (k,q['options'][k]) for k in 'ABCD'),q['answer'],q['mine'] or '?',
                    '\n'.join('> '+line for line in q['analysis'].splitlines())))
            importer._write(folder/('%02d-%s.md' % (importer.BOARDS.index(board)+1,board)),''.join(lines))
    report['review_preserved'] = bool(prior)
    return report
