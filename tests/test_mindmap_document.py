"""3.1.0：分级文档外部编辑、只读无写入、冲突保护与复习计时，全部使用临时库。"""
import copy
import datetime as dt
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rpg import api, cards, config, engine, mindmap, paths, store
import study_clock_fixture


class MindmapDocumentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = paths.Paths(Path(self.tmp.name))
        self.p.ensure_train_dir()
        self.root = {'data': {'text': '自编知识'}, 'children': [
            {'data': {'text': '方法 <script> & 条件'}, 'children': [
                {'data': {'text': '第一行\n第二行'}, 'children': []}]},
            {'data': {'text': '另一方法'}, 'children': []}]}
        mindmap._READERS.clear()
    def tearDown(self):
        self.tmp.cleanup()
    def create(self):
        return mindmap.create(self.p, '资料分析', '自编图', {'root': copy.deepcopy(self.root), 'layout':'mindMap'})
    def test_roundtrip_and_read_does_not_change_json(self):
        r = self.create()
        f = mindmap._file(self.p, '资料分析', r['name'])
        raw, stamp = f.read_bytes(), f.stat().st_mtime_ns
        for _ in range(2):
            d = mindmap.document(self.p, '资料分析', r['name'], False)
            self.assertEqual(d['data']['root'], self.root)
            self.assertEqual(mindmap.from_markdown(d['markdown'], '备用'), self.root)
        self.assertEqual((f.read_bytes(), f.stat().st_mtime_ns), (raw, stamp))
        self.assertTrue((self.p.vault / d['document_path']).is_file())
    def test_read_missing_creates_nothing(self):
        r = mindmap.document(self.p, '资料分析', '资料分析', False)
        self.assertEqual(r['document_path'], '')
        self.assertFalse(mindmap._file(self.p, '资料分析', '资料分析').exists())
    def test_external_edit_reload_and_optimistic_conflict(self):
        r = self.create()
        md = self.p.vault / r['document_path']
        changed = '# 新标题\n\n## 第一章\n- 外部编辑\n  - 子节点\n## 第二章\n正文\n'
        md.write_text(changed, encoding='utf-8')
        with self.assertRaises(mindmap.MapError):
            mindmap.save_document(self.p, '资料分析', r['name'], {'root':self.root}, r['document_revision'])
        with self.assertRaises(mindmap.MapError):
            mindmap.save_document(self.p, '资料分析', r['name'], {'root':self.root})
        self.assertEqual(md.read_text(encoding='utf-8'), changed)
        d = mindmap.document(self.p, '资料分析', r['name'], False)
        self.assertEqual(d['data']['root']['data']['text'], '新标题')
        self.assertEqual(d['data']['root']['children'][0]['children'][0]['data']['text'], '外部编辑')
        d['data']['root']['children'][1]['data']['text'] += ' 编辑器改动'
        saved = mindmap.save_document(self.p, '资料分析', d['name'], d['data'], d['document_revision'])
        self.assertNotEqual(saved['document_revision'], d['document_revision'])
        self.assertIn('编辑器改动', md.read_text(encoding='utf-8'))
    def test_legacy_json_and_rich_text(self):
        rich = {'root':{'data':{'text':'<p>根</p>','richText':True}, 'children':[{'data':{'text':'<p>甲</p><p>乙</p>','richText':True},'children':[]}]}}
        mindmap.save(self.p, '资料分析', '旧图', rich)
        r = mindmap.document(self.p, '资料分析', '旧图', False)
        self.assertEqual(r['markdown'], '# 根\n\n- 甲\n  乙\n')
        self.assertEqual(mindmap.get(self.p, '资料分析', '旧图')['data'], rich)
    def test_companion_rename_delete_and_collision(self):
        r = self.create()
        target = mindmap._file(self.p, '资料分析', '保留文档').with_suffix('.md')
        target.write_text('保留', encoding='utf-8')
        with self.assertRaises(mindmap.MapError):
            mindmap.rename(self.p, '资料分析', r['name'], '保留文档')
        new = mindmap.rename(self.p, '资料分析', r['name'], '新名字')
        f = mindmap._file(self.p, '资料分析', new['name'])
        self.assertTrue(f.with_suffix('.md').exists())
        mindmap.delete(self.p, '资料分析', new['name'])
        self.assertFalse(f.exists() or f.with_suffix('.md').exists())
        self.assertEqual(target.read_text(encoding='utf-8'), '保留')
    def test_md_symlink_cannot_read_outside_training(self):
        self.create()
        md = mindmap._file(self.p, '资料分析', '自编图').with_suffix('.md')
        md.unlink()
        outside = self.p.vault / '库外文档.md'
        outside.write_text('不可读取', encoding='utf-8')
        md.symlink_to(outside)
        with self.assertRaises(mindmap.MapError):
            mindmap.document(self.p, '资料分析', '自编图', False)
    def test_reader_scope_stop_and_expiry(self):
        self.create()
        token = mindmap.start_reading(self.p, '资料分析', '自编图')
        self.assertEqual(mindmap.reading(self.p, token), '资料分析')
        self.assertIsNone(mindmap.reading(paths.Paths(self.p.vault / '另一个库'), token))
        mindmap._READERS[token]['time'] -= 43201
        self.assertIsNone(mindmap.reading(self.p, token))
        mindmap.end_reading(token)
        self.assertIsNone(mindmap.reading(self.p, token))
    @study_clock_fixture.elapsed_heartbeats
    def test_api_reader_and_card_view_use_review_category(self):
        self.create()
        day = dt.date(2026,10,14)
        g = engine.Game(self.p, config.Rules(), config.Persona(), config.Lines(), store.new_state(day), day)
        g.store = SimpleNamespace(heartbeat=lambda:None)
        @contextmanager
        def game(*a, **kw):
            yield g
        with patch.object(api,'open_game',game), patch.object(api.tutor,'enrich',side_effect=lambda g,ev:ev):
            r = api.mm_get(dict(board='资料分析',name='自编图',readonly=True))
            self.assertIn('reading_token', r)
            self.assertFalse(api.heartbeat(dict(seconds=60,mindmap='伪造'))['studying'])
            hb = api.heartbeat(dict(seconds=60,mindmap=r['reading_token']))
            self.assertTrue(hb['studying'])
            self.assertEqual(hb['minutes'],1)
            self.assertEqual(g.state['seconds'][str(day)] - g.state.get('seconds_kind',{}).get(str(day),{}).get('practice',0),60)
            mindmap.end_reading(r['reading_token'])
            self.assertFalse(api.heartbeat(dict(seconds=60,mindmap=r['reading_token']))['studying'])
            c = cards.add(g,dict(deck='资料分析',type='问答',front='自编条件',back='自编回答'))
            cards.LAST_ANSWER['t']=0
            api.cards_info(dict(key=c['id']+'#1'))
            self.assertTrue(api.heartbeat(dict(seconds=60,cards=True,cards_board='资料分析'))['studying'])
            self.assertEqual(g.state['seconds'][str(day)] - g.state.get('seconds_kind',{}).get(str(day),{}).get('practice',0),120)
    def test_images_directory_and_cache_key(self):
        @contextmanager
        def game(*a, **kw):
            yield SimpleNamespace(paths=self.p)
        with patch.object(api,'open_game',game):
            empty = api.study_regions_images({})
            folder = self.p.vault / empty['folder']
            self.assertTrue(folder.is_dir())
            (folder/'万象峰.png').write_bytes(b'fixture')
            (folder/'忽略.md').write_text('忽略',encoding='utf-8')
            r = api.study_regions_images({})
            self.assertEqual(list(r['images']),['万象峰'])
            self.assertIn('&v=',r['images']['万象峰'])

if __name__ == '__main__':
    unittest.main()
