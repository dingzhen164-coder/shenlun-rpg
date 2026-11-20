"""桌面更新断点续传回归：验证 Mac/Windows 更新失败保留缓存、再次点击续传以及多次断连单次下完。"""
import hashlib
import io
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rpg import download, mac_update, paths, update


class _Resp(io.BytesIO):
    def __init__(self, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class UpdateResumeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="update-resume-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.settings_dir = self.root / ".settings"
        self.app = self.root / "公考模拟器.app"
        self.exe = self.app / "Contents/MacOS/Run"
        self.exe.parent.mkdir(parents=True)
        self.exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.exe.chmod(0o755)
        (self.app / "Contents/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleExecutable": "Run", "CFBundleIdentifier": "test.rpg", "CFBundleShortVersionString": "4.3.0",
        }))
        self.data = b"0123456789abcdefghij"
        self.info = dict(
            newer=True, latest="4.3.1", asset_url="https://example.test/mac.zip",
            size=len(self.data), digest="sha256:" + hashlib.sha256(self.data).hexdigest(),
            page="https://example.test/release",
        )
        for p in (
            patch.object(paths, "SETTINGS_DIR", self.settings_dir),
            patch.object(sys, "platform", "darwin"),
            patch.object(update, "FROZEN", True),
            patch.object(sys, "executable", str(self.exe)),
            patch.object(download, "RETRY_DELAY", 0),
        ):
            p.start()
            self.addCleanup(p.stop)
        update._APPLY_PENDING = False
        self.addCleanup(setattr, update, "_APPLY_PENDING", False)

    def test_mac_update_preserves_partial_cache_across_calls_and_resumes(self):
        # 预放一个旧版本缓存，验证会被自动清理
        cache_dir = self.root / ".rpg-dl-cache"
        cache_dir.mkdir(parents=True)
        stale = cache_dir / "v4.2.0-old-mac.zip"
        stale.write_bytes(b"stale")

        # 第一次：故意只给 2 次重试，下到前 8 字节后失败
        first_resps = [
            _Resp(self.data[:5], 200, {"Content-Length": str(len(self.data))}),
            _Resp(self.data[5:8], 206, {"Content-Range": "bytes 5-19/20"}),
        ]
        with patch.object(update, "DOWNLOAD_ATTEMPTS", 2), \
             patch.object(update, "check", return_value=self.info), \
             patch.object(download.net, "urlopen", side_effect=first_resps), \
             patch.object(update.threading, "Timer") as timer:
            with self.assertRaisesRegex(update.UpdateError, "已收到8字节，应收20字节"):
                update.apply()
            timer.assert_not_called()

        self.assertFalse(stale.exists(), "旧版本缓存应被清理")
        self.assertFalse(list(self.root.glob(".rpg-update-*")), "失败后应清理 .rpg-update-* 临时 stage 目录")
        cached_files = list(cache_dir.glob("v4.3.1-*-mac.zip"))
        self.assertEqual(len(cached_files), 1)
        self.assertEqual(cached_files[0].read_bytes(), self.data[:8], "失败后应保留已下载的 8 字节缓存")

        # 第二次：直接从第 8 字节续传，完整下完并进入 prepare/launch
        seen_ranges = []
        def second_open(req, timeout=60):
            seen_ranges.append(req.get_header("Range"))
            return _Resp(self.data[8:], 206, {"Content-Range": "bytes 8-19/20"})

        with patch.object(update, "check", return_value=self.info), \
             patch.object(download.net, "urlopen", side_effect=second_open), \
             patch.object(mac_update, "prepare", return_value=self.root / "new.app") as prep, \
             patch.object(mac_update, "launch") as launch, \
             patch.object(update.threading, "Timer") as timer:
            res = update.apply()
        self.assertEqual(res, {"ok": True, "version": "4.3.1"})
        self.assertEqual(seen_ranges, ["bytes=8-"])
        prep.assert_called_once()
        launch.assert_called_once()
        timer.assert_called_once()
        self.assertFalse(cached_files[0].exists(), "校验通过移交给 stage 后缓存文件应已移走")

    def test_single_call_tolerates_more_than_three_disconnects(self):
        # 连续断 5 次（每次下 4 字节），在单次 update.apply() 内完成全部 20 字节下载
        chunks = [self.data[i:i + 4] for i in range(0, len(self.data), 4)]
        resps = [_Resp(chunks[0], 200, {"Content-Length": str(len(self.data))})] + [
            _Resp(chunks[k], 206, {"Content-Range": "bytes %d-%d/%d" % (k * 4, len(self.data) - 1, len(self.data))})
            for k in range(1, len(chunks))
        ]
        with patch.object(update, "check", return_value=self.info), \
             patch.object(download.net, "urlopen", side_effect=resps) as req, \
             patch.object(mac_update, "prepare", return_value=self.root / "new.app"), \
             patch.object(mac_update, "launch"), \
             patch.object(update.threading, "Timer"):
            res = update.apply()
        self.assertEqual(res["ok"], True)
        self.assertEqual(req.call_count, 5)


if __name__ == "__main__":
    unittest.main()
