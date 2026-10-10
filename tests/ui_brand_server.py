"""两科统一品牌浏览器验证：独立临时库和本机配置，无用户数据、无真实AI。"""
import os
import sys
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ.pop('SHENLUN_SUBJECT',None)
from rpg import paths,api

def main():
    with tempfile.TemporaryDirectory() as t:
        r=Path(t);paths.SETTINGS_DIR=r/'home';paths.SETTINGS_FILE=paths.SETTINGS_DIR/'settings.json';paths.LEGACY_SETTINGS=r/'无.json'
        vaults={}
        for subject in ['行测','申论']:
            v=r/subject;(v/'copilot/skills/test').mkdir(parents=True);vaults[subject]=str(v);paths.Paths(v,subject).ensure_train_dir()
        paths.save_settings({'subject':'申论','vaults':vaults})
        server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler);api.RUNTIME.update(port=server.server_port,lan=False)
        print('UI-READY http://127.0.0.1:%d'%server.server_port,flush=True);server.serve_forever()
if __name__=='__main__':main()
