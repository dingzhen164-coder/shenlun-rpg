"""
HTTP 接口与静态文件。只监听 127.0.0.1。

接口：
    GET  /api/dashboard   今日概览（统计卡片、职级、每日一题、提醒）
    GET  /api/health      心跳与状态
其余路径按 web/ 目录提供静态文件。每个请求加锁读写存档。
谁调用：server.py。
"""
import datetime as dt
import json
import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from . import ai, themes
from .paths import APP_DIR, Paths, find_vault
from .store import LOCK, Store
from subjects.shenlun import samples

WEB = APP_DIR / "web"
_PATHS = None


def paths():
    global _PATHS
    if _PATHS is None:
        _PATHS = Paths(find_vault())
        _PATHS.ensure_train_dir()
    return _PATHS


def streak(state, today):
    """连续练习天数：从今天（今天没练则从昨天）往前数连续有记录的天数"""
    days = {r["d"] for r in state["records"]} | set(state["leave"])
    d = today if today.isoformat() in days else today - dt.timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= dt.timedelta(days=1)
    return n


def dashboard(today=None, store=None):
    today = today or dt.date.today()
    store = store or Store(paths())
    state = store.load(today)
    th = themes.get(state.get("theme"))
    recs = state["records"]
    rated = [r for r in recs if r.get("rate") is not None]
    score = round(sum(r["rate"] for r in rated[-10:]) / len(rated[-10:]) * 100, 1) if rated else None
    rank, nxt, nxt_at = themes.rank_of(state.get("theme"), score)
    daily = state["daily"].get(today.isoformat())
    q = samples.SAMPLES[today.toordinal() % len(samples.SAMPLES)]
    wrong_due = [k for k, v in state["wrong"].items() if v.get("due", "9999") <= today.isoformat()]
    return {
        "date": today.isoformat(),
        "weekday": "一二三四五六日"[today.weekday()],
        "theme": {"name": th["name"], "app": th["app"], "tagline": th["tagline"],
                  "terms": th["terms"], "tutor": th["tutor"]},
        "rank": {"name": rank, "next": nxt, "next_at": nxt_at, "score": score},
        "stats": {
            "wrong_due": len(wrong_due),
            "streak": streak(state, today),
            "total": len(recs),
            "rated": len(rated),
        },
        "daily": {"question": q, "done": bool(daily and daily.get("done"))},
        "ai": ai.available(),
        "version": "0.1.0",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ShenlunRPG/0.1"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/dashboard":
            with LOCK:
                return self._json(dashboard())
        if u.path == "/api/health":
            return self._json({"ok": True})
        rel = u.path.lstrip("/") or "index.html"
        f = (WEB / rel).resolve()
        try:
            f.relative_to(WEB.resolve())
        except ValueError:
            return self._json({"error": "not found"}, 404)
        if not f.is_file():
            return self._json({"error": "not found"}, 404)
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(str(f))[0] or "application/octet-stream") + ("; charset=utf-8" if f.suffix in (".html", ".css", ".js") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
