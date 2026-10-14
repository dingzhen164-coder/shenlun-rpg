"""给 tests/ui_layout_check.cjs 起服务：两科各一个临时库 + 临时本机设置，不碰用户数据、不连真 AI。
用法：python tests/ui_layout_server.py [行测|申论]（默认申论）。打印 “UI-READY 网址” 后一直运行。"""
import os
import sys
import tempfile
os.environ.pop('DEEPSEEK_API_KEY', None)
os.environ.pop('SHENLUN_AI_BASE_URL', None)
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop('SHENLUN_SUBJECT', None)
# 在导入前隔离自动找库和旧版设置。
from unittest.mock import patch
_import_home = tempfile.TemporaryDirectory()
_home_patch = patch.object(Path, 'home', return_value=Path(_import_home.name))
_home_patch.start()
from rpg import api, paths  # noqa: E402


def main():
    subject = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ('行测', '申论') else '申论'
    with tempfile.TemporaryDirectory() as t:
        r = Path(t)
        paths.SETTINGS_DIR = r / 'home'
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / 'settings.json'
        paths.LEGACY_SETTINGS = r / '无.json'
        vaults = {}
        for s in ('行测', '申论'):
            v = r / s
            (v / 'copilot/skills/test').mkdir(parents=True)
            if s == '行测':
                (v / 'FB模考试卷复盘/板块复盘').mkdir(parents=True)
            vaults[s] = str(v)
            paths.Paths(v, s).ensure_train_dir()
        paths.save_settings({'subject': subject, 'vaults': vaults})
        if '--journey-fixture' in sys.argv:
            # 第二批交互用自编卡片，不连接AI、不读取真实题库。
            from rpg import cards
            with api.open_game() as g:
                deck = next(iter(g.boards))
                cards.add(g, dict(deck=deck, type='问答', front='自编练习：解释一个方法的适用条件。', back='先说明条件，再用自己的话举例。'))
                cards.add(g, dict(deck=deck, type='问答', front='自编练习二：用自己的话举例。', back='说明条件与边界。'))
        if '--merge-fixture' in sys.argv:
            # 自编演示成绩，覆盖合并后的走势、双录入方式与手动领奖。
            from rpg import mock_rewards, mock
            with api.open_game() as g:
                for num, score in ((37, 62), (38, 72)):
                    if g.paths.seasons:
                        folder = g.paths.seasons / ('第%d季' % num)
                        folder.mkdir(parents=True, exist_ok=True)
                        board = next(iter(mock.MODULE_OF))
                        (folder / ('01-' + board + '.md')).write_text('### 1. ✅\n\n自编题目：选择A。\n\n### 2. ❌\n\n自编题目：解释条件。\n', encoding='utf-8')
                    g.state.setdefault('mocks', {})[str(num)] = dict(score=score, date=g.t, avg=55, top=88, beat=80, rank=20, people=100, minutes={}, scores={})
                    g.state['boss'].append(dict(d=g.t, name='第%d季' % num, score=score, kind='大比'))
                mock_rewards.offer(g, '自编模考奖励', 72, g.raw_score())
        if '--review-fixture' in sys.argv:
            # 自编长材料，复现平板复盘底部操作被裁切；只写临时库。
            with api.open_game() as g:
                board = next(iter(g.boards))
                if g.paths.seasons:
                    folder = g.paths.seasons / '第38季'
                    folder.mkdir(parents=True, exist_ok=True)
                    material = '> 自编材料：本月数据100，下月数据120，增长率为20%。\n' * 35
                    body = '## 材料（第1-2题）\n> [!abstract]- 自编数据\n' + material + '\n---\n'
                    for i, icon in ((1, '✅'), (2, '❌')):
                        body += '### %d. %s\n自编题：增长率为多少？\n- **A.** 20%%\n- **B.** 30%%\n\n> [!check]- 答案\n> 正确答案：**A**　我的答案：**B**　错误\n\n> [!note] 复盘\n> 自编解析：用增加量除以原值。\n\n---\n' % (i, icon)
                    (folder / ('01-' + board + '.md')).write_text(body, encoding='utf-8')
                api.bank_add(dict(board=board, topic='自编条件验证', source='UI测试', stem='自编题：哪个选项符合条件？', options=dict(A='符合', B='不符合', C='无关', D='无关'), answer='A', analysis='自编解析：逐项核对条件。'))
        if '--reader-fixture' in sys.argv:
            from rpg import cards, mindmap
            with api.open_game() as g:
                board = next(iter(g.boards))
                root = {'data': {'text': board + ' · 自编知识纲要'}, 'children': []}
                for i in range(12):
                    root['children'].append({'data': {'text': '方法%d：理解适用条件' % (i + 1)}, 'children': [
                        {'data': {'text': '先辨析问题，再核对条件。'}, 'children': []},
                        {'data': {'text': '自编示例，逐步整理知识脉络。'}, 'children': []}]})
                mindmap.create(g.paths, board, board, {'root': root, 'layout': 'logicalStructure'})
                cards.add(g,dict(deck=board,type='问答',front='自编记忆卡：说明一个方法的条件。',back='核对条件，再解释边界。'))
                print('UI-READER ' + __import__('json').dumps(dict(vault=str(g.paths.vault),board=board),ensure_ascii=False),flush=True)
        srv = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        api.RUNTIME.update(port=srv.server_port, lan=False)
        print('UI-READY http://127.0.0.1:%d' % srv.server_port, flush=True)
        srv.serve_forever()


if __name__ == '__main__':
    main()
