"""2.4.1：千字两页、旧批注不丢、默认女性领导、申论取消两个时政接口。"""
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rpg import api, article_notes, articles, career, config, notes, paths, prompts, themes


class Update241Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = paths.Paths(Path(self.tmp.name), '申论')
        self.art = {'id': 'abcd1234', 'title': '自编排版测试', 'source': '测试', 'date': '2026-10-10',
                    'url': 'https://example.test/test', 'category': '科技',
                    'paras': ['创新服务群众，让基层治理更有温度。' * 4 for _ in range(16)]}
        articles.save_article(self.p, self.art)

    def tearDown(self):
        self.tmp.cleanup()

    def test_thousand_chars_fit_two_pages_without_truncation(self):
        self.assertGreater(sum(map(len, self.art['paras'])), 1000)
        b = notes.get(self.p, article_notes.open_book(self.p, self.art['id'])['id'])
        self.assertLessEqual(len(b['pages']), 2)
        self.assertEqual(''.join(''.join(p['article_lines']) for p in b['pages']).replace('　', ''), ''.join(self.art['paras']))

    def old_book(self, ink):
        nid = article_notes.open_book(self.p, self.art['id'])['id']
        b = notes.get(self.p, nid)
        b['article']['layout'] = 1
        b['text'], b['compiled'], b['revision'] = '保留心得', '整理好的笔记', 7
        b['pages'] = [{'article_lines': ['旧版原文'], 'strokes': [{'t': 'pen', 'c': '#000000', 'w': 3, 'p': [[60,275],[200,275]]}] if ink else []}]
        notes._file(self.p, nid).write_text(json.dumps(b, ensure_ascii=False), encoding='utf-8')
        return b

    def test_migrate_ink_archive_coordinates_revision_and_snapshot(self):
        old = self.old_book(True)
        # 用户后来编辑的文章不能改变已有批注本的原文快照。
        changed = dict(self.art, paras=['用户后来改写的原文'])
        articles.save_article(self.p, changed)
        r = article_notes.open_book(self.p, self.art['id'])
        archive = notes.get(self.p, r['archived'])
        self.assertEqual(archive['pages'], old['pages'])
        self.assertEqual(archive['article'], old['article'])
        new = notes.get(self.p, r['id'])
        self.assertEqual(new['article']['paras'], old['article']['paras'])
        self.assertEqual(new['text'], old['text'])
        self.assertEqual(new['compiled'], old['compiled'])
        self.assertEqual(new['revision'], 8)
        self.assertEqual(new['article']['layout'], 2)
        self.assertFalse(any(p['strokes'] for p in new['pages']))
        with self.assertRaises(notes.NotesError):
            notes.save(self.p, old)
        article_notes.open_book(self.p, self.art['id'])
        self.assertEqual(notes.get(self.p, r['archived'])['pages'], old['pages'])

    def test_migrate_unwritten_book_no_archive(self):
        self.old_book(False)
        r = article_notes.open_book(self.p, self.art['id'])
        self.assertFalse(r['archived'])
        self.assertEqual(len(notes.listing(self.p)), 1)

    def test_female_names_all_stages_and_old_persona_override(self):
        c = career.Career()
        for score in range(50, 85, 5):
            info = c.describe(score)
            self.assertEqual(info['leader']['gender'], '女')
            self.assertIn('女性直属领导', career.persona_patch(info)['导师人设'])
        p = config.Persona('- 官场.导师人设: 他很严肃', '官场')
        self.assertIn('旧人设里的男性代词以此为准', prompts.persona_system(p))
        self.assertNotIn('旧人设', prompts.persona_system(config.Persona('', '修仙')))
        self.assertEqual(themes.get('官场')['tutor_face'], '👩\u200d💼')

    def test_upgrade_only_official_names_preserves_custom_career(self):
        f = self.p.career
        f.parent.mkdir(parents=True, exist_ok=True)
        original = (paths.DEFAULTS_DIR / '申论/职务履历.md').read_text(encoding='utf-8').replace('周静宜', '周国梁').replace('陈知微', '我自定义的陈领导').replace('干了二十年基层', '我的自定义性格')
        f.write_text(original, encoding='utf-8')
        career.upgrade_defaults(self.p)
        current = f.read_text(encoding='utf-8')
        self.assertIn('领导: 周静宜', current)
        self.assertIn('我自定义的陈领导', current)
        self.assertIn('我的自定义性格', current)
        bak = f.with_name('职务履历.女性设定前.md')
        self.assertEqual(bak.read_text(encoding='utf-8'), original)
        career.upgrade_defaults(self.p)
        self.assertEqual(f.read_text(encoding='utf-8'), current)
        self.assertEqual(bak.read_text(encoding='utf-8'), original)

    def test_shenlun_removed_period_routes_without_deleting_files(self):
        sentinel = self.p.train / '旧资料.txt'
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text('原有时政资料', encoding='utf-8')
        @contextmanager
        def game(**kwargs):
            yield SimpleNamespace(subject='申论', paths=self.p)
        with patch.object(api, 'open_game', game):
            for fn in (api.tj_list, api.tj_get, api.tj_mark, api.tj_meta, api.tj_delete, api.tj_cards, api.tj_ask, api.tj_pdf):
                with self.assertRaisesRegex(api.ApiError, '取消'):
                    fn({})
        self.assertEqual(sentinel.read_text(encoding='utf-8'), '原有时政资料')
        @contextmanager
        def xingce(**kwargs):
            yield SimpleNamespace(subject='行测', paths=self.p)
        with patch.object(api, 'open_game', xingce):
            self.assertEqual(api._tj(lambda g: '仍可用'), '仍可用')
