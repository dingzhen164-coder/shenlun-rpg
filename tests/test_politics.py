"""时政批注的语境绑定、并发去重、失败不落盘及进度增量保存。全部自编资料/假AI。"""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from rpg import paths, politics
from tests.politics_fixture import atlas_data


class PoliticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pp = paths.Paths(Path(self.tmp.name), '行测')
        self.data = atlas_data()
        politics.atomic_json(self.pp.train / '时政知识地图/内容.json', self.data)
        self.src = politics.source(self.pp, {'source': 'atlas', 'material': 'm1'})
        paragraph = self.src['text']
        self.body = {'paragraph': paragraph, 'word': '主产区', 'start': paragraph.index('主产区'),
                     'end': paragraph.index('主产区') + 3}
        self.answer = {k: '对象在本句限定为主产区。' for k in politics.FIELDS}
        self.answer['evidence'] = '在主产区布局产能'

    def test_cached_reopen_without_api(self):
        with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value=json.dumps(self.answer)) as chat:
            first = politics.explain(self.pp, self.src, self.body)
            with patch('rpg.politics.ai.available', return_value=False):
                again = politics.explain(self.pp, self.src, self.body)
            self.assertFalse(first['cached'])
            self.assertTrue(again['cached'])
            self.assertEqual(chat.call_count, 1)
            self.assertEqual(len(politics.list_notes(self.pp, self.src)), 1)

    def test_concurrent_requests_charge_once(self):
        with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value=json.dumps(self.answer)) as chat:
            with ThreadPoolExecutor(max_workers=3) as pool:
                out = list(pool.map(lambda _: politics.explain(self.pp, self.src, self.body), range(3)))
            self.assertEqual(chat.call_count, 1)
            self.assertEqual(sum(not r['cached'] for r in out), 1)

    def test_wrong_context_and_offset_rejected_before_ai(self):
        for body in [dict(self.body, paragraph='伪造段落主产区'), dict(self.body, start=0), dict(self.body, end=True)]:
            with self.assertRaises(politics.PoliticsError), patch('rpg.politics.ai.chat') as chat:
                politics.explain(self.pp, self.src, body)
            chat.assert_not_called()

    def test_invalid_answers_not_saved(self):
        for answer in ['not json', json.dumps({'meaning': '不完整'}), json.dumps(dict(self.answer, evidence='捏造依据'))]:
            with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value=answer):
                with self.assertRaises(politics.PoliticsError):
                    politics.explain(self.pp, self.src, self.body)
            self.assertEqual(politics.list_notes(self.pp, self.src), {})

    def test_source_update_does_not_reuse_notes(self):
        with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value=json.dumps(self.answer)):
            politics.explain(self.pp, self.src, self.body)
        changed = dict(self.src, text=self.src['text'] + '这是新条件。')
        self.assertEqual(politics.list_notes(self.pp, changed), {})
        self.assertEqual(len(politics.list_notes(self.pp, self.src)), 1)

    def test_progress_merge_retry_and_validation(self):
        politics.set_progress(self.pp, {'field': 'status', 'id': 'm1', 'value': 'done'})
        politics.set_progress(self.pp, {'field': 'attempts', 'id': 1, 'value': {'choice': 'A', 'at': 'today'}})
        result = politics.progress(self.pp)
        self.assertEqual(result['status']['m1'], 'done')
        self.assertEqual(result['attempts']['1']['choice'], 'A')
        politics.set_progress(self.pp, {'field': 'attempts', 'id': 1, 'value': None})
        self.assertEqual(politics.progress(self.pp)['attempts'], {})
        with self.assertRaises(politics.PoliticsError):
            politics.set_progress(self.pp, {'field': 'status', 'id': 'missing', 'value': 'done'})

    def test_corrupt_notes_not_overwritten(self):
        file = self.pp.train / '词义批注' / (politics.identity(self.src) + '.json')
        file.parent.mkdir(parents=True)
        file.write_text('{bad', encoding='utf-8')
        with self.assertRaises(politics.PoliticsError):
            politics.list_notes(self.pp, self.src)
        self.assertEqual(file.read_text(encoding='utf-8'), '{bad')
