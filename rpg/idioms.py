"""逻辑填空选项分词：粉笔模考 PDF 拆出来的选项常把几个词连在一起（“截然不同歪曲”），按空数切开给网页显示。

（2026-11 起，原“成语实词录”自动收录词条的功能已取消；词录改为以组为单位读用户本地文档，见 rpg/wordbook.py。
本模块只保留分词：trainer.display 调用 display_options。）
"""
import re

from . import question_bank


def split_words(opt):
    """“蕴含  方兴未艾” → [蕴含, 方兴未艾]"""
    return [w for w in re.split(r'[\s　，,、；;/｜|]+', (opt or '').strip()) if w]


# ---------------------------------------------------------------- 选项里几个词连在一起（粉笔模考 PDF 导入时空格丢了）
# “克服渐进性纠正”要切成 克服 / 渐进性 / 纠正：没有词典库，就用题库自己当词典——历年逻辑填空里用空格分好的选项词、
# 解析里打了引号的词；再看四个选项同一个空的词长是不是一致、结尾是不是同一个字（渐进性 / 持续性 / 阶段性）。
_VOCAB = {'sig': None, 'words': set()}


def vocab(g):
    files = question_bank.files(g.paths, '逻辑填空') if g.paths.train else []
    sig = tuple((str(f), f.stat().st_mtime_ns) for f in files)
    if _VOCAB['sig'] != sig:
        words = set()
        for q in question_bank.read_all(g.paths, '逻辑填空')[0]:
            single = blanks(q.get('stem')) == 1          # 只有一个空：选项就是一个完整的词（多是成语），也收
            for v in q['options'].values():
                ws = split_words(v)
                if len(ws) > 1 or (single and len(ws) == 1 and 2 <= len(ws[0]) <= 4):
                    words.update(w for w in ws if 2 <= len(w) <= 6)
            words.update(w for w in re.findall(r'“([\u4e00-\u9fff]{2,6})”', q.get('analysis') or ''))
        _VOCAB.update(sig=sig, words=words)
    return _VOCAB['words']


def _cuts(text, k):
    """把 text 切成 k 段、每段 2–4 个字的所有切法"""
    if k == 1:
        return [[text]] if 2 <= len(text) <= 4 else []
    out = []
    for n in (2, 3, 4):
        if len(text) - n >= 2 * (k - 1):
            out += [[text[:n]] + rest for rest in _cuts(text[n:], k - 1)]
    return out


def resplit(opts, k, words, scored=False):
    """四个选项都没分词时一起切：词典里有的词加分，同一个空四个选项词长一致、结尾同字加分，三字词略减分。
    切不出（字数对不上）返回 None"""
    import itertools
    keys = sorted(opts)
    cands = [_cuts(opts[x], k) for x in keys]
    if not all(cands) or len(keys) < 2:
        return None
    def one(w):
        if w in words:
            return 3
        if len(w) == 3:
            return 1 if w[-1] in SUFFIX else -2
        if len(w) == 4 and (w[:2] in words or w[2:] in words):   # 没见过的四字块，一半是认识的双字词：多半是两个词拼的
            return -2
        return 0

    def own(seg):
        return sum(one(w) for w in seg)
    # 每个选项先按自己的分数留前几种切法，再一起比对齐
    cands = [sorted(c, key=own, reverse=True)[:6] for c in cands]
    best, best_score, second = None, None, None
    for combo in itertools.product(*cands):
        score = sum(own(seg) for seg in combo)
        for i in range(k):
            col = [seg[i] for seg in combo]
            lens = [len(w) for w in col]
            score += 2 * (max(lens.count(n) for n in set(lens)) - 1)
            if all(len(w) == 3 for w in col) and len({w[-1] for w in col}) == 1 and col[0][-1] in SUFFIX:
                score += 4
        if best_score is None or score > best_score:
            second = best_score
            best, best_score = combo, score
        elif second is None or score > second:
            second = score
    out = dict(zip(keys, (list(x) for x in best)))
    return (out, best_score == second) if scored else out


SUFFIX = set('性化感度力型式者家学观论率量制界级态')   # 三字词常见的后缀：渐进性、现代化、获得感……


def blanks(stem):
    return len(re.findall(r'_{2,}|＿{2,}|（\s*）|\(\s*\)', stem or ''))


def is_fill(q):
    return q.get('board') == '逻辑填空' or str(q.get('topic', '')).startswith('逻辑填空')


def display_options(g, stem, opts):
    """逻辑填空的选项几个词连在一起（粉笔模考 PDF 拆出来空格丢了，如“截然不同歪曲”）：按题干的空数切开，
    用全角空格连回去给网页显示（“截然不同　歪曲”）。切不出、本来就分好了，原样返回"""
    if not opts or any(len(split_words(v)) != 1 for v in opts.values()):
        return opts
    k = blanks(stem)
    longest = max(len(v.strip()) for v in opts.values())
    raw = {x: v.strip() for x, v in opts.items()}
    cache = g.state.setdefault('fill_split', {})          # AI 切过的存下来，下次不再问
    key = '|'.join(raw[x] for x in sorted(raw))
    if key in cache:
        return dict(cache[key])
    for kk in ([k] if k >= 2 else ([2, 3] if longest >= 7 else [])):
        got = resplit(raw, kk, vocab(g), scored=True)
        if not got:
            continue
        split, tie = got
        if tie:                                             # 词典分不出（如 截然不同|歪曲 还是 截然|不同歪曲）：问一次 AI
            split = _ai_split(raw, kk) or split
        out = {x: "　".join(ws) for x, ws in split.items()}
        if tie and split is not got[0]:
            cache[key] = out
        return out
    return opts


def _ai_split(raw, k):
    """让 AI 把连在一起的选项切成 k 个词；切完拼回去必须和原文一模一样，不然不用"""
    from . import ai
    if not ai.available():
        return None
    msg = [{"role": "system", "content": "你是行测逻辑填空的助手，只输出 JSON。"},
           {"role": "user", "content": "下面是一道有 %d 个空的逻辑填空题的四个选项，每个选项是 %d 个词连在一起写的（空格丢了）。"
            "按词切开，返回 JSON：{\"A\": [\"词1\", \"词2\"], ...}，每个选项正好 %d 个词，不改任何字。\n%s" % (
                k, k, k, "\n".join("%s. %s" % kv for kv in sorted(raw.items())))}]
    try:
        got = ai.chat_json(msg, temperature=0)
    except Exception:
        return None
    if not isinstance(got, dict) or set(got) != set(raw):
        return None
    out = {}
    for x, ws in got.items():
        if not isinstance(ws, list) or len(ws) != k or "".join(map(str, ws)) != raw[x]:
            return None
        out[x] = [str(w) for w in ws]
    return out
