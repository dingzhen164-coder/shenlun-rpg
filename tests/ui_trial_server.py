"""试炼塔交互夹具：仅临时假HOME/自编题、历史与续做，不连接AI。"""
import os
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for key in ('DEEPSEEK_API_KEY', 'SHENLUN_AI_BASE_URL', 'SHENLUN_SUBJECT', 'XINGCE_VAULT', 'SHENLUN_VAULT', 'FAKAO_VAULT'):
    os.environ.pop(key, None)


def install(g):
    from rpg import question_bank as bank
    names = ['逻辑填空', '片段阅读'] if '--teachers-fixture' in sys.argv else bank.boards(g)[:2]
    for board in names:
        text = ''
        for paper in range(1, 31):
            for num in range(1, 4):
                ident = '自编修习-%02d-%02d' % (paper, num)
                text += ('\n## 题目 %s\n### 知识点\n自编方法%d\n### 题干\n自编练习：选择符合条件的答案。\n'
                         '### 选项\nA. 符合\nB. 不符合\nC. 无关\nD. 未说明\n### 答案\nA\n### 解析\n自编解析：先核对条件。\n') % (ident, num)
        (g.paths.train/'题库'/(board+'真题.md')).write_text(text, encoding='utf-8')
    questions = sorted([q for board in names for q in bank.read(g.paths, board)[0]], key=lambda q: (q['id'], q['board']))
    data = bank.state(g)
    for i, q in enumerate(questions[:111]):
        ok = i % 5 != 0
        data['records'][q['key']] = {'question': q, 'history': [{'date': g.t, 'ok': ok, 'answer': 'A' if ok else 'B', 'mode': 'new'}], 'wrong': not ok, 'streak': 1 if ok else 0}
    bank.begin(g, '套:自编修习-24', 'new')
    # 最后一组知识点已答完但尚未结束复盘，目录必须仍允许继续。
    slot = '点:'+names[1]+':自编方法3'
    run = bank.begin(g, slot, 'new')
    for q in run['questions']:
        data['records'][q['key']] = {'question': q, 'history': [{'date': g.t, 'ok': True, 'answer': 'A', 'mode': 'new'}], 'wrong': False, 'streak': 1}
    run.update(phase='review', results=[{'date': g.t, 'ok': True, 'first': True, 'answer': 'A', 'mode': 'new'} for _ in run['questions']], exam=True, picks={str(i): 'A' for i in range(len(run['questions']))})
    bank.finish(g, run, keep=True)
    return names


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        with patch.object(Path, 'home', return_value=root/'home'):
            from rpg import api, paths
            paths.SETTINGS_DIR = root/'home/settings'
            paths.SETTINGS_FILE = paths.SETTINGS_DIR/'settings.json'
            paths.LEGACY_SETTINGS = root/'no-legacy.json'
            vaults = {}
            for subject in ('行测', '申论'):
                v = root/subject
                (v/'copilot/skills/自编').mkdir(parents=True)
                if subject == '行测':
                    (v/'FB模考试卷复盘/板块复盘').mkdir(parents=True)
                paths.Paths(v, subject).ensure_train_dir()
                vaults[subject] = str(v)
            if '--old-room-exports' in sys.argv:
                from rpg import art
                folder = art.art_dir(paths.Paths(Path(vaults['行测']), '行测')) / '子地图背景'
                folder.mkdir(parents=True, exist_ok=True)
                image = (paths.WEB_DIR / 'assets/beauty/scenes/xingce/hd/381/settings-day.webp').read_bytes()
                for name in ['洞府', '洞府-修为与突破', '试炼塔', '宗门大比', '藏经阁', '天机台', '设置']:
                    (folder / (name + '.webp')).write_bytes(image)
            paths.save_settings({'subject': '行测', 'vaults': vaults})
            with api.open_game() as g:
                install(g)
            api.ai.available = lambda: '--teachers-fixture' in sys.argv
            if '--teachers-fixture' in sys.argv:
                def fake_chat(messages, **kwargs):
                    text = str(messages)
                    if '猫专属标记' in text and '句号专属标记' in text:
                        raise AssertionError('不能混入两位老师的心法/历史')
                    if '猫专属标记' in text:
                        return '猫专属讲解：按所选完整文档核对条件。'
                    if '句号专属标记' in text:
                        return '句号专属讲解：按所选完整文档核对条件。'
                    return '自编测试回复'
                api.ai.chat = fake_chat
            server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
            api.RUNTIME.update(port=server.server_port, lan=False)
            print('UI-READY http://127.0.0.1:%d' % server.server_port, flush=True)
            server.serve_forever()


if __name__ == '__main__':
    main()
