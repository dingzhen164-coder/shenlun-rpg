#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
申论官途 · 启动入口。

    python server.py              # 启动并自动打开浏览器（Mac 用 python3）
    python server.py --port 9000  # 换端口
    python server.py --no-browser # 不自动打开浏览器

只用 Python 标准库，不需要 pip install。关掉这个终端窗口 = 关掉程序。
"""
import argparse
import mimetypes
import socket
import sys
import threading
import webbrowser

sys.dont_write_bytecode = True

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

from http.server import ThreadingHTTPServer  # noqa: E402

from core.api import Handler, paths  # noqa: E402


def free_port(start):
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


def main():
    ap = argparse.ArgumentParser(description="申论官途训练网页")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    print("申论库：%s" % paths().vault)
    port = free_port(a.port)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % port
    print("\n申论官途已启动：%s\n关掉这个窗口就会退出。" % url)
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
