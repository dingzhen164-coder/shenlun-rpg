"""
批改：把作答和采分点交给 AI 判断，分数由 rubric.score 计算。

流程：
    1. build_messages  组装提示词（题干、采分点清单、作答）；
    2. check_reply     校验 AI 返回的 JSON：每个采分点都要有 hit（full/half/none），失分类型要在白名单里；
    3. grade           调 AI（校验不过带着错误重试 1 次），再交给 rubric.score 算分
                       （依据句不在作答里 → 该点判未命中；加分点封顶；字数硬规则）；
    4. calibrate       标定：把参考答案逐份批一遍，得分率应当很高，用来检查采分点和提示词。

AI 只返回判断：每个点的命中程度、依据句、一句话理由、失分类型、总评。**不返回任何分数。**
没有 AI 或 AI 失败时抛 GradeError，调用方应提示用户重试，不计分、不入统计。

数据格式：返回 {content, bonus, deductions, total, full, rate, words, points:[{id,name,score,hit,earned,evidence,reason,flag,bonus}],
               lost:[{code,name,note}], summary, draft}
谁调用：core/api.py（POST /api/grade）、命令行 python -m subjects.shenlun.grader calibrate。
"""
import argparse
import sys
from pathlib import Path

from . import rubric

# 失分类型（只记类型，不记具体错误，才能跨题累积；见 DESIGN.md 5.6）
LOST_CODES = {
    "A1": "漏采分点", "A2": "找错位置", "A3": "自我脑补", "A4": "未用材料原词",
    "B1": "概括词不统一", "B2": "分类逻辑混乱",
    "C1": "表述口语化", "C2": "条理不清", "C3": "篇幅失控",
    "D1": "格式缺失",
}

SYSTEM = """你是严谨的申论阅卷人。只做判断，不打总分。判断规则：
1. 按含义判断，不是字面匹配：作答用自己的话表达了采分点的意思，就算命中；关键词只是锚点。
2. hit 三档：full = 要点完整表达（≥80%）；half = 只表达了一部分或表述不准（40%–80%）；none = 没有或不足 40%。
3. evidence 必须是从作答里原样摘出的一句或一段（逐字相同，不要改写）；hit 为 none 时留空字符串。
4. 编造材料里没有的内容不给分，也不要因此额外扣分；顺序不影响得分；不写总括句、不写具体地名不算错，除非题干明确要求。
5. lost 只列最主要的失分类型（最多 4 个），code 必须取自给定清单；note 一句话说明。
6. summary 是给考生的一句话总评（60 字以内），先肯定做对的，再指出最该改的一点。
只返回 JSON，不要多余文字。"""

USER = """题型：%(type)s　满分：%(total)s 分　字数上限：%(words)s
题干：
%(stem)s

采分点（id：名称｜关键词｜材料依据）：
%(points)s
%(bonus)s
失分类型清单：%(codes)s

考生作答：
%(answer)s

返回格式：
{"points":[{"id":1,"hit":"full|half|none","evidence":"","reason":"一句话理由"}],
 "bonus":[{"id":"加1","hit":"full|half|none","evidence":"","reason":""}],
 "lost":[{"code":"A1","note":""}],
 "summary":""}
points 必须覆盖上面每一个采分点，bonus 必须覆盖每一个加分点（没有就给空数组）。"""


class GradeError(Exception):
    pass


def _fmt(items):
    return "\n".join("%s：%s｜%s｜%s" % (p["id"], p["name"], "；".join(p["keywords"]), p.get("source") or "—") for p in items)


def build_messages(r, answer):
    bonus = ("\n加分点（命中额外加分，总分封顶）：\n" + _fmt(r["bonus"])) if r["bonus"] else ""
    body = USER % {
        "type": r.get("type") or "未标注", "total": r["total"], "words": r.get("words") or "不限",
        "stem": r.get("stem") or "（未录入题干）", "points": _fmt(r["points"]), "bonus": bonus,
        "codes": "、".join("%s %s" % kv for kv in LOST_CODES.items()), "answer": answer.strip(),
    }
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]


def check_reply(r, data):
    """校验 AI 返回；返回 (问题列表, 规整后的 judgments)"""
    errs, judg = [], {}
    if not isinstance(data, dict):
        return ["返回的不是 JSON 对象"], {}
    for kind, items in (("points", r["points"]), ("bonus", r["bonus"])):
        got = {str(x.get("id")): x for x in (data.get(kind) or []) if isinstance(x, dict)}
        for p in items:
            x = got.get(str(p["id"]))
            if x is None:
                errs.append("缺少 %s 里 id=%s 的判断" % (kind, p["id"]))
            elif x.get("hit") not in rubric.HIT_FACTOR:
                errs.append("id=%s 的 hit 必须是 full/half/none" % p["id"])
            else:
                judg[p["id"]] = {"hit": x["hit"], "evidence": str(x.get("evidence") or ""), "reason": str(x.get("reason") or "")}
    return errs, judg


def grade(r, answer, chat_json, allow_draft=True):
    """r: rubric.parse 的结果；chat_json(messages) → dict（core.ai.chat_json 或假 AI）"""
    if not (answer or "").strip():
        raise GradeError("作答是空的")
    if r["status"] != rubric.STATUS_FINAL and not allow_draft:
        raise GradeError("这道题的采分点还是草稿，请先审定")
    errs = rubric.validate(r)
    if errs:
        raise GradeError("采分点有问题：" + "；".join(errs))
    msgs = build_messages(r, answer)
    data, last = None, []
    for attempt in range(2):
        try:
            data = chat_json(msgs)
        except Exception as e:  # AIError 等：网络、key、格式
            raise GradeError(str(e))
        last, judg = check_reply(r, data)
        if not last:
            break
        msgs = msgs + [{"role": "assistant", "content": str(data)},
                       {"role": "user", "content": "你的返回有问题：" + "；".join(last) + "。请按格式重新完整返回。"}]
    if last:
        raise GradeError("AI 两次都没有按要求返回：" + "；".join(last))
    res = rubric.score(r, answer, judg)
    for row in res["points"]:
        row["reason"] = judg.get(row["id"], {}).get("reason", "")
    res["lost"] = [{"code": x["code"], "name": LOST_CODES[x["code"]], "note": str(x.get("note") or "")}
                   for x in (data.get("lost") or []) if isinstance(x, dict) and x.get("code") in LOST_CODES][:4]
    res["summary"] = str(data.get("summary") or "").strip()
    res["draft"] = r["status"] != rubric.STATUS_FINAL
    return res


def calibrate(r, reference_answers, chat_json, target=0.9):
    """标定：参考答案的得分率应 ≥ target。返回 [{n, rate, ok, missed:[未命中采分点名]}]"""
    out = []
    for i, ans in enumerate(reference_answers, 1):
        res = grade(r, ans, chat_json)
        out.append({"n": i, "rate": res["rate"], "ok": res["rate"] >= target,
                    "missed": [p["name"] for p in res["points"] if not p["bonus"] and p["hit"] != "full"]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="用参考答案标定采分点和批改提示词")
    ap.add_argument("src", help="解析文档（.pdf/.txt）")
    ap.add_argument("--prefix", required=True, help="题目编号前缀，与起草采分点时一致")
    ap.add_argument("--dir", help="采分点目录（默认 训练/采分点）")
    ap.add_argument("--target", type=float, default=0.9)
    a = ap.parse_args(argv)
    from core import ai
    from core.paths import Paths, find_vault
    from . import analysis
    d = Path(a.dir) if a.dir else Paths(find_vault()).rubric_dir
    for b in analysis.split_questions(analysis.read_source(a.src)):
        f = d / ("%s-%02d.md" % (a.prefix, b["no"]))
        if not f.exists():
            print("第%d题：没有采分点文件 %s，跳过" % (b["no"], f.name))
            continue
        r = rubric.parse(f.read_text(encoding="utf-8"))
        for row in calibrate(r, b["answers"], ai.chat_json, a.target):
            print("第%d题 参考答案%d：得分率 %.0f%% %s%s" % (b["no"], row["n"], row["rate"] * 100, "✓" if row["ok"] else "✗偏低",
                                                      "｜没拿满：" + "、".join(row["missed"]) if row["missed"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
