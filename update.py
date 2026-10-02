#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键更新：从 GitHub 下载最新代码，覆盖程序文件。你的数据不受影响。

    python update.py            # 更新（Windows 双击 更新.bat）
    python update.py --check    # 只看有没有新版本，不覆盖

只覆盖程序自己的文件（core/ subjects/ web/ tests/ 与根目录的程序、脚本、说明）；
data/ 文件夹、你设置里指定的申论库（里面的“训练”文件夹）、~/.shenlun-rpg 都不会碰。
更新源默认是下面的 DEFAULT_URL；以后项目合并进 main，可在本目录建一个 更新源.txt，里面写新的 zip 地址。
只用 Python 标准库。
"""
import io
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_URL = "https://github.com/dingzhen164-coder/shenlun-rpg/archive/refs/heads/claude/dazzling-fermat-0n9kbc.zip"
APP = Path(__file__).resolve().parent
DIRS = ["core", "subjects", "web", "tests", "defaults"]
FILES = ["server.py", "update.py", "VERSION", "README.md", "DESIGN.md", "AGENTS.md", ".gitignore", ".gitattributes"]
GLOBS = ["*.bat", "*.command"]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def source_url():
    f = APP / "更新源.txt"
    if f.exists() and f.read_text(encoding="utf-8").strip():
        return f.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return DEFAULT_URL


def current_version():
    try:
        return (APP / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "未知"


def download(url):
    print("正在下载：%s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": "shenlun-rpg-updater"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    check_only = "--check" in sys.argv
    try:
        data = download(source_url())
    except Exception as e:  # noqa: BLE001
        print("下载失败：%s\n请检查网络；或者手动到 GitHub 下载 zip 覆盖到本文件夹。" % e)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(io.BytesIO(data)).extractall(tmp)
        roots = [p for p in Path(tmp).iterdir() if p.is_dir()]
        if len(roots) != 1:
            print("压缩包结构不对，已放弃更新。")
            return 1
        src = roots[0]
        new_v = (src / "VERSION").read_text(encoding="utf-8").strip() if (src / "VERSION").exists() else "未知"
        print("当前版本 %s → 最新版本 %s" % (current_version(), new_v))
        if check_only:
            print("（只检查，没有改动）")
            return 0
        n = 0
        for d in DIRS:
            if (src / d).is_dir():
                if (APP / d).exists():
                    shutil.rmtree(str(APP / d))
                shutil.copytree(str(src / d), str(APP / d))
                n += 1
        for f in FILES:
            if (src / f).exists():
                shutil.copy2(str(src / f), str(APP / f))
                n += 1
        for g in GLOBS:
            for f in src.glob(g):
                shutil.copy2(str(f), str(APP / f.name))
                n += 1
    print("更新完成（%d 项）。请关闭程序后重新双击“启动”。你的数据没有被改动。" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
