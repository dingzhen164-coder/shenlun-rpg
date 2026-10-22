"""手动学习蜡烛/阅读计时凭据，供api心跳调用。
凭据仅留内存并绑定资料库和科目；最后真实交互过期后失效，计秒不能超过服务端单调时钟。
不直接写存档或发奖，返回秒数和板块给原Game.add_seconds统一结算。
"""
import math
import secrets
import threading
import time

_LOCK = threading.RLock()
_READERS = {}
IDLE_SECONDS = 180


def _scope(paths):
    return (str(paths.vault.resolve()), getattr(paths, 'subject', '法考')) if paths.vault else None


def _get(paths, token, now):
    r = _READERS.get(str(token or ''))
    return r if r and r['scope'] == _scope(paths) and 0 <= now-r['touched'] <= IDLE_SECONDS else None


def start(paths, board=''):
    scope = _scope(paths)
    if scope is None:
        raise ValueError('请先选择资料库')
    now = time.monotonic()
    with _LOCK:
        for k, r in list(_READERS.items()):
            if now-r['touched'] > IDLE_SECONDS:
                _READERS.pop(k, None)
        if len(_READERS) >= 256:
            _READERS.pop(next(iter(_READERS)))
        token = secrets.token_urlsafe(24)
        _READERS[token] = dict(scope=scope, board=str(board or '')[:120], touched=now, claimed=now)
    return token


def touch(paths, token):
    with _LOCK:
        now = time.monotonic(); r = _get(paths, token, now)
        if r is None:
            return False
        r['touched'] = now
        return True


def seconds(paths, token, requested):
    with _LOCK:
        now = time.monotonic(); r = _get(paths, token, now)
        if r is None:
            return None
        n = max(0, min(90, int(requested), math.floor(max(0, now-r['claimed']))))
        r['claimed'] += n
        return n, r['board']


def stop(paths, token):
    with _LOCK:
        if _get(paths, token, time.monotonic()) is not None:
            _READERS.pop(str(token), None)
