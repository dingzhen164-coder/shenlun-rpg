"""宗门人物浏览器检查：隔离假HOME、自编图片、假AI与物品，不读取用户资料。"""
import base64
import os
import sys
import tempfile
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
for key in ('DEEPSEEK_API_KEY', 'SHENLUN_AI_BASE_URL', 'SHENLUN_SUBJECT', 'XINGCE_VAULT', 'SHENLUN_VAULT'):
    os.environ.pop(key, None)


def main():
    subject = '申论' if '申论' in sys.argv else '行测'
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        with patch.object(Path, 'home', return_value=root/'home'):
            from rpg import api, paths, characters, store
            paths.SETTINGS_DIR = root/'home/settings'
            paths.SETTINGS_FILE = paths.SETTINGS_DIR/'settings.json'
            paths.LEGACY_SETTINGS = root/'no-legacy.json'
            vaults = {}
            for sub in ('行测','申论'):
                v=root/sub; (v/'copilot/skills/自编').mkdir(parents=True)
                if sub=='行测':(v/'FB模考试卷复盘/板块复盘').mkdir(parents=True)
                vaults[sub]=str(v);paths.Paths(v,sub).ensure_train_dir()
            paths.save_settings(dict(subject=subject, vaults=vaults))
            if subject=='行测':
                with api.open_game() as g:
                    folder=characters.install(g)
                    (folder/'规则.md').write_text('- 空场概率：0\n- 同场人数：2\n- 相遇间隔分钟：30\n', encoding="utf-8")
                    g.state['bag']={'护心丹':20}
                    # 自编小图片用于核验两条资源映射与HTTP请求，不使用真人素材。
                    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
                    for d in folder.iterdir():
                        if d.is_dir() and d.name.startswith('xc-'):
                            for kind in ('three-quarter','bust'):
                                (d/'立绘'/(d.name+'-'+kind+'.png')).write_bytes(png)
            api.ai.available=lambda:True

            def fake_chat(messages, **kwargs):
                if 'AI生成的游戏对话' in messages[0]['content']:
                    if store.LOCK._is_owned():
                        raise RuntimeError('人物AI调用不应持有存档锁')
                    text=messages[-1]['content']
                    if '__fail__' in text:raise api.ai.AIError('自编失败，请重试')
                    if '__delay__' in text:time.sleep(.7)
                    return ('自编论道：' if '现在是论道' in messages[0]['content'] else '自编交流：')+text
                return '自编导师问候'
            api.ai.chat=fake_chat
            server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler)
            api.RUNTIME.update(port=server.server_port,lan=False)
            print('UI-READY http://127.0.0.1:%d'%server.server_port,flush=True)
            server.serve_forever()


if __name__=='__main__':main()
