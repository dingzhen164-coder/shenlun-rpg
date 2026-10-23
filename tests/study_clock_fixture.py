"""旧计时来源回归用虚拟服务端时钟：显式经过一分钟，不再瞬发心跳冒充已学习。
防重复预算本身由test_repairs368以静止/小数时钟单独验证；本辅助不跳过预算校验。
"""
import functools
import itertools
from unittest.mock import patch
from rpg import api, study_clock


def elapsed_heartbeats(fn):
    @functools.wraps(fn)
    def run(*args, **kwargs):
        with patch.object(study_clock, '_now', side_effect=itertools.count(1000,60)):
            with api.open_game(save=False) as g:
                study_clock.seconds(g.paths)
            return fn(*args, **kwargs)
    return run
