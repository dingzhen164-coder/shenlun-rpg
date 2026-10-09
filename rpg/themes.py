"""
官场风格的全部“说法”。游戏规则只有一套，风格只决定名字、导师、台词库和界面文字。

- 当前只有一种风格：官场（申论官途）。保留“风格表”这层结构，是为了以后和行测合并时能再加别的风格。
- 网页从 /api/dashboard 的 theme.terms 取界面文字，后端用 T(g, "键") 取。
- 新增一个说法：往 TERMS 里加同一个键，网页用 W("键") 取。

职级（realms）按“预估分”划分：
    50 办事员 | 51–59 科员一～九级 | 60–64 副科级 | 65–69 正科级 | 70–74 副处级 | 75–79 正处级 | 80–84 副厅级 | 85+ 正厅级
    五分一个大职级：初任 2 分、在任 2 分、资深 1 分（如副科级 60–61 初任、62–63 在任、64 资深）。
    进入 60/65/70/75/80/85 这些大职级需要“晋升考核”（分数线在 规则.md 的“渡劫分数线”）。
"""

# (起始分, 结束分(不含), 类型)：mortal 办事员 / layers 每分一级 / stages 初任在任资深 / single 不再细分
BANDS = [(50, 51, "mortal"), (51, 60, "layers"), (60, 65, "stages"), (65, 70, "stages"),
         (70, 75, "stages"), (75, 80, "stages"), (80, 85, "stages"), (85, 999, "single")]
CN_NUM = "一二三四五六七八九"

# 专长品阶（8 档，index 0～7），四个大阶（index // 2）
BOARD_PILLS = {"官场": {"归纳概括": "提炼补课券", "综合分析": "研判补课券", "提出对策": "对策补课券",
                      "贯彻执行": "公文补课券", "大作文": "文章补课券"}}
ROOT_NAMES = {"官场": {"归纳概括": "概括专长", "综合分析": "分析专长", "提出对策": "对策专长",
                      "贯彻执行": "公文专长", "大作文": "文章专长"}}

THEMES = {
    "官场": {
        "realms": ["办事员", "科员", "副科级", "正科级", "副处级", "正处级", "副厅级", "正厅级"],
        "layer": "{n}级",                       # 科员三级
        "stages": ["初任", "在任", "资深"],
        "mortal_sub": "试用期",
        "gate_items": {60: "副科推荐函", 65: "正科推荐函", 70: "副处推荐函", 75: "正处推荐函", 80: "副厅推荐函", 85: "正厅推荐函"},
        "grades": ["初级Ⅰ", "初级Ⅱ", "中级Ⅰ", "中级Ⅱ", "高级Ⅰ", "高级Ⅱ", "资深Ⅰ", "资深Ⅱ"],
        "tiers": ["初级", "中级", "高级", "资深"],
        "pill_grades": ["合格", "良好", "优秀"],
        "thunders": {"recite": "要点关", "wrong": "整改关", "apply": "实操关", "final": "终审关"},
        "tutor_face": "🧑\u200d💼",
        "world": ("世界观（公文官场）：学员是一名基层干部，目标是通过“录用大考”（国考 / 省考）上岸。"
                  "申论的五个题型对应五项专长（归纳概括、综合分析、提出对策、贯彻执行、大作文）；每个题型的答题方法是“业务手册”，"
                  "每一条是一“条”，【术语】是必须一字不差的“要点”；"
                  "默写叫“汇报要点”，费曼讲解叫“向领导汇报”，应用小题叫“实操”（按采分点批改，领导给“批示”），"
                  "做错过、失分的题是“整改”（做对叫整改销号，没销掉会反复），复查叫“复核”（失败叫业务生疏）；"
                  "分数对应职级：办事员50、科员51–59（一至九级）、副科级60、正科级65、副处级70、正处级75、副厅级80、正厅级85；"
                  "晋升大职级要通过“晋升考核”（连续闯过几道关：要点关背要点、整改关重做失分题、实操关答应用题、最后一道终审关来自最弱专长），"
                  "并且最近两次“年度考核”（整套模考）都要达到该职级分数线；专长品阶分初级、中级、高级、资深各两档；"
                  "加练叫“加班补课”；集中练一个题型叫“下乡调研”；连续打卡叫“连续出勤”；请假叫“调休”；理想进度叫“年度目标进度”；"
                  "学习过久或连续失误会“过劳预警”，要休息。说话时自然地用这些说法，但判题内容必须严谨准确。"),
        "terms": {
            'yj': '便笺', 'yj_deck': '便笺夹', 'yj_add': '记便笺', 'yj_review': '过便笺', 'yj_browse': '便笺库', 'yj_stats': '记忆台账',
            'yj_rule': '便笺夹规矩', 'yj_new': '新便笺', 'yj_learn': '记忆中', 'yj_due': '待复习', 'yj_unit': '张',
            'yj_r1': '再看', 'yj_r2': '模糊', 'yj_r3': '清楚', 'yj_r4': '牢记', 'yj_done': '今日便笺已过完',
            'yj_leech': '顽固', 'yj_show': '显示答案',
            "brand": "🏛 申论官途", "nav.home": "🏛 办公室", "nav.train": "📝 办理", "nav.notes": "📒 公务手账", "nav.contest": "📊 年度考核",
            "nav.tianji": "📰 时政简报", "nav.skeleton": "🗄 档案室",
            "nav.wrong": "📌 整改录", "nav.pill": "⏱ 补课室", "nav.log": "📈 政绩录", "nav.settings": "⚙ 设置",
            "minutes": "今日办理", "lecture": "听课", "lecture_title": "听课 · 学习记录", "study": "办理",
            "lecture_hint": "在别处听课（看网课、听讲座）的时间也算学习。听完来这里记一笔，与办理合计每日学时。",
            "xp": "政绩", "realm": "职级", "score": "综合评价（预估分）",
            "streak": "连续出勤", "ideal": "年度目标进度", "lap": "考核周期", "batch": "个阶段",
            "skeleton": "业务手册", "item": "条", "term": "要点", "thought": "思路",
            "teach": "领导讲解", "recite": "汇报要点", "feynman": "向领导汇报", "example": "案例推演（举例）", "apply": "实操", "wrong": "整改", "kill": "整改销号",
            "redo": "整改反复", "review": "复核", "rust": "业务生疏", "speedrun": "重温手册",
            "levels": "未接手,能背要点,能汇报,已精通", "tasks": "今日待办", "side": "专项", "boss": "年度考核",
            "ascend": "录用大考", "leave": "调休", "practice": "实操", "practice_title": "实操 · 历练记", "selfstudy": "自习", "selfstudy_title": "自习 · 复习记", "tribulation": "晋升考核", "bottleneck": "瓶颈",
            "root": "专长", "pill": "补课券", "alchemy": "加班补课", "pill_room": "补课室", "retreat": "下乡调研", "retreat_end": "调研结束",
            "epiphany": "领导点拨", "qi": "过劳预警", "dao": "官声", "weekly": "周例会", "bag": "文件袋", "heal": "补救",
            "demon_rank": "整改榜", "tutor_room": "主任办公室", "chat_btn": "向主任请教", "breakthrough": "晋升",
            "hero_empty_id": "无名科员",
        },
    },
}

DEFAULT_THEME = "官场"


def get(name):
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def band_of(score_int):
    for i, (lo, hi, kind) in enumerate(BANDS):
        if lo <= score_int < hi:
            return i, lo, hi, kind
    return (0,) + BANDS[0] if score_int < 50 else (len(BANDS) - 1,) + BANDS[-1]


def sub_stage(score_int):
    """返回 (大境界序号, 小境界名(不含大境界名), 小境界起始分, 小境界结束分(不含))，风格无关的部分"""
    i, lo, hi, kind = band_of(score_int)
    if kind == "mortal":
        return i, None, lo, hi
    if kind == "layers":
        return i, ("layer", score_int - lo + 1), score_int, score_int + 1
    if kind == "stages":
        off = score_int - lo
        k = 0 if off < 2 else (1 if off < 4 else 2)
        a = lo + (0, 2, 4)[k]
        b = lo + (2, 4, 5)[k]
        return i, ("stage", k), a, b
    return i, None, lo, hi


def realm_name(theme, score_int):
    """如 “科员 + 第三级” → “科员三级”；“副科级 + 在任” → “副科级在任”；办事员 → “办事员 · 试用期”"""
    t = get(theme)
    i, sub, _, _ = sub_stage(score_int)
    big = t["realms"][i]
    short = big[:-1] if big.endswith("期") else big
    if sub is None:
        return f"{big} · {t['mortal_sub']}" if i == 0 else big
    if sub[0] == "layer":
        return short + t["layer"].format(n=CN_NUM[sub[1] - 1])
    return short + t["stages"][sub[1]]


def realm_of_gate(theme, gate):
    return get(theme)["realms"][band_of(gate)[0]]

