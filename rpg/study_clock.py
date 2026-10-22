"""学习心跳的统一服务端秒数预算，由api.dashboard/heartbeat调用。
内存按(资料库,科目)保存{last,budget}，同库多标签/计时来源共用预算；不写存档或发奖。
只使用单调时钟，单次/积攒上限90秒，保留不足一秒的余量，重启后不补发未知时长。
"""
import math
import threading
import time

_LOCK = threading.Lock()
_CLOCKS = {}


def _now():
    return time.monotonic()


def seconds(paths, requested=0):
    if not paths.vault:
        return 0
    key = (str(paths.vault.resolve()), getattr(paths, 'subject', '法考'))
    with _LOCK:
        now = _now()
        clock = _CLOCKS.get(key)
        if clock is None:
            if len(_CLOCKS) >= 256:
                _CLOCKS.pop(next(iter(_CLOCKS)))
            clock = _CLOCKS[key] = {'last':now, 'budget':0.0}
        clock['budget'] = min(90.0, clock['budget'] + max(0.0, now-clock['last']))
        clock['last'] = now
        count = min(max(0, min(90, int(requested))), int(math.floor(clock['budget']+1e-9)))
        clock['budget'] = max(0.0, clock['budget']-count)
        return count
