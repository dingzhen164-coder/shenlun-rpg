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

            from rpg import exam_scan

            def fake_split(paths_, pdf, number, engine=None, part_sizes=None):
                if '拆分失败' in Path(pdf).name:
                    raise exam_scan.ScanError('拆分失败：\n共解析0题（自编日志：这份PDF的版式拆分脚本不认识）')
                exam_scan.set_progress('识别页面文字', 3, 10)
                blank_paper(paths_.train/('模考复盘/第%d季' % number), unknown={5, 6})
                return {'found': 130, 'total': 130, 'missing': [], 'modules': {'政治理论': 20, '常识判断': 15, '言语理解': 30, '数量关系': 10, '判断推理': 35, '资料分析': 20},
                        'split_log': '按版面拆分：认出 130/130 题'}
            exam_scan.split = fake_split
            importer.has_pymupdf = lambda: True
            with api.open_game() as g:
                blank_paper(g.paths.train/'模考复盘/第1001季')
                att = g.paths.train/'模考复盘/第1001季/attachments'
                att.mkdir(parents=True, exist_ok=True)
                from PIL import Image
                Image.new('RGB', (600, 120), 'white').save(att/'O001-1.jpg')        # 第1题按“文字题”处理时留的原图
                g.state.setdefault('mocks', {})['1001'] = {'name': NAME}
                if '--ads' in sys.argv:       # 藏经阁「清除」用：在第1题下面放一整行广告，第2题的句子中间夹一段广告
                    f = sorted((g.paths.train/'模考复盘/第1001季').glob('[0-9][0-9]-*.md'))[0]
                    text = f.read_text(encoding='utf-8')
                    text = text.replace('### 1. ⚪\n自编条件题，仅用于隔离测试。', '### 1. ⚪\n自编条件题，仅用于隔离测试。\n一手最全公考资源加微信 biguo368', 1)
                    text = text.replace('### 2. ⚪\n自编条件题，仅用于隔离测试。', '### 2. ⚪\n自编条件题，仅用于隔离测试。一手最全公考资源 加微信biguo368 继续正文', 1)
                    f.write_text(text, encoding='utf-8')
            api.ai.available = lambda: False
            server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
            api.RUNTIME.update(port=server.server_port, lan=False)
            print('UI-READY http://127.0.0.1:%d' % server.server_port, flush=True)
            server.serve_forever()


if __name__ == '__main__':
    main()
