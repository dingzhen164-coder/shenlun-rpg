"""仅main发布：复用同树、同提交validate构建的三端包，不重新构建。

由build-exe.yml的publish调用。要求真正的双亲merge且与第二亲整树一致，
原构建/UI工作流成功、三个artifact齐全；先上传草稿并核对大小/摘要，再公开。
GitHub API/下载使用gh及当前仓库token；不读取用户库或凭据文件。
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def command(*args):
    return subprocess.check_output(args,text=True).strip()


def api(repo,path):
    return json.loads(command('gh','api','repos/'+repo+'/'+path))


def validated_run(runs,source):
    found=[r for r in runs if r.get('head_sha')==source and r.get('head_branch','').startswith('validate/')
           and r.get('event') in ('push','workflow_dispatch') and r.get('status')=='completed' and r.get('conclusion')=='success']
    if not found:raise RuntimeError('缺少同提交validate分支的成功验证，拒绝发布')
    return max(found,key=lambda r:r['id'])


def verify_assets(assets,expected):
    by_name={a['name']:a for a in assets}
    if set(by_name)!=set(expected):raise RuntimeError('草稿资源不齐或含意外文件，拒绝公开')
    for name,(size,digest) in expected.items():
        asset=by_name[name]
        if asset.get('size')!=size:raise RuntimeError(name+'资源大小不一致')
        if asset.get('digest') and asset['digest']!='sha256:'+digest:raise RuntimeError(name+'资源摘要不一致')


def main():
    repo=os.environ['GITHUB_REPOSITORY'];head=os.environ['GITHUB_SHA']
    if os.environ.get('GITHUB_REF')!='refs/heads/main':raise RuntimeError('只能从main发布')
    parents=command('git','rev-list','--parents','-n','1','HEAD').split()
    if len(parents)!=3 or parents[0]!=head:raise RuntimeError('发布须保留双亲merge提交')
    source=parents[2]
    if command('git','rev-parse','HEAD^{tree}')!=command('git','rev-parse',source+'^{tree}'):
        raise RuntimeError('main与已验证提交内容不同，须重新验证')
    run=validated_run(api(repo,'actions/workflows/build-exe.yml/runs?head_sha='+source+'&status=success&per_page=20')['workflow_runs'],source)
    if repo.endswith('/shenlun-rpg'):
        validated_run(api(repo,'actions/workflows/ui-check.yml/runs?head_sha='+source+'&status=success&per_page=20')['workflow_runs'],source)
        stem,title='gongkao-simulator','公考模拟器'
    elif repo.endswith('/fakao-rpg'):stem,title='fakao-mage','法师成长记'
    else:raise RuntimeError('未知发布仓库')
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from rpg import changelog
    from rpg.version import VERSION
    req=json.loads(Path('.github/release-request.json').read_text(encoding='utf-8'))
    if req['version']!=VERSION:raise RuntimeError('发布请求版本与程序不符')
    entries=changelog.entries()
    if not entries or entries[0]['version']!=VERSION:raise RuntimeError('缺少本版更新说明')
    tag='v'+VERSION
    # 允许失败后继续同版本草稿；已经公开的版本不覆盖。
    releases=api(repo,'releases?per_page=30')
    existing=next((r for r in releases if r['tag_name']==tag),None)
    if existing and (not existing['draft'] or existing['target_commitish']!=head):raise RuntimeError('此版本已公开或草稿目标不同，拒绝覆盖')
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);expected={};files=[]
        for platform,name in [('windows',stem+'.exe'),('apk',stem+'.apk'),('mac',stem+'-mac.zip')]:
            folder=root/platform
            subprocess.run(['gh','run','download',str(run['id']),'--repo',repo,'--name','package-'+platform,'--dir',str(folder)],check=True)
            contents=[f for f in folder.rglob('*') if f.is_file()]
            if len(contents)!=1 or contents[0].name!=name:raise RuntimeError(platform+'构建资源不符')
            file=contents[0];data=file.read_bytes()
            if len(data)<10000:raise RuntimeError(name+'安装包过小')
            expected[name]=(len(data),hashlib.sha256(data).hexdigest());files.append(file)
        checks=root/'SHA256SUMS';checks.write_text(''.join(d+'  '+n+'\n' for n,(_,d) in expected.items()),encoding='utf-8')
        data=checks.read_bytes();expected[checks.name]=(len(data),hashlib.sha256(data).hexdigest());files.append(checks)
        notes=root/'notes.md';notes.write_text('\n'.join('- '+x for x in entries[0]['items'])+'\n',encoding='utf-8')
        if not existing:
            subprocess.run(['gh','release','create',tag,'--repo',repo,'--draft','--target',head,'--title',title+' v'+VERSION,'--notes-file',str(notes)],check=True)
        subprocess.run(['gh','release','upload',tag,'--repo',repo,'--clobber']+[str(f) for f in files],check=True)
        release=next(r for r in api(repo,'releases?per_page=30') if r['tag_name']==tag);verify_assets(release['assets'],expected)
        subprocess.run(['gh','release','edit',tag,'--repo',repo,'--draft=false','--latest'],check=True)
        print('RELEASE-OK',tag,'validated-run',run['id'],'source',source)
        print(json.dumps(expected,ensure_ascii=False))


if __name__=='__main__':main()
