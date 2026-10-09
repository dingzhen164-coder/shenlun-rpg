"""
申论题库与批改的服务层（给 rpg/api.py 的 /api/shenlun/* 接口用）。

做什么：
    list_questions   题库：训练/采分点/*.md，每题一份采分点文件（含题干），状态 草稿 / 已定稿
    finalize         校验通过后把采分点定稿（草稿也能试批，但不计入专长和统计）
    import_doc       把真题解析文档（PDF / txt / md）存到 训练/资料/，识别各题
    draft            让 AI 起草某一题的采分点（已有的文件不覆盖，用户审定过的内容不会被冲掉）
    install_pdf      装 PDF 读取组件（pymupdf），只需一次
    judge / record   批改：judge 让 AI 判断每个采分点、程序算分（慢，不占存档锁）；record 把成绩交给 engine.on_grade 计入政绩 / 专长，写复盘文件 训练/作答/<日期>/
    touch / answering  作答页的活动记录：只有 2 分钟内敲过键盘才给“作答”计时（服务端校验，防挂机）

数据格式：采分点文件见 rpg/shenlun_rubric.py；复盘文件是 Markdown，Obsidian 里直接能看。
谁调用：rpg/api.py。出错抛 ShenlunError，消息直接给用户看。
"""
import base64
import re
import subprocess
import sys
import time

from . import shenlun_analysis as analysis
from . import shenlun_grader as grader
from . import shenlun_rubric as rubric


class ShenlunError(Exception):
    pass


_TOUCH = {"t": 0.0}
ANSWER_GRACE = 120   # 秒：最后一次敲键盘到现在不超过这个才算在作答


def touch():
    _TOUCH["t"] = time.time()


def answering():
    return time.time() - _TOUCH["t"] <= ANSWER_GRACE


def _safe_name(name):
    name = str(name or "").strip()
    if not name or re.search(r"[\\/\n]|\.\.", name):
        raise ShenlunError("名字里不能有 / \\ 或 ..")
    return name


def load_rubric(paths, qid):
    f = paths.rubrics / (_safe_name(qid) + ".md")
    if not f.exists():
        raise ShenlunError("没有找到题目 " + str(qid))
    try:
        return rubric.parse(f.read_text(encoding="utf-8")), f
    except rubric.RubricError as e:
        raise ShenlunError("采分点文件有问题：%s" % e)


def list_questions(paths):
    out = []
    if not paths.rubrics or not paths.rubrics.is_dir():
        return out
    for f in sorted(paths.rubrics.glob("*.md")):
        try:
            r = rubric.parse(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  坏文件不影响其他题
            continue
        out.append({"qid": r["qid"] or f.stem, "type": r["type"], "total": r["total"], "words": r["words"],
                    "status": r["status"], "points": len(r["points"]), "stem": r["stem"], "source": r["source"],
                    "errors": rubric.validate(r, final=True)})
    return out


def question(paths, qid):
    r, _ = load_rubric(paths, qid)
    return {"qid": r["qid"], "type": r["type"], "total": r["total"], "words": r["words"], "status": r["status"],
            "stem": r["stem"], "points": [{"id": p["id"], "name": p["name"], "score": p["score"]} for p in r["points"]],
            "errors": rubric.validate(r, final=True)}


def finalize(paths, qid):
    r, f = load_rubric(paths, qid)
    errs = rubric.validate(r, final=True)
    if errs:
        raise ShenlunError("不能定稿：" + "；".join(errs))
    r["status"] = rubric.STATUS_FINAL
    f.write_text(rubric.dumps(r), encoding="utf-8", newline="\n")
    return {"ok": True, "status": r["status"]}


# ---------------------------------------------------------------- 导入解析文档
def _blocks(paths, file):
    f = paths.materials / _safe_name(file)
    if not f.exists():
        raise ShenlunError("没有找到文件 " + str(file))
    try:
        return analysis.split_questions(analysis.read_source(f))
    except RuntimeError as e:
        raise ShenlunError(str(e))


def _block_info(b):
    return {"no": b["no"], "type": b["type"], "score": b["score"], "words": b["words"],
            "stem": b["stem"].splitlines()[0] if b["stem"] else "", "table_lines": len(b["table"].splitlines()),
            "answers": len(b["answers"])}


def import_doc(paths, name, data_b64):
    name = re.sub(r"[\\/:*?\"<>|]", "_", str(name or "")).strip()
    if not name.lower().endswith((".pdf", ".txt", ".md")):
        raise ShenlunError("只支持 .pdf / .txt / .md 文件")
    try:
        raw = base64.b64decode(data_b64 or "", validate=False)
    except Exception:  # noqa: BLE001
        raise ShenlunError("文件内容读取失败")
    paths.materials.mkdir(parents=True, exist_ok=True)
    (paths.materials / name).write_bytes(raw)
    try:
        blocks = _blocks(paths, name)
    except ShenlunError as e:
        e.need_pdf_tool = name.lower().endswith(".pdf") and "pymupdf" in str(e)
        raise
    if not blocks:
        raise ShenlunError("没有识别到“第N题”。这个文档的版式暂不支持，请把文件发给开发者适配")
    return {"file": name, "questions": [_block_info(b) for b in blocks]}


def draft(paths, file, prefix, no, chat_json, overwrite=False):
    prefix = _safe_name(prefix)
    blocks = [b for b in _blocks(paths, file) if b["no"] == int(no or 0)]
    if not blocks:
        raise ShenlunError("文档里没有这一题")
    b = blocks[0]
    qid = "%s-%02d" % (prefix, b["no"])
    f = paths.rubrics / (qid + ".md")
    if f.exists() and not overwrite:
        return {"qid": qid, "skipped": True, "message": "已存在，没有覆盖（你审定过的内容不会被冲掉）"}
    try:
        r, warns = analysis.draft(b, chat_json, qid, "用户提供（%s）" % file)
    except rubric.RubricError as e:
        raise ShenlunError(str(e))
    paths.rubrics.mkdir(parents=True, exist_ok=True)
    f.write_text(rubric.dumps(r), encoding="utf-8", newline="\n")
    return {"qid": qid, "skipped": False, "points": len(r["points"]), "warnings": warns + rubric.validate(r, final=True)}


def install_pdf():
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=600)
    except Exception as e:  # noqa: BLE001
        raise ShenlunError("安装失败：%s" % e)
    if out.returncode != 0:
        raise ShenlunError("安装失败（可能需要联网）：" + out.stdout.decode("utf-8", "replace")[-400:])
    return {"ok": True, "message": "安装完成"}


# ---------------------------------------------------------------- 批改
def judge(paths, qid, answer, chat_json):
    """让 AI 判断并算分（慢，几秒到一分钟；不要在存档锁里调）。返回 (采分点, 批改结果)"""
    r, _ = load_rubric(paths, qid)
    try:
        return r, grader.grade(r, answer, chat_json)
    except grader.GradeError as e:
        raise ShenlunError(str(e))


def record(g, r, res, answer, now=None):
    """把一次批改记进存档（engine.on_grade 计入政绩和专长）并写复盘文件。g 是 engine.Game（在 open_game 里，退出时存档）"""
    import datetime as dt
    now = now or dt.datetime.now()
    rec = g.on_grade(qid=r["qid"], board=r["type"], score=res["total"], full=res["full"], words=res["words"],
                     lost=[x["code"] for x in res["lost"]], summary=res["summary"], draft=res["draft"])
    res["record"] = rec["id"]
    res["events"] = rec["events"]
    res["review_file"] = _save_review(g.paths, r, res, answer, now)
    return res


def _save_review(paths, r, res, answer, now):
    d = paths.reviews / now.strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    lines = ["# %s · %s" % (r["qid"], now.strftime("%H:%M")), "",
             "得分：**%s / %s**（%d 字%s）" % (res["total"], res["full"], res["words"], "，试批" if res["draft"] else ""), "",
             "## 总评", res["summary"] or "—", "", "## 采分点"]
    for p in res["points"]:
        mark = {"full": "✅", "half": "◐", "none": "❌"}[p["hit"]]
        lines.append("- %s [%s/%s] %s %s%s" % (mark, p["earned"], p["score"], p["name"], p["reason"],
                                              ("｜依据：" + p["evidence"]) if p["evidence"] else ""))
    for x in res["deductions"]:
        lines.append("- ➖ %s：-%s" % (x["reason"], x["points"]))
    if res["lost"]:
        lines += ["", "## 失分类型"] + ["- %s %s：%s" % (x["code"], x["name"], x["note"]) for x in res["lost"]]
    lines += ["", "## 作答", answer.strip(), ""]
    f = d / ("%s-%s.md" % (r["qid"], now.strftime("%H%M%S")))
    f.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return f.relative_to(paths.vault).as_posix()
