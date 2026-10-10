"""联网统一入口：给 https 请求配好根证书。
Mac App（打包进去的 Python）找不到系统的根证书，会报 CERTIFICATE_VERIFY_FAILED（检查更新、AI、抓文章都连不上）；
这里优先用 certifi 带的证书，没有就用 macOS 自带的 /etc/ssl/cert.pem，都没有才用 Python 默认的。"""
import os
import ssl
import urllib.request

_CTX = None


def context():
    global _CTX
    if _CTX is None:
        ctx = None
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            for f in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
                if os.path.isfile(f):
                    try:
                        ctx = ssl.create_default_context(cafile=f)
                        break
                    except Exception:
                        pass
        _CTX = ctx or ssl.create_default_context()
    return _CTX


def urlopen(req, timeout=15):
    return urllib.request.urlopen(req, timeout=timeout, context=context())
