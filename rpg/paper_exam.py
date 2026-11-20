"""自考（纸质试卷计时 + 录分）：辅助线下纸质套卷模考。

- 计时：预设做题顺序，指针挂钟（默认从 9:00 起走），按钮或空格键按顺序记录各板块实际用时；
- 录分：按各板块对题数、错题数与预设每题分值（Decimal 精确求和；超百分制卷自动折合百分制计入大比走势）汇总；
- 记入宗门大比：与普通模考一样进入考情与战绩（触发录分奖励、待领悟道与历练时长），不生成逐题复盘文件。
"""
import datetime as dt
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from . import mock, tutor, vault

BASE_SEASON = 2000


class PaperExamError(Exception):
    pass


# 内置分值与顺序预设：(名称, 归属六大模块, 题量, 每题分值, 目标分钟)
_GUOKAO_ROWS = (
    ("政治理论", "政治理论", 20, "0.5", 15),
    ("常识判断", "常识判断", 15, "0.5", 10),
    ("言语理解", "言语理解", 30, "0.8", 30),
    ("图形推理", "判断推理", 10, "0.8", 10),
    ("定义判断", "判断推理", 10, "0.8", 10),
    ("类比推理", "判断推理", 5, "0.8", 5),
    ("逻辑判断", "判断推理", 10, "0.85", 12),
    ("数量关系", "数量关系", 10, "1.0", 10),
    ("资料分析", "资料分析", 20, "1.0", 25),
)

_SC_GZ_ROWS = (
    ("政治理论", "政治理论", 10, "0.8", 8),
    ("常识判断", "常识判断", 10, "0.8", 7),
    ("言语理解", "言语理解", 30, "1.0", 30),
    ("图形推理", "判断推理", 5, "1.0", 6),
    ("定义判断", "判断推理", 5, "1.0", 5),
    ("类比推理", "判断推理", 5, "0.8", 4),
    ("逻辑判断", "判断推理", 10, "1.0", 12),
    ("数量关系", "数量关系", 10, "1.2", 15),
    ("资料分析", "资料分析", 15, "1.2", 20),
)

_LIANKAO_ROWS = (
    ("常识判断", "常识判断", 15, "0.8", 10),
    ("言语理解", "言语理解", 25, "1.0", 25),
    ("图形推理", "判断推理", 5, "1.0", 6),
    ("定义判断", "判断推理", 10, "0.9", 10),
    ("类比推理", "判断推理", 5, "0.8", 4),
    ("逻辑判断", "判断推理", 10, "1.0", 12),
    ("数量关系", "数量关系", 10, "1.5", 15),
    ("资料分析", "资料分析", 20, "1.0", 25),
)


def _rows_to_sections(rows):
    return [
        {"name": name, "module": mod, "total": int(total), "points": str(pts), "target_minutes": int(tmin)}
        for name, mod, total, pts, tmin in rows
    ]


def _guokao_default(g):
    """国考默认预设优先读取 训练/规则.md 的 模考参考.* 配置（若合法），否则用内置 130 题表。"""
    secs = []
    try:
        for name, mod, default_n, default_w, tmin in _GUOKAO_ROWS:
            raw_n = g.rules.get("模考参考.题量." + name)
            raw_w = g.rules.get("模考参考.分值." + name)
            n = int(Decimal(str(raw_n))) if raw_n not in (None, "") else default_n
            w = Decimal(str(raw_w)) if raw_w not in (None, "") else Decimal(default_w)
            if n <= 0 or n > 300 or w <= 0 or w > 20:
                raise ValueError()
            secs.append({"name": name, "module": mod, "total": n, "points": str(w.normalize() if w == w.to_integral() else w), "target_minutes": tmin})
        return secs
    except Exception:
        return _rows_to_sections(_GUOKAO_ROWS)


def _builtin_presets(g):
    return [
        {"id": "guokao_130", "name": "国考默认（130题·100分）", "builtin": True, "sections": _guokao_default(g)},
        {"id": "sc_gz_100", "name": "川黔省考常见（100题·100分）", "builtin": True, "sections": _rows_to_sections(_SC_GZ_ROWS)},
        {"id": "liankao_100", "name": "省考联考通用（100题·100分）", "builtin": True, "sections": _rows_to_sections(_LIANKAO_ROWS)},
    ]


def _split_verbal(sections):
    """内置卷保留言语模块原题量、分值与目标用时；奇数时片段阅读多分一道题。"""
    result = []
    for s in sections:
        if s["name"] != "言语理解" or s["total"] < 2:
            result.append(s)
            continue
        count = s["total"] // 2
        minutes = s["target_minutes"] // 2
        result.extend([
            dict(s, name="逻辑填空", total=count, target_minutes=minutes),
            dict(s, name="片段阅读", total=s["total"] - count, target_minutes=s["target_minutes"] - minutes),
        ])
    return result


def _same_sections_ignoring_order(saved, builtin):
    def signature(s):
        return (s["name"], s["module"], s["total"], Decimal(s["points"]), s["target_minutes"])
    return sorted(map(signature, saved)) == sorted(map(signature, builtin))


def _guard(g):
    if g.subject != "行测":
        raise PaperExamError("纸质自考板块仅在行测科目启用")
    if not g.paths.vault:
        raise PaperExamError("请先在设置中指定行测库路径")


def _dec(val, label, lo=Decimal("0"), hi=Decimal("500")):
    try:
        d = Decimal(str(val).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise PaperExamError("%s请填写有效数字" % label)
    if not d.is_finite() or d < lo or d > hi:
        raise PaperExamError("%s超出合理范围" % label)
    return d


def _int(val, label, lo=0, hi=500):
    if val in (None, ""):
        return 0
    try:
        n = int(val)
        if str(val).strip() != str(n) and float(val) != n:
            raise ValueError()
    except (ValueError, TypeError):
        raise PaperExamError("%s请填写整数" % label)
    if n < lo or n > hi:
        raise PaperExamError("%s须在 %d～%d 之间" % (label, lo, hi))
    return n


def _clean_preset_sections(raw_sections):
    if not isinstance(raw_sections, list) or not raw_sections:
        raise PaperExamError("预设至少保留一个板块")
    if len(raw_sections) > 24:
        raise PaperExamError("单个预设最多 24 个板块")
    out = []
    for idx, item in enumerate(raw_sections, 1):
        if not isinstance(item, dict):
            raise PaperExamError("第 %d 个板块格式有误" % idx)
        name = str(item.get("name") or "").strip()[:24]
        if not name:
            raise PaperExamError("第 %d 个板块名称不能为空" % idx)
        mod = str(item.get("module") or "").strip()
        if mod not in mock.MODULE_NAMES:
            mod = mock.MODULE_OF.get(name) or ""
        if mod not in mock.MODULE_NAMES:
            raise PaperExamError("板块「%s」请指定所属六大模块" % name)
        total = _int(item.get("total"), "「%s」题量" % name, 1, 200)
        pts = _dec(item.get("points"), "「%s」每题分值" % name, Decimal("0.01"), Decimal("20"))
        tmin = _int(item.get("target_minutes", 10), "「%s」参考用时" % name, 0, 180)
        pts_str = format(pts.quantize(Decimal("0.0001")).normalize(), "f")
        if "." in pts_str:
            pts_str = pts_str.rstrip("0").rstrip(".")
        out.append({"name": name, "module": mod, "total": total, "points": pts_str, "target_minutes": tmin})
    return out


def _preset_summary(p):
    secs = p["sections"]
    total_q = sum(s["total"] for s in secs)
    full = sum(Decimal(s["total"]) * Decimal(str(s["points"])) for s in secs)
    target_min = sum(s.get("target_minutes", 0) for s in secs)
    return dict(
        p,
        total_questions=total_q,
        full_score=float(full.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)),
        target_minutes=target_min,
    )


def _prefs(g):
    p = g.state.setdefault("paper_exam_prefs", {})
    p.setdefault("active_preset", "guokao_130")
    p.setdefault("preset_overrides", {})
    p.setdefault("custom_presets", [])
    p.setdefault("show_digital", False)
    p.setdefault("blank_as_wrong", False)
    return p


def presets_list(g):
    prefs = _prefs(g)
    overrides = prefs.get("preset_overrides") or {}
    out = []
    for bp in _builtin_presets(g):
        cur = dict(bp, sections=_split_verbal(bp["sections"]))
        ov = overrides.get(bp["id"])
        if isinstance(ov, dict) and ov.get("sections"):
            try:
                saved = _clean_preset_sections(ov["sections"])
                # 仅调整顺序的旧内置卷在原位置展开；用户改过结构或分值的方案照原样读取。
                if not ov.get("layout_version") and _same_sections_ignoring_order(saved, bp["sections"]):
                    saved = _split_verbal(saved)
                cur["sections"] = saved
                cur["overridden"] = True
            except PaperExamError:
                cur["overridden"] = False
        else:
            cur["overridden"] = False
        out.append(_preset_summary(cur))
    for cp in prefs.get("custom_presets") or []:
        if not isinstance(cp, dict) or not cp.get("id") or not cp.get("sections"):
            continue
        try:
            secs = _clean_preset_sections(cp["sections"])
            out.append(_preset_summary({
                "id": str(cp["id"]),
                "name": str(cp.get("name") or "自定义预设")[:36],
                "builtin": False,
                "overridden": False,
                "sections": secs,
            }))
        except PaperExamError:
            continue
    return out


def records_list(g):
    data = g.state.get("mocks", {})
    hidden = set(str(x) for x in g.state.get("mocks_hidden", []))
    items = []
    for k, rec in data.items():
        if not isinstance(rec, dict) or not rec.get("paper_exam") or str(k) in hidden or not str(k).isdigit():
            continue
        n = int(k)
        items.append({
            "season": n,
            "name": mock.season_name(g, n),
            "date": rec.get("date", ""),
            "score": rec.get("score"),
            "raw_score": rec.get("raw_score", rec.get("score")),
            "full_score": rec.get("full_score", 100.0),
            "ok": rec.get("ok", 0),
            "wrong": rec.get("wrong", 0),
            "blank": rec.get("blank", 0),
            "total": rec.get("total", 0),
            "total_seconds": rec.get("total_seconds", 0),
            "total_minutes": rec.get("total_minutes"),
            "preset_id": rec.get("preset_id", ""),
            "preset_name": rec.get("preset_name", ""),
            "sections": rec.get("paper_sections") or [],
        })
    items.sort(key=lambda r: (r.get("date") or "", r["season"]), reverse=True)
    return items


def view(g):
    _guard(g)
    prefs = _prefs(g)
    plist = presets_list(g)
    valid_ids = {p["id"] for p in plist}
    active = prefs.get("active_preset")
    if active not in valid_ids:
        active = plist[0]["id"]
        prefs["active_preset"] = active
    limit_min = max(30, int(g.rules.num("整卷考试.分钟") or 120))
    return {
        "active_preset": active,
        "show_digital": bool(prefs.get("show_digital")),
        "blank_as_wrong": bool(prefs.get("blank_as_wrong")),
        "limit_minutes": limit_min,
        "today": g.t,
        "module_names": list(mock.MODULE_NAMES),
        "presets": plist,
        "records": records_list(g),
    }


def save_prefs(g, body):
    """保存预设切换、做题顺序调整、自定义预设增删改、钟表数字显示开关等。"""
    _guard(g)
    prefs = _prefs(g)
    act = str(body.get("action") or "update").strip()

    if "show_digital" in body:
        prefs["show_digital"] = bool(body.get("show_digital"))
    if "blank_as_wrong" in body:
        prefs["blank_as_wrong"] = bool(body.get("blank_as_wrong"))

    builtin_ids = {b["id"] for b in _builtin_presets(g)}

    if act == "select":
        pid = str(body.get("preset_id") or "").strip()
        if any(p["id"] == pid for p in presets_list(g)):
            prefs["active_preset"] = pid
    elif act == "save_preset":
        pid = str(body.get("preset_id") or "").strip()
        name = str(body.get("name") or "").strip()[:36]
        secs = _clean_preset_sections(body.get("sections"))
        as_new = bool(body.get("as_new"))
        if not as_new and pid in builtin_ids:
            prefs.setdefault("preset_overrides", {})[pid] = {"sections": secs, "layout_version": 2}
            prefs["active_preset"] = pid
        else:
            if not name:
                raise PaperExamError("请填写预设名称（如：四川省考行测、我的做题顺序）")
            customs = [c for c in (prefs.get("custom_presets") or []) if isinstance(c, dict)]
            if not as_new and pid and pid not in builtin_ids and any(c.get("id") == pid for c in customs):
                for c in customs:
                    if c.get("id") == pid:
                        c["name"] = name
                        c["sections"] = secs
                prefs["custom_presets"] = customs
                prefs["active_preset"] = pid
            else:
                new_id = "custom_%d" % (int(time.time() * 1000) % 10 ** 9)
                customs.append({"id": new_id, "name": name, "sections": secs})
                prefs["custom_presets"] = customs
                prefs["active_preset"] = new_id
    elif act == "reset_builtin":
        pid = str(body.get("preset_id") or "").strip()
        if pid in builtin_ids:
            (prefs.get("preset_overrides") or {}).pop(pid, None)
            prefs["active_preset"] = pid
    elif act == "delete_preset":
        pid = str(body.get("preset_id") or "").strip()
        if pid in builtin_ids:
            raise PaperExamError("内置预设不能删除（可恢复默认）")
        prefs["custom_presets"] = [c for c in (prefs.get("custom_presets") or []) if c.get("id") != pid]
        if prefs.get("active_preset") == pid:
            prefs["active_preset"] = "guokao_130"
    elif act == "reorder":
        pid = str(body.get("preset_id") or prefs.get("active_preset") or "").strip()
        secs = _clean_preset_sections(body.get("sections"))
        if pid in builtin_ids:
            prefs.setdefault("preset_overrides", {})[pid] = {"sections": secs, "layout_version": 2}
        else:
            for c in (prefs.get("custom_presets") or []):
                if c.get("id") == pid:
                    c["sections"] = secs
        prefs["active_preset"] = pid
    elif act != "update":
        raise PaperExamError("不支持的预设操作")

    return view(g)


def _next_season(g):
    used = [BASE_SEASON]
    used.extend(k for k, _ in vault.seasons(g.paths))
    used.extend(int(k) for k in g.state.get("mocks", {}) if str(k).isdigit())
    return max(used) + 1


def save_exam(g, body):
    """录入或修改一场纸质自考模考：算分、汇总六大模块与板块用时、记入宗门大比。"""
    _guard(g)
    raw_season = body.get("season")
    editing = raw_season not in (None, "", 0, "0")
    data = g.state.setdefault("mocks", {})
    if editing:
        try:
            season = int(raw_season)
        except (TypeError, ValueError):
            raise PaperExamError("无效的模考编号")
        old_rec = data.get(str(season))
        if not isinstance(old_rec, dict) or not old_rec.get("paper_exam"):
            raise PaperExamError("找不到这场纸质自考记录")
    else:
        season = _next_season(g)
        old_rec = {}

    try:
        date = mock.exam_date(body.get("date")) or g.t
    except mock.MockError as e:
        raise PaperExamError(str(e))

    name = str(body.get("name") or "").strip()[:40] or ("纸质模考 · %s" % date)
    preset = old_rec if editing else body
    preset_id = str(preset.get("preset_id") or "").strip()
    preset_name = str(preset.get("preset_name") or "").strip()[:36]

    raw_secs = body.get("sections")
    if not isinstance(raw_secs, list) or not raw_secs:
        raise PaperExamError("请至少录入一个板块的成绩")

    sections = []
    mod_acc = {m: {"ok": 0, "wrong": 0, "blank": 0, "total": 0, "score": Decimal("0"), "seconds": 0.0, "boards": []}
               for m in mock.MODULE_NAMES}
    raw_total_score = Decimal("0")
    full_total_score = Decimal("0")
    total_q = 0
    ok_all = 0
    wrong_all = 0
    total_seconds = 0.0

    for idx, item in enumerate(raw_secs, 1):
        if not isinstance(item, dict):
            raise PaperExamError("第 %d 个板块数据格式错误" % idx)
        sname = str(item.get("name") or "").strip()[:24]
        if not sname:
            raise PaperExamError("第 %d 个板块名称不能为空" % idx)
        mod = str(item.get("module") or "").strip()
        if mod not in mock.MODULE_NAMES:
            mod = mock.MODULE_OF.get(sname) or ""
        if mod not in mock.MODULE_NAMES:
            raise PaperExamError("板块「%s」未指定有效模块" % sname)
        total = _int(item.get("total"), "「%s」总题数" % sname, 1, 200)
        pts = _dec(item.get("points"), "「%s」每题分值" % sname, Decimal("0.01"), Decimal("20"))
        ok = _int(item.get("ok", 0), "「%s」对题数" % sname, 0, total)
        wrong = _int(item.get("wrong", 0), "「%s」错题数" % sname, 0, total)
        if ok + wrong > total:
            raise PaperExamError("「%s」对题数（%d）+ 错题数（%d）不能超过总题数（%d）" % (sname, ok, wrong, total))
        blank = total - ok - wrong
        sec_val = item.get("seconds")
        if sec_val in (None, "") and item.get("minutes") not in (None, ""):
            sec = float(_dec(item.get("minutes"), "「%s」用时" % sname, Decimal("0"), Decimal("300")) * Decimal("60"))
        elif sec_val not in (None, ""):
            sec = float(_dec(sec_val, "「%s」用时" % sname, Decimal("0"), Decimal("18000")))
        else:
            sec = 0.0
        sec_score = (Decimal(ok) * pts).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        sec_full = (Decimal(total) * pts).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)

        raw_total_score += Decimal(ok) * pts
        full_total_score += Decimal(total) * pts
        total_q += total
        ok_all += ok
        wrong_all += wrong
        total_seconds += sec

        pts_str = format(pts.quantize(Decimal("0.0001")).normalize(), "f")
        if "." in pts_str:
            pts_str = pts_str.rstrip("0").rstrip(".")
        sec_min = round(sec / 60.0, 1) if sec > 0 else None
        sections.append({
            "name": sname,
            "module": mod,
            "total": total,
            "points": pts_str,
            "ok": ok,
            "wrong": wrong,
            "blank": blank,
            "score": float(sec_score),
            "full_score": float(sec_full),
            "seconds": round(sec) if sec > 0 else 0,
            "minutes": sec_min,
        })
        mc = mod_acc[mod]
        mc["ok"] += ok
        mc["wrong"] += wrong
        mc["blank"] += blank
        mc["total"] += total
        mc["score"] += Decimal(ok) * pts
        mc["seconds"] += sec
        mc["boards"].append({
            "board": sname,
            "ok": ok,
            "wrong": wrong,
            "blank": blank,
            "total": total,
            "seconds": round(sec) if sec > 0 else None,
            "minutes": sec_min,
        })

    if full_total_score <= 0:
        raise PaperExamError("试卷满分必须大于 0")
    raw_score_f = float(raw_total_score.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
    full_score_f = float(full_total_score.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
    # 百分制及以内直接按原始分计入宗门大比；超百分制（如 150 分卷）自动折算为百分制进走势图与大比奖励
    scale = (Decimal("100") / full_total_score) if full_total_score > Decimal("100") else Decimal("1")
    norm_score_f = float((raw_total_score * scale).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
    norm_score_f = min(100.0, max(0.0, norm_score_f))

    paper_modules = []
    for m in mock.MODULE_NAMES:
        mc = mod_acc[m]
        if not mc["total"]:
            continue
        msec = mc["seconds"]
        mscore = float((mc["score"] * scale).quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
        paper_modules.append({
            "name": m,
            "ok": mc["ok"],
            "total": mc["total"],
            "acc": mc["ok"] / mc["total"],
            "score": mscore,
            "estimated": False,
            "minutes": round(msec / 60.0, 1) if msec > 0 else None,
            "minutes_auto": False,
            "seconds": round(msec) if msec > 0 else None,
            "boards": mc["boards"],
        })

    total_minutes = round(total_seconds / 60.0, 1) if total_seconds > 0 else None
    old_name = old_rec.get("name")
    had_credit = mock._credited(g, season)

    rec = data.setdefault(str(season), {})
    mock.unhide(g, season)
    rec.update({
        "paper_exam": True,
        "name": name,
        "date": date,
        "score": norm_score_f,
        "raw_score": raw_score_f,
        "full_score": full_score_f,
        "score_source": "paper",
        "preset_id": preset_id,
        "preset_name": preset_name,
        "ok": ok_all,
        "wrong": wrong_all,
        "blank": total_q - ok_all - wrong_all,
        "total": total_q,
        "total_seconds": round(total_seconds),
        "total_minutes": total_minutes,
        "paper_sections": sections,
        "paper_modules": paper_modules,
        "minutes": {x["name"]: x["minutes"] for x in paper_modules if x["minutes"] is not None},
        "scores": {x["name"]: x["score"] for x in paper_modules},
    })

    events = []
    if not had_credit:
        mock._mark_credited(g, season)
        events += g.add_boss(name, norm_score_f)
        if g.state.get("boss"):
            g.state["boss"][-1]["paper_season"] = season
    else:
        for b in reversed(g.state.get("boss", [])):
            if b.get("kind", "大比") == "大比" and (b.get("paper_season") == season or (old_name and b.get("name") == old_name)):
                b["name"] = name
                b["score"] = norm_score_f
                b["paper_season"] = season
                break

    done_prac = g.state.setdefault("mock_practice", [])
    if total_seconds > 0 and str(season) not in {str(x) for x in done_prac}:
        limit_min = max(30, int(g.rules.num("整卷考试.分钟") or 120))
        p_mins = max(1, min(limit_min, int(round(total_seconds / 60.0))))
        try:
            d_obj = dt.date.fromisoformat(date)
            in_window = (g.today - dt.timedelta(days=7)) <= d_obj <= g.today
        except ValueError:
            in_window = False
        done_prac.append(str(season))
        events += g.add_practice("模考", total_q, ok_all, p_mins, name, "纸质自考模考计时与录分", day=date if in_window else None)

    events += g.housekeeping()
    return {
        "season": season,
        "score": norm_score_f,
        "raw_score": raw_score_f,
        "full_score": full_score_f,
        "events": tutor.enrich(g, events),
        "paper_exam": view(g),
        "summary": mock.summary(g),
    }


def delete_exam(g, body):
    """删除一场纸质自考记录（从考情与战绩移出；已发放的修为与奖励不倒扣）。"""
    _guard(g)
    try:
        season = int(body.get("season") or 0)
    except (TypeError, ValueError):
        raise PaperExamError("无效的模考编号")
    data = g.state.get("mocks", {})
    rec = data.get(str(season))
    if not isinstance(rec, dict) or not rec.get("paper_exam"):
        raise PaperExamError("找不到这场纸质自考记录")
    old_name = rec.get("name")
    data.pop(str(season), None)
    bosses = g.state.get("boss", [])
    idx = next((i for i in range(len(bosses) - 1, -1, -1)
                if bosses[i].get("kind", "大比") == "大比"
                and (bosses[i].get("paper_season") == season or (old_name and bosses[i].get("name") == old_name))), None)
    if idx is not None:
        bosses.pop(idx)
    return {
        "ok": True,
        "paper_exam": view(g),
        "summary": mock.summary(g),
    }
