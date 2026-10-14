"""Mac App 更新：rpg.update 下载 ZIP 后调用 prepare/launch，app.main 确认启动。

临时目录位于当前 App 同级，内含下载包、解压 App、旧 App 备份及启动回执；
后台 shell 等旧进程退出后替换，45 秒内未收到启动回执则恢复旧 App。
只替换程序目录，不读取或修改用户库、存档和本机设置。
"""
import os
import plistlib
import posixpath
import shlex
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath


class MacUpdateError(Exception):
    pass


def app_bundle(executable=None):
    exe = Path(executable or sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix.lower() == ".app" and exe.parent == parent / "Contents" / "MacOS":
            return parent
    raise MacUpdateError("没有找到完整的 Mac App；请先安装正式 Mac 安装包")


def writable_bundle():
    app = app_bundle()
    if "AppTranslocation" in app.parts or str(app).startswith("/Volumes/"):
        raise MacUpdateError("请先退出并把 App 移到“应用程序”或自己的应用文件夹，再打开更新")
    if not os.access(str(app.parent), os.W_OK | os.X_OK):
        raise MacUpdateError("当前应用文件夹不可写；请把 App 移到自己的应用文件夹后再更新")
    return app


def read_info(app):
    try:
        with (app / "Contents" / "Info.plist").open("rb") as f:
            info = plistlib.load(f)
        name = info["CFBundleExecutable"]
        if not isinstance(name, str) or not name or "/" in name or name in (".", ".."):
            raise ValueError("程序名称不正确")
        exe = app / "Contents" / "MacOS" / name
        if not exe.is_file() or not os.access(str(exe), os.X_OK):
            raise ValueError("缺少可运行的程序")
        return info, exe
    except Exception as e:
        raise MacUpdateError("Mac 安装包不完整（%s）" % e)


def validate_zip(archive):
    """解压前检查路径与符号链接，允许 PyInstaller 包内链接，拒绝写出临时目录。"""
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        roots = set()
        links = set()
        for item in members:
            raw = item.orig_filename  # Windows zipfile会改写反斜杠，按原始名称校验。
            p = PurePosixPath(raw)
            if p.is_absolute() or ".." in p.parts or "\\" in raw or "\x00" in raw or not p.parts:
                raise MacUpdateError("安装包包含不安全的路径")
            root = p.parts[0]
            if root != "__MACOSX":
                if not root.endswith(".app"):
                    raise MacUpdateError("安装包不是完整的 Mac App")
                roots.add(root)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                target = z.read(item).decode("utf-8")
                resolved = posixpath.normpath(posixpath.join(str(p.parent), target))
                if root == "__MACOSX" or target.startswith("/") or resolved.split("/")[0] != root:
                    raise MacUpdateError("安装包中的链接指向应用外部")
                links.add(str(p))
            elif stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise MacUpdateError("安装包包含不支持的文件类型")
        if len(roots) != 1:
            raise MacUpdateError("安装包必须只包含一个 Mac App")
        for item in members:
            if any(str(p) in links for p in PurePosixPath(item.filename).parents):
                raise MacUpdateError("安装包不能通过链接写入其他位置")
        return roots.pop()


def prepare(stage, archive, app, version):
    """保持执行权限/框架链接地解压，并核对应用身份、版本、签名。旧 App 尚未改动。"""
    validate_zip(archive)
    extracted = stage / "unpacked"
    extracted.mkdir()
    try:
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(extracted)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        # ditto 的中文ZIP文件名可能未设UTF-8标记，zipfile会误解码。
        # 安全路径检查已完成；使用ditto实际解出的唯一App，不靠猜文件名。
        bundles = list(extracted.glob("*.app"))
        if len(bundles) != 1 or bundles[0].is_symlink() or not bundles[0].is_dir():
            raise MacUpdateError("解压后没有找到唯一的完整 Mac App")
        new = bundles[0]
        for p in new.rglob("*"):
            if p.is_symlink():
                try:
                    p.resolve().relative_to(new.resolve())
                except (ValueError, RuntimeError):
                    raise MacUpdateError("安装包中的链接指向应用外部")
        old_info, _ = read_info(app)
        info, _ = read_info(new)
        identity = old_info.get("CFBundleIdentifier")
        if not identity or info.get("CFBundleIdentifier") != identity:
            raise MacUpdateError("下载的安装包不属于当前应用")
        if info.get("CFBundleShortVersionString") != version:
            raise MacUpdateError("安装包版本与发布版本不一致")
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(new)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return new
    except (OSError, subprocess.SubprocessError, zipfile.BadZipFile) as e:
        raise MacUpdateError("Mac 安装包校验失败（%s）；旧应用未改动" % e)


def swap_script(pid, new, app, stage, args=()):
    """独立 shell 脚本：旧程序退出 → 备份/替换 → 启动确认；失败恢复备份。"""
    _, exe = read_info(new)
    _, old_exe = read_info(app)
    q = shlex.quote
    variables = {"target": app, "incoming": new, "stage": stage,
                 "backup": stage / "previous.app", "ready": stage / "ready",
                 "exe": app / exe.relative_to(new), "old_exe": old_exe,
                 "failed": stage / "failed.app"}
    script = ["#!/bin/sh", "umask 077"]
    script += [key + "=" + q(str(value)) for key, value in variables.items()]
    script += [
        "i=0", "while /bin/kill -0 %d 2>/dev/null; do" % int(pid),
        "  i=$((i+1)); if [ \"$i\" -ge 60 ]; then exit 1; fi", "  /bin/sleep 1", "done",
        'cd / || exit 1',
        'if ! /bin/mv "$target" "$backup"; then printf "备份旧应用失败\\n" > "$stage/error.txt"; "$old_exe" >/dev/null 2>&1 & exit 1; fi',
        'restore() {',
        '  if [ -e "$target" ]; then /bin/mv "$target" "$failed" || return 1; fi',
        '  /bin/mv "$backup" "$target" || return 1',
        '  unset RPG_UPDATE_READY_FILE',
        '  "$old_exe" > "$stage/rollback.log" 2>&1 &',
        '}',
        'if ! /bin/mv "$incoming" "$target"; then printf "替换失败，恢复旧应用\\n" > "$stage/error.txt"; restore; exit 1; fi',
        'RPG_UPDATE_READY_FILE="$ready" "$exe" '+ ' '.join(q(str(arg)) for arg in args) + ' > "$stage/startup.log" 2>&1 &',
        'child=$!', 'i=0',
        'while [ "$i" -lt 45 ]; do',
        '  if [ -s "$ready" ] && /bin/kill -0 "$child" 2>/dev/null; then /bin/rm -rf "$stage"; exit 0; fi',
        '  /bin/kill -0 "$child" 2>/dev/null || break',
        '  /bin/sleep 1; i=$((i+1))', 'done',
        '/bin/kill "$child" 2>/dev/null || true',
        'wait "$child" 2>/dev/null || true',
        'printf "新应用未确认启动，已尝试恢复旧应用\\n" > "$stage/error.txt"',
        'restore', 'exit 1', '']
    return "\n".join(script)


def launch(pid, new, app, stage, env, args=()):
    helper = stage / "replace.sh"
    helper.write_text(swap_script(pid, new, app, stage, args=args), encoding="utf-8")
    return subprocess.Popen(["/bin/sh", str(helper)], cwd="/", env=env, start_new_session=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def confirm_startup():
    """仅写当前 App 同级更新目录的回执；app.main 在窗口加载或浏览器打开后调用。"""
    receipt = os.environ.pop("RPG_UPDATE_READY_FILE", "")
    if not receipt:
        return
    try:
        app = app_bundle()
        p = Path(receipt)
        if (p.name == "ready" and p.parent.name.startswith(".rpg-update-")
                and p.parent.resolve().parent == app.parent and p.parent.is_dir()):
            p.write_text(str(os.getpid()), encoding="ascii")
    except (OSError, MacUpdateError):
        pass
