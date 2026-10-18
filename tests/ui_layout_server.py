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
        if '--art-fixture' in sys.argv:
            # 美术文件夹覆盖测试：首页白天全景、洞府背景各放一张纯色小图
            import base64
            png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
            for s2, place in (('行测', '洞府'), ('申论', '办公室')):
                d = Path(vaults[s2]) / '训练/外观/美术'
                (d / '首页全景').mkdir(parents=True, exist_ok=True); (d / '子地图背景').mkdir(parents=True, exist_ok=True)
                (d / '首页全景' / '白天.png').write_bytes(png)
                (d / '子地图背景' / (place + '.png')).write_bytes(png)
                if s2 == '申论':      # 申论领导立绘：洋红底的假人物，根目录英文编号即可
                    from PIL import Image, ImageDraw
                    for expr in ('calm', 'cheer', 'blink'):
                        im = Image.new('RGB', (600, 800), (255, 0, 255)); ImageDraw.Draw(im).ellipse((150, 120, 450, 700), fill=(30, 70, 110))
                        im.save(d / ('sl-zhoujingyi-%s.png' % expr))
                if s2 == '行测':
                    (d / '子地图背景' / '洞府-十二经.png').write_bytes(png); (d / '子地图背景' / '万象峰.png').write_bytes(png)
        if '--art-real' in sys.argv:
            # 看合成效果用：把程序自带的青衡宗全景当作所有行测子地图的背景
            from PIL import Image
            from rpg import art as _art
            im = Image.open(Path(__file__).resolve().parent.parent / 'web/assets/sect/xc-sect-day.webp').convert('RGB')
            d = Path(vaults['行测']) / '训练/外观/美术/子地图背景'; d.mkdir(parents=True, exist_ok=True)
            for _f, name, *_r in _art.slots('行测'):
                if _f == '子地图背景' and not name.endswith(('-白天', '-夜晚')) and '-' not in name:
                    im.save(d / (name + '.png'))
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
        if '--score-fixture' in sys.argv:
            from tests.test_mock_score import paper
            with api.open_game() as g:
                paper(g.paths.train/'模考复盘/第39季',wrong={101})
                g.state.setdefault('mocks',{}).setdefault('39',{})['html_import']={'reported_score':70.6,'question_seconds':{'1':85},'known_numbers':list(range(1,131))}
        if '--import-management-fixture' in sys.argv:
            from tests.test_mock_imports import management_fixture
            with api.open_game() as g:
                management_fixture(g.paths)
                g.state.setdefault('mocks',{})['33']={'score':72.3}
                # 故意缺旧版mock_practice标记，覆盖补导入重复计时问题。
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
        if '--image-clean-fixture' in sys.argv:
            from image_fixture311 import install
            with api.open_game() as g:
                install(g)
        if '--layout335-fixture' in sys.argv:
            from layout335_fixture import install
            with api.open_game() as g:
                install(g)
        srv = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        api.RUNTIME.update(port=srv.server_port, lan=False)
        print('UI-READY http://127.0.0.1:%d' % srv.server_port, flush=True)
        srv.serve_forever()


if __name__ == '__main__':
    main()
