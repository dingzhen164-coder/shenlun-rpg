"""Mac 更新针对性回归：仅临时 App/ZIP/本机目录；shell 真替换与恢复，不启动用户应用。
准备阶段 mock 签名工具；Mac 原生 ditto 真跑；冻结应用启动另由发布 CI 检查。
"""
import hashlib
import io
import json
import os
import plistlib
import shlex
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from rpg import mac_update, update


def bundle(root, name="程序 空格'中文.app", version="9.9.9", executable="Run", body="#!/bin/sh\nexit 0\n", identity="test.rpg"):
    app = root / name
    exe = app / "Contents" / "MacOS" / executable
    exe.parent.mkdir(parents=True)
    exe.write_text(body)
    exe.chmod(0o755)
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
        "CFBundleExecutable": executable, "CFBundleIdentifier": identity, "CFBundleShortVersionString": version}))
    return app, exe


def zip_bundle(app, target):
    with zipfile.ZipFile(target, "w") as z:
        for p in app.rglob("*"):
            if p.is_file():
                z.write(p, str(p.relative_to(app.parent)))
    return target


class MacUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mac-update-test-")
        self.root = Path(self.tmp.name)
        self.app, self.exe = bundle(self.root, version="1.0.0")
        self.platform = patch.object(sys, "platform", "darwin")
        self.frozen = patch.object(update, "FROZEN", True)
        self.executable = patch.object(sys, "executable", str(self.exe))
        for p in (self.platform, self.frozen, self.executable): p.start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.tmp.cleanup)
        update._APPLY_PENDING = False
        self.addCleanup(setattr, update, "_APPLY_PENDING", False)

    def stage(self):
        return Path(tempfile.mkdtemp(prefix=".rpg-update-", dir=str(self.root)))

    def info(self, data=b"fake"):
        return dict(newer=True, latest="9.9.9", asset_url="https://example.test/mac.zip", size=len(data),
                    digest="sha256:" + hashlib.sha256(data).hexdigest(), page="https://example.test/release")

    def release(self, mac=True):
        assets = [{"name": "rpg.exe", "browser_download_url": "https://example/windows.exe", "size": 10},
                  {"name": "rpg.apk", "browser_download_url": "https://example/android.apk", "size": 20},
                  {"name": "other-mac.zip", "browser_download_url": "https://example/wrong.zip"}]
        if mac: assets += [{"name": update.MAC_ASSET, "browser_download_url": "https://example/mac.zip", "size": 30, "digest": "sha256:abc"}]
        return io.BytesIO(json.dumps({"tag_name": "v9.9.9", "assets": assets}).encode())

    def test_platform_asset_and_missing_mac(self):
        with patch.object(update.net, "urlopen", return_value=self.release()):
            r = update.check()
        self.assertEqual((r["asset_url"], r["size"], r["digest"]), ("https://example/mac.zip", 30, "sha256:abc"))
        self.assertTrue(r["can_apply"])
        self.assertEqual(r["apk_url"], "https://example/android.apk")
        with patch.object(update.net, "urlopen", return_value=self.release(mac=False)):
            r = update.check()
        self.assertFalse(r["can_apply"])
        self.assertEqual(r["asset_url"], "")
        with patch.object(sys, "platform", "win32"), patch.object(update.os, "name", "nt"), patch.object(update.net, "urlopen", return_value=self.release()):
            self.assertEqual(update.check()["asset_url"], "https://example/windows.exe")

    def test_source_and_translocated_or_readonly_app(self):
        with patch.object(update, "FROZEN", False):
            with self.assertRaises(update.UpdateError): update.apply()
        trans = self.root / "AppTranslocation"
        trans.mkdir()
        _, exe = bundle(trans)
        with patch.object(sys, "executable", str(exe)):
            with self.assertRaisesRegex(mac_update.MacUpdateError, "移到"): mac_update.writable_bundle()
        with patch.object(mac_update.os, "access", return_value=False), patch.object(update.net, "urlopen", return_value=self.release()):
            r = update.check()
        self.assertFalse(r["can_apply"])
        self.assertIn("不可写", r["update_reason"])

    def test_incomplete_download_never_exits_or_replaces(self):
        info = self.info(); info["size"] += 1
        self.assert_download_rejected(info, "下载不完整")

    def test_digest_mismatch_never_exits_or_replaces(self):
        info = self.info(); info["digest"] = "sha256:" + "0" * 64
        self.assert_download_rejected(info, "校验不通过")

    def test_network_failure_releases_lock_for_retry(self):
        with patch.object(update, "check", return_value=self.info()), patch.object(update.net, "urlopen", side_effect=OSError("离线")), patch.object(update.threading, "Timer") as timer:
            for _ in range(2):
                with self.assertRaisesRegex(update.UpdateError, "离线"): update.apply()
            timer.assert_not_called()
        self.assertFalse(update._APPLY_PENDING)
        self.assertFalse(list(self.root.glob(".rpg-update-*")))
        self.assertEqual(self.exe.read_text(), "#!/bin/sh\nexit 0\n")

    def assert_download_rejected(self, info, message):
        with patch.object(update, "check", return_value=info), patch.object(update.net, "urlopen", return_value=io.BytesIO(b"fake")), patch.object(mac_update, "launch") as launch, patch.object(update.threading, "Timer") as timer:
            with self.assertRaisesRegex(update.UpdateError, message): update.apply()
            launch.assert_not_called(); timer.assert_not_called()
        self.assertTrue(self.exe.is_file())
        self.assertFalse(list(self.root.glob(".rpg-update-*")))

    def test_success_handoff_and_duplicate_prevention(self):
        with patch.object(update, "check", return_value=self.info()), patch.object(update.net, "urlopen", return_value=io.BytesIO(b"fake")), patch.object(mac_update, "prepare", return_value=self.app), patch.object(mac_update, "launch") as launch, patch.object(update.threading, "Timer") as timer:
            r = update.apply()
            self.assertTrue(r["ok"])
            launch.assert_called_once()
            timer.return_value.start.assert_called_once()
            with self.assertRaisesRegex(update.UpdateError, "正在更新"): update.apply()
            self.assertEqual(launch.call_count, 1)
            env = launch.call_args[0][-1]
            self.assertEqual(env["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_concurrent_request_rejected(self):
        update._APPLY_LOCK.acquire()
        try:
            with self.assertRaisesRegex(update.UpdateError, "正在准备"): update.apply()
        finally: update._APPLY_LOCK.release()

    def test_zip_rejects_traversal_absolute_and_other_files(self):
        for entry in ("../outside", "/tmp/outside", "P.app/../outside", "installer.sh", "P.app\\outside"):
            p = self.root / "bad.zip"
            with zipfile.ZipFile(p, "w") as z: z.writestr(entry, b"bad")
            with self.assertRaises(mac_update.MacUpdateError): mac_update.validate_zip(p)
        p = self.root / "two.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("A.app/Contents/Info.plist", b"a"); z.writestr("B.app/Contents/Info.plist", b"b")
        with self.assertRaises(mac_update.MacUpdateError): mac_update.validate_zip(p)

    def test_zip_links_stay_inside_app(self):
        def archive(target, nested=False):
            p = self.root / "links.zip"
            i = zipfile.ZipInfo("P.app/Contents/Current")
            i.create_system = 3; i.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(i, target)
                z.writestr("P.app/Contents/Version/info", b"ok")
                if nested: z.writestr("P.app/Contents/Current/file", b"bad")
            return p
        self.assertEqual(mac_update.validate_zip(archive("Version")), "P.app")
        for target in ("../../../outside", "/tmp/outside"):
            with self.assertRaises(mac_update.MacUpdateError): mac_update.validate_zip(archive(target))
        with self.assertRaises(mac_update.MacUpdateError): mac_update.validate_zip(archive("Version", nested=True))

    @unittest.skipUnless(Path("/usr/bin/ditto").is_file(), "Mac 原生解压工具")
    def test_real_extract_preserves_permissions_and_checks_identity_version_signature(self):
        source = self.root / "source"; source.mkdir()
        new, _ = bundle(source)
        archive = zip_bundle(new, self.root / "new.zip")
        original_run = subprocess.run
        def tools(args, **kwargs):
            if args[0] == "/usr/bin/codesign": return subprocess.CompletedProcess(args, 0)
            return original_run(args, **kwargs)
        with patch.object(mac_update.subprocess, "run", side_effect=tools):
            extracted = mac_update.prepare(self.stage(), archive, self.app, "9.9.9")
            self.assertTrue(os.access(str(extracted / "Contents/MacOS/Run"), os.X_OK))
            with self.assertRaisesRegex(mac_update.MacUpdateError, "版本"): mac_update.prepare(self.stage(), archive, self.app, "8.0.0")
            with (new / "Contents/Info.plist").open("wb") as f:
                plistlib.dump({"CFBundleExecutable": "Run", "CFBundleIdentifier": "wrong", "CFBundleShortVersionString": "9.9.9"}, f)
            zip_bundle(new, archive)
            with self.assertRaisesRegex(mac_update.MacUpdateError, "不属于"): mac_update.prepare(self.stage(), archive, self.app, "9.9.9")
        zip_bundle(bundle(self.root / "signed")[0], archive)
        def bad_sign(args, **kwargs):
            if args[0] == "/usr/bin/codesign": raise subprocess.CalledProcessError(1, args)
            return original_run(args, **kwargs)
        with patch.object(mac_update.subprocess, "run", side_effect=bad_sign):
            with self.assertRaisesRegex(mac_update.MacUpdateError, "校验失败"): mac_update.prepare(self.stage(), archive, self.app, "9.9.9")
        self.assertTrue(self.exe.is_file())

    def test_startup_receipt_only_in_current_update_directory(self):
        stage = self.stage(); receipt = stage / "ready"
        with patch.dict(os.environ, {"RPG_UPDATE_READY_FILE": str(receipt)}): mac_update.confirm_startup()
        self.assertEqual(receipt.read_text(), str(os.getpid()))
        other = self.root / "settings.json"
        with patch.dict(os.environ, {"RPG_UPDATE_READY_FILE": str(other)}): mac_update.confirm_startup()
        self.assertFalse(other.exists())

    def test_native_window_loaded_confirms_startup(self):
        import app, server
        from types import SimpleNamespace
        class Loaded:
            handlers = None
            def __init__(self): self.handlers = []
            def __iadd__(self, fn): self.handlers.append(fn); return self
        loaded = Loaded()
        win = SimpleNamespace(events=SimpleNamespace(loaded=loaded))
        view = SimpleNamespace(create_window=lambda *a, **k: win, start=lambda **k: [fn() for fn in loaded.handlers])
        with patch.dict(sys.modules, {"webview": view}), patch.object(server, "prepare"), patch.object(server, "start_server", return_value=(SimpleNamespace(serve_forever=lambda: None), "http://127.0.0.1:1/")), patch.object(app.threading, "Thread"), patch.object(app.webbrowser, "open") as browser, patch.object(app.os, "_exit", side_effect=SystemExit), patch.object(mac_update, "confirm_startup") as confirm:
            with self.assertRaises(SystemExit): app.main()
            confirm.assert_called_once()
            browser.assert_not_called()
        self.assertEqual(len(loaded.handlers), 1)

    @unittest.skipUnless(os.name == "posix", "真跑独立 shell 更新助手")
    def test_real_swap_and_failed_start_rollback(self):
        # 引号、空格、中文路径真跑；启动脚本只写临时回执，不打开实际应用。
        for success in (True, False):
            stage = self.stage(); ready_pid = self.root / ("new.pid" if success else "old.pid")
            old_body = "#!/bin/sh\nprintf '%s' $$ > %s\nsleep 3\n" % ("%s", shlex.quote(str(ready_pid)))
            self.exe.write_text(old_body); self.exe.chmod(0o755)
            body = ("#!/bin/sh\nprintf '%s' $$ > %s\nprintf ready > \"$RPG_UPDATE_READY_FILE\"\nsleep 3\n" % ("%s", shlex.quote(str(ready_pid)))) if success else "#!/bin/sh\nexit 1\n"
            new, _ = bundle(stage, body=body)
            # pid 已被回收后助手可立即换文件；不会终止测试自身。
            previous = subprocess.Popen(["/bin/sh", "-c", "exit 0"]); previous.wait()
            helper = mac_update.launch(previous.pid, new, self.app, stage, update.clean_env())
            code = helper.wait(timeout=12)
            self.assertEqual(code, 0 if success else 1)
            self.assertEqual(self.exe.read_text(), body if success else old_body)
            if success: self.assertFalse(stage.exists())
            else:
                self.assertTrue((stage / "error.txt").is_file())
                self.assertTrue((stage / "failed.app").is_dir())
                self.assertFalse((stage / "previous.app").exists())
            # 只结束夹具进程，避免后台 sleep 残留。
            import time
            for _ in range(50):
                if ready_pid.exists(): break
                time.sleep(.02)
            if ready_pid.exists():
                try: os.kill(int(ready_pid.read_text()), 15)
                except ProcessLookupError: pass
            self.assertTrue(self.app.is_dir())


if __name__ == "__main__": unittest.main()
