"""检查正式 Release 与桌面一键更新（Windows exe / Mac App）。

rpg.api 的本机接口调用 check/apply；Windows 交给 PowerShell，Mac 交给
mac_update 的独立助手替换并确认重启。源码版仍手工更新；日常开发不触发发布。
"""
import hashlib
import json
import shutil
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from . import mac_update, net
from .paths import FROZEN
from .version import REPO, VERSION

MAC_ASSET = 'gongkao-simulator-mac.zip'

API = "https://api.github.com/repos/%s/releases/latest" % REPO


class UpdateError(Exception):
    pass


def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", str(s or ""))[:4]) or (0,)


def _notes(body):
    """更新说明：只留改了什么（去掉提交署名行）"""
    lines = [ln for ln in (body or "").replace("\r\n", "\n").split("\n") if not re.match(r"\s*(Co-Authored-By|Claude-Session):", ln)]
    return "\n".join(lines).strip()[:2000]


def check():
    req = urllib.request.Request(API, headers={"User-Agent": "shenlun-rpg", "Accept": "application/vnd.github+json"})
    try:
        with net.urlopen(req, timeout=15) as r:
            rel = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:       # 还没发布过 Release
            return {"current": VERSION, "latest": "", "newer": False, "frozen": FROZEN, "notes": "", "asset_url": "", "size": 0,
                    "page": "https://github.com/%s/releases" % REPO, "windows": os.name == "nt"}
        raise UpdateError("GitHub 回应 %s。也可以直接打开 https://github.com/%s/releases 下载" % (e.code, REPO))
    except Exception as e:
        raise UpdateError("连不上 GitHub（%s）。也可以直接打开 https://github.com/%s/releases 下载" % (e, REPO))
    tag = rel.get("tag_name") or ""
    assets = rel.get("assets", [])
    windows = next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None)
    mac = next((a for a in assets if a.get("name") == MAC_ASSET), None)
    apk = next((a for a in assets if a.get("name", "").lower().endswith(".apk")), None)
    asset = mac if sys.platform == "darwin" else windows
    reason = ""
    supported = FROZEN and (os.name == "nt" or sys.platform == "darwin")
    if supported and sys.platform == "darwin":
        try:
            mac_update.writable_bundle()
        except mac_update.MacUpdateError as e:
            supported, reason = False, str(e)
    return {"current": VERSION, "latest": tag.lstrip("v"), "newer": _ver(tag) > _ver(VERSION), "frozen": FROZEN,
            "notes": _notes(rel.get("body")), "page": rel.get("html_url") or "https://github.com/%s/releases" % REPO,
            "asset_url": asset.get("browser_download_url") if asset else "", "size": asset.get("size") if asset else 0,
            "digest": asset.get("digest") if asset else "",
            "apk_url": apk.get("browser_download_url") if apk else "", "apk_size": apk.get("size") if apk else 0,
            "windows": os.name == "nt", "macos": sys.platform == "darwin",
            "can_apply": bool(supported and asset and asset.get("browser_download_url")), "update_reason": reason}


def swap_script(pid, new, exe):
    """等进程 pid 退出 → 用 new 换掉 exe（占用中就重试）→ 启动 exe。换不成也照样把程序打开（还是旧版，不至于“消失”）"""
    q = lambda p: "'" + str(p).replace("'", "''") + "'"
    return "\r\n".join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        "Wait-Process -Id %d -Timeout 60" % pid,
        "for ($i = 0; $i -lt 60; $i++) {",
        "  try { Move-Item -LiteralPath %s -Destination %s -Force -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 500 }" % (q(new), q(exe)),
        "}",
        "Start-Process -FilePath %s -WorkingDirectory %s" % (q(exe), q(Path(exe).parent)),
        "Remove-Item -LiteralPath $PSCommandPath",
        ""])


def clean_env(env=None):
    """给“换文件再重开”的脚本用的环境：去掉 PyInstaller 留给自己子进程的变量（_PYI_*、_MEIPASS2），
    不然新 exe 会以为自己是旧 exe 的子进程，去已经删掉的旧临时目录（_MEIxxxx）找 python312.dll，报 Failed to load Python DLL"""
    env = dict(os.environ if env is None else env)
    for k in list(env):
        if k.upper().startswith("_PYI_") or k.upper().startswith("_MEIPASS"):
            env.pop(k)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"      # PyInstaller 6.9+：当成全新启动
    return env


def launch_swap(pid, new, exe):
    """后台起一个看不见窗口的 PowerShell 去换文件（不用批处理：脱离控制台时 find / tasklist 会弹黑框卡住）"""
    fd, ps1 = tempfile.mkstemp(prefix="shenlun-rpg-update-", suffix=".ps1")
    os.close(fd)
    Path(ps1).write_text(swap_script(pid, new, exe), encoding="utf-8-sig", newline="")    # 带 BOM，中文路径不乱码
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", ps1],
                            creationflags=flags, close_fds=True, env=clean_env(),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _apply_mac(info):
    stage = None
    try:
        app = mac_update.writable_bundle()
        stage = Path(tempfile.mkdtemp(prefix=".rpg-update-", dir=str(app.parent)))
        archive = stage / "download.zip"
        req = urllib.request.Request(info["asset_url"], headers={"User-Agent": REPO.split("/")[-1]})
        digest = hashlib.sha256()
        with net.urlopen(req, timeout=60) as r, archive.open("wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                digest.update(chunk)
        if info.get("size") and archive.stat().st_size != info["size"]:
            raise UpdateError("下载不完整，再试一次；旧应用未改动")
        expected = info.get("digest") or ""
        if expected.startswith("sha256:") and digest.hexdigest() != expected[7:]:
            raise UpdateError("下载校验不通过，再试一次；旧应用未改动")
        new = mac_update.prepare(stage, archive, app, info["latest"])
        mac_update.launch(os.getpid(), new, app, stage, clean_env())
    except Exception as e:
        if stage is not None:
            shutil.rmtree(str(stage), ignore_errors=True)
        if isinstance(e, UpdateError):
            raise
        raise UpdateError("Mac 更新准备失败（%s）；旧应用未改动" % e)
    threading.Timer(1.5, lambda: os._exit(0)).start()
    return {"ok": True, "version": info["latest"]}


_APPLY_LOCK = threading.Lock()
_APPLY_PENDING = False


def apply():
    """防止重复下载和并发替换；成功交给独立助手后等待退出。"""
    global _APPLY_PENDING
    if not _APPLY_LOCK.acquire(blocking=False):
        raise UpdateError("正在准备更新，请稍候")
    try:
        if _APPLY_PENDING:
            raise UpdateError("正在更新并重启，请稍候")
        result = _apply()
        _APPLY_PENDING = True
        return result
    finally:
        _APPLY_LOCK.release()


def _apply():
    """下载平台对应安装包，验证后交给独立进程替换并重启。"""
    if not (FROZEN and (os.name == "nt" or sys.platform == "darwin")):
        raise UpdateError("自动更新支持 Windows exe 和 Mac App；源码版请照旧下载压缩包更新")
    info = check()
    if not info["newer"]:
        raise UpdateError("已经是最新版（%s）" % VERSION)
    if not info["asset_url"]:
        raise UpdateError("新版本还在打包，过几分钟再试")
    if sys.platform == "darwin":
        return _apply_mac(info)
    exe = Path(sys.executable).resolve()
    new = exe.with_name(exe.stem + ".new.exe")
    req = urllib.request.Request(info["asset_url"], headers={"User-Agent": "shenlun-rpg"})
    try:
        with net.urlopen(req, timeout=60) as r, open(new, "wb") as f:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        try:
            new.unlink()
        except OSError:
            pass
        raise UpdateError("下载新版本失败（%s）。可以打开 %s 手动下载，换掉旧的 exe" % (e, info["page"]))
    if info["size"] and new.stat().st_size != info["size"]:
        new.unlink()
        raise UpdateError("下载不完整，再试一次")
    launch_swap(os.getpid(), new, exe)
    threading.Timer(1.5, lambda: os._exit(0)).start()      # 先把回应发给网页，再退出让脚本换文件
    return {"ok": True, "version": info["latest"]}
