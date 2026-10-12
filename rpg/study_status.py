"""3.0.2常驻状态信息：按备考开始日至今天（含空白日）统计平均学习分钟。
只读取已计入的seconds/lectures与规则日期；不发经验、不写存档、不重复加自练时间。
由Game.dashboard调用，返回start/exam/day/remaining/average_minutes。
"""
import math


def view(g):
    start, exam = g.rules.date("开始日期"), g.rules.date("目标日")
    days = max(0, (g.today - start).days + 1)
    def valid_date(value):
        return isinstance(value, str) and start.isoformat() <= value <= g.t
    def positive(value):
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 else 0
    total = sum(positive(v) / 60 for d, v in g.state.get("seconds", {}).items() if valid_date(d))
    total += sum(positive(x.get("minutes")) for x in g.state.get("lectures", []) if valid_date(x.get("d")))
    return {"start": start.isoformat(), "exam": exam.isoformat(), "day": days,
            "remaining": (exam - g.today).days,
            "average_minutes": round(total / days, 1) if days else 0}
