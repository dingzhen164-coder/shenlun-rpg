"""
主题注册表：只换名词、职级名、导师，不换规则。
现有主题：官场（申论）。日后合并行测时在这里注册 修仙 / 玄幻，由科目选默认主题。
谁调用：core/api.py（dashboard.theme）、前端通过 dashboard.theme.terms 取说法。
"""

THEMES = {
    "官场": {
        "name": "官场",
        "app": "申论官途",
        "tagline": "笔下有乾坤，材料见真章",
        "terms": {
            "xp": "政绩", "score": "综合评价", "rank": "职级", "streak": "连续出勤",
            "daily": "每日一题", "wrong": "整改", "boss": "年度考核",
            "tutor": "领导批示", "leave": "调休", "pill": "加班补课",
            "retreat": "下乡调研", "heart": "官声", "weekly": "周例会",
            "root": "专长", "promote": "晋升考核", "start": "开始办理",
        },
        # (预估分下限, 职级名)；分数线放规则.md 时以规则为准
        "ranks": [(0, "科员"), (55, "副科"), (60, "正科"), (65, "副处"),
                  (70, "正处"), (75, "副厅"), (80, "正厅"), (85, "副部")],
        "tutor": {"name": "陈主任", "title": "分管领导"},
    },
}
DEFAULT_THEME = "官场"


def get(name):
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def rank_of(theme, score):
    """预估分 → (职级名, 下一职级名或 None, 下一职级分数线或 None)"""
    ranks = get(theme)["ranks"]
    idx = 0
    for i, (low, _) in enumerate(ranks):
        if score is not None and score >= low:
            idx = i
    nxt = ranks[idx + 1] if idx + 1 < len(ranks) else None
    return ranks[idx][1], (nxt[1] if nxt else None), (nxt[0] if nxt else None)
