"""
存档：训练/存档/存档.json 的读写。

- 所有训练结果都在这一个 JSON 里（结构见 DESIGN.md 与下面的 new_state）；
- 写入是原子的（先写临时文件再替换）；
- 每天第一次写入前备份一份到 存档/备份/，保留最近 14 份；
- 多设备同步时 “正在使用.json” 记录哪台电脑在用，另一台 10 分钟内有心跳就提醒；同步冲突副本也提醒。
- 事件、进度都带 subject 字段（"shenlun" / "xingce"），为日后合并行测预留。
谁调用：core/api.py。
"""
import json
import os
import platform
import threading
import time

LOCK = threading.RLock()  # 所有读改写存档的操作都要先拿这把锁
SCHEMA_VERSION = 1
DEVICE = platform.node() or "本机"


def new_state(today):
    return {
        "version": SCHEMA_VERSION,
        "created": today.isoformat(),
        "theme": "官场",
        "xp": 0,                  # 累计政绩（程序计算，含连续打卡加成）
        "events": [],             # {t, d, subject, type, board, item, ok, xp, note}
        "records": [],            # 作答与批改记录 {id, d, subject, qid, board, score, full, rate, ...}
        "items": {},              # 方法骨架大项的掌握状态，键 "题型::大项"
        "wrong": {},              # 整改（错题）状态
        "seconds": {},            # 每天学习秒数 {日期: 秒}
        "leave": [],              # 调休日期
        "plan": None,             # 今日任务 {date, tasks}
        "daily": {},              # 每日一题打卡 {日期: {qid, done}}
        "boss": [],               # 年度考核（模考）/ 大考成绩 {d, name, score}
        "weekly": {},
        "bag": {},
        "last_seen": None,
    }


class Store:
    def __init__(self, paths):
        self.paths = paths

    def load(self, today):
        f = self.paths.save_file
        if not f or not f.exists():
            return new_state(today)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            bad = f.with_name("存档-损坏-%d.json" % int(time.time()))
            os.replace(str(f), str(bad))
            return self._latest_backup() or new_state(today)
        base = new_state(today)
        base.update(data)  # 老存档缺的新字段用默认值补齐
        return base

    def save(self, state, today):
        f = self.paths.save_file
        if not f:
            return
        f.parent.mkdir(parents=True, exist_ok=True)
        self._daily_backup(today)
        tmp = f.with_suffix(".tmp")
        with open(str(tmp), "w", encoding="utf-8", newline="\n") as fp:
            json.dump(state, fp, ensure_ascii=False, indent=1)
        os.replace(str(tmp), str(f))

    def _backup_dir(self):
        return self.paths.save_dir / "备份"

    def _daily_backup(self, today):
        f = self.paths.save_file
        if not f.exists():
            return
        d = self._backup_dir()
        d.mkdir(exist_ok=True)
        dst = d / ("存档-%s.json" % today.strftime("%Y%m%d"))
        if not dst.exists():
            dst.write_bytes(f.read_bytes())
            for old in sorted(d.glob("存档-*.json"))[:-14]:
                old.unlink()

    def _latest_backup(self):
        d = self._backup_dir()
        for b in sorted(d.glob("存档-*.json"), reverse=True) if d.exists() else []:
            try:
                return json.loads(b.read_text(encoding="utf-8"))
            except Exception:
                continue
        return None

    def heartbeat(self):
        """写入“本机正在使用”；返回另一台电脑的名字（10 分钟内有心跳），没有返回 None"""
        if not self.paths.save_dir:
            return None
        self.paths.save_dir.mkdir(parents=True, exist_ok=True)
        lf = self.paths.save_dir / "正在使用.json"
        other = None
        try:
            cur = json.loads(lf.read_text(encoding="utf-8"))
            if cur.get("device") != DEVICE and time.time() - cur.get("ts", 0) < 600:
                other = cur.get("device")
        except Exception:
            pass
        if not other:
            try:
                lf.write_text(json.dumps({"device": DEVICE, "ts": time.time()}, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return other

    def conflicts(self):
        d = self.paths.save_dir
        if not d or not d.exists():
            return []
        return [p.name for p in d.iterdir()
                if p.is_file() and ("冲突" in p.name or "conflict" in p.name.lower())]
