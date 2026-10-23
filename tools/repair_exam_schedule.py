"""显式校正误改考试日期的存档副本，不启动Game、不动原件、不重发奖励。

只处理未过大境界关卡的原始JSON；调用者按自己的规则提供成长参数。
输出仅改study_schedule.exam和claimed，禁止覆盖任何已有文件。
"""
import argparse
import copy
import datetime as dt
import json
import math
from pathlib import Path


def repair(state, exam, daily, start_score, target_score, curve):
    if state.get('gates'):
        raise ValueError('已有大境界关卡，须按实际规则单独核对，未修改')
    days = (dt.date.fromisoformat(exam) - dt.date.fromisoformat(state['study_schedule']['start'])).days
    if days <= 0 or daily <= 0 or curve <= 0 or target_score <= start_score:
        raise ValueError('日期或成长规则无效')
    xp = state['xp']
    if isinstance(xp, bool) or not isinstance(xp, (int, float)) or xp < 0:
        raise ValueError('修为值无效')
    score = start_score + (target_score-start_score) * (xp/(days*daily)) ** curve
    if not math.isfinite(score):
        raise ValueError('计算结果无效')
    result = copy.deepcopy(state)
    result['study_schedule']['exam'] = exam
    result['claimed'] = min(state['claimed'], math.floor(score))
    # 不改XP、悟道/扣除账本、events、题库进度或任何其他字段。
    check = copy.deepcopy(result)
    check['study_schedule']['exam'] = state['study_schedule']['exam']
    check['claimed'] = state['claimed']
    assert check == state
    return result, score


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--exam', required=True)
    p.add_argument('--daily', required=True, type=float)
    p.add_argument('--start-score', required=True, type=float)
    p.add_argument('--target-score', required=True, type=float)
    p.add_argument('--curve', required=True, type=float)
    a = p.parse_args()
    state = json.loads(a.source.read_text(encoding='utf-8'))
    result, score = repair(state, a.exam, a.daily, a.start_score, a.target_score, a.curve)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    # x模式：不覆盖原件或上次结果；只写调用者指定的交付位置。
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('已生成校正副本：日期%s，突破标记%s→%s，修为不变；计算分数%.8f' %
          (a.exam, state['claimed'], result['claimed'], score))


if __name__ == '__main__':
    main()
