"""
读取 训练/ 下的三个用户配置文件，给出带默认值的配置对象。

    规则.md                    → Rules      （游戏规则：时间线、职级、晋升考核、专长、补课券、分批、政绩值……）
    角色设定.md                → Persona    （ID、头像；称呼、导师名 / 头像 / 人设）
    台词库.md                  → Lines      （导师在各场景下随机说的话）

每次请求都重新读取（文件很小），所以用户改完刷新网页就生效。
规则文件里缺的键一律用 DEFAULT_RULES 里的默认值，写错的值也回退到默认值，程序不会因此崩溃。
"""
import datetime as dt
import random
import re

from . import mdconf

# 默认规则：和 defaults/规则.md 保持一致。新增规则时两边都要加。
DEFAULT_RULES = {
    "经验.批改满分": 60,    # 一次批改满分拿到的政绩，实际按得分率折算
    "经验.简报答对": 5,
    "经验.简报答错": 1,
    "经验.举例通过": 25,
    "经验.举例未过": 5,
    "分钟.举例": 6,
    # 时间线
    "开始日期": "2026-09-29",
    "目标日": "2027-12-01",
    "每日目标分钟": 300,    # 办理 + 听课（网课）合计
    "保底分钟": 15,
    "每月请假卡": 4,
    # 分数与职级（政绩 → 预估分 → 职级）
    "起始分数": 50,
    "目标分数": 80,
    "最高分数": 100,
    "每日理想经验": 300,
    "成长曲线指数": 0.7,     # 综合评价 = 起始 + 跨度 ×（政绩/理想政绩）^指数；<1 前快后慢，1 是直线
    # 晋升考核
    "晋升分数线": "60, 65, 70, 75, 80, 85",
    "晋升关数": "3, 5, 7, 9, 9, 9",
    "晋升冷却天数": 3,
    "晋升官声": 60,
    "晋升专长.60": "激活1",
    "晋升专长.65": "激活3",
    "晋升专长.70": "激活5 中级2",
    "晋升专长.75": "激活7 中级4 高级1",
    "晋升专长.80": "激活9 中级6 高级3",
    "晋升专长.85": "激活10 高级5 资深2",
    # 专长
    "专长得分率": "55, 60, 65, 70, 75, 80, 85, 90",
    "专长取最近几次": 3,
    "专长每阶加成": 0.05,
    "专长复查间隔加成": 0.1,
    # 补课券 / 下乡调研 / 领导点拨 / 过劳预警 / 官声
    "补课题数": 5,
    "补课加成": "0.1, 0.2, 0.3",
    "调研加成": 0.2,
    "点拨概率": 0.08,
    "点拨倍数": 1.0,
    "过劳预警分钟": 180,
    "过劳预警连错": 5,
    "过劳休息分钟": 10,
    "官声统计天数": 14,
    "补卡券连续天数": 30,
    # 周例会（每周一刷新）
    "周例会.整改销号": 20,
    "周例会.汇报要点": 15,
    "周例会.向领导汇报": 3,
    "周例会.办理分钟": 1500,
    "周例会.年度考核": 1,
    # 导师
    "导师AI": "开",
    # 分批与日常
    "每批预计天数": 14,
    "每日新学大项": 4,
    "每日新学题型数": 2,
    "每日复查上限": 6,
    "默写连续通过次数": 2,
    "思路达标比例": 0.8,
    "费曼追问轮数": 2,
    "应用连续通过次数": 2,
    "复查间隔天数": "3, 7, 15, 30, 60",
    "每日错题下限": 4,
    "每日错题上限": 10,
    "回炉间隔天数": 2,
    "回炉连续判对": 2,
    "错题只取最近几季": 0,
    # 政绩（经验）
    "经验.默写通过": 30,
    "经验.默写未过": 5,
    "经验.首次通过加成": 20,
    "经验.费曼通过": 50,
    "经验.费曼未过": 10,
    "经验.应用通过": 25,
    "经验.应用未过": 5,
    "经验.错题判对": 15,
    "经验.错题判错": 3,
    "经验.回炉判对加成": 10,
    "经验.复查通过": 15,
    "经验.复查未过": 3,
    "经验.大项掌握": 40,
    "经验.批次通关": 500,
    "经验.周目通关": 2000,
    "经验.晋升成功": 500,
    "经验.自练每题": 2,
    "经验.办理每分钟": 1,     # 有效办理时间（做题、过便笺、时政简报、公务手账、复盘…心跳计时的那些）每分钟的基础政绩
    "经验.听课每分钟": 0.5,   # 听课（网课）每分钟的政绩；主要靠办理拿政绩，听课只给少量
    "听课单次上限": 600,
    "经验.静修每分钟": 0.5,   # 静修（自己复习：背要点、看笔记、整理错题本）每分钟的政绩
    "经验.模考录分": 100,
    "经验.周例会": 150,
    "经验.上岸": 3000,
    "连续打卡每天加成": 0.02,
    "连续打卡加成上限": 0.2,
    "分钟.默写": 5,
    "分钟.费曼": 12,
    "分钟.应用": 6,
    "分钟.错题": 4,
    "分钟.复查": 3,
    "分钟.骨架": 15,
    "分钟.补救": 5,
    "分钟.晋升考核": 20,
}

# 用户配置文件的版本号。defaults/ 里的文件改了结构（不只是改数值）时 +1，
# 程序启动时会把旧版本的用户文件备份成 “xxx.旧版.md” 并换成新默认文件（见 paths.ensure_train_dir）。
CONFIG_VERSION = 1
# 每个配置文件各自的版本：只升级真正改了结构的文件，其余文件不动（用户改过的内容保留）
FILE_VERSIONS = {"规则.md": 1, "角色设定.md": 1, "台词库.md": 1}
TIER_WORDS = {"初级": 0, "中级": 1, "高级": 2, "资深": 3}

# 默认分批：先学归纳概括和综合分析，再学对策和公文，最后是大作文
DEFAULT_BATCHES = [
    ["归纳概括", "综合分析"],
    ["提出对策", "贯彻执行"],
    ["大作文"],
]

# 题型名 → (skill 文件夹名, [复盘里的题型名])。skill 文件夹放在 <库>/copilot/skills/，名字对不上就在 规则.md 里改“题型.xxx”
DEFAULT_BOARDS = {
    "归纳概括": ("shenlun-xiaoti", ["归纳概括"]),
    "综合分析": ("shenlun-xiaoti", ["综合分析"]),
    "提出对策": ("shenlun-xiaoti", ["提出对策"]),
    "贯彻执行": ("shenlun-xiaoti", ["贯彻执行"]),
    "大作文": ("shenlun-dawenti", ["大作文"]),
}
DEFAULT_SIDE = {}


def _date(s, default):
    try:
        return dt.date.fromisoformat(str(s).strip())
    except Exception:
        return dt.date.fromisoformat(default)


class Rules:
    """规则。用 r.num("经验.默写通过") / r.date("目标日") / r.nums("复查间隔天数") 取值。"""

    def __init__(self, text=""):
        self.raw = mdconf.parse(text)

    def get(self, key):
        return self.raw.get(key, DEFAULT_RULES.get(key))

    def has(self, key):
        return key in self.raw or key in DEFAULT_RULES

    def num(self, key):
        return mdconf.to_num(self.get(key), DEFAULT_RULES[key])

    def date(self, key):
        return _date(self.get(key), DEFAULT_RULES[key])

    def nums(self, key):
        vals = [mdconf.to_num(x, None) for x in mdconf.split_list(str(self.get(key)))]
        vals = [v for v in vals if v is not None]
        return vals or [mdconf.to_num(x, 0) for x in mdconf.split_list(DEFAULT_RULES[key])]

    def on(self, key):
        """开关类规则：“开 / 是 / true / 1” 为真"""
        return str(self.get(key)).strip().lower() in ("开", "是", "true", "1", "on", "yes")

    def xp(self, name):
        """经验值：r.xp("默写通过")"""
        return self.num("经验." + name)

    def minutes(self, task_type):
        key = "分钟." + task_type
        return self.num(key) if key in DEFAULT_RULES else 5

    @property
    def batches(self):
        """[[题型, …], …]，按 “第N批” 的 N 排序；规则里一批都没写就用默认分批"""
        found = []
        for k, v in self.raw.items():
            m = re.fullmatch(r"第\s*(\d+)\s*批", k)
            if m and mdconf.split_list(v):
                found.append((int(m.group(1)), mdconf.split_list(v)))
        return [b for _, b in sorted(found)] or [list(b) for b in DEFAULT_BATCHES]

    @property
    def boards(self):
        """{题型: {"skill": 文件夹名, "sources": [复盘题型名]}}，保持规则里的顺序"""
        out = {}
        for k, v in self.raw.items():
            if k.startswith("题型."):
                name = k[3:].strip()
                skill, _, src = v.partition("|")
                out[name] = {"skill": skill.strip(), "sources": mdconf.split_list(src) or [name]}
        if not out:
            out = {k: {"skill": s, "sources": list(src)} for k, (s, src) in DEFAULT_BOARDS.items()}
        # 分批里出现、但没有定义的题型：skill 名留空（显示为待接入）
        for b in [x for batch in self.batches for x in batch]:
            out.setdefault(b, {"skill": "", "sources": [b]})
        return out

    def gate_roots(self, gate):
        """某道晋升考核线的专长要求：{"激活": n, 0: 初级及以上个数, 1: 中级…, 2: 高级…, 3: 资深…}"""
        out = {}
        for m in re.finditer(r"(激活|初级|中级|高级|资深)\s*(\d+)", str(self.get(f"晋升专长.{gate}") or "")):
            key = "激活" if m.group(1) == "激活" else TIER_WORDS[m.group(1)]
            out[key] = int(m.group(2))
        return out

    def root_thresholds(self, board):
        """专长八个品阶的正确率门槛（0~1）"""
        key = f"专长得分率.{board}"
        raw = self.raw.get(key) or DEFAULT_RULES.get(key) or self.get("专长得分率")
        vals = [mdconf.to_num(x, None) for x in mdconf.split_list(str(raw))]
        vals = [v / 100 if v and v > 1 else v for v in vals if v is not None]
        return (vals + [1.01] * 8)[:8]

    @property
    def side(self):
        """副线 {复盘题型名: 目标正确率}"""
        out = {k[3:].strip(): mdconf.to_num(v, 0.7) for k, v in self.raw.items() if k.startswith("副线.")}
        return out or dict(DEFAULT_SIDE)


class Persona:
    """角色设定：角色设定.md 里写成 “官场.导师名: …”；不带前缀的键（ID、头像）是你自己的。用 p["导师名"] 取值。
    结构按“风格”分组，是为了以后和行测合并时能再加别的风格。"""
    COMMON = {"ID": "", "头像": "头像.png"}
    THEMED = {
        "官场": {"称呼": "小同志", "导师名": "陈主任", "导师头像": "主任.png", "吐槽尺度": "中",
                 "导师人设": ("你的分管领导陈主任，四十来岁，办公室里最严的人，也是最护短的人。说话直、不绕弯，口头禅是“材料要吃透”“原词别丢”“数据说话”；"
                            "你偷懒时他板着脸批评“小同志，这个态度不行”，你写得好时只说“嗯，有进步，继续保持”，其实比谁都高兴；"
                            "你真的累了或遇到难处时，他会放下批评，语重心长地跟你聊两句，让你先休息。")},
    }

    def __init__(self, text="", theme="官场"):
        from . import themes
        raw = mdconf.parse(text)
        self.theme = theme if theme in self.THEMED else "官场"
        self.d = {k: (raw.get(k) or v) for k, v in self.COMMON.items()}
        for k, v in self.THEMED[self.theme].items():
            self.d[k] = raw.get(f"{self.theme}.{k}") or v
        if not self.d["ID"]:
            self.d["ID"] = themes.get(self.theme)["terms"]["hero_empty_id"]

    def __getitem__(self, k):
        return self.d[k]


class Lines:
    """台词库：lines.pick("开场·落后", 称呼="小岸", 落后天数=3)"""

    def __init__(self, text="", fallback=""):
        # 自己的台词库里没有的场景（程序新加的），用默认台词库里的
        self.sec = mdconf.sections(fallback)
        self.sec.update({k: v for k, v in mdconf.sections(text).items() if v})

    def pick(self, scene, **vals):
        opts = self.sec.get(scene) or []
        if not opts:
            return ""
        s = random.choice(opts)
        for k, v in vals.items():
            s = s.replace("{" + k + "}", str(v))
        return re.sub(r"\{[^{}]{1,6}\}", "", s)  # 没提供的占位符直接去掉


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


LINES_FILE = {"官场": "台词库.md"}


def load_all(paths, theme="官场"):
    """返回 (Rules, Persona, Lines)；库没找到或文件缺失时用 defaults/ 里的默认文件。"""
    from .paths import DEFAULTS_DIR

    def txt(p, name):
        return (read_text(p) if p else "") or read_text(DEFAULTS_DIR / name)

    lines_name = LINES_FILE.get(theme, "台词库.md")
    return (Rules(txt(paths.rules, "规则.md")), Persona(txt(paths.persona, "角色设定.md"), theme),
            Lines(txt(paths.train / lines_name if paths.train else None, lines_name), read_text(DEFAULTS_DIR / lines_name)))
