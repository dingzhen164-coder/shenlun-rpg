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
        if '--politics-fixture' in sys.argv:
            from rpg import politics
            from tests.politics_fixture import atlas_data
            pp = paths.Paths(Path(vaults['行测']), '行测')
            data = atlas_data()
            politics.atomic_json(pp.train / '时政知识地图/内容.json', data)
            news = {'id': '2026-10-上', 'kind': 'month', 'title': '自编十月上时政', 'label': '自编时政', 'year': 2026,
                    'month': 10, 'half': '上', 'category': '其他', 'overview': '自编理解练习', 'groups': [],
                    'news': [{'no': 1, 'stars': 1, 'tag': '农业', 'title': '自编政策材料', 'group': '',
                              'paras': [data['materials'][0]['original']], 'qs': []}],
                    'cloze': [{'no': 1, 'title': '自编政策材料', 'news': 0,
                               'parts': [{'t': '在'}, {'a': '主产区'}, {'t': '布局产能。'}]}], 'questions': []}
            politics.atomic_json(pp.train / '天机简报/月半时政/2026-10-上.json', news)
            settings = paths.load_settings()
            settings['api_key'] = 'fake-key-for-local-test-only'
            paths.save_settings(settings)
            def fake_explain(*args, **kwargs):
                import json
                return json.dumps({'meaning': '本段讨论生产地区的发展支持。', 'role': '主产区限定政策对象。',
                                   'compare': '主销区改变了支持对象，不能替换本段原文。', 'plain': '让主要生产的地方发展产业。',
                                   'evidence': '在主产区布局产能', 'example': '产粮多的地方需要厂房把粮食加工为食品，销售多的地方不一定生产粮食。', 'background': '加工厂靠近原料，可降低运输损耗；这解释政策机制，不代表原文列明全部原因。'}, ensure_ascii=False)
            politics.ai.chat = fake_explain
            politics.policy_search.search = lambda *args: {'status': 'unavailable', 'sources': []}
            topic = dict(news, id='old-topic', kind='topic', title='自编两会专题', category='两会·政府报告',
                         news=[{'no':i+1, 'title':'习近平强调，到2035年建成健康中国是我们作出的一项战略决策',
                                'group':'两会讲话', 'paras':['建设健康中国，自编原文第%d段。'%i], 'qs':[]} for i in range(3)], cloze=[])
            politics.atomic_json(pp.train / '天机简报/专题时政/old-topic.json', topic)
            from tests.test_tianji import make_pdf
            make_pdf(pp.train/'自编补充.pdf', [[(1,'一、自编经济会议'),(1,'在主产区布局产能，支持主产区发展产业。'),
                     (1,'配套练习'),(1,'1.（多选）自编政策对象包括哪些？'),(1,'A.主产区'),(1,'B.生产区'),
                     (1,'C.销售区'),(1,'D.其他'),(1,'参考答案'),(1,'1.【答案】AB。解析：自编选项的说明。')]])
            from tests.test_politics_exam import make as make_exam, PAGE1 as EXAM1, PAGE2 as EXAM2, ANSWERS as EXAM3
            with make_exam([EXAM1, EXAM2, EXAM3]) as exam_doc:       # 3.7.5：十套卷式的冲刺刷题PDF（两套，答案按套分开）
                exam_doc.save(str(pp.train/'自编十套卷.pdf'))
            print('UI-POLITICS ' + str(pp.train), flush=True)
            if '--wanxiang373-fixture' in sys.argv:
                # 本批界面只用自编长题、四类目录与零空场人物，仍是隔离临时库。
                import copy
                from rpg import characters
                for i in range(1,4):
                    m=copy.deepcopy(data['materials'][0]);m.update(id='m'+str(i+1),title=['','自编讲话资料','自编指导资料','自编文件资料'][i],chapter=i,questions=[])
                    if i==1:m.update(original='😀支持甲方。\n\n😀支持甲方。',originalEmphasis=[])
                    if i==2:    # 带两级标题且整段（含标题）都标红的讲义：检查标题不加红、正文标红保持
                        text='二、自编标题\n（一）自编小标题\n'+m['original'];m.update(original=text,originalEmphasis=[[0,len(''.join(text.split()))]])
                    data['materials'].append(m)
                politics.atomic_json(pp.train/'时政知识地图/内容.json',data)
                make_pdf(pp.train/'自编消化清单.pdf',[[(1,'自编消化清单'),(1,'1.在________布局产能。'),(1,'2.自编未知政策提出________要求。')]])
                news['questions']=[{'key':0,'no':1,'kind':'单选','stem':'自编题面应该连续显示，不应在半句\n中换行。'*5,'stmts':[],'opts':{'A':'自编甲方选项\n的续行','B':'自编乙方','C':'自编丙方','D':'自编丁方'},'answer':'A','analysis':'自编说明','news':0}]
                news['news'][0]['qs']=[0]
                politics.atomic_json(pp.train/'天机简报/月半时政/2026-10-上.json',news)
                with api.open_game() as g:
                    folder=characters.install(g)
                    (folder/'规则.md').write_text('- 空场概率：0\n- 同场人数：2\n- 相遇间隔分钟：30\n',encoding='utf8')
        if '--skillbook-fixture' in sys.argv:
            # 藏经阁·心法：只有一个板块（行测 论证逻辑 / 申论 归纳概括）预先放了自编的三个文件，其余板块都是空的；不读真实资料。
            from rpg import skillbook
            for s2, board in (('行测', '论证逻辑'), ('申论', '归纳概括')):
                pp = paths.Paths(Path(vaults[s2]), s2)
                for rel, text in (('SKILL.md', '# 自编入口\n先识别题型，再用方法。\n- 第一步：找条件\n- 第二步：排除干扰'),
                                  ('cheatsheet.md', '# 速查\n口诀：自编口诀一'), ('chapters/01.md', '## 第一章\n自编方法正文。')):
                    skillbook.save(pp, board, rel, text, '')
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
        if '--art-generic-train' in sys.argv:
            # 3.7.4：用户在美术文件夹里放过“修炼”整页背景（白天/夜晚/无后缀）——五峰仍须各用自己的图，不被它顶替。
            import base64
            from rpg import art as _art
            png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
            d = Path(vaults['行测']) / '训练/外观/美术/子地图背景'; d.mkdir(parents=True, exist_ok=True)
            for _f, name, rel, *_r in _art.slots('行测'):
                if rel in ('beauty/page/train.webp', 'beauty/page/train-day.webp', 'beauty/page/train-night.webp'):
                    (d / (name + '.png')).write_bytes(png)
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
        if '--review362-fixture' in sys.argv:
            from rpg import ai
            ai.available = lambda: True
            def fake_independent(messages, **kwargs):
                return '**结论：选 A**\n\n自编独立解析：先核对题干条件。\n\n| 选项 | 判断 | 理由 |\n|---|---|---|\n| A | 正确 | 符合条件 |\n| B | 错误 | 缺少条件 |'
            ai.chat = fake_independent
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
        if '--fixes359-fixture' in sys.argv:
            from tests.fixture359 import install
            with api.open_game() as g:install(g)
        if '--tablet-fixture' in sys.argv:
            from tests.fixture_tablet import install
            with api.open_game() as g:install(g)
        srv = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        api.RUNTIME.update(port=srv.server_port, lan=False)
        print('UI-READY http://127.0.0.1:%d' % srv.server_port, flush=True)
        srv.serve_forever()


if __name__ == '__main__':
    main()
