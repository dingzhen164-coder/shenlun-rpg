"""构建前下载用户授权随包的时政资料并核对摘要；原文及答案不进入源码仓库。

仅build-exe.yml的电脑打包调用，下载位置固定rpg/data/political_atlas.json。
源码运行可把同一资料放在此处，或使用训练/时政知识地图/内容.json。
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rpg import net


def main():
    spec = json.loads((ROOT / 'rpg/data/political_atlas_seed.json').read_text(encoding='utf-8'))
    file = ROOT / 'rpg/data/political_atlas.json'
    if file.exists() and hashlib.sha256(file.read_bytes()).hexdigest() == spec['sha256']:
        print('ATLAS-SEED-OK cached')
        return
    with net.urlopen(spec['url'], timeout=60) as response:
        data = response.read(spec['size'] + 1)
    if len(data) != spec['size'] or hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise RuntimeError('时政资料大小或SHA256不匹配，停止打包')
    json.loads(data.decode('utf-8'))
    file.write_bytes(data)
    print('ATLAS-SEED-OK', spec['sha256'])


if __name__ == '__main__':
    main()
