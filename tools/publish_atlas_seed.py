"""GitHub Actions手动资料通道：两个gzip分块仅暂存Release草稿，合并校验后公开。

由build-exe.yml workflow_dispatch调用；不在Git保存原文，不输出输入内容。
使用runner现有GH_TOKEN发布本仓库资料资产，不需要用户额外密钥。
"""
import base64
import gzip
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

TAG = 'political-atlas-20261020'


def gh(*args, **kwargs):
    return subprocess.run(['gh'] + list(args), check=True, **kwargs)


def main():
    if os.environ.get('GITHUB_REPOSITORY') != 'dingzhen164-coder/shenlun-rpg':
        raise RuntimeError('资料通道只用于公考仓库')
    repo = os.environ['GITHUB_REPOSITORY']
    part = os.environ.get('ATLAS_PART', '')
    if part not in ('0', '1', 'finalize'):
        raise RuntimeError('资料分块编号无效')
    spec = json.loads(Path('rpg/data/political_atlas_seed.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        if part != 'finalize':
            payload = base64.b64decode(os.environ['ATLAS_PAYLOAD'], validate=True)
            if not 1 <= len(payload) <= 48000:
                raise RuntimeError('资料分块大小无效')
            result = subprocess.run(['gh', 'release', 'view', TAG, '--repo', repo, '--json', 'isDraft'], capture_output=True, text=True)
            if result.returncode:
                gh('release', 'create', TAG, '--repo', repo, '--draft', '--prerelease', '--target', 'main', '--title', '时政知识地图资料 · 2026-10-20', '--notes', '用户提供的时政资料。随包构建前核对固定SHA256，独立于源码保存。')
            elif not json.loads(result.stdout)['isDraft']:
                raise RuntimeError('资料已公开，拒绝覆盖')
            file = root / ('seed.part' + part)
            file.write_bytes(payload)
            gh('release', 'upload', TAG, '--repo', repo, '--clobber', str(file))
            print('ATLAS-PART-OK', part)
            return
        gh('release', 'download', TAG, '--repo', repo, '--pattern', 'seed.part*', '--dir', str(root))
        data = gzip.decompress((root / 'seed.part0').read_bytes() + (root / 'seed.part1').read_bytes())
        if len(data) != spec['size'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise RuntimeError('资料SHA256或大小不符，保持草稿不公开')
        json.loads(data.decode('utf-8'))
        file = root / 'political-atlas.json'
        file.write_bytes(data)
        gh('release', 'upload', TAG, '--repo', repo, '--clobber', str(file))
        for name in ('seed.part0', 'seed.part1'):
            gh('release', 'delete-asset', TAG, name, '--repo', repo, '--yes')
        gh('release', 'edit', TAG, '--repo', repo, '--draft=false', '--prerelease', '--latest=false')
        print('ATLAS-CONTENT-OK', spec['sha256'])


if __name__ == '__main__':
    main()
