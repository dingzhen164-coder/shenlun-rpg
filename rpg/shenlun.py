"""
申论作答活动记录（给 rpg/api.py 的 /api/shenlun/active 和心跳用）。

touch / answering  作答页的活动记录：只有 2 分钟内敲过键盘才给“作答”计时（服务端校验，防挂机）。
完整真题的题库、作答、批改见 rpg/shenlun_bank.py、rpg/shenlun_review.py。
"""
import time


class ShenlunError(Exception):
    pass


_TOUCH = {"t": 0.0}
ANSWER_GRACE = 120   # 秒：最后一次敲键盘到现在不超过这个才算在作答


def touch():
    _TOUCH["t"] = time.time()


def answering():
    return time.time() - _TOUCH["t"] <= ANSWER_GRACE
