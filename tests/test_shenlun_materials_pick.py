"""申论题按题匹配材料：题干写明的资料、手动选定、写不明时退回整卷。仅自编材料。"""
import os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('SHENLUN_SUBJECT', '申论')
from rpg import paths, api, shenlun_bank as bank

MATS = [{'id': str(i), 'label': '材料%d' % i, 'text': '材料%d：社区便民服务改革，居民办事需求增长。' % i + ('独有的引文句子出现在第四则。' if i == 4 else '')} for i in range(1, 6)]


class InferTest(unittest.TestCase):
    def ids(self, stem):
        return bank.infer_material_ids(stem, MATS)

    def test_explicit_references(self):
        self.assertEqual(self.ids('请根据“给定资料2”，概括做法'), ['2'])
        self.assertEqual(self.ids('结合给定资料1～3，分析意义'), ['1', '2', '3'])
        self.assertEqual(self.ids('根据资料二、四，提出对策'), ['2', '4'])
        self.assertEqual(self.ids('资料3至5'), ['3', '4', '5'])

    def test_not_guessed_when_unclear(self):
        self.assertEqual(self.ids('全部给定资料，写一篇文章'), [])
        self.assertEqual(self.ids('请根据“给定资料[materialid]7901228[/materialid]”概述'), [])
        self.assertEqual(self.ids('资料1-5'), [])  # 等于全卷
        self.assertEqual(self.ids('资料9'), [])  # 不存在的序号


class PickTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent.parent)
        root = Path(self.tmp.name); v = root / '库'; (v / 'copilot/skills/test').mkdir(parents=True)
        self.old = (paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths.LEGACY_SETTINGS)
        self.env = patch.dict(os.environ, {'SHENLUN_SUBJECT': '申论'}); self.env.start()
        paths.SETTINGS_DIR = root / 'home'; paths.SETTINGS_FILE = paths.SETTINGS_DIR / 'settings.json'; paths.LEGACY_SETTINGS = root / '无.json'
        paths.save_settings({'subject': '申论', 'vaults': {'申论': str(v)}})
        self.p = paths.Paths(v, '申论'); self.p.ensure_train_dir()
        bank.import_packages(self.p, {'title': '自编选材料卷', 'region': '自编', 'year': '2026', 'materials': MATS, 'questions': [
            {'type': '归纳概括', 'text': '请根据给定资料2，概括做法。', 'score': 15, 'limit': 200},
            {'type': '提出对策', 'text': '请提出对策。', 'score': 20, 'limit': 300},
            {'type': '提出对策', 'text': '“给定资料[materialid]123[/materialid]”提到：“独有的引文句子出现在第四则。”请谈对策。', 'score': 20, 'limit': 300}]})
        qs = bank.listing(self.p)[0]['questions']
        self.q1, self.q2, self.q3 = qs[0]['qid'], qs[1]['qid'], qs[2]['qid']

    def tearDown(self):
        paths.SETTINGS_DIR, paths.SETTINGS_FILE, paths.LEGACY_SETTINGS = self.old; self.env.stop(); self.tmp.cleanup()

    def test_stem_filters_and_unclear_keeps_all(self):
        q = bank.question(self.p, self.q1)
        self.assertEqual([m['id'] for m in q['materials']], ['2']); self.assertEqual(q['material_source'], 'stem')
        q = bank.question(self.p, self.q2)
        self.assertEqual(len(q['materials']), 5); self.assertEqual(q['material_source'], 'whole')  # 没点名具体材料=整套
        q = bank.question(self.p, self.q3)
        self.assertEqual(q['material_source'], 'all'); self.assertEqual(len(q['materials']), 5)  # 点名了但对不上，先显示全卷
        self.assertEqual((q['suggested_material_ids'], q['suggest_kind']), (['4'], 'quote'))

    def test_listing_and_auto_by_quote(self):
        sources = {x['qid']: x['material_source'] for x in bank.listing(self.p)[0]['questions']}
        self.assertEqual([sources[self.q1], sources[self.q2], sources[self.q3]], ['stem', 'whole', 'quote'])
        paper = bank.listing(self.p)[0]['id']
        self.assertEqual(bank.material_auto(self.p, paper), {'done': 1})
        q = bank.question(self.p, self.q3)
        self.assertEqual((q['material_source'], [m['id'] for m in q['materials']]), ('manual', ['4']))
        self.assertEqual(bank.material_auto(self.p, paper), {'done': 0})

    def test_manual_pick_overrides_and_resets(self):
        q = bank.material_pick(self.p, {'qid': self.q2, 'ids': ['4', '5']})
        self.assertEqual([m['id'] for m in q['materials']], ['4', '5']); self.assertEqual(q['material_source'], 'manual')
        self.assertEqual([m['id'] for m in bank.question(self.p, self.q2)['materials']], ['4', '5'])
        q = bank.material_pick(self.p, {'qid': self.q2, 'ids': []})
        self.assertEqual(q['material_source'], 'whole')
        with self.assertRaises(bank.BankError):
            bank.material_pick(self.p, {'qid': self.q2, 'ids': ['99']})

    def test_pick_does_not_touch_draft_or_marks_keys(self):
        before = bank.question(self.p, self.q2)['material_mark_keys'][3]
        bank.material_pick(self.p, {'qid': self.q2, 'ids': ['4']})
        self.assertEqual(bank.question(self.p, self.q2)['material_mark_keys'][0], before)
        self.assertEqual(bank.answer_get(self.p, self.q2)['revision'], 0)


if __name__ == '__main__':
    unittest.main()
