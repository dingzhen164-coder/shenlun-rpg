"""
路径：找 Obsidian 申论库（vault）、训练文件夹、本机设置。

约定：
    <库>/训练/                      本程序的数据（规则、题库、采分点、存档……），随库同步
    ~/.shenlun-rpg/settings.json    本机设置（API key、库路径），不同步、不进仓库

库的查找顺序：环境变量 SHENLUN_VAULT → 设置里的 vault → 程序放在 <库>/训练/程序/ 时自动取上上级 → 都没有则用程序目录下的 data/（开发和试用；已在 .gitignore）。
谁调用：server.py、core/store.py、core/ai.py。
"""
import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DEFAULTS_DIR = APP_DIR / "defaults"
SETTINGS_DIR = Path.home() / ".shenlun-rpg"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
TRAIN_REL = Path("训练")


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    cur = load_settings()
    cur.update(data)
    SETTINGS_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")


def find_vault():
    env = os.environ.get("SHENLUN_VAULT")
    if env and Path(env).is_dir():
        return Path(env)
    v = load_settings().get("vault")
    if v and Path(v).is_dir():
        return Path(v)
    if APP_DIR.name == "程序" and APP_DIR.parent.name == TRAIN_REL.name:  # <库>/训练/程序/
        return APP_DIR.parent.parent
    dev = APP_DIR / "data"
    dev.mkdir(exist_ok=True)
    return dev


class Paths:
    def __init__(self, vault):
        self.vault = Path(vault)
        self.train = self.vault / TRAIN_REL
        self.save_dir = self.train / "存档"
        self.save_file = self.save_dir / "存档.json"
        self.bank_dir = self.train / "题库"
        self.rubric_dir = self.train / "采分点"
        self.skeleton_dir = self.train / "方法骨架"

    def ensure_train_dir(self):
        """建 训练/ 及子文件夹（只建缺的，不覆盖用户文件）"""
        for d in (self.save_dir, self.bank_dir, self.rubric_dir, self.skeleton_dir):
            d.mkdir(parents=True, exist_ok=True)
        return []
