"""
申论的“仕途”：每一段综合评价对应的单位、岗位、职级、背景故事和直属领导（官场风格，2.2.0 起）。

数据放在 训练/职务履历.md（默认见 defaults/申论/职务履历.md，用户可以在 Obsidian 里直接改）：
    ## 段名 | 起始分-结束分        一段 = 一个 5 分的大段（共 8 段：50 起每 5 分一段，最后一段 85 分以上）
    单位: …    背景: …            （各一行）
    领导: 姓名 | 职务 | 职级或层次 | 简称: … | 称呼: … | 性格: …    （最后一段没有领导）
    - 职务 | 职级 | 领导职务层次   三行，依次是这一段的“初任 / 在任 / 资深”岗位（占 2、2、1 分）
分数怎么分段、哪些分数要晋升考核，由 themes.BANDS_GUANCHANG 和 规则.md 决定，这里只管“叫什么”；段的顺序就是行的顺序，
文件里写的分数范围只是给人看的。文件缺失或格式不对时用程序自带的默认文件，不会崩。

谁调用：engine.Game（申论科目下 realm_info、说话的导师）、api.dashboard（办公室人物卡）、ceremony（任免通知）。
"""
import re

from .paths import DEFAULTS_DIR

STAGE_SPAN = (0, 2, 4, 5)       # 一段里三个岗位占的分数：初任 0–1、在任 2–3、资深 4
NO_RANK = ("", "—", "-", "无")


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse(text):
    bands, cur = [], None
    for raw in text.splitlines():
        ln = raw.strip()
        m = re.match(r"^##\s+(.+?)\s*(?:\|\s*(\d+)\s*-\s*(\d+))?\s*$", ln)
        if m:
            cur = {"name": m.group(1).strip(), "lo": int(m.group(2) or 0), "hi": int(m.group(3) or 0),
                   "unit": "", "story": "", "leader": None, "stages": []}
            bands.append(cur)
            continue
        if cur is None or not ln or ln.startswith(">"):
            continue
        if re.match(r"^[-*]\s+", ln):
            parts = [p.strip() for p in re.sub(r"^[-*]\s+", "", ln).split("|")]
            if parts and parts[0]:
                cur["stages"].append({"post": parts[0], "rank": parts[1] if len(parts) > 1 else "",
                                      "level": parts[2] if len(parts) > 2 else ""})
            continue
        key, sep, val = ln.partition(":")
        if not sep:
            key, sep, val = ln.partition("：")
        key, val = key.strip(), val.strip()
        if key == "单位":
            cur["unit"] = val
        elif key == "背景":
            cur["story"] = val
        elif key == "领导":
            cur["leader"] = _leader(val)
    return bands


def _leader(val):
    parts = [p.strip() for p in val.split("|")]
    out = {"name": parts[0] if parts else "", "title": parts[1] if len(parts) > 1 else "", "rank": parts[2] if len(parts) > 2 else "",
           "short": "", "call": "", "note": ""}
    for p in parts[3:]:
        k, _, v = p.replace("：", ":").partition(":")
        k, v = k.strip(), v.strip()
        if k == "简称":
            out["short"] = v
        elif k == "称呼":
            out["call"] = v
        elif k == "性格":
            out["note"] = v
    if not out["short"]:
        out["short"] = (out["name"][:1] + out["title"][-2:]) if out["name"] else out["title"]
    return out if out["name"] else None


def _valid(bands):
    return len(bands) >= 2 and all(b["stages"] and b["unit"] for b in bands)


class Career:
    def __init__(self, text=""):
        bands = _parse(text)
        if not _valid(bands):
            bands = _parse(_read(DEFAULTS_DIR / "申论" / "职务履历.md"))
        self.bands = bands

    def band_name(self, i):
        i = max(0, min(i, len(self.bands) - 1))
        return self.bands[i]["name"]

    def stage(self, score):
        """分数 → (段序号, 岗位序号 0/1/2)"""
        s = int(score)
        i = max(0, min((s - 50) // 5, len(self.bands) - 1))
        off = s - (50 + 5 * i)
        k = 0 if off < 2 else (1 if off < 4 else 2)
        return i, min(k, len(self.bands[i]["stages"]) - 1)

    def describe(self, score):
        i, k = self.stage(score)
        b = self.bands[i]
        st = b["stages"][k]
        rank = "" if st["rank"] in NO_RANK else st["rank"]
        label = f"{st['post']}（{rank}）" if rank else f"{st['post']}（{st['level']}）"
        return {"band": i, "stage": k, "band_name": b["name"], "unit": b["unit"], "story": b["story"],
                "post": st["post"], "rank": rank, "level": st["level"], "label": label,
                "leader": b["leader"]}

    def label(self, score):
        return self.describe(score)["label"]


def load(paths):
    """读 训练/职务履历.md（缺失或坏了用默认）"""
    f = getattr(paths, "career", None)
    return Career(_read(f) if f else "")


def persona_patch(info):
    """当前阶段的导师设定：{导师名, 称呼, 导师人设}；最后一段没有领导时返回 None"""
    ld = info.get("leader")
    if not ld:
        return None
    lvl = f"{ld['title']}" + (f"，{ld['rank']}" if ld["rank"] else "")
    me = f"{info['unit']}的{info['post']}（{info['level']}）"
    text = (f"你是学员的直属领导{ld['name']}，{lvl}；学员现在是{me}。{ld['note']}"
            f"此刻的背景：{info['story']}说话要符合你的职务和职级：用你这个层次的领导会用的口吻，称呼学员为「{ld['call'] or '同志'}」。")
    return {"导师名": ld["short"], "称呼": ld["call"] or "同志", "导师人设": text}
