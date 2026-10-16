"""行测五峰讲题身份：trainer在生成讲解和返回会话时调用。
按当前题目板块选择固定人物ID，复用人物卡性格/语录/头像；不访问人物私聊或赠礼存档。
响应仅增加mentor={id,name,role,avatar}及NPC消息身份，不改变题库、计分、AI接口或旧存档。
"""
import copy
from . import characters

PEAKS = (
    ('xc-xiaohei', '小黑', '万象峰峰主', ('常识判断', '政治理论', '常识')),
    ('xc-zhanggong', '张弓', '辨言峰峰主', ('片段阅读', '逻辑填空', '言语理解', '成语实词')),
    ('xc-xuerui', '薛睿', '明理峰峰主', ('论证逻辑', '形式逻辑', '一拖五', '定义判断', '类比推理', '图形推理', '判断推理')),
    ('xc-huasheng13', '花生十三', '演数峰峰主', ('数量关系',)),
    ('xc-chenhuaian', '陈怀安', '观星峰峰主', ('资料分析',)),
)


def profile(g, board):
    if getattr(g, 'subject', '') != '行测':
        return None
    row = next((p for p in PEAKS if board in p[3]), None)
    if not row:
        return None
    cid, name, role, _ = row
    # 不读取人物私聊；坏配置/停用人物安全回退对应峰主，不串到其他科目导师。
    try:
        p = characters.profiles(g)[0].get(cid)
    except (ValueError, OSError, UnicodeError):
        p = None
    return dict(id=cid, name=p['name'] if p else name, role=p['role'] if p else role,
                avatar=(p['portraits'].get('bust') or p['portraits'].get('three_quarter') or '') if p else '',
                persona=p['persona'] if p else '%s，负责%s，讲解清楚、具体，不冒充现实本人。' % (role, board),
                quotes=p['quotes'] if p else '')


def persona(g, board):
    p = profile(g, board)
    if not p:
        return g.persona
    result = copy.copy(g.persona)
    result.d = dict(g.persona.d, 导师名=p['name'], 称呼='你',
                    导师人设=p['persona'] + '\n参考语录与口头禅：\n' + p['quotes'] +
                    '\n你是游戏中的对应峰主，按当前题目和知识资料讲解，不冒充现实本人，不编造其经历。')
    return result


def session_board(g, s):
    if s.get('type') in ('bank', 'bank_review'):
        run = g.state.get('bank', {}).get('runs', {}).get(s.get('board'), {})
        qs = run.get('questions') or []
        i = run.get('rpos', 0) if run.get('phase') == 'review' else run.get('pos', 0)
        return qs[min(max(i, 0), len(qs)-1)]['board'] if qs else ''
    return (s.get('discuss') or {}).get('board') or s.get('board') or s.get('source') or (s.get('task') or {}).get('board', '')


def attach(g, response, sessions):
    if getattr(g, 'subject', '') != '行测':
        return response
    s = sessions.get(response.get('session'), {})
    if s.get('type') in ('chat', 'skeleton'):
        return response
    p = profile(g, session_board(g, s))
    if not p:
        return response
    brief = {k:p[k] for k in ('id', 'name', 'role', 'avatar')}
    response['mentor'] = brief
    for m in response.get('messages', []):
        if m.get('who') == 'npc' and not m.get('history'):
            m.setdefault('mentor', brief)
    inp = response.get('input') or {}
    if inp.get('placeholder'):
        inp['placeholder'] = inp['placeholder'].replace('师傅', p['name'])
    for b in inp.get('buttons', []):
        b['label'] = b['label'].replace('师傅', p['name'])
    return response
