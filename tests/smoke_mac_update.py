"""发布 CI：冻结 Mac App 内运行，仅临时副本与假 HOME；真签名/解压/替换/重启。
调用：MacOS/<程序> --run-script tests/smoke_mac_update.py <发布 ZIP>
新副本以 --run-script 写启动回执，避免 CI 打开真实窗口/库；loaded 绑定由单元测试验证。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform != "darwin" or not getattr(sys, "frozen", False):
    raise RuntimeError("必须在冻结 Mac App 内检查")
archive = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="mac-frozen-update-") as tmp:
    root = Path(tmp)
    home = root / "home"; home.mkdir()
    Path.home = classmethod(lambda cls: home)
    from rpg import mac_update, update
    from rpg.version import VERSION
    source = mac_update.app_bundle()
    old = root / "副本 空格'中文.app"
    subprocess.run(["/usr/bin/ditto", str(source), str(old)], check=True)
    stage = Path(tempfile.mkdtemp(prefix=".rpg-update-", dir=str(root)))
    incoming = mac_update.prepare(stage, archive, old, VERSION)
    ready = root / "ready_script.py"
    pidfile = root / "started.pid"
    ready.write_text("from pathlib import Path\nimport os,time\n"
                     "Path.home=classmethod(lambda cls: Path(%r))\n" % str(home)
                     + "from rpg.mac_update import confirm_startup\nconfirm_startup()\n"
                     + "Path(%r).write_text(str(os.getpid()))\ntime.sleep(8)\n" % str(pidfile), encoding="utf-8")
    handoff = root / "handoff.py"
    handoff.write_text("from pathlib import Path\nimport os\n"
                       "Path.home=classmethod(lambda cls: Path(%r))\n" % str(home)
                       + "from rpg import mac_update,update\n"
                       + "mac_update.launch(os.getpid(),Path(%r),Path(%r),Path(%r),update.clean_env(),"
                       "args=('--run-script',%r))\nprint('MAC-HANDOFF')\n" % (str(incoming), str(old), str(stage), str(ready)), encoding="utf-8")
    _, exe = mac_update.read_info(old)
    env = update.clean_env()
    out = subprocess.check_output([str(exe), "--run-script", str(handoff)], env=env, timeout=30).decode("utf-8")
    if "MAC-HANDOFF" not in out: raise RuntimeError(out)
    import time
    for _ in range(200):
        if not stage.exists() and pidfile.exists(): break
        if (stage / "error.txt").exists(): raise RuntimeError((stage / "error.txt").read_text())
        time.sleep(.1)
    if stage.exists() or not pidfile.exists(): raise RuntimeError("替换或冻结重启未完成")
    try: os.kill(int(pidfile.read_text()), 15)
    except ProcessLookupError: pass
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(old)], check=True)
    print("MAC-UPDATE-FROZEN-OK：签名、真实替换、清理和冻结程序重新启动")
