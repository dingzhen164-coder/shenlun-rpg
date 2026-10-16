"""一次性升级入口：由已安装的Mac App --run-script运行，不读题库、存档或API密钥。
同目录放本项目的download.py和update.py；仅补上下载重试，替换与回滚沿用App原有助手。
"""
import importlib.util
import sys
import time
from pathlib import Path


def load_module(name, file):
    spec=importlib.util.spec_from_file_location(name,str(file))
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def main():
    if sys.platform!='darwin':
        raise RuntimeError('此工具只用于已安装的公考模拟器Mac App')
    import rpg
    from rpg import version, paths
    if not paths.FROZEN or version.REPO!='dingzhen164-coder/shenlun-rpg':
        raise RuntimeError('请用工具中的.command启动，不要使用系统Python或其它应用')
    here=Path(__file__).resolve().parent
    rpg.download=load_module('rpg.download',here/'download.py')
    raw_download=rpg.download.archive
    previous=[0]
    def report(actual,total,attempt):
        now=time.monotonic()
        if now-previous[0]>=2 or (total and actual==total):
            previous[0]=now
            print('第%d次尝试：已下载 %.1f / %s MB'%(attempt,actual/1048576,('%.1f'%(total/1048576)) if total else '?'),flush=True)
    def monitored(*args,**kwargs):
        kwargs['progress']=report
        return raw_download(*args,**kwargs)
    rpg.download.archive=monitored
    updater=load_module('rpg.repair_update',here/'update.py')
    info=updater.check()
    print('当前版本：%s；正式版本：%s'%(info['current'],info['latest']),flush=True)
    if not info['newer']:
        print('已经是最新版，没有修改应用。',flush=True)
        return
    print('正在下载并校验更新包，显示下载大小；最多尝试3次，总等待不超过约5分钟。旧应用会保留到校验通过。',flush=True)
    result=updater.apply()
    print('校验通过，正在交给原更新助手替换并打开%s。'%result['version'],flush=True)
    time.sleep(3)  # 原更新器1.5秒后退出此进程，助手再替换，保留其启动失败回滚。


if __name__=='__main__':
    main()
