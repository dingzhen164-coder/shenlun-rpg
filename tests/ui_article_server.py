"""Playwright专用的隔离申论库及自编文章服务，绝不读取用户HOME或访问真实文章来源。"""
import datetime as dt
import os
import sys
import tempfile
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ['SHENLUN_SUBJECT'] = '申论'
from rpg import paths, articles, api


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths.SETTINGS_DIR = root / 'home'
        paths.SETTINGS_FILE = paths.SETTINGS_DIR / 'settings.json'
        paths.LEGACY_SETTINGS = root / '不存在.json'
        v = root / '申论库'
        (v / 'copilot/skills/test').mkdir(parents=True)
        paths.save_settings({'subject': '申论', 'vaults': {'申论': str(v)}})
        p = paths.Paths(v, '申论')
        p.ensure_train_dir()
        paras = ['科技的价值在于服务群众。完善基层公共服务，需要从群众实际需求出发，既关注办事效率，也关注老年人等群体的使用体验。',
                 '一是明确需求。通过走访调研了解高频事项，将群众反馈转化为服务改进清单。二是协同办理。优化部门之间的信息流转，减少重复提交材料。三是保留线下渠道。让不熟悉数字设备的群众同样能够便捷办事。',
                 '提升服务水平，要建立反馈、办理、回访的闭环。不能只看系统上线了多少功能，更要看群众少跑了多少趟、难题解决了多少件。'] * 6
        today = dt.date.today().isoformat()
        articles.save_article(p, {'id': 'abcd1234', 'title': '让科技服务走进基层，让群众办事更加便利', 'source': '自编验证文章', 'category': '科技', 'url': '', 'date': today, 'paras': paras})
        articles.save_jd(p, 'abcd1234', {'theme': '让技术创新回应群众需要', 'points': ['从群众需求出发', '部门协同减少重复提交', '保留线下服务渠道'], 'structure': ['发现问题', '优化流程', '回访改进'], 'quotes': [], 'materials': [], 'tixing': ['提出对策'], 'writing': '结合具体需求说明措施和成效。'})
        base = 'http://fixture.test/'
        fake = {base: ''.join('<a href="/art/%d.html">%s</a>' % (i, t) for i, t in enumerate(['科技创新服务人民', '科技赋能基层治理', '绿色发展的生态文章']))}
        for i, t in enumerate(['科技创新服务人民', '科技赋能基层治理', '绿色发展的生态文章']):
            fake[base + 'art/%d.html' % i] = '<meta name="publishdate" content="%s"><h1>%s</h1><p>%s</p>' % (today, t, paras[0] * 5)
        articles.fetch = fake.__getitem__
        articles._write_custom(p, [{'name': '本地测试源', 'url': base, 'pat': r'/art/\d+\.html', 'category': ''}])
        server = ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
        api.RUNTIME.update(port=server.server_port, lan=False)
        print('UI-READY http://127.0.0.1:%d' % server.server_port, flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
