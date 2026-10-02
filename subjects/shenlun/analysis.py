"""
从“真题解析文档”（机构出的 PDF / 文本）起草采分点。

做什么：
    1. read_source   读 .txt/.md，或 .pdf（依次尝试 pymupdf、pdftotext；都没有就提示用户先转成文本）；
    2. clean         去掉页眉页脚、水印残片；
    3. split_questions 按“第N题”切成一题一块，抽出 题干 / 分值 / 字数 / 题型 / 各章节 / 得分要点清单 / 参考答案；
    4. draft         把“得分要点清单”交给 AI 结构化成采分点（AI 只负责抄表，不打分值），
                     程序校验并按 0.5 分粒度分配分值，写成状态“草稿”的采分点文件，等用户审定。

为什么不用规则直接解析表格：PDF 表格转文字后单元格会断行、被水印打乱，各家解析文档的版式也不同，
规则解析很脆；让 AI 抄表再由程序校验更稳。AI 输出必须能通过 rubric.validate，关键词必须在文档原文里出现
（防止 AI 自己编关键词）。

数据格式：块 = {no, stem, score, words, type, sections: {标题: 文本}, table, bonus_table, answers: [文本]}。
谁调用：命令行 python -m subjects.shenlun.analysis；M1 后续会接到网页的“导入解析文档”。
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import rubric

# 页眉页脚、水印特征
NOISE_LINE = re.compile(r"上岸杜弗伦|©\s*20\d\d|第\s*\d+\s*页\s*/\s*共\s*\d+\s*页|反不正当竞争法|未经授权获取")
WATERMARK_TAIL = re.compile(r"\s{8,}/[抖微小红书].{0,6}$")
HEADING_RE = re.compile(r"^\s*([一二三四五六七八九十]+)、\s*(.+?)\s*$")


def read_source(path):
    p = Path(path)
    if p.suffix.lower() in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() == ".pdf":
        try:
            import fitz  # pymupdf，可选
            with fitz.open(str(p)) as doc:
                return "\n".join(pg.get_text() for pg in doc)
        except ImportError:
            pass
        exe = shutil.which("pdftotext")
        if exe:
            out = subprocess.run([exe, "-layout", str(p), "-"], stdout=subprocess.PIPE, check=True)
            return out.stdout.decode("utf-8", "replace")
        raise RuntimeError("读不了 PDF：请先 pip install pymupdf，或把 PDF 另存/复制成 .txt 再导入")
    raise RuntimeError("只支持 .txt / .md / .pdf")


def _is_watermark(ln):
    """缩进很深的碎字 = 水印。≤2 字一律算；3-4 字只有含字母数字符号才算（纯中文 4 字可能是被换行的单元格，如“撤销项目”）"""
    indent = len(ln) - len(ln.lstrip())
    core = re.sub(r"\s", "", ln)
    if indent < 20 or not core:
        return False
    if len(core) <= 2:
        return True
    return len(core) <= 4 and not re.fullmatch(r"[\u4e00-\u9fff]+", core)


def clean(text):
    out = []
    for ln in text.splitlines():
        if NOISE_LINE.search(ln):
            continue
        ln = WATERMARK_TAIL.sub("", ln).rstrip()
        if _is_watermark(ln):
            continue
        out.append(ln)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text)


def _first(rx, s, conv=None):
    m = rx.search(s)
    if not m:
        return None
    v = m.group(1)
    return conv(v) if conv else v


def split_questions(text):
    """清洗后的全文 → 题块列表"""
    lines = clean(text).splitlines()
    starts = [i for i, ln in enumerate(lines) if re.match(r"^\s*(?:[^\n]*·\s*)?第\s*(\d+)\s*题\s*$", ln)]
    blocks = []
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        # 下一块的标题行（“国考 · 26 · ……”）在“第N题”前一行，要从本块去掉
        if k + 1 < len(starts) and end > 0 and "·" in lines[end - 1] and "第" not in lines[end - 1]:
            end -= 1
        seg = lines[i:end]
        no = int(re.search(r"第\s*(\d+)\s*题", seg[0]).group(1))
        body = "\n".join(seg)
        blocks.append(_parse_block(no, body))
    return blocks


def _tidy(txt):
    """参考答案：去掉水印碎字行（缩进深且 ≤2 个字）"""
    keep = [ln for ln in txt.splitlines() if not (len(ln) - len(ln.lstrip()) >= 15 and len(ln.strip()) <= 2)]
    return re.sub(r"\n\s*\n+", "\n", "\n".join(keep)).strip()


def _parse_block(no, body):
    secs, cur, buf = {}, "_head", []
    for ln in body.splitlines():
        h = HEADING_RE.match(ln)
        if h and len(ln.strip()) < 30:
            secs[cur] = "\n".join(buf).strip()
            cur, buf = h.group(2), []
        else:
            buf.append(ln)
    secs[cur] = "\n".join(buf).strip()
    head = secs.get("_head", "")
    # 题干：开头到“解题解析”之前（含“要求”）
    stem_part = re.split(r"\n[^\n]*解题解析", head)[0]
    stem_lines = [ln for ln in stem_part.splitlines()  # 题干行从不深缩进，深缩进的碎字都是水印
                  if not (len(ln) - len(ln.lstrip()) >= 15 and len(ln.strip()) <= 8)]
    stem_part = "\n".join(stem_lines)
    if "题干" in stem_part:  # 题干标记之前只可能是标题和水印
        stem_part = stem_part.split("题干", 1)[1]
    stem = re.sub(r"^\s*[❓?？]?\s*题干\s*", "", re.sub(r"^\s*第\s*\d+\s*题\s*", "", stem_part)).strip()
    stem = re.sub(r"\n\s*\n", "\n", stem)
    score = _first(re.compile(r"[（(]\s*(\d+)\s*分\s*[）)]"), stem, int)
    words = _first(re.compile(r"不超过\s*(\d+)\s*字"), stem, int) or _first(re.compile(r"(\d+)\s*字左右"), stem, int)
    typ = ""
    for key, txt in secs.items():
        if "题型" in key:
            m = re.search(r"(?:题型[：:]|本题属于[：:]?)\s*([^\n（(，。]+)", txt)
            typ = m.group(1).strip() if m else ""
    if not typ:
        m = re.search(r"(?:题型[：:]|本题属于[：:])\s*([^\n（(，。]+)", body)
        typ = m.group(1).strip() if m else ""
    table = next((t for k, t in secs.items() if "得分要点" in k), "")
    # 参考答案：从“参考答案”之后到块尾
    ans_txt = body[body.index("参考答案"):] if "参考答案" in body else ""
    answers = [_tidy(a) for a in re.split(r"参考答案\s*\d+\s*[（(][^）)]*[）)]", ans_txt)[1:] if a.strip()]
    return {"no": no, "stem": stem, "score": score, "words": words, "type": typ,
            "sections": secs, "table": table, "answers": answers}


PROMPT = """你是申论采分点整理助手。下面是一份真题解析文档里「得分要点清单」的文字（表格被转成了文字，可能断行、有水印残片）。
请把它整理成采分点，只做“抄表”，不要自己增删观点：
- points：必踩/核心采分点，按文档顺序；name 用文档里的“前置提炼 / 要点类别”，没有就用内容概括成 4-8 个字；
  keywords 是该点下的关键词/短语列表，必须是文档原文里出现的词句，保持原样，不要改写，不要合并；
  source 是“材料依据/材料来源”（如“第2-3段”），没有就留空。
- bonus：文档里“加分点”部分的内容，格式同 points；没有就给空数组。
只返回 JSON：{"points":[{"name":"","keywords":[""],"source":""}],"bonus":[{"name":"","keywords":[""],"source":""}]}

题干：
%s

得分要点清单原文：
%s
"""


def _split_bonus(table):
    """把“得分要点清单”文本拆成 (主表, 加分点表)"""
    m = re.search(r"【加分点】|加分点", table)
    return (table[:m.start()], table[m.start():]) if m else (table, "")


def in_text(kw, haystack):
    """关键词是否出现在原文里（haystack 已去空白）。
    表格单元格被换行后，中间常夹着相邻列的内容，所以整词找不到时，按“/”“+”拆成片段，每个片段（≥2 字）都在原文里就算在。"""
    k = re.sub(r"\s", "", str(kw))
    if k and k in haystack:
        return True
    frags = [f for f in re.split(r"[/+＋]", k) if f]
    return len(frags) > 1 and all(len(f) >= 2 and f in haystack for f in frags)


def draft(block, chat_json, qid, source="用户提供"):
    """
    block → rubric dict（状态=草稿）。chat_json(messages) → dict，生产环境传 core.ai.chat_json，测试传假 AI。
    校验：关键词必须在块原文里出现；采分点分值按总分均分。
    """
    if not block["table"]:
        raise rubric.RubricError("第%d题没有找到“得分要点清单”" % block["no"])
    if not block["score"]:
        raise rubric.RubricError("第%d题没能识别分值（题干里要有“（N分）”）" % block["no"])
    msg = [{"role": "user", "content": PROMPT % (block["stem"], block["table"])}]
    data = chat_json(msg)
    haystack = re.sub(r"\s", "", block["table"])
    warns = []

    def norm(items, label):
        res = []
        for it in items or []:
            kws = []
            for k in it.get("keywords") or []:
                if in_text(k, haystack):
                    kws.append(str(k).strip())
                else:
                    warns.append("%s「%s」的关键词“%s”不在文档原文里，已丢弃" % (label, it.get("name", ""), k))
            if kws:
                res.append({"name": str(it.get("name", "")).strip() or kws[0][:8], "keywords": kws,
                            "source": str(it.get("source", "")).strip()})
            else:
                warns.append("%s「%s」没有可用关键词，已丢弃" % (label, it.get("name", "")))
        return res

    points, bonus = norm(data.get("points"), "采分点"), norm(data.get("bonus"), "加分点")
    if not points:
        raise rubric.RubricError("AI 没有整理出采分点")
    for p, sc in zip(points, rubric.allocate(block["score"], len(points))):
        p["score"] = sc
    for i, p in enumerate(points):
        p["id"] = i + 1
    for i, p in enumerate(bonus):
        p["score"], p["id"] = 1, "加%d" % (i + 1)
    r = {"qid": qid, "status": rubric.STATUS_DRAFT, "total": block["score"], "words": block["words"],
         "type": block["type"], "source": source, "points": points, "bonus": bonus, "rules": [],
         "stem": block["stem"]}
    return r, warns


def main(argv=None):
    ap = argparse.ArgumentParser(description="从真题解析文档起草采分点")
    ap.add_argument("src", help=".pdf / .txt / .md")
    ap.add_argument("--prefix", required=True, help="题目编号前缀，如 国考2026-副省；编号 = 前缀-两位题号")
    ap.add_argument("--out", help="输出目录（默认 训练/采分点）")
    ap.add_argument("--list", action="store_true", help="只列出识别到的题，不调用 AI")
    a = ap.parse_args(argv)
    blocks = split_questions(read_source(a.src))
    for b in blocks:
        print("第%d题 | %s | %s分 | %s字 | 要点表 %d 行 | 参考答案 %d 份 | %s" % (
            b["no"], b["type"] or "题型未识别", b["score"], b["words"], len(b["table"].splitlines()), len(b["answers"]),
            b["stem"].splitlines()[0][:30]))
    if a.list:
        return 0
    from core import ai
    from core.paths import Paths, find_vault
    out = Path(a.out) if a.out else Paths(find_vault()).rubric_dir
    out.mkdir(parents=True, exist_ok=True)
    for b in blocks:
        qid = "%s-%02d" % (a.prefix, b["no"])
        try:
            r, warns = draft(b, ai.chat_json, qid)
        except Exception as e:  # noqa: BLE001  单题失败不影响其他题
            print("第%d题失败：%s" % (b["no"], e))
            continue
        errs = rubric.validate(r, final=True)
        (out / (qid + ".md")).write_text(rubric.dumps(r), encoding="utf-8", newline="\n")
        print("已写入 %s（%d 个采分点）%s" % (qid, len(r["points"]), "；需处理：" + "；".join(warns + errs) if warns or errs else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
