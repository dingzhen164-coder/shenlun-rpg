"""整卷模拟考试交互夹具：临时假HOME，自编130题（第1001季），拆分PDF用自编数据代替，不连接AI。"""
import os
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for key in ('DEEPSEEK_API_KEY', 'SHENLUN_AI_BASE_URL', 'SHENLUN_SUBJECT', 'XINGCE_VAULT', 'SHENLUN_VAULT', 'FAKAO_VAULT'):
    os.environ.pop(key, None)

NAME = '花生26下模拟卷第一套'


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        with patch.object(Path, 'home', return_value=root/'home'):
            from rpg import api, importer, paths
            from tests.test_exam_room import blank_paper
            paths.SETTINGS_DIR = root/'home/settings'
            paths.SETTINGS_FILE = paths.SETTINGS_DIR/'settings.json'
            paths.LEGACY_SETTINGS = root/'no-legacy.json'
            vaults = {}
            for subject in ('行测', '申论'):
                v = root/subject
                (v/'copilot/skills/自编').mkdir(parents=True)
                paths.Paths(v, subject).ensure_train_dir()
                vaults[subject] = str(v)
            paths.save_settings({'subject': '行测', 'vaults': vaults})

            def fake_split(paths_, body):
                number = int(body['file'].split('季')[0].lstrip('第'))
                blank_paper(paths_.train/('模考复盘/第%d季' % number), unknown={5, 6})
                return {'ready': 130, 'fix': 0}
            importer.split_pdf = fake_split
            importer.split_script = lambda p: True
            importer.has_pymupdf = lambda: True
            with api.open_game() as g:
                blank_paper(g.paths.train/'模考复盘/第1001季')
                g.state.setdefault('mocks', {})['1001'] = {'name': NAME}
            api.ai.available = lambda: False
            server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
            api.RUNTIME.update(port=server.server_port, lan=False)
            print('UI-READY http://127.0.0.1:%d' % server.server_port, flush=True)
            server.serve_forever()


if __name__ == '__main__':
    main()
