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
        # 五步精读（新版）：词语 / 原文方向 / 金句都取自上面的正文；另放一篇旧版精读验证兼容
        articles.save_jd(p, 'abcd1234', {
            'version': 2,
            'step1': {'old_words': [{'term': '闭环', 'note': '从反馈到回访的完整链条'}], 'verbs': [{'term': '提升', 'note': '服务水平'}], 'new_terms': [{'term': '线下渠道', 'definition': '不熟悉数字设备的群众也能办事的窗口'}]},
            'step2': {'thesis': '让技术创新回应群众需要', 'parts': [{'point': '明确需求', 'kind': '提出对策'}, {'point': '协同办理', 'kind': '提出对策'}],
                      'paragraphs': [{'no': 1, 'summary': '科技要服务群众', 'type': '解释说明'}, {'no': 2, 'summary': '三条具体做法', 'type': '提出要求'}]},
            'step3': {'items': [{'direction': '优化部门之间的信息流转，减少重复提交材料', 'domain': '治理', 'landing': '打通部门数据，一次采集多方共享', 'source': '文中'},
                                {'direction': '让不熟悉数字设备的群众同样能够便捷办事', 'domain': '民生', 'landing': '保留人工窗口并设代办员', 'source': '参考做法'}]},
            'step4': {'quotes': [{'kind': '辩证论述', 'text': '不能只看系统上线了多少功能，更要看群众少跑了多少趟', 'use': '评价标准'}]},
            'step5': {'yuyan': [{'type': '主旨概括题', 'question': '这段文字意在强调什么？'}], 'shenlun': [{'type': '提出对策', 'question': '请根据材料，概括基层服务存在的问题并提出建议'}]}})
        articles.save_article(p, {'id': 'beef0001', 'title': '旧版精读的验证文章', 'source': '自编验证文章', 'category': '科技', 'url': '', 'date': today, 'paras': paras})
        articles.save_jd(p, 'beef0001', {'theme': '让技术创新回应群众需要', 'points': ['从群众需求出发'], 'structure': ['发现问题'], 'quotes': [], 'materials': [], 'tixing': ['提出对策'], 'writing': '结合具体需求说明措施和成效。'})
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
