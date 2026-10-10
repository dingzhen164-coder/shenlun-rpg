"""申论闭环浏览器夹具：自编试卷、假AI、隔离库，无真实题目或网络请求。"""
import json
import os
import sys
import tempfile
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ['SHENLUN_SUBJECT']='申论'
from rpg import paths,api,ai,shenlun_bank as bank
from test_shenlun_complete import PACKAGE,ANSWER

def fake(msgs,**kwargs):
    d=json.loads(msgs[1]['content'])
    if 'answer' not in d:
        return {'task':'报告服务优化措施，回应居民办事需要','points':[{'name':'走访需求','material_quote':'社区走访居民，收集办事需求。'},{'name':'资料共享','material_quote':'部门共享资料，减少重复提交。'}]}
    answer=d['answer']
    return {'points':[{'id':i+1,'hit':'full' if i==0 or '共享' in answer else 'none','quote':answer if i==0 or '共享' in answer else '', 'reason':'回应了材料中的措施','suggestion':'补充具体成效'} for i in range(2)], 'dimensions':[{'name':n,'level':4,'quote':answer,'reason':'表达与任务一致','improvement':'保持清晰'} for n in d['dimension_names']], 'checks':[{'name':'报告目的','status':'通过','quote':answer,'reason':'向有关单位报告服务优化措施'}], 'revisions':[{'quote':answer,'rewrite':'走访居民了解需求，推动部门资料共享，减少重复提交。','reason':'措施与成效相连接'}], 'lost':[],'summary':'措施清晰，继续把群众获得的便利写具体。'}

def main():
    with tempfile.TemporaryDirectory() as t:
        r=Path(t);v=r/'库';(v/'copilot/skills/test').mkdir(parents=True)
        paths.SETTINGS_DIR=r/'home';paths.SETTINGS_FILE=paths.SETTINGS_DIR/'settings.json';paths.LEGACY_SETTINGS=r/'无.json'
        paths.save_settings({'subject':'申论','vaults':{'申论':str(v)}})
        p=paths.Paths(v,'申论');p.ensure_train_dir();ai.chat_json=fake
        def source_start(p):
            result=bank.import_packages(p,dict(PACKAGE,title='2025自编下载验证卷',region='国考'))
            bank.JOBS[str(p.train)]={'running':False,'message':'录入完成','progress':100,'result':result}
            return bank.source_status(p)
        bank.source_start=source_start
        server=ThreadingHTTPServer(('127.0.0.1',0),api.Handler);api.RUNTIME.update(port=server.server_port,lan=False)
        print('UI-READY http://127.0.0.1:%d'%server.server_port,flush=True);server.serve_forever()
if __name__=='__main__':main()
