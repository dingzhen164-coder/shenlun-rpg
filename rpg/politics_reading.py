"""万象峰研读重点位置。politics/wanxiang_journal调用，纯文本按Unicode码点定位。

原文/批注不改写；取消及重新标红存训练/时政重点/<来源内容摘要>.json的added/removed区间。
仅输出ranges，不再生成消化挖空；独立清单由politics_digest负责。不调用AI、不发奖励。
"""
import re


def normalized(text):
    return ''.join(c for c in text if not c.isspace())


def merge(ranges):
    out = []
    for a, b in sorted(ranges):
        if a >= b:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def subtract(ranges, cuts):
    result = merge(ranges)
    for a, b in merge(cuts):
        result = [part for x, y in result for part in ([x, min(y, a)], [max(x, b), y]) if part[0] < part[1]]
    return merge(result)


def raw_ranges(text, ranges):
    """旧originalEmphasis的原文坐标转为去空白码点坐标。"""
    result = []
    for row in ranges or []:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            continue
        a, b = row
        if type(a) is int and type(b) is int and 0 <= a < b <= len(text):
            result.append([len(normalized(text[:a])), len(normalized(text[:b]))])
    return merge(result)


def anchor_range(text, anchor):
    """选词必须属于同一真实段落；block_offset区分内容完全相同的重复段落。"""
    from .politics import PoliticsError
    paragraph = anchor.get('paragraph', '')
    start, end = anchor.get('start'), anchor.get('end')
    if not isinstance(paragraph, str) or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(paragraph):
        raise PoliticsError('选词位置无效，请重新选择')
    if paragraph[start:end] != anchor.get('word') or not normalized(anchor.get('word', '')):
        raise PoliticsError('选词位置已变化，请重新选择')
    whole, block = normalized(text), normalized(paragraph)
    hint = anchor.get('block_offset')
    offset = whole.find(block) if hint is None else hint
    if type(offset) is not int or offset < 0 or whole[offset:offset+len(block)] != block:
        raise PoliticsError('原文已变化，请重新打开资料')
    return [offset+len(normalized(paragraph[:start])), offset+len(normalized(paragraph[:end]))]


def cloze_ranges(text, rows):
    """沿用期刊红字的上下文定位，不把所有同名词都标红。返回区间及旧进度键。"""
    whole, cursor, out, keys = normalized(text), 0, [], {}
    for row, old_index in rows:
        for i, part in enumerate(row.get('parts', [])):
            answer = normalized(part.get('a', ''))
            if not answer:
                continue
            pre = normalized(''.join(p.get('t', p.get('a', '')) for p in row['parts'][:i]))[-12:]
            at = whole.find(pre+answer, cursor) if pre else -1
            at = at+len(pre) if at >= 0 else whole.find(answer, cursor)
            if at < 0:
                continue
            end = at+len(answer)
            out.append([at, end]);keys[(at, end)] = '%s-%s' % (old_index, i)
            cursor = end
    return out, keys


def reading(pp, src):
    from . import politics
    text = src['text'];whole = normalized(text)
    spans = list(src.get('emphasis', []))
    for note in (politics.list_notes(pp, src).values() if pp is not None else []):
        try:
            spans.append(anchor_range(text, note))
        except (politics.PoliticsError, TypeError, AttributeError):
            continue
    custom = politics.read_json(pp.train/'时政重点'/(politics.identity(src)+'.json'), {'added': [], 'removed': []}) if pp is not None else {}
    valid = lambda rows: [r for r in rows if isinstance(r, list) and len(r) == 2 and all(type(x) is int for x in r) and 0 <= r[0] < r[1] <= len(whole)]
    spans = subtract(valid(spans)+valid(custom.get('added', [])), valid(custom.get('removed', [])))
    return {'ranges': spans, 'edited': bool(valid(custom.get('added', [])) or valid(custom.get('removed', [])))}


def mark(pp, src, body):
    from . import politics
    if type(body.get('enabled')) is not bool:
        raise politics.PoliticsError('请选择标红或取消标红')
    span = anchor_range(src['text'], politics.validate_anchor(src, body))
    with politics._LOCK:
        file = pp.train/'时政重点'/(politics.identity(src)+'.json')
        data = politics.read_json(file, {'added': [], 'removed': []})
        own, other = ('added', 'removed') if body['enabled'] else ('removed', 'added')
        data[own] = merge(data.get(own, [])+[span])
        data[other] = subtract(data.get(other, []), [span])
        politics.atomic_json(file, data)
        return reading(pp, src)


def clear(pp, src, on):
    """这一篇一键取消全部红标记（on=True）或恢复成原来的红标记（on=False）。
    只改“训练/时政重点”里的added/removed，不动原文、批注、消化清单的空和进度，不发奖励、不调AI。"""
    from . import politics
    with politics._LOCK:
        file = pp.train/'时政重点'/(politics.identity(src)+'.json')
        if on:
            data = politics.read_json(file, {'added': [], 'removed': []})
            data = {'added': [], 'removed': merge(list(data.get('removed', [])) + reading(pp, src)['ranges'])}
        else:
            data = {'added': [], 'removed': []}
        politics.atomic_json(file, data)
        return reading(pp, src)
