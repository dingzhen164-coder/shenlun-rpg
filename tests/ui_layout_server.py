"""给 tests/ui_layout_check.cjs 起服务：两科各一个临时库 + 临时本机设置，不碰用户数据、不连真 AI。
用法：python tests/ui_layout_server.py [行测|申论]（默认申论）。打印 “UI-READY 网址” 后一直运行。"""
import os
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.pop('SHENLUN_SUBJECT', None)
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
        srv = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        api.RUNTIME.update(port=srv.server_port, lan=False)
        print('UI-READY http://127.0.0.1:%d' % srv.server_port, flush=True)
        srv.serve_forever()


if __name__ == '__main__':
    main()
