"""整卷模拟考试（行测，试炼塔左侧「套卷」）：导入模拟试卷PDF → 导入答案 → 2小时倒计时作答 → 答题卡交卷 → 批改记分 → 记入宗门大比。

不重复造轮子：
- 试卷PDF沿用宗门大比的导入（importer.save_pdf + split_pdf，调用库里的 xingce-mokao-split 拆成各板块复盘文件，题目同时入试炼塔题库）；
  试卷在内部仍以一个数字编号（旧的粉笔季是1~999，整卷考试的试卷从1001起，不会和粉笔季混），给人看的名字是自己起的试卷名（mock.season_name）。
- 题目、材料、图片、正确答案都读复盘文件（vault.parse_board_file）；答案导入同时补进复盘文件和试炼塔题库（importer.fill_answers）。
- 批改后把对错和“我的答案”写回复盘文件（宗门大比的考情、复盘、错题都读它），总分按规则里的参考分值表算（mock_score.estimate），
  再用 mock.set_score 记成绩——录分奖励与悟道机缘走大比原来的规则，同一张试卷只结算一次。

数据：
  state["exam_runs"][编号] = {name, limit(秒), elapsed(秒), answers{题号:字母}, marks[题号], status:"running", started}
  state["mocks"][编号]["exam"] = {answers, marks, elapsed, limit, submitted, minutes, score, basis, partial, overtime, attempts, results[[题号,我的答案,状态]]}
  状态：ok答对 bad答错 blank没答 nokey没有标准答案（不判分）
作答记录单独存，不写试炼塔的已做题（不影响塔层数和首次奖励）。倒计时时长可在 训练/规则.md 用“整卷考试.分钟”调整，默认120。
"""
import base64
import datetime as dt
import re

from . import importer, mock, mock_score, vault

BASE = 1000                      # 整卷考试自己的试卷编号从1001起
LETTERS = "ABCD"
DISPLAY = {"言语理解": "言语理解与表达"}
STATUS_ICON = {"ok": "✅", "bad": "❌", "blank": "⚪", "nokey": "⚪"}
MAX_PDF = 40 * 1024 * 1024


class ExamError(ValueError):
    pass


def limit_seconds(g):
    try:
        minutes = float(g.rules.num("整卷考试.分钟") or 120)
    except (TypeError, ValueError):
        minutes = 120
    return int(max(10, min(300, minutes)) * 60)


def _guard(g):
    if getattr(g, "subject", "") != "行测":
        raise ExamError("整卷模拟考试只在行测科目使用")
    if not g.paths.train:
        raise ExamError("请先选择行测学习库")


# ---------------------------------------------------------------- 读试卷
def _season_dir(g, n):
    d = next((d for k, d in vault.seasons(g.paths) if k == n), None)
    if not d:
        raise ExamError("没有这份试卷，请先导入")
    return d


def _letters(value):
    """复盘文件里的“正确答案”：A~D的字母；“?”或空是还没有答案"""
    v = re.sub(r"[^A-Da-d]", "", str(value or "")).upper()
    return v if v else ""


def _questions(g, n):
    """这份试卷的全部题目（按题号）：[{num, board, module, correct, q, dir}]"""
    d = _season_dir(g, n)
    out, seen = [], set()
    for f in sorted(d.glob("[0-9][0-9]-*.md")):
        board = f.stem[3:]
        module = mock.MODULE_OF.get(board)
        if not module:
            continue
        for q in vault.parse_board_file(f):
            if q["num"] in seen:
                continue
            seen.add(q["num"])
            out.append(dict(num=q["num"], board=board, module=module, correct=_letters(q["correct"]), q=q, dir=str(d)))
    return sorted(out, key=lambda x: x["num"]), d


def _summary(g, n, qs=None):
    qs = qs if qs is not None else _questions(g, n)[0]
    rec = g.state.get("mocks", {}).get(str(n), {})
    run = g.state.get("exam_runs", {}).get(str(n))
    done = rec.get("exam") or {}
    return {"season": n, "name": mock.season_name(g, n), "total": len(qs), "keyed": sum(1 for q in qs if q["correct"]),
            "date": rec.get("date", ""), "score": rec.get("score"), "attempts": done.get("attempts", 0),
            "last": ({"score": done.get("score"), "minutes": done.get("minutes"), "submitted": done.get("submitted"),
                      "partial": done.get("partial"), "basis": done.get("basis")} if done else None),
            "run": ({"elapsed": run["elapsed"], "answered": len([1 for v in run["answers"].values() if v]), "limit": run["limit"]} if run else None),
            "modules": [{"name": m, "display": DISPLAY.get(m, m), "total": sum(1 for q in qs if q["module"] == m)}
                        for m in mock.MODULE_NAMES if any(q["module"] == m for q in qs)]}


def papers(g):
    _guard(g)
    hidden = {str(x) for x in g.state.get("mocks_hidden", [])}
    out = []
    for n, _d in vault.seasons(g.paths):
        if str(n) in hidden:
            continue
        qs, _ = _questions(g, n)
        if qs:
            out.append(_summary(g, n, qs))
    out.sort(key=lambda p: (p["run"] is None, -p["season"]))
    return {"papers": out, "limit": limit_seconds(g), "minutes": limit_seconds(g) // 60,
            "split_ready": bool(importer.split_script(g.paths)), "pymupdf": importer.has_pymupdf()}


# ---------------------------------------------------------------- 导入试卷、答案
def next_season(g):
    used = [k for k, _ in vault.seasons(g.paths)] + [int(k) for k in g.state.get("mocks", {}) if str(k).isdigit()]
    return max([BASE] + used) + 1


def import_paper(g, body):
    """导入一份模拟试卷PDF：起一个试卷名，程序拆成各板块并入库（和宗门大比的导入同一套）。导入本身不计学习时间，交卷时才记。"""
    _guard(g)
    name = re.sub(r"\s+", " ", str(body.get("name") or "")).strip()[:40]
    if not name:
        raise ExamError("请给这份试卷起个名字（如：花生26下模拟卷第一套）")
    if any(mock.season_name(g, k).strip() == name for k, _ in vault.seasons(g.paths)):
        raise ExamError("已经有同名的试卷了，换个名字")
    raw = str(body.get("data") or "").split(",", 1)[-1]
    if len(raw) > MAX_PDF * 4 // 3 + 16:
        raise ExamError("PDF太大，请拆成40MB以内再导入")
    n = next_season(g)
    file = "第%d季-%s.pdf" % (n, mock.safe_name(name))
    try:
        importer.save_pdf(g.paths, {"name": file, "data": raw, "season": n})
        report = importer.split_pdf(g.paths, {"file": file})
    except importer.ImportError_ as error:
        raise ExamError(str(error))
    rec = g.state.setdefault("mocks", {}).setdefault(str(n), {})
    rec["name"] = name
    rec.setdefault("date", "")
    mock.unhide(g, n)
    done = g.state.setdefault("mock_practice", [])
    if str(n) not in [str(x) for x in done]:
        done.append(str(n))                   # 导入不另给120分钟，交卷时按实际用时记
    qs, _ = _questions(g, n)
    return {"season": n, "name": name, "total": len(qs), "keyed": sum(1 for q in qs if q["correct"]),
            "split_log": report.get("split_log", ""), "ready": report.get("ready"), "fix": report.get("fix")}


def _write_correct(paths, season, key):
    """把答案写进复盘文件的“正确答案：**?**”（只补没有答案的）。返回补了几题"""
    d = next((d for k, d in vault.seasons(paths) if k == season), None)
    if not d:
        return 0
    n = 0
    for f in sorted(d.glob("[0-9][0-9]-*.md")):
        text = f.read_text(encoding="utf-8")
        new = text
        for num, letter in key.items():
            m = re.search(r"^### %d\. (?:✅|❌|⚪)[ \t]*$" % num, new, re.M)
            if not m:
                continue
            end = re.search(r"^### \d+\. ", new[m.end():], re.M)
            stop = m.end() + end.start() if end else len(new)
            seg = new[m.start():stop]
            fixed = re.sub(r"(正确答案：\*\*)([^*]*)(\*\*)", lambda mm: mm.group(1) + letter + mm.group(3) if not _letters(mm.group(2)) else mm.group(0), seg, count=1)
            if fixed != seg:
                new = new[:m.start()] + fixed + new[stop:]
                n += 1
        if new != text:
            f.write_text(new, encoding="utf-8", newline="\n")
    vault._cache.clear()
    return n


def _pdf_text(data):
    """答案页PDF的文字层（扫描图片版没有文字，需要先转成文字）"""
    import base64
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            raise ExamError("缺少PDF组件，请直接粘贴答案文字")
    try:
        doc = fitz.open(stream=base64.b64decode(data.split(",", 1)[-1]), filetype="pdf")
    except Exception:
        raise ExamError("这个PDF打不开，请换一个或直接粘贴答案文字")
    text = "\n".join(page.get_text() for page in doc)
    if not text.strip():
        raise ExamError("这个PDF里没有文字层（可能是扫描图片），请粘贴答案文字")
    return text


def import_answers(g, body):
    """导入这份试卷的答案：粘贴“1-20 BCDA…”“1.A 2.B”之类，或答案文本。只补还没有答案的题。已交卷的试卷会按新答案重新批改。"""
    _guard(g)
    n = int(body.get("season") or 0)
    qs, _d = _questions(g, n)
    text = str(body.get("text") or "").strip()
    if not text and body.get("pdf"):
        text = _pdf_text(str(body["pdf"]))
    if not text:
        raise ExamError("请粘贴答案（如：1-20 BCDAB…，或每行 1.A 2.B）")
    key = {k: v for k, v in importer.parse_key(text).items() if v in LETTERS and any(q["num"] == k for q in qs)}
    if not key:
        raise ExamError("没认出答案：请写成“1-20 BCDAB…”或“1.A 2.B”的样子，题号要在这份试卷的范围内")
    before = sum(1 for q in qs if q["correct"])
    try:
        importer.fill_answers(g.paths, {"prefix": "粉笔%d季" % n, "key": text})
    except importer.ImportError_:
        pass                                              # 题库里没有这份题也没关系，批改读的是复盘文件
    _write_correct(g.paths, n, key)
    qs, _ = _questions(g, n)
    after = sum(1 for q in qs if q["correct"])
    out = {"season": n, "filled": after - before, "keyed": after, "total": len(qs),
           "missing": [q["num"] for q in qs if not q["correct"]][:30]}
    if g.state.get("mocks", {}).get(str(n), {}).get("exam", {}).get("answers"):
        out["regraded"] = _grade(g, n, (g.state["mocks"][str(n)]["exam"]))
    return out


# ---------------------------------------------------------------- 作答
def _blocks(g, item):
    from . import trainer
    q = dict(item["q"], season=item["num"], source=item["board"], dir=item["dir"])
    body = trainer._fill_body(g, q)
    return vault.render_blocks(g.paths, body, material=False), vault.render_material(g.paths, q)


def payload(g, n):
    """给答题页的整份试卷：不含标准答案和解析"""
    qs, d = _questions(g, n)
    items, mats = [], {}
    for item in qs:
        blocks, material = _blocks(g, item)
        q = item["q"]
        key = None
        if material and q.get("material"):
            key = "%d-%d" % tuple(q["material"])
            mats.setdefault(key, material)
        letters = "".join(sorted(set(re.findall(r"^\s*[-*]?\s*\*{0,2}([A-D])[.．、)]", q["body"], re.M)))) or LETTERS
        items.append({"num": item["num"], "board": item["board"], "module": item["module"], "blocks": blocks,
                      "material": key, "choices": list(letters)})
    return {"questions": items, "materials": mats,
            "modules": [{"name": m, "display": DISPLAY.get(m, m)} for m in mock.MODULE_NAMES if any(x["module"] == m for x in qs)]}


def begin(g, n):
    _guard(g)
    qs, _ = _questions(g, n)
    if not qs:
        raise ExamError("这份试卷没有题目")
    runs = g.state.setdefault("exam_runs", {})
    run = runs.get(str(n))
    if not run:
        run = runs[str(n)] = {"name": mock.season_name(g, n), "limit": limit_seconds(g), "elapsed": 0, "answers": {}, "marks": [],
                              "status": "running", "started": dt.datetime.now().isoformat(timespec="seconds"), "date": g.t}
    data = payload(g, n)
    data.update(run=dict(run), summary=_summary(g, n, qs), warning=("有 %d 题还没有标准答案，交卷时这些题不判分；可以先导入答案。" % sum(1 for q in qs if not q["correct"])) if any(not q["correct"] for q in qs) else "")
    return data


def _clean_answers(qs, answers):
    nums = {q["num"] for q in qs}
    out = {}
    for k, v in (answers or {}).items():
        try:
            num = int(k)
        except (TypeError, ValueError):
            continue
        v = str(v or "").strip().upper()
        if num in nums and (not v or (len(v) == 1 and v in LETTERS)):
            out[str(num)] = v
    return out


def save_run(g, n, body):
    _guard(g)
    run = g.state.get("exam_runs", {}).get(str(n))
    if not run:
        raise ExamError("这场考试还没开始或已经交卷")
    qs, _ = _questions(g, n)
    if "answers" in body:
        run["answers"] = _clean_answers(qs, body["answers"])
    if "marks" in body:
        nums = {q["num"] for q in qs}
        run["marks"] = sorted({int(x) for x in (body.get("marks") or []) if str(x).isdigit() and int(x) in nums})
    try:
        elapsed = int(body.get("elapsed"))
        run["elapsed"] = max(run["elapsed"], min(elapsed, run["limit"] * 3))
    except (TypeError, ValueError):
        pass
    return {"elapsed": run["elapsed"], "answered": len([1 for v in run["answers"].values() if v])}


def discard(g, n):
    """放弃这场考试（不批改、不记成绩）"""
    g.state.get("exam_runs", {}).pop(str(n), None)
    return {"ok": True}


# ---------------------------------------------------------------- 批改、记成绩
def _apply_results(paths, season, results):
    """{题号: (图标, 我的答案)} 写回复盘文件：标题图标、总览链接、答案栏；统计行同步"""
    d = next((d for k, d in vault.seasons(paths) if k == season), None)
    if not d:
        return
    head = re.compile(r"^### (\d+)\. (✅|❌|⚪)[ \t]*$", re.M)
    word = {"✅": "正确", "❌": "错误", "⚪": "未作答"}
    for f in sorted(d.glob("[0-9][0-9]-*.md")):
        text = f.read_text(encoding="utf-8")
        new = text
        for num, (icon, mine) in results.items():
            m = re.search(r"^### %d\. (✅|❌|⚪)[ \t]*$" % num, new, re.M)
            if not m:
                continue
            old = m.group(1)
            new = new[:m.start()] + "### %d. %s" % (num, icon) + new[m.end():]
            if old != icon:
                for bar in ("|", "\\|"):
                    new = new.replace("[[#%d. %s%s%d]]" % (num, old, bar, num), "[[#%d. %s%s%d]]" % (num, icon, bar, num))
            start = new.find("### %d. %s" % (num, icon))
            nxt = head.search(new, start + 5)
            stop = nxt.start() if nxt else len(new)
            seg = new[start:stop]
            seg = re.sub(r"(正确答案：\*\*[^*]*\*\*　我的答案：)\*\*[^*]*\*\*　\S*",
                         lambda mm: "%s**%s**　%s" % (mm.group(1), mine or "—", word[icon]), seg, count=1)
            new = new[:start] + seg + new[stop:]
        if new != text:
            heads = head.findall(new)
            done = sum(i != "⚪" for _, i in heads)
            ok = sum(i == "✅" for _, i in heads)
            rate = "%.0f%%" % (100 * ok / done) if done else "—"
            new = re.sub(r"^作答: .*$", "作答: %d" % done, new, count=1, flags=re.M)
            new = re.sub(r"^正确: .*$", "正确: %d" % ok, new, count=1, flags=re.M)
            new = re.sub(r'^正确率: .*$', '正确率: "%s"' % rate, new, count=1, flags=re.M)
            f.write_text(new, encoding="utf-8", newline="\n")
    vault._cache.clear()


def _grade(g, n, exam):
    """按保存的作答批改一次：写回复盘文件、算分、更新成绩；返回结果（不重复发奖励）"""
    qs, d = _questions(g, n)
    answers = exam.get("answers") or {}
    results, per, writes = [], {}, {}
    for item in qs:
        mine = str(answers.get(str(item["num"])) or "")
        key = item["correct"]
        status = "blank" if not mine else "nokey" if not key else "ok" if mine == key else "bad"
        results.append([item["num"], mine, status])
        writes[item["num"]] = (STATUS_ICON[status], mine)
        m = per.setdefault(item["module"], {"name": item["module"], "display": DISPLAY.get(item["module"], item["module"]),
                                            "total": 0, "ok": 0, "bad": 0, "blank": 0, "nokey": 0})
        m["total"] += 1
        m[status] += 1
    _apply_results(g.paths, n, writes)
    rec = g.state.setdefault("mocks", {}).setdefault(str(n), {})
    rec["exam"] = exam
    exam["known_numbers"] = [r[0] for r in results if r[2] != "nokey"]
    counts = mock.season_counts(g.paths, d)
    est = mock_score.estimate(g, d, counts, rec)
    total = len(qs)
    nokey = sum(1 for r in results if r[2] == "nokey")
    ok = sum(1 for r in results if r[2] == "ok")
    if est and est["ready"]:
        score, basis, scores = est["score"], "按规则里的参考分值表（地市级/行政执法130题）", est["modules"]
    elif nokey == 0 and total:
        score, basis, scores = round(100.0 * ok / total, 1), "题量与参考分值表不一致，按正确率折算成百分制", {}
    elif est and est.get("known_score") is not None and total == 130:
        score, basis, scores = est["known_score"], "有题没有标准答案，只按已有答案算的暂估分", est.get("modules") or {}
    else:
        graded = total - nokey
        score = round(100.0 * ok / graded, 1) if graded else None
        basis, scores = "有题没有标准答案，按已有答案的正确率暂估", {}
    exam.update(score=score, basis=basis, partial=bool(nokey), nokey=nokey, results=results, graded_at=g.t)
    rec["scores"] = {m: v for m, v in (scores or {}).items()}
    return {"score": score, "basis": basis, "partial": bool(nokey), "modules": list(per.values()), "ok": ok, "total": total,
            "bad": sum(1 for r in results if r[2] == "bad"), "blank": sum(1 for r in results if r[2] == "blank"), "nokey": nokey,
            "modules_score": scores or {}}


def submit(g, n, body):
    """交卷：批改 → 写回复盘 → 记成绩进宗门大比（奖励只结算一次）→ 按实际用时记一次模拟训练"""
    _guard(g)
    run = g.state.get("exam_runs", {}).get(str(n))
    if not run:
        raise ExamError("这场考试还没开始或已经交卷")
    save_run(g, n, body)
    run = g.state["exam_runs"].pop(str(n))
    rec = g.state.setdefault("mocks", {}).setdefault(str(n), {})
    previous = rec.get("exam") or {}
    elapsed = int(run["elapsed"])
    minutes = max(1, int(round(min(elapsed, run["limit"]) / 60.0)))
    exam = {"answers": run["answers"], "marks": run["marks"], "elapsed": elapsed, "limit": run["limit"],
            "minutes": minutes, "overtime": elapsed > run["limit"], "submitted": g.t,
            "attempts": int(previous.get("attempts", 0)) + 1}
    result = _grade(g, n, exam)
    rec["date"] = g.t                                  # 走势按交卷日期排
    events = []
    if result["score"] is not None:
        events += mock.set_score(g, n, result["score"], "exam")
    total = result["total"]
    events += g.add_practice("模考", total, result["ok"], minutes, mock.season_name(g, n),
                             "整卷模拟考试，实际用时 %d 分钟" % minutes)
    rec["practice_source"] = mock.season_name(g, n)
    mock.unhide(g, n)
    result.update(minutes=minutes, overtime=exam["overtime"], attempts=exam["attempts"], name=mock.season_name(g, n),
                  season=n, date=g.t, events=events)
    return result


def result(g, n):
    """最近一次交卷的结果（给结果页和“去大比看复盘”）"""
    rec = g.state.get("mocks", {}).get(str(n), {})
    exam = rec.get("exam")
    if not exam or not exam.get("results"):
        raise ExamError("这份试卷还没有交卷记录")
    qs, _ = _questions(g, n)
    by = {q["num"]: q for q in qs}
    per = {}
    for num, mine, status in exam["results"]:
        q = by.get(num)
        if not q:
            continue
        m = per.setdefault(q["module"], {"name": q["module"], "display": DISPLAY.get(q["module"], q["module"]),
                                         "total": 0, "ok": 0, "bad": 0, "blank": 0, "nokey": 0})
        m["total"] += 1
        m[status] += 1
    rows = [{"num": num, "mine": mine, "status": status, "correct": (by[num]["correct"] if num in by else ""),
             "module": (by[num]["module"] if num in by else ""), "board": (by[num]["board"] if num in by else "")}
            for num, mine, status in exam["results"]]
    return {"season": n, "name": mock.season_name(g, n), "score": exam.get("score"), "basis": exam.get("basis"),
            "partial": exam.get("partial"), "minutes": exam.get("minutes"), "overtime": exam.get("overtime"),
            "attempts": exam.get("attempts"), "submitted": exam.get("submitted"), "modules": list(per.values()),
            "rows": rows, "modules_score": rec.get("scores") or {}}
