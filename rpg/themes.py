"""
两种风格（东方修仙 / 西方玄幻）的全部“说法”。游戏规则只有一套，风格只决定名字、导师、台词库和界面文字。

- 当前风格存在存档的 state["theme"]（两台电脑同步），网页“设置”里切换；默认修仙。
- 网页从 /api/dashboard 的 theme.terms 取界面文字，后端用 T(g, "键") 取。
- 新增一个说法：两种风格的 TERMS 都要加同一个键。

境界（REALMS）按“预估分”划分，两种风格共用分数段，只是名字不同：
    50 凡人 | 51–59 炼气一～九层 | 60–64 筑基 | 65–69 金丹 | 70–74 元婴 | 75–79 化神 | 80–84 大乘 | 85+ 真仙
    五分一个大境界：初期 2 分、中期 2 分、后期 1 分（如筑基 60–61 初期、62–63 中期、64 后期）。
    进入 60/65/70/75/80/85 这些大境界需要渡劫（分数线在 规则.md 的“渡劫分数线”）。
"""
from .version import APP_NAME

# (起始分, 结束分(不含), 类型)：mortal 凡人 / layers 每分一层 / stages 初中后 / single 不再细分
BANDS = [(50, 51, "mortal"), (51, 60, "layers"), (60, 65, "stages"), (65, 70, "stages"),
         (70, 75, "stages"), (75, 80, "stages"), (80, 85, "stages"), (85, 999, "single")]
CN_NUM = "一二三四五六七八九"
# 官场（申论）的分段：50 起每 5 分一段（乡镇、县委办、检察院、公安厅、部委、正部、副国、正国），每段三个岗位占 2、2、1 分
BANDS_GUANCHANG = [(50, 55, "stages"), (55, 60, "stages"), (60, 65, "stages"), (65, 70, "stages"),
                   (70, 75, "stages"), (75, 80, "stages"), (80, 85, "stages"), (85, 999, "single")]


def bands_of(theme):
    return BANDS_GUANCHANG if theme == "官场" else BANDS

# 八个灵根品阶（index 0～7），四个大阶（index // 2）
BOARD_PILLS = {
    "修仙": {"政治理论": "学思践悟丹", "常识判断": "博闻强识丹", "逻辑填空": "咬文嚼字丹", "片段阅读": "一目十行丹",
             "数量关系": "速算凝元丹", "资料分析": "截位直除丹", "图形推理": "火眼金睛丹", "定义判断": "字斟句酌丹",
             "类比推理": "触类旁通丹", "论证逻辑": "明辨是非丹", "形式逻辑": "逆否归元丹", "一拖五": "排兵布阵丹"},
    "玄幻": {"政治理论": "信仰圣水", "常识判断": "博学者药剂", "逻辑填空": "词锋药剂", "片段阅读": "鹰眼药剂",
             "数量关系": "算术师药剂", "资料分析": "统计学家药剂", "图形推理": "真视药剂", "定义判断": "律法药剂",
             "类比推理": "共鸣药剂", "论证逻辑": "辩术药剂", "形式逻辑": "逆否秘药", "一拖五": "战术家药剂"},
}
ROOT_NAMES = {
    "修仙": {"政治理论": "政理灵根", "常识判断": "常识灵根", "逻辑填空": "填空灵根", "片段阅读": "阅读灵根",
             "数量关系": "数量灵根", "资料分析": "资料灵根", "图形推理": "图推灵根", "定义判断": "定义灵根",
             "类比推理": "类比灵根", "论证逻辑": "论证灵根", "形式逻辑": "推演灵根", "一拖五": "排布灵根"},
    "玄幻": {"政治理论": "信仰天赋", "常识判断": "博学天赋", "逻辑填空": "词锋天赋", "片段阅读": "阅读天赋",
             "数量关系": "算术天赋", "资料分析": "统计天赋", "图形推理": "真视天赋", "定义判断": "律法天赋",
             "类比推理": "共鸣天赋", "论证逻辑": "辩术天赋", "形式逻辑": "推演天赋", "一拖五": "战术天赋"},
}

THEMES = {
    "修仙": {
        "realms": ["凡人", "炼气期", "筑基期", "金丹期", "元婴期", "化神期", "大乘期", "真仙"],
        "layer": "{n}层",                       # 炼气三层
        "stages": ["初期", "中期", "后期"],
        "mortal_sub": "未入道",
        "gate_items": {60: "筑基丹", 65: "凝金丹", 70: "化婴丹", 75: "化神丹", 80: "渡厄丹", 85: "登仙丹"},
        "grades": ["黄阶下品", "黄阶上品", "玄阶下品", "玄阶上品", "地阶下品", "地阶上品", "天阶下品", "天阶上品"],
        "tiers": ["黄阶", "玄阶", "地阶", "天阶"],
        "pill_grades": ["下品", "中品", "上品"],
        "thunders": {"recite": "心法雷", "wrong": "心魔雷", "apply": "问道雷", "final": "紫霄神雷"},
        "tutor_face": "🌸",
        "world": ("世界观（东方修仙）：学员是踏上仙途的修士，目标是在“飞升大典”（国考）上飞升（上岸）。"
                  "行测各板块对应一条灵根，每个板块的知识骨架是“功法”，每一章是“一重”，【术语】是必须一字不差的“口诀”；"
                  "默写叫“背诵口诀”，费曼讲解叫“论道”，应用小题叫“试剑”，做错过的题是“心魔”（做对叫斩心魔，没斩掉会心魔复生），"
                  "复查叫“温养道基”（失败叫根基松动）；分数对应境界：凡人50、炼气51–59（一至九层）、筑基60、金丹65、元婴70、化神75、大乘80、真仙85；"
                  "突破大境界要“渡劫”（连续闯过几道天雷：心法雷背口诀、心魔雷重做错题、问道雷答应用题、最后一道紫霄神雷来自最弱灵根），"
                  "并且最近两次“宗门大比”（模考）都要达到该境界分数线；灵根品阶分天地玄黄各上下品；"
                  "加练叫炼丹服丹；专注修炼叫闭关；连续修炼叫“周天不息”；请假叫“告假玉简”；理想进度叫“天道进度”；"
                  "学习过久或连续失败会“走火入魔”，要调息。说话时自然地用这些说法，但判题内容必须严谨准确。"),
        "terms": {
            'skillbook': '心法', 'skillbook_hall': '心法阁',
            'yj': '玉简', 'yj_deck': '简匣', 'yj_add': '刻简', 'yj_review': '温简', 'yj_browse': '藏简阁', 'yj_stats': '灵识图',
            'yj_rule': '简匣规矩', 'yj_new': '新简', 'yj_learn': '参悟中', 'yj_due': '待温', 'yj_unit': '枚',
            'yj_r1': '再参', 'yj_r2': '晦涩', 'yj_r3': '通透', 'yj_r4': '了然', 'yj_done': '今日玉简已温毕',
            'yj_leech': '顽固', 'yj_show': '显示答案',
                        'nav.bank': '🗼 试炼塔',
            'bank': '真题试炼',
            'bank_review': '伏魔再战',
            'bank_library': '真题经卷',
            'bank_remaining': '待闯关卡',
            'bank_wrong': '心魔残影',
            'bank_start': '入塔试炼',
            'bank_resume': '继续登塔',
            'bank_pause': '暂离试炼塔（保存进度）',
            'bank_next': '闯下一关',
            'bank_result': '查看试炼战报',
            'bank_history': '试炼战绩',
            'bank_rank.0': '磨砺道心',
            'bank_rank.1': '道基渐稳',
            'bank_rank.2': '剑心通明',
            'bank_rank.3': '破阵无伤',
            'bank_intro': '百层试炼塔，以真题验功法。每参透一批新经卷便登高一层，失手留下的心魔也要记得回头斩除。',
            'bank_good': '这一剑落得准。记住所用功法，别只记答案。',
            'bank_bad': '心魔已留下残影。先看清错因，待伏魔再战时把它斩去。',
            'bank_close': '本轮试炼已结。把失手的关卡练透，才算将功法化为本领。',
            'bank_empty': '经卷已练完，添入新真题后再来入阵。',
            'bank_no_wrong': '心魔残影已清，继续稳固道基。',
            'bank_unit': '关',
            'bank_record': '收录心魔残影',
            "brand": APP_NAME, "nav.home": "🏯 洞府", "nav.train": "🧘 修炼", "nav.notes": "🪶 手札", "nav.contest": "⚔ 宗门大比", "nav.tianji": "🔮 天机简报", "nav.skeleton": "📜 藏经阁",
            "nav.wrong": "👹 心魔录", "nav.pill": "⚗ 丹房", "nav.log": "📖 修仙录", "nav.settings": "⚙ 设置",
            "minutes": "今日修炼", "lecture": "听道", "lecture_title": "听道 · 闻法记", "study": "修炼",
            "lecture_hint": "在别处听高人讲法（看网课）的时辰，也是修行。听完来此记一笔，与修炼合计每日功行。",
            "xp": "修为", "realm": "境界", "score": "道行（预估分）",
            "streak": "周天不息", "ideal": "天道进度", "lap": "大周天", "batch": "重秘境",
            "skeleton": "功法", "item": "重", "term": "口诀", "thought": "心得",
            "teach": "传授", "recite": "背诵口诀", "feynman": "论道", "example": "化法为境（举例）", "apply": "试剑", "wrong": "心魔", "kill": "斩心魔",
            "redo": "心魔复生", "review": "温养道基", "rust": "根基松动", "speedrun": "重温功法",
            "levels": "未入门,小成,大成,圆满", "tasks": "今日功课", "side": "支线", "boss": "宗门大比",
            "ascend": "飞升大典", "leave": "告假玉简", "practice": "演武", "practice_title": "演武 · 历练记", "selfstudy": "静修", "selfstudy_title": "静修 · 温养记", "tribulation": "渡劫", "bottleneck": "瓶颈",
            "root": "灵根", "pill": "丹药", "alchemy": "炼丹", "pill_room": "丹房", "retreat": "闭关", "retreat_end": "出关",
            "epiphany": "顿悟", "qi": "走火入魔", "dao": "道心", "weekly": "宗门周常", "bag": "储物袋", "heal": "疗伤",
            "demon_rank": "心魔榜", "tutor_room": "师尊的静室", "chat_btn": "向师尊请教", "breakthrough": "突破",
            "hero_empty_id": "无名散修",
        },
    },
    "玄幻": {
        "realms": ["平民", "见习学徒", "青铜骑士", "白银骑士", "黄金圣骑士", "秘银剑圣", "龙骑士", "神域·上岸者"],
        "layer": "{n}星",
        "stages": ["下位", "中位", "上位"],
        "mortal_sub": "未觉醒",
        "gate_items": {60: "青铜徽记", 65: "白银徽记", 70: "黄金徽记", 75: "秘银徽记", 80: "龙之徽记", 85: "神域徽记"},
        "grades": ["普通Ⅰ", "普通Ⅱ", "精良Ⅰ", "精良Ⅱ", "史诗Ⅰ", "史诗Ⅱ", "传说Ⅰ", "传说Ⅱ"],
        "tiers": ["普通", "精良", "史诗", "传说"],
        "pill_grades": ["劣质", "标准", "完美"],
        "thunders": {"recite": "咒文关", "wrong": "魔物关", "apply": "贤者之问", "final": "终焉之门"},
        "tutor_face": "🔮",
        "world": ("世界观（西方玄幻）：这里是“王立行测魔法学院”。学员是冒险者，目标是在“封神典礼”（国考）上封神（上岸）。"
                  "行测各板块对应一种元素天赋；每个板块的知识骨架是“咒文书”，每一章是一章咒文，【术语】是必须一字不差的“咒文真名”；"
                  "默写叫“咏唱咒文”，费曼讲解叫“传授奥义”，应用小题叫“实战演练”，做错过的题是“魔物”（没讨伐成功会卷土重来），"
                  "复查叫“驱散遗忘”（失败叫遗忘诅咒）；分数对应位阶：平民50、见习学徒51–59（一至九星）、青铜骑士60、白银骑士65、"
                  "黄金圣骑士70、秘银剑圣75、龙骑士80、神域·上岸者85；晋升大位阶要通过“晋升试炼”并在最近两次“竞技场”（模考）达线；"
                  "加练叫调配药剂；专注修炼叫冥想；连续打卡叫“圣火连燃”；请假叫“休憩卷轴”；理想进度叫“命运之线”；"
                  "学习过久或连续失败会“魔力过载”。说话时自然地用这些说法，但判题内容必须严谨准确。"),
        "terms": {
            'skillbook': '秘典', 'skillbook_hall': '秘典阁',
            'yj': '符文卡', 'yj_deck': '卷轴匣', 'yj_add': '刻录符文', 'yj_review': '温习符文', 'yj_browse': '符文库', 'yj_stats': '记忆星图',
            'yj_rule': '卷轴规则', 'yj_new': '新符', 'yj_learn': '研习中', 'yj_due': '待温', 'yj_unit': '张',
            'yj_r1': '再研', 'yj_r2': '艰涩', 'yj_r3': '熟记', 'yj_r4': '通晓', 'yj_done': '今日符文已温毕',
            'yj_leech': '顽固', 'yj_show': '揭示答案',
                        'nav.bank': '🗼 试炼塔',
            'bank': '真题试炼',
            'bank_review': '魔物再战',
            'bank_library': '真题卷轴',
            'bank_remaining': '待闯关卡',
            'bank_wrong': '魔物残影',
            'bank_start': '进入试炼',
            'bank_resume': '继续探索',
            'bank_pause': '返回营地（保存进度）',
            'bank_next': '挑战下一关',
            'bank_result': '查看冒险战报',
            'bank_history': '冒险战绩',
            'bank_rank.0': '磨砺意志',
            'bank_rank.1': '战技渐熟',
            'bank_rank.2': '奥义精通',
            'bank_rank.3': '完美通关',
            'bank_intro': '百层试炼塔，以真题验奥义。完成新卷轴便可继续登高，失手的魔物残影留待再次讨伐。',
            'bank_good': '这次施法很准确。记住判断的依据，下一关继续。',
            'bank_bad': '魔物留下了残影。先查清失手原因，再来完成讨伐。',
            'bank_close': '本轮冒险结束。把失手的关卡重新练透，才算掌握真正的奥义。',
            'bank_empty': '卷轴已练完，添入新真题后继续探索。',
            'bank_no_wrong': '魔物残影已清，继续精进战技。',
            'bank_unit': '关',
            'bank_record': '收录魔物残影',
            "brand": APP_NAME, "nav.home": "🏕 营地", "nav.train": "⚔ 冒险", "nav.notes": "📓 魔法手记", "nav.contest": "🏆 竞技场", "nav.tianji": "🔮 星象密报", "nav.skeleton": "📕 咒文书",
            "nav.wrong": "👾 魔物图鉴", "nav.pill": "⚗ 炼金室", "nav.log": "📖 编年史", "nav.settings": "⚙ 设置",
            "minutes": "今日修炼", "lecture": "听讲", "lecture_title": "听讲 · 课堂笔记", "study": "修炼",
            "lecture_hint": "在别处旁听导师讲课（看网课）的时间也算修行。听完来此登记，与修炼合计每日学时。",
            "xp": "经验", "realm": "位阶", "score": "战力预估",
            "streak": "圣火连燃", "ideal": "命运之线", "lap": "轮征程", "batch": "层地下城",
            "skeleton": "咒文书", "item": "章", "term": "咒文真名", "thought": "思路",
            "teach": "导师讲解", "recite": "咏唱咒文", "feynman": "传授奥义", "example": "构筑幻境（举例）", "apply": "实战演练", "wrong": "魔物", "kill": "讨伐魔物",
            "redo": "卷土重来", "review": "驱散遗忘", "rust": "遗忘诅咒", "speedrun": "重温咒文",
            "levels": "未习得,能咏唱,能讲授,已精通", "tasks": "今日委托", "side": "支线任务", "boss": "竞技场",
            "ascend": "封神典礼", "leave": "休憩卷轴", "practice": "野外历练", "practice_title": "野外历练 · 实战日志", "selfstudy": "自习", "selfstudy_title": "自习 · 温故笔记", "tribulation": "晋升试炼", "bottleneck": "瓶颈",
            "root": "天赋", "pill": "药剂", "alchemy": "调配药剂", "pill_room": "炼金室", "retreat": "冥想", "retreat_end": "结束冥想",
            "epiphany": "灵感迸发", "qi": "魔力过载", "dao": "意志", "weekly": "公会周常", "bag": "背包", "heal": "治疗",
            "demon_rank": "弱点榜", "tutor_room": "学姐的研究室", "chat_btn": "找学姐聊聊", "breakthrough": "晋升",
            "hero_empty_id": "无名冒险者",
        },
    },
}

# 官场风格（申论）：单独一个文件，这里并进来；没写到的键回退到修仙那一套
from . import themes_guanchang as _gc  # noqa: E402

BOARD_PILLS["官场"] = _gc.PILLS
ROOT_NAMES["官场"] = _gc.ROOTS
THEMES["官场"] = dict(_gc.THEME, terms={**THEMES["修仙"]["terms"], **_gc.THEME["terms"]})

DEFAULT_THEME = "修仙"


def get(name):
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def band_of(score_int, theme=None):
    bands = bands_of(theme)
    for i, (lo, hi, kind) in enumerate(bands):
        if lo <= score_int < hi:
            return i, lo, hi, kind
    return (0,) + bands[0] if score_int < 50 else (len(bands) - 1,) + bands[-1]


def sub_stage(score_int, theme=None):
    """返回 (大境界序号, 小境界名(不含大境界名), 小境界起始分, 小境界结束分(不含))，风格无关的部分"""
    i, lo, hi, kind = band_of(score_int, theme)
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
    """如 “炼气期三层” → 显示为 “炼气三层”；“筑基期中期” → “筑基中期”；凡人 → “凡人 · 未入道”。
    官场：岗位（职级），用默认的职务履历；用户改过 训练/职务履历.md 的，由 engine.realm_label 读"""
    if theme == "官场":
        from .career import Career
        return Career().label(score_int)
    t = get(theme)
    i, sub, _, _ = sub_stage(score_int, theme)
    big = t["realms"][i]
    short = big[:-1] if big.endswith("期") else big
    if sub is None:
        return f"{big} · {t['mortal_sub']}" if i == 0 else big
    if sub[0] == "layer":
        return short + t["layer"].format(n=CN_NUM[sub[1] - 1])
    return short + t["stages"][sub[1]]


def realm_of_gate(theme, gate):
    return get(theme)["realms"][band_of(gate, theme)[0]]



# 3.0人物与纪事的风格名词；申论人物名由实际职务履历覆盖。
NARRATIVE_PROFILES = {'xingce': {'title': '任务大殿', 'character': '沈清禾', 'role': '引导师尊', 'mark': '竹', 'portrait': 'assets/guide/shen-qinghe.webp', 'intro': '青衡宗引导师尊。陪你梳理修行路线，具体授业仍由你设定的导师负责。', 'greeting': '任务大殿是接取日常任务的地方：先领取任务，再去修炼，完成真实练习后回来交付。', 'study': '今天的功课', 'review': '洞府', 'room': '洞府', 'echo': '你已留下真实修行记录。慢一些无妨，重要的是知道每一步为何如此。'}, 'office': {'title': '工作纪事', 'character': '直属领导', 'role': '工作引导', 'mark': '章', 'portrait': '', 'intro': '当前阶段的女性直属领导。依据你的真实办理与学习记录提供建议，具体批改沿用原有评分标准。', 'greeting': '欢迎回到政务大厅。先读材料，把问题与依据理清，再动笔。你想先了解什么？', 'study': '今天的办理', 'review': '政绩复盘', 'room': '办公室', 'echo': '你已经留下学习记录。回看材料、要点和自己的表达，再确定下一步安排。'}}


# 3.4半身立绘：基础图+4个表情+眨眼叠层（眨眼框为占整图的比例）。路径相对web/；缺图时前端回退到portrait或主题印记。
def _portraits(base, name, blink):
    d = {k: '%s/%s-%s.webp' % (base, name, k) for k in ('calm', 'cheer', 'explain', 'concern', 'proud')}
    d['blink'] = dict(src='%s/%s-blink.webp' % (base, name), **blink)
    return d
NARRATIVE_PROFILES['xingce']['portrait'] = 'assets/guide/xc-qinghe-calm.webp'
NARRATIVE_PROFILES['xingce']['portraits'] = _portraits('assets/guide', 'xc-qinghe', {'x': 0.4917, 'y': 0.1344, 'w': 0.1583, 'h': 0.0469})

# 3.0学习委托与收藏的三主题名词/内置台词，程序核验逻辑在journey.py。
JOURNEY_PROFILES = {
    'xingce': {'cards': '温简', 'exercise': '修习', 'title': '五脉初课', 'daily': '今日修习', 'first': '明理初试', 'second': '回望与再练',
               'letter': '清禾书信', 'badge': '五脉初修徽记', 'ornament': '竹卷摆件',
               'intro': '清禾为你留下一卷空白竹简。先完成一次真实练习，再带着疑问回来。',
               'echo': '清禾指向问道群峰：再温习一张卡片、复练一道错题，或重新讲清一个要点。',
               'end': '竹简上已有你的学习足迹。五脉初课告一段落，修炼入口随时为你开放。'},
    'office': {'cards': '便笺复习', 'exercise': '办理', 'title': '第一份办理记录', 'daily': '今日办理', 'first': '办理初课', 'second': '回看与修订',
               'letter': '领导批示', 'badge': '办理纪念印章', 'ornament': '案头卷宗',
               'intro': '领导把一份空白办理记录交给你。先完成一次正式作答批改或便笺复习，再回来汇报。',
               'echo': '领导请你回看学习记录与要点。再温习一张卡片，或修改后重新提交一次正式批改。',
               'end': '卷宗里留下了学习与再练的记录。这次办理告一段落，新的练习仍可自由选择。'},
    'mage': {'cards': '符文温习', 'exercise': '课程练习', 'title': '法典的第一页', 'daily': '今日课程', 'first': '学院初试', 'second': '重读与论证',
             'letter': '艾琳的书签信', 'badge': '学院研习徽章', 'ornament': '案头法典',
             'intro': '艾琳递来一页空白书签。完成一次已核验真题作答或符文温习，再把问题带回学院。',
             'echo': '艾琳翻回法典：温习一张符文、复练一道题，或重新讲清规则与适用条件。',
             'end': '书签与徽章记下了研习的经过。法典的第一页已经写下，八科课程仍可随时进入。'}
}


# 3.0世界阶段与同伴；只影响叙事、外观与纪念，不增加学业成绩。
WORLD_PROFILES = {'mage': {'title': '学院复兴', 'stages': ['初入学院', '长廊点灯', '法典修缮', '考核庭开放', '赴考准备'], 'regions': ['法典长廊', '研习工坊', '考核庭'], 'finish': '学院的灯火记下你的研习，下一门课程仍在等你。', 'honor': '法典研习者', 'companions': [{'id': 'peer_method', 'name': '莉娅', 'role': '课程学员', 'mark': '书', 'intro': '与你一起梳理构成要件与适用边界的学员。', 'greeting': '法典页边还空着。你想先画出规则脉络，还是用一个问题检验边界？', 'method': '莉娅留下几条空白索引：“按要件、例外、效果分开整理；不确定的内容留待核对。”', 'practice': '莉娅递来一页练习纸：“先独立作答，再核对可靠答案与法源。”', 'echo_method': '你上次选择先梳理规则。可以从咒文书馆继续，具体掌握仍以练习记录为准。', 'echo_practice': '你上次选择先用题目检验。可以从原课程继续，遇到疑点再回法典核对。', 'keepsake': '莉娅的索引签'}, {'id': 'peer_review', 'name': '诺亚', 'role': '复盘学员', 'mark': '灯', 'intro': '陪你回看练习与考核记录的学员，不替你判断掌握程度。', 'greeting': '学过的内容还值得回看。你想温习一张符文，还是复练一道题？', 'method': '诺亚在灯下留出一张空白书签：“先说出答案，再翻看背面，按真实表现评分。”', 'practice': '诺亚指向试炼塔：“复练保留原规则，弄清判断依据比多点一次领奖更有用。”', 'echo_method': '你上次选择温习符文；新的复习记录仍由原卡片模块保存。', 'echo_practice': '你上次选择复练题目；沿用原练习与复盘，不靠剧情给自己加分。', 'keepsake': '诺亚的灯下札记'}]}, 'xingce': {'title': '青衡宗修复', 'stages': ['初入山门', '藏经阁重开', '五脉竹廊修复', '会试台开放', '赴选准备'], 'regions': ['藏经阁竹廊', '五脉修习庭', '宗门会试台'], 'finish': '竹廊已留下修行足迹，五脉仍可随时修习。', 'honor': '五脉同行者', 'companions': [{'id': 'peer_method', 'name': '陆衡', 'role': '明理殿同门', 'mark': '竹', 'intro': '与你梳理判断方法的同门。具体授业仍由原导师负责。', 'greeting': '明理殿的竹简还未写满。你想先理清方法，还是试一道题？', 'method': '陆衡留下一卷空白竹简：“把适用条件与边界讲清，不必只背方法名字。”', 'practice': '陆衡指向试炼塔：“先独立作答，再看判断依据；错了也能留下真实练习记录。”', 'echo_method': '你上次选择先明理。藏经阁与原训练随时可进，不必每天来刷熟悉度。', 'echo_practice': '你上次选择以题检验。去原试炼或修炼殿继续，判断仍依据真实作答。', 'keepsake': '陆衡的明理竹签'}, {'id': 'peer_review', 'name': '苏苓', 'role': '任务大殿同门', 'mark': '镜', 'intro': '与你回看修习记录的同门，不凭空推测薄弱处。', 'greeting': '照心台前，苏苓留出两条路：温一张玉简，或复练一道题。你想从哪边开始？', 'method': '苏苓展开玉简：“先回忆，再翻看；忘记了就按真实表现评分。”', 'practice': '苏苓轻指旧题：“复练看依据，不重复发通关奖励，也不替你改正确率。”', 'echo_method': '你上次选择温简，原卡片记录仍是下一步安排的依据。', 'echo_practice': '你上次选择复练，可从洞府的修行日志回看真实练习记录。', 'keepsake': '苏苓的照心札记'}]}, 'office': {'title': '单位工作阶段', 'stages': ['报到起步', '学习档案建立', '复盘卷宗归档', '模拟考核阶段', '考前安排'], 'regions': ['学习资料室', '复盘协作台', '模拟考核室'], 'finish': '学习与复盘卷宗已经归档，下一项办理仍可自由选择。', 'honor': '学习复盘同行者', 'companions': [{'id': 'peer_method', 'name': '许知宁', 'role': '材料整理同事', 'mark': '笺', 'intro': '与你核对材料与表达的同事；正式批改仍用原采分点标准。', 'greeting': '工作台上留着一张便笺。你想先梳理材料要点，还是先独立写一份答案？', 'method': '许知宁留出要点栏：“先看材料中的依据与范围，再决定如何表达；不要补造材料事实。”', 'practice': '许知宁整理好空白答题纸：“独立作答后提交原正式批改；草稿与剧情都不能替代评分。”', 'echo_method': '你上次选择先整理材料，可继续查看档案与便笺。是否掌握仍以真实练习为准。', 'echo_practice': '你上次选择先独立作答，可回办理中心继续正式训练。', 'keepsake': '知宁的材料便笺'}, {'id': 'peer_review', 'name': '林悦', 'role': '复盘协作同事', 'mark': '卷', 'intro': '陪你回看办理与学习记录的同事，不替领导作出评价。', 'greeting': '林悦把复盘页留在卷宗旁。你想先复习一张便笺，还是重新整理后再正式作答？', 'method': '林悦翻开便笺夹：“先独立回忆，再核对背面，按实际记忆情况评分。”', 'practice': '林悦留出修订页：“根据已有材料和批改反馈修改，再提交正式批改；原评分标准不变。”', 'echo_method': '你上次选择先复习便笺，可从原便笺夹继续。', 'echo_practice': '你上次选择修订后再作答，原批改记录会保留这次办理。', 'keepsake': '林悦的复盘便笺'}]}}
