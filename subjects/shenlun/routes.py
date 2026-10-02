"""
申论科目的 HTTP 路由（由 core/api.py 转发 /api/shenlun/*）。

    GET  /api/shenlun/questions        题目列表（来自 训练/采分点/*.md）
    GET  /api/shenlun/question?qid=    单题（题干、采分点、状态）
    POST /api/shenlun/grade            {qid, answer} → 批改，写存档记录和 训练/作答/<日期>/ 下的复盘文件
    POST /api/shenlun/finalize         {qid} → 校验通过后把采分点从“草稿”改成“已定稿”

草稿状态的题也能批（标“试批”），但不计入预估分和统计。出错抛 ApiError(状态码, 消息)。
谁调用：core/api.py。
"""
import datetime as dt
import re
from urllib.parse import parse_qs

from core import ai
from core.store import LOCK, Store

from . import grader, rubric, samples


class ApiError(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, msg)
        self.code, self.msg = code, msg


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
