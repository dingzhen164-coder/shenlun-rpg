"""一次性升级入口：由已安装的Mac App --run-script运行，不读题库、存档或API密钥。
同目录放本项目的download.py和update.py；仅补上下载重试，替换与回滚沿用App原有助手。
"""
import importlib.util
import hashlib
import shutil
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
        # 缓存放在工具旁边，不放会被原更新器清理的临时替换目录。
        url,destination,size,digest,user_agent=args
        cache=here/'.update-cache'
        cache.mkdir(exist_ok=True)
        if cache.is_symlink():
            raise RuntimeError('工具缓存目录不能是符号链接，请重新解压工具')
        key=hashlib.sha256((url+'\n'+str(size)+'\n'+digest).encode('utf-8')).hexdigest()[:24]
        partial=cache/(key+'.zip.part')
        if partial.is_symlink():
            raise RuntimeError('下载缓存不能是符号链接，请重新解压工具')
        if partial.exists():
            print('发现缓存 %.1f MB，将校验并尝试续传。'%(partial.stat().st_size/1048576),flush=True)
        kwargs['progress']=report
        kwargs['resume']=True
        result=raw_download(url,partial,size,digest,user_agent,**kwargs)
        shutil.copyfile(partial,destination)
        return result
    rpg.download.archive=monitored
    updater=load_module('rpg.repair_update',here/'update.py')
    info=updater.check()
    print('当前版本：%s；正式版本：%s'%(info['current'],info['latest']),flush=True)
    if not info['newer']:
        print('已经是最新版，没有修改应用。',flush=True)
        return
    print('正在下载并校验更新包，显示下载大小；持续有数据就继续，不再限制总下载时间。网络60秒无数据则重试，失败缓存可供下次续传。',flush=True)
    result=updater.apply()
    print('校验通过，正在交给原更新助手替换并打开%s。'%result['version'],flush=True)
    time.sleep(3)  # 原更新器1.5秒后退出此进程，助手再替换，保留其启动失败回滚。


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('更新未完成：%s'%error,flush=True)
        print('未完成的下载保留在本工具的.update-cache目录。请保留整个工具文件夹，重新运行即可尝试续传。',flush=True)
        sys.exit(1)
