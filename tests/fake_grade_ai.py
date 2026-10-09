"""
假 AI 服务：在本机起一个 OpenAI 兼容的 /chat/completions，测试批改流程用，不联网、不花钱。

判断逻辑是关键词近似（真实 AI 按含义判断）：某采分点的关键词有 ≥60% 出现在作答里 → full，有任意一个 → half，否则 none；
依据句 = 作答里含命中关键词的那一句。用 mode 可以模拟坏情况：
    ok            正常
    bad_once      第一次返回缺字段的 JSON，之后正常（测重试）
    always_bad    一直返回缺字段的 JSON（测放弃）
    fake_evidence 依据句是编造的（测核验）
用法：with FakeAI(mode) as srv: os.environ["SHENLUN_AI_BASE_URL"] = srv.url
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def judge(prompt, mode="ok"):
    """从批改提示词里取采分点和作答，返回批改 JSON"""
    answer = prompt.split("考生作答：", 1)[1].split("返回格式：", 1)[0].strip()
    pts = prompt.split("采分点（id：名称｜关键词｜材料依据）：", 1)[1].split("失分类型清单", 1)[0]
    sentences = [s for s in re.split(r"(?<=[。；;！？\n])", answer) if s.strip()]
    flat = re.sub(r"\s", "", answer)
    points, bonus = [], []
    for ln in pts.splitlines():
        m = re.match(r"^(加?\d+)：(.+?)｜(.*?)｜", ln)
        if not m:
            continue
        pid, kws = m.group(1), [k for k in m.group(3).split("；") if k]
        hits = [k for k in kws if re.sub(r"\s", "", k) in flat]
        ratio = len(hits) / float(len(kws) or 1)
        hit = "full" if ratio >= 0.6 else "half" if hits else "none"
        ev = ""
        if hits:
            ev = next((s.strip() for s in sentences if hits[0] in s), hits[0])
        if mode == "fake_evidence" and hit != "none":
            ev = "这句话考生根本没写过"
        item = {"id": int(pid) if pid.isdigit() else pid, "hit": hit, "evidence": ev, "reason": "关键词命中 %d/%d" % (len(hits), len(kws))}
        (points if pid.isdigit() else bonus).append(item)
    return {"points": points, "bonus": bonus, "lost": [{"code": "A1", "note": "有要点没写到"}] if any(p["hit"] != "full" for p in points) else [],
            "summary": "基本到位，注意补全遗漏要点。"}


class FakeAI:
    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls += 1
                prompt = next((m["content"] for m in reversed(body["messages"]) if "考生作答" in m["content"]), None)
                if prompt is None:
                    reply = "好的，继续努力。"
                elif outer.mode == "always_bad" or (outer.mode == "bad_once" and outer.calls == 1):
                    reply = {"points": [], "bonus": []}
                else:
                    reply = judge(prompt, outer.mode)
                text = reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
                out = json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
