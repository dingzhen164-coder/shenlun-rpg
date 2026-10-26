"""大作文写作支架：立意拆解（按指纹缓存、依据必须出自材料）、提纲点评（引用必须出自提纲）。仅自编材料、假AI。"""
import os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('SHENLUN_SUBJECT', '申论')
from rpg import paths, shenlun_bank as bank, shenlun_essay as essay, shenlun_review as review

MAT = '社区推进便民服务改革，居民办事更方便。部门协同共享资料，减少重复提交。'
OUTLINE = '中心论点：服务要以居民需求为中心。\n分论点一：简化流程。\n分论点二：数据共享。'


class EssayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent.parent)
        root = Path(self.tmp.name); v = root / '库'; (v / 'copilot/skills/test').mkdir(parents=True)
        self.old = (paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths.LEGACY_SETTINGS)
        self.env = patch.dict(os.environ, {'SHENLUN_SUBJECT': '申论'}); self.env.start()
        paths.SETTINGS_DIR = root / 'home'; paths.SETTINGS_FILE = paths.SETTINGS_DIR / 'settings.json'; paths.LEGACY_SETTINGS = root / '无.json'
        paths.save_settings({'subject': '申论', 'vaults': {'申论': str(v)}})
        self.p = paths.Paths(v, '申论'); self.p.ensure_train_dir()
        bank.import_packages(self.p, {'title': '自编大作文卷', 'region': '自编', 'year': '2026',
            'materials': [{'id': '1', 'text': MAT}], 'questions': [
                {'type': '大作文', 'text': '请结合给定资料，以“服务”为题写一篇文章。（40分）不少于800字。', 'score': 40, 'limit': 1000,
                 'references': [{'answer': '隐藏的参考范文'}]},
                {'type': '归纳概括', 'text': '概括做法。', 'score': 15, 'limit': 200}]})
        qs = bank.listing(self.p)[0]['questions']
        self.essay_q = next(q['qid'] for q in qs if q['type'] == '大作文'); self.small_q = next(q['qid'] for q in qs if q['type'] != '大作文')
        self.calls = []

    def tearDown(self):
        paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths.LEGACY_SETTINGS = self.old; self.env.stop(); self.tmp.cleanup()

    def chat(self, bad_basis=False, bad_quote=False):
        def fake(msgs):
            self.calls.append(msgs)
            payload = msgs[1]['content']
            assert '隐藏的参考范文' not in payload      # 参考答案不能发给AI
            if '"outline"' in payload:
                return {'thesis': {'status': '切题', 'reason': '回应了服务主题'},
                        'parts': [{'quote': '分论点一：简化流程。' if not bad_quote else '提纲里没有的句子', 'comment': '可以补一句理由'}],
                        'material_use': [{'quote': '分论点二：数据共享。', 'material_quote': '部门协同共享资料，减少重复提交。', 'comment': '用得准确'}],
                        'next': '先把中心论点写成一句完整的话'}
            return {'task': '写议论文，回应服务主题', 'angles': [{'title': '以人为本', 'thesis': '服务要以居民需求为中心',
                    'basis': '居民办事更方便。' if not bad_basis else '材料里没有这句话', 'risk': '容易空谈口号'}], 'avoid': ['不要只列政策']}
        return fake

    def test_angles_cached_and_validated(self):
        out = essay.angles(self.p, self.essay_q, self.chat())
        self.assertEqual(out['angles'][0]['basis'], '居民办事更方便。')
        n = len(self.calls)
        self.assertEqual(essay.angles(self.p, self.essay_q, self.chat())['created'], out['created'])
        self.assertEqual(len(self.calls), n)              # 同题不重复调用
        essay.angles(self.p, self.essay_q, self.chat(), force=True)
        self.assertEqual(len(self.calls), n + 1)
        self.calls.clear()
        with self.assertRaises(review.ReviewError):
            essay.angles(self.p, self.essay_q, self.chat(bad_basis=True), force=True)
        self.assertEqual(len(self.calls), 2)              # 校验不过重试一次

    def test_only_for_big_essay(self):
        with self.assertRaises(review.ReviewError):
            essay.angles(self.p, self.small_q, self.chat())

    def test_outline_save_review_and_stale_review_dropped(self):
        with self.assertRaises(review.ReviewError):
            essay.outline_review(self.p, self.essay_q, self.chat())     # 没写提纲
        essay.outline_save(self.p, self.essay_q, OUTLINE)
        out = essay.outline_review(self.p, self.essay_q, self.chat())
        self.assertEqual(out['review']['thesis']['status'], '切题')
        self.assertEqual(essay.outline_save(self.p, self.essay_q, OUTLINE)['review']['next'], out['review']['next'])   # 文字没变保留点评
        self.assertNotIn('review', essay.outline_save(self.p, self.essay_q, OUTLINE + '\n分论点三：评估'))            # 改了就作废
        with self.assertRaises(review.ReviewError):
            essay.outline_save(self.p, self.essay_q, 'x' * 6001)

    def test_review_quotes_must_come_from_outline(self):
        essay.outline_save(self.p, self.essay_q, OUTLINE)
        with self.assertRaises(review.ReviewError):
            essay.outline_review(self.p, self.essay_q, self.chat(bad_quote=True))

    def test_state_reports_saved_items(self):
        s = essay.state(self.p, self.essay_q)
        self.assertEqual((s['angles'], s['outline']['text']), (None, ''))
        essay.angles(self.p, self.essay_q, self.chat()); essay.outline_save(self.p, self.essay_q, OUTLINE)
        s = essay.state(self.p, self.essay_q)
        self.assertTrue(s['angles'] and s['outline']['text'] == OUTLINE)


if __name__ == '__main__':
    unittest.main()
