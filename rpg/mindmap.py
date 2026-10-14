"""🌿 灵脉图：每个板块的思维导图（编辑器用 simple-mind-map，github.com/wanglin2/mind-map，MIT，放在 web/vendor/mindmap/）。

- 存在库里 训练/灵脉图/<板块>/<名字>.json（simple-mind-map 的完整数据：root 节点树 + layout / theme / view），坚果云同步；
  一个板块可以有好几幅；资料库首次编辑可建空图，修炼只读入口不建空图。
- 导入：.xmind / Markdown / .json（.smm）在网页上转成节点树再存；导出：xmind / png / Markdown / json 存到 训练/灵脉图/导出/。
"""
import base64
import datetime as dt
import json
import re
from pathlib import Path

BOARDS = ["政治理论", "常识判断", "逻辑填空", "片段阅读", "数量关系", "图形推理", "定义判断",
          "类比推理", "论证逻辑", "形式逻辑", "一拖五", "资料分析"]
BOARDS_SHENLUN = ["归纳概括", "综合分析", "提出对策", "贯彻执行", "大作文"]


def default_boards():
    """默认的脉络图题型（板块）：行测 12 个；申论 5 个题型"""
    from . import subjects
    return BOARDS_SHENLUN if subjects.active() == "申论" else BOARDS
EXPORT_EXT = {"xmind", "png", "md", "json", "svg", "pdf"}


class MapError(Exception):
    pass


def folder(paths):
    return paths.train / "灵脉图"


def _safe(name, what="名字"):
    name = re.sub(r'[\\/:*?"<>|#^\[\]\n\r\t]+', " ", str(name or "")).strip()[:40]
    if not name or name.startswith("."):
        raise MapError("%s不能是空的" % what)
    return name


def _file(paths, board, name):
    f = (folder(paths) / _safe(board, "板块") / (_safe(name) + ".json")).resolve()
    if paths.train.resolve() not in f.parents or paths.vault.resolve() not in f.parents:
        raise MapError("导图路径必须位于当前库的训练文件夹内")
    return f


def _count(node):
    return 1 + sum(_count(c) for c in (node or {}).get("children") or [])


def blank(title):
    return {"root": {"data": {"text": title}, "children": []}, "layout": "logicalStructure"}


def listing(paths):
    """[{board, maps: [{name, nodes, updated}]}]：默认 12 个板块在前，自己建的其它板块（文件夹）在后"""
    d = folder(paths)
    boards = list(default_boards())
    if d.is_dir():
        boards += sorted(p.name for p in d.iterdir() if p.is_dir() and p.name not in boards and p.name != "导出")
    out = []
    for b in boards:
        maps = []
        for f in sorted((d / b).glob("*.json")) if (d / b).is_dir() else []:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                n = _count(data.get("root"))
            except (OSError, ValueError):
                n = 0
            maps.append({"name": f.stem, "nodes": n, "updated": dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")})
        out.append({"board": b, "maps": maps})
    return {"boards": out}


def get(paths, board, name):
    f = _file(paths, board, name)
    if not f.is_file():
        if name == board:                 # 第一次打开这个板块：建一幅空的
            return save(paths, board, name, blank(board))
        raise MapError("这幅灵脉图不见了（可能在另一台电脑上删了）")
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        raise MapError("这幅灵脉图的文件坏了：%s" % f.name)
    return {"board": board, "name": f.stem, "data": data}


def save(paths, board, name, data):
    if not isinstance(data, dict) or not isinstance(data.get("root"), dict):
        raise MapError("数据不对：没有根节点")
    f = _file(paths, board, name)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)
    return {"board": board, "name": f.stem, "data": data, "nodes": _count(data["root"])}


def create(paths, board, name, data=None):
    f = _file(paths, board, name)
    base, k = f.stem, 2
    while f.exists() or f.with_suffix(".md").exists():                       # 重名就加个“（2）”
        f = f.with_name("%s（%d）.json" % (base, k))
        k += 1
    return save_document(paths, board, f.stem, data or blank(f.stem))


def rename(paths, board, name, new):
    f, g = _file(paths, board, name), _file(paths, board, new)
    if not f.is_file():
        raise MapError("这幅灵脉图不见了")
    if (g.exists() or g.with_suffix(".md").exists()) and g != f:
        raise MapError("已经有一幅叫「%s」的了" % g.stem)
    with _LOCK:
        f.replace(g)
        if f.with_suffix(".md").exists():
            f.with_suffix(".md").replace(g.with_suffix(".md"))
    return {"board": board, "name": g.stem}


def delete(paths, board, name):
    f = _file(paths, board, name)
    with _LOCK:
        for target in (f, f.with_suffix(".md")):
            if target.is_file():
                target.unlink()
    return {"ok": True}


def export(paths, board, name, ext, data_url):
    """网页导出的结果（dataURL）存到 训练/灵脉图/导出/<名字>.<扩展名>"""
    ext = str(ext or "").lower()
    if ext not in EXPORT_EXT:
        raise MapError("不支持导出成 %s" % ext)
    m = re.match(r"^data:[^;,]*(?:;[^,]*)?;base64,(.+)$", str(data_url or ""), re.S)
    if m:
        raw = base64.b64decode(m.group(1))
    elif str(data_url or "").startswith("data:"):
        from urllib.parse import unquote
        raw = unquote(str(data_url).split(",", 1)[1]).encode("utf-8")
    else:
        raise MapError("导出的数据不对")
    d = export_dir(paths)
    d.mkdir(parents=True, exist_ok=True)
    f = d / ("%s.%s" % (_safe(name), ext))
    f.write_bytes(raw)
    return {"path": f.relative_to(paths.vault).as_posix(), "name": f.name, "size": f.stat().st_size}


def export_dir(paths):
    return folder(paths) / "导出"

# 3.1.0：导图旁的Markdown是可在本地编辑的分级文档；浏览不改JSON，保存用内容指纹防止覆盖外部修改。
import hashlib
import copy
import time
import uuid
import threading
from html.parser import HTMLParser
_LOCK = threading.RLock()
_READERS = {}


class _Text(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('p', 'div'):
            self.parts.append('\n')


def _text(node):
    text = str((node.get('data') or {}).get('text') or '')
    if (node.get('data') or {}).get('richText'):
        parser = _Text()
        parser.feed(text)
        text = ''.join(parser.parts).strip()
    return text


def to_markdown(root):
    """根标题 + 缩进列表，支持超过六级；转义列表文本，避免将文字误作标题或HTML。"""
    out = ['# ' + _text(root).replace('\n', ' '), '']
    def walk(node, depth):
        text = _text(node).replace('\\', '\\\\')
        text = re.sub(r'([`*_<>\[\]#])', r'\\\1', text)
        lines = text.split('\n')
        out.append('  ' * depth + '- ' + lines[0])
        for line in lines[1:]:
            out.append('  ' * depth + '  ' + line)
        for child in node.get('children') or []:
            walk(child, depth + 1)
    for child in root.get('children') or []:
        walk(child, 0)
    return '\n'.join(out) + '\n'


def from_markdown(text, title):
    """读取#标题与缩进列表，正文续行保留在节点内；只转换结构，不执行HTML。"""
    root = {'data': {'text': title}, 'children': []}
    heads = [(0, root)]
    items = []
    current = root
    first = True
    for line in text.expandtabs(2).splitlines():
        if not line.strip():
            continue
        h = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', line)
        li = re.match(r'^(\s*)(?:[-+*]|\d+[.)])\s+(.*)$', line)
        if h:
            level, value = len(h.group(1)), h.group(2)
            if first and level == 1:
                root['data']['text'] = value
                heads = [(1, root)]
                current = root
            else:
                while len(heads) > 1 and heads[-1][0] >= level:
                    heads.pop()
                current = {'data': {'text': value}, 'children': []}
                heads[-1][1]['children'].append(current)
                heads.append((level, current))
            items = []
        elif li:
            indent = len(li.group(1))
            while items and items[-1][0] >= indent:
                items.pop()
            value = re.sub(r'\\([\\`*_<>\[\]#])', r'\1', li.group(2))
            current = {'data': {'text': value}, 'children': []}
            (items[-1][1] if items else heads[-1][1])['children'].append(current)
            items.append((indent, current))
        else:
            value = re.sub(r'\\([\\`*_<>\[\]#])', r'\1', line.strip())
            current['data']['text'] += '\n' + value
        first = False
    return root


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _atomic(f, text):
    tmp = f.with_name(f.name + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(f)


def document(paths, board, name, create_missing=True):
    """旧JSON首次浏览生成旁置.md；已有.md直接读取，始终保留外部修改。"""
    with _LOCK:
        f = _file(paths, board, name)
        if not f.is_file():
            if not create_missing:
                data = blank(name or board)
                return dict(board=board, name=name or board, data=data, markdown=to_markdown(data['root']), document_path='', document_revision='')
            get(paths, board, name)
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except (ValueError, OSError) as e:
            raise MapError('导图文件无法读取：%s' % f.name) from e
        md = f.with_suffix('.md')
        if paths.train.resolve() not in md.resolve().parents or paths.vault.resolve() not in md.resolve().parents:
            raise MapError('Markdown文档必须在当前库的训练目录内')
        if not isinstance(data, dict) or not isinstance(data.get('root'), dict):
            raise MapError('导图文件缺少根节点：%s' % f.name)
        generated = to_markdown(data['root'])
        if not md.exists():
            _atomic(md, generated)
        text = md.read_text(encoding='utf-8-sig')
        if text != generated:
            data = copy.deepcopy(data)
            data['root'] = from_markdown(text, f.stem)
            data.pop('view', None)
        return dict(board=board, name=f.stem, data=data, markdown=text,
                    document_path=md.relative_to(paths.vault.resolve()).as_posix(), document_revision=_digest(text))


def save_document(paths, board, name, data, revision=None):
    with _LOCK:
        f = _file(paths, board, name)
        md = f.with_suffix('.md')
        if paths.train.resolve() not in md.resolve().parents or paths.vault.resolve() not in md.resolve().parents:
            raise MapError('Markdown文档必须在当前库的训练目录内')
        if md.exists():
            text = md.read_text(encoding='utf-8-sig')
            expected = revision
            if expected is None and f.exists():
                expected = _digest(to_markdown(json.loads(f.read_text(encoding='utf-8'))['root']))
            if expected != _digest(text):
                raise MapError('本地Markdown已修改，请重新载入后再编辑，避免覆盖新内容')
        result = save(paths, board, name, data)
        text = to_markdown(data['root'])
        _atomic(md, text)
        result.update(document_path=md.relative_to(paths.vault.resolve()).as_posix(), document_revision=_digest(text))
        return result


def start_reading(paths, board, name):
    """只读入口签发短期阅读凭据，绑定当前库和板块；计时仍由原心跳统一累计。"""
    now = time.time()
    with _LOCK:
        for key, value in list(_READERS.items()):
            if now - value['time'] > 43200:
                _READERS.pop(key, None)
        if len(_READERS) >= 256:
            _READERS.pop(next(iter(_READERS)))
        token = uuid.uuid4().hex
        _READERS[token] = dict(vault=str(paths.vault.resolve()), subject=getattr(paths,'subject','法考'), board=_safe(board, '板块'), name=name, time=now)
        return token


def reading(paths, token):
    with _LOCK:
        value = _READERS.get(str(token or ''))
        if not value or value['vault'] != str(paths.vault.resolve()) or value['subject'] != getattr(paths,'subject','法考') or time.time() - value['time'] > 43200:
            return None
        value['time'] = time.time()
        return value['board']


def end_reading(token):
    with _LOCK:
        _READERS.pop(str(token or ''), None)
    return {'ok': True}
