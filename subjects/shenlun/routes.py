"""
申论科目的 HTTP 路由（由 core/api.py 转发 /api/shenlun/*）。

    GET  /api/shenlun/questions        题目列表（来自 训练/采分点/*.md）
    GET  /api/shenlun/question?qid=    单题（题干、采分点、状态）
    POST /api/shenlun/grade            {qid, answer} → 批改，写存档记录和 训练/作答/<日期>/ 下的复盘文件
    POST /api/shenlun/finalize         {qid} → 校验通过后把采分点从“草稿”改成“已定稿”
    POST /api/shenlun/import           {name, data}（data=文件的 base64）→ 存到 训练/资料/ 并识别各题
    POST /api/shenlun/draft            {file, prefix, no, overwrite} → 让 AI 起草第 no 题的采分点（已有文件默认不覆盖）
    POST /api/shenlun/install-pdf      装 PDF 读取组件（pymupdf），只需一次

草稿状态的题也能批（标“试批”），但不计入预估分和统计。出错抛 ApiError(状态码, 消息)。
谁调用：core/api.py。
"""
import base64
import datetime as dt
import re
import subprocess
import sys
from urllib.parse import parse_qs

from core import ai
from core.store import LOCK, Store

from . import analysis, grader, rubric, samples


class ApiError(Exception):
    def __init__(self, code, msg, extra=None):
        Exception.__init__(self, msg)
        self.code, self.msg, self.extra = code, msg, extra or {}


def _safe_qid(qid):
    if not qid or re.search(r"[\\/\n]|\.\.", qid):
        raise ApiError(400, "题目编号不合法")
    return qid


def load_rubric(paths, qid):
    f = paths.rubric_dir / (_safe_qid(qid) + ".md")
    if not f.exists():
        raise ApiError(404, "没有找到题目 " + qid)
    try:
        return rubric.parse(f.read_text(encoding="utf-8")), f
    except rubric.RubricError as e:
        raise ApiError(422, "采分点文件有问题：%s" % e)


def list_questions(paths):
    out = []
    for f in sorted(paths.rubric_dir.glob("*.md")):
        try:
            r = rubric.parse(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  坏文件不影响其他题
            continue
        out.append({"qid": r["qid"] or f.stem, "type": r["type"], "total": r["total"], "words": r["words"],
                    "status": r["status"], "points": len(r["points"]), "stem": r["stem"], "source": r["source"]})
    return out


def daily_question(paths, today):
    """每日一题：有已导入的题就按日期轮换，没有就用自编样例"""
    qs = list_questions(paths)
    if qs:
        q = qs[today.toordinal() % len(qs)]
        return {"id": q["qid"], "type": q["type"] or "未分类", "score": q["total"], "words": q["words"] or 0,
                "source": q["source"] or "已导入", "topic": q["status"], "stem": q["stem"] or "（未录入题干）", "real": True}
    q = dict(samples.SAMPLES[today.toordinal() % len(samples.SAMPLES)])
    q["real"] = False
    return q


def _save_review(paths, rec, r, res, answer, now):
    d = paths.train / "作答" / now.strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    lines = ["# %s · %s" % (rec["qid"], now.strftime("%H:%M")), "",
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
    f = d / ("%s-%s.md" % (rec["qid"], now.strftime("%H%M%S")))
    f.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return f


def _blocks(paths, file):
    f = paths.train / "资料" / _safe_qid(file)
    if not f.exists():
        raise ApiError(404, "没有找到文件 " + file)
    try:
        return analysis.split_questions(analysis.read_source(f))
    except RuntimeError as e:
        raise ApiError(422, str(e), {"need_pdf_tool": f.suffix.lower() == ".pdf"})


def _block_info(b):
    return {"no": b["no"], "type": b["type"], "score": b["score"], "words": b["words"],
            "stem": b["stem"].splitlines()[0] if b["stem"] else "", "table_lines": len(b["table"].splitlines()),
            "answers": len(b["answers"])}


def handle(method, path, query, body, paths, today=None, chat_json=None, now=None):
    """返回 JSON 可序列化对象；出错抛 ApiError"""
    today = today or dt.date.today()
    now = now or dt.datetime.now()
    chat_json = chat_json or ai.chat_json
    if method == "GET" and path == "/api/shenlun/questions":
        return {"questions": list_questions(paths)}
    if method == "GET" and path == "/api/shenlun/question":
        qid = (parse_qs(query).get("qid") or [""])[0]
        r, _ = load_rubric(paths, qid)
        return {"qid": r["qid"], "type": r["type"], "total": r["total"], "words": r["words"], "status": r["status"],
                "stem": r["stem"], "points": [{"id": p["id"], "name": p["name"], "score": p["score"]} for p in r["points"]]}
    if method == "POST" and path == "/api/shenlun/finalize":
        r, f = load_rubric(paths, body.get("qid"))
        errs = rubric.validate(r, final=True)
        if errs:
            raise ApiError(422, "不能定稿：" + "；".join(errs))
        r["status"] = rubric.STATUS_FINAL
        f.write_text(rubric.dumps(r), encoding="utf-8", newline="\n")
        return {"ok": True, "status": r["status"]}
    if method == "POST" and path == "/api/shenlun/import":
        name = re.sub(r"[\\/:*?\"<>|]", "_", str(body.get("name") or "")).strip()
        if not name.lower().endswith((".pdf", ".txt", ".md")):
            raise ApiError(400, "只支持 .pdf / .txt / .md 文件")
        try:
            raw = base64.b64decode(body.get("data") or "", validate=False)
        except Exception:  # noqa: BLE001
            raise ApiError(400, "文件内容读取失败")
        d = paths.train / "资料"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(raw)
        blocks = _blocks(paths, name)
        if not blocks:
            raise ApiError(422, "没有识别到“第N题”。这个文档的版式暂不支持，请把文件发给我看看", {"file": name})
        return {"file": name, "questions": [_block_info(b) for b in blocks]}
    if method == "POST" and path == "/api/shenlun/draft":
        prefix = _safe_qid(str(body.get("prefix") or "").strip())
        blocks = [b for b in _blocks(paths, body.get("file")) if b["no"] == int(body.get("no") or 0)]
        if not blocks:
            raise ApiError(404, "文档里没有这一题")
        b, qid = blocks[0], "%s-%02d" % (prefix, blocks[0]["no"])
        f = paths.rubric_dir / (qid + ".md")
        if f.exists() and not body.get("overwrite"):
            return {"qid": qid, "skipped": True, "message": "已存在，没有覆盖（你审定过的内容不会被冲掉）"}
        try:
            r, warns = analysis.draft(b, chat_json, qid, "用户提供（%s）" % body.get("file"))
        except rubric.RubricError as e:
            raise ApiError(422, str(e))
        except Exception as e:  # noqa: BLE001  AIError 等
            raise ApiError(502, str(e))
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(rubric.dumps(r), encoding="utf-8", newline="\n")
        return {"qid": qid, "skipped": False, "points": len(r["points"]), "warnings": warns + rubric.validate(r, final=True)}
    if method == "POST" and path == "/api/shenlun/install-pdf":
        try:
            out = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=600)
        except Exception as e:  # noqa: BLE001
            raise ApiError(500, "安装失败：%s" % e)
        text = out.stdout.decode("utf-8", "replace")[-400:]
        if out.returncode != 0:
            raise ApiError(500, "安装失败（可能需要联网）：" + text)
        return {"ok": True, "message": "安装完成"}
    if method == "POST" and path == "/api/shenlun/grade":
        r, _ = load_rubric(paths, body.get("qid"))
        answer = str(body.get("answer") or "")
        try:
            res = grader.grade(r, answer, chat_json)
        except grader.GradeError as e:
            raise ApiError(502, str(e))
        with LOCK:
            store = Store(paths)
            state = store.load(today)
            rec = {"id": now.strftime("%Y%m%d%H%M%S"), "d": today.isoformat(), "subject": "shenlun", "qid": r["qid"],
                   "board": r["type"], "score": res["total"], "full": res["full"], "rate": res["rate"], "words": res["words"],
                   "scored": not res["draft"], "lost": [x["code"] for x in res["lost"]], "summary": res["summary"]}
            state["records"].append(rec)
            store.save(state, today)
        res["record"] = rec["id"]
        res["review_file"] = str(_save_review(paths, rec, r, res, answer, now).relative_to(paths.vault))
        return res
    raise ApiError(404, "没有这个接口")
