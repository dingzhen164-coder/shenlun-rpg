"""
科目表：一个程序里的两个科目（行测修仙传 / 申论官途）。

每个科目各有一套：库路径、存档、规则文件、风格（名词）、功能集。切换科目 = 设置里改 settings["subject"]，网页重新加载。
    行测：风格 修仙 / 玄幻（可在设置里切）；功能含 题库、试炼塔、成语实词录、模考分析（宗门大比）
    申论：风格 官场（固定）；功能含 采分点批改（办理 → 实操）、年度考核

本机设置（~/.shenlun-rpg/settings.json）里和科目有关的键：
    subject   "行测" | "申论"，当前科目（默认 申论）
    vaults    {"行测": 路径, "申论": 路径}；旧版只有一个 vault 键，视为申论库
环境变量：SHENLUN_SUBJECT 临时指定科目（测试用）；XINGCE_VAULT / SHENLUN_VAULT 临时指定各自的库。
"""
import os

DEFAULT_SUBJECT = "申论"

SUBJECTS = {
    "行测": {
        "id": "xingce",
        "brand": "行测修仙传",
        "themes": ["修仙", "玄幻"],
        "default_theme": "修仙",
        "defaults_dir": "",          # defaults/ 根目录
        "vault_env": "XINGCE_VAULT",
        "features": {"bank": True, "idioms": True, "mock": True, "grading": False},
    },
    "申论": {
        "id": "shenlun",
        "brand": "申论官途",
        "themes": ["官场"],
        "default_theme": "官场",
        "defaults_dir": "申论",       # defaults/申论/
        "vault_env": "SHENLUN_VAULT",
        "features": {"bank": False, "idioms": False, "mock": False, "grading": True},
    },
}
NAMES = list(SUBJECTS)


def valid(name):
    return name in SUBJECTS


def get(name):
    return SUBJECTS[name if name in SUBJECTS else DEFAULT_SUBJECT]


def active():
    """当前科目名"""
    env = os.environ.get("SHENLUN_SUBJECT")
    if env in SUBJECTS:
        return env
    from .paths import load_settings
    s = load_settings().get("subject")
    return s if s in SUBJECTS else DEFAULT_SUBJECT


def feature(name, subject=None):
    return bool(get(subject or active())["features"].get(name))
