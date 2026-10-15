"""两仓库（fakao-rpg、shenlun-rpg）共用文件的转移与防漂移检查。只用标准库，两份内容相同。

规则（用户2026-10-15定）：新功能先在主仓库shenlun-rpg（行测+申论）开发并验证；一个功能批次完成后，
把共用文件转到fakao-rpg，再只跑法考自己的布局检查与相关交互测试。哪些文件算“共用”写在tools/shared_files.txt。

清单格式（每行一条，#开头为注释）：
  shared   <路径或通配>   两边必须逐字节相同（如web/tokens.css、web/ds.css、纪事/地点牌/状态牌的CSS与JS）
  diverged <路径或通配>   两边有意不同（如style.css的主题变量、各科引擎文件），改一边时人工判断另一边要不要跟

用法（在任一仓库根目录，兄弟目录里要有另一个仓库）：
  python3 tools/sync_shared.py                  报告：共用文件待转移、未声明文件、可升级为shared的文件（退出码0）
  python3 tools/sync_shared.py --strict         同上，但共用文件不一致或有未声明文件时退出码1（统一发布前用）
  python3 tools/sync_shared.py --pull           把另一仓库里“内容不同”的共用文件复制进本仓库（转移功能批次时用）
  python3 tools/sync_shared.py --other 路径     指定另一仓库位置
转移后请用git diff核对，再按“转移后只跑本仓库自己的布局检查与相关交互测试”的约定验证。"""
import argparse
import fnmatch
import os
import shutil
import subprocess
import sys

SCAN_DIRS = ("web", "rpg", "tests", "tools", "defaults")
SKIP_DIRS = {"__pycache__", "node_modules", ".git"}
SKIP_FILES = {".DS_Store"}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join("tools", "shared_files.txt")


def read_manifest(root):
    shared, diverged = [], []
    path = os.path.join(root, MANIFEST)
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kind, _, pattern = line.partition(" ")
            if kind not in ("shared", "diverged") or not pattern.strip():
                raise SystemExit("%s 第%d行格式不对：%s" % (MANIFEST, n, line))
            (shared if kind == "shared" else diverged).append(pattern.strip())
    return shared, diverged


def scan(root):
    out = set()
    for d in SCAN_DIRS:
        for dp, dn, fn in os.walk(os.path.join(root, d)):
            dn[:] = [x for x in dn if x not in SKIP_DIRS]
            for f in fn:
                if f in SKIP_FILES or f.endswith(".pyc"):
                    continue
                out.add(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return out


def match(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def same(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def last_commit_time(root, rel):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel], cwd=root, capture_output=True, text=True).stdout.strip()
        return int(out) if out else 0
    except Exception:
        return 0


def default_other():
    name = os.path.basename(HERE)
    mate = {"fakao-rpg": "shenlun-rpg", "shenlun-rpg": "fakao-rpg"}.get(name)
    return os.path.join(os.path.dirname(HERE), mate) if mate else None


def main():
    ap = argparse.ArgumentParser(description="共用文件转移与防漂移检查")
    ap.add_argument("--other", default=default_other(), help="另一个仓库的路径")
    ap.add_argument("--strict", action="store_true", help="共用文件不一致或有未声明文件时退出码1")
    ap.add_argument("--pull", action="store_true", help="把另一仓库里内容不同的共用文件复制进本仓库")
    args = ap.parse_args()
    if not args.other or not os.path.isdir(args.other):
        raise SystemExit("找不到另一个仓库，请用 --other 指定路径")
    shared, diverged = read_manifest(HERE)
    here, there = scan(HERE), scan(args.other)
    both = sorted(here & there)
    pending, missing, undeclared_same, undeclared_diff, upgradable = [], [], [], [], []
    for rel in sorted(p for p in (here | there) if match(p, shared)):
        a, b = os.path.join(HERE, rel), os.path.join(args.other, rel)
        if rel not in here or rel not in there:
            missing.append((rel, "本仓库缺" if rel not in here else "另一仓库缺"))
        elif not same(a, b):
            pending.append(rel)
    for rel in both:
        if match(rel, shared):
            continue
        same_now = same(os.path.join(HERE, rel), os.path.join(args.other, rel))
        if match(rel, diverged):
            if same_now:
                upgradable.append(rel)
        else:
            (undeclared_same if same_now else undeclared_diff).append(rel)

    name_here, name_there = os.path.basename(HERE), os.path.basename(args.other)
    if args.pull:
        copied = []
        for rel in pending + [m[0] for m in missing if m[1] == "本仓库缺"]:
            src, dst = os.path.join(args.other, rel), os.path.join(HERE, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)
        print("已从 %s 复制 %d 个共用文件到 %s：" % (name_there, len(copied), name_here))
        for rel in copied:
            print("  ", rel)
        print("请用 git diff 核对后再提交，并只跑本仓库自己的布局检查与相关交互测试。")
        return 0

    print("共用文件 %d 条规则；本仓库 %s，对照 %s" % (len(shared), name_here, name_there))
    if pending:
        print("\n待转移（内容不同，较新的一侧用提交时间判断）：")
        for rel in pending:
            ta, tb = last_commit_time(HERE, rel), last_commit_time(args.other, rel)
            side = name_here if ta > tb else name_there if tb > ta else "时间相同（可能是未提交改动）"
            print("   %s    较新：%s" % (rel, side))
    if missing:
        print("\n共用文件缺失：")
        for rel, why in missing:
            print("   %s（%s）" % (rel, why))
    if undeclared_same:
        print("\n未声明但两边相同，建议加入 shared：")
        for rel in undeclared_same:
            print("   ", rel)
    if undeclared_diff:
        print("\n未声明且两边不同，请在清单里归入 shared（需转移）或 diverged（有意不同）：")
        for rel in undeclared_diff:
            print("   ", rel)
    if upgradable:
        print("\n已声明 diverged 但现在两边相同，可考虑升级为 shared：")
        for rel in upgradable:
            print("   ", rel)
    clean = not (pending or missing or undeclared_same or undeclared_diff)
    if clean:
        print("\n共用文件一致，无未声明文件。")
    if args.strict and not clean:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
