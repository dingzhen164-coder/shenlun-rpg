"""联网统一入口 rpg/net.py：https 请求都带上根证书（Mac App 里 Python 找不到系统证书会连不上 GitHub / AI）"""
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rpg import net  # noqa: E402


class NetTest(unittest.TestCase):
    def test_context_has_trusted_roots_and_verifies(self):
        net._CTX = None
        ctx = net.context()
        self.assertIsInstance(ctx, ssl.SSLContext)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreater(len(ctx.get_ca_certs()), 0)

    def test_urlopen_passes_the_context(self):
        with patch("urllib.request.urlopen") as m:
            net.urlopen("http://x.test", timeout=3)
        self.assertIs(m.call_args.kwargs["context"], net.context())

    def test_falls_back_to_macos_system_bundle_without_certifi(self):
        net._CTX = None
        with patch.dict(sys.modules, {"certifi": None}), patch("os.path.isfile", side_effect=lambda f: f == "/etc/ssl/cert.pem"), \
                patch("ssl.create_default_context") as c:
            net.context()
        self.assertEqual(c.call_args_list[0].kwargs, {"cafile": "/etc/ssl/cert.pem"})
        net._CTX = None


if __name__ == "__main__":
    unittest.main()
