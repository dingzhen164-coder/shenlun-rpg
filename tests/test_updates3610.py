"""精简批注、旧缓存显式升级、误改日期校正；全部使用自编数据和假AI。"""
import copy
import json
import unittest
from unittest.mock import patch

from rpg import politics, config, art, paths
import tempfile
import hashlib
from pathlib import Path
from tests.test_politics import PoliticsTests
from tools.repair_exam_schedule import repair


class AnnotationTests(unittest.TestCase):
    setUp = PoliticsTests.setUp

    def test_three_fields_and_no_evidence(self):
        answer = {k: '自编简短说明。' for k in politics.FIELDS}
        with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value=json.dumps(answer)):
            note = politics.explain(self.pp, self.src, self.body)['note']
        self.assertEqual(note['version'], 4)
        self.assertEqual(set(note['explanation']), {'meaning', 'background', 'compare'})
        for word in ['稳定支持', '竞争性支持', '要素流动型开放', '提高与降低']:
            self.assertIn(word, politics.PROMPT)

    def test_enforced_half_length_and_preserve_v3_on_failed_upgrade(self):
        anchor = politics.validate_anchor(self.src, self.body)
        key = politics.digest(anchor)
        old = dict(anchor, key=key, version=3, explanation=dict(self.answer))
        politics.atomic_json(self.pp.train/'词义批注'/(politics.identity(self.src)+'.json'), {key:old})
        for field, limit in politics.LIMITS.items():
            answer = {k: '自编解释' for k in politics.FIELDS}
            answer[field] = '长' * (limit+1)
            with patch('rpg.politics.ai.available', return_value=True), patch('rpg.politics.ai.chat', return_value=json.dumps(answer)) as ai:
                self.assertEqual(politics.explain(self.pp,self.src,self.body)['note'],old)
                ai.assert_not_called()
                with self.assertRaises(politics.PoliticsError):
                    politics.explain(self.pp,self.src,dict(self.body,refresh=True))
            self.assertEqual(politics.list_notes(self.pp,self.src)[key],old)


class ScheduleRepairTests(unittest.TestCase):
    def test_default_date_and_only_two_leaf_changes(self):
        self.assertEqual(config.DEFAULT_RULES['目标日'], '2027-12-01')
        source={'xp':16455,'claimed':59,'gates':[], 'study_schedule':{'start':'2026-09-29','exam':'2026-11-30'},
                'events':[{'xp':16455}], 'mock_rewards':{'fake':'preserved'}}
        before=copy.deepcopy(source)
        out,score=repair(source,'2027-12-01',300,50,80,.7)
        self.assertEqual(source,before)
        self.assertEqual(out['claimed'],57)
        self.assertAlmostEqual(score,57.1208897,places=6)
        out['claimed']=59;out['study_schedule']['exam']='2026-11-30'
        self.assertEqual(out,source)

    def test_no_new_breakthrough_or_unsafe_gates(self):
        s={'xp':16455,'claimed':53,'gates':[], 'study_schedule':{'start':'2026-09-29','exam':'2026-11-30'}}
        self.assertEqual(repair(s,'2027-12-01',300,50,80,.7)[0]['claimed'],53)
        with self.assertRaises(ValueError):repair(dict(s,gates=[60]),'2027-12-01',300,50,80,.7)


class RetiredArtTests(unittest.TestCase):
    def test_only_exact_legacy_copy_falls_back_without_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            pp=paths.Paths(Path(tmp),'行测')
            f=art.art_dir(pp)/'子地图背景/观星峰.webp'
            f.parent.mkdir(parents=True)
            original=paths.WEB_DIR/'assets/beauty/scenes/xingce/train-zi.webp'
            f.write_bytes(original.read_bytes())
            rel='beauty/page/train-zi.webp'
            self.assertIsNone(art.lookup(pp,'行测',rel))
            self.assertNotIn(rel,dict(art.files(pp,'行测')))
            self.assertIn(rel,dict(art.available(pp,'行测')))
            self.assertEqual(f.read_bytes(),original.read_bytes())
            data=bytearray(f.read_bytes());data[-1]^=1;f.write_bytes(data)
            self.assertEqual(art.lookup(pp,'行测',rel),f,'同尺寸但编辑过的图仍是用户覆盖')


class Art3610Tests(unittest.TestCase):
    def test_three_native_4k_assets(self):
        from PIL import Image
        assets=paths.WEB_DIR/'assets/beauty'
        hashes=set()
        for rel in ['trial/hd/3610/selection','loading/3610/dawn','loading/3610/night']:
            file=assets/(rel+'.webp')
            meta=json.loads((assets/(rel+'.provenance.json')).read_text(encoding='utf-8'))
            with Image.open(file) as im:
                self.assertEqual(im.size,(3840,2880));self.assertEqual(im.mode,'RGB')
            digest=hashlib.sha256(file.read_bytes()).hexdigest();hashes.add(digest)
            self.assertEqual(meta['sha256'],digest)
            self.assertEqual(meta['bytes'],file.stat().st_size)
            self.assertLess(file.stat().st_size,12*1024*1024)
            self.assertFalse(meta['interpolated_upscale'])
            self.assertEqual(meta['grid'],[4,2])
            self.assertEqual({t['index'] for t in meta['tiles']},set(range(8)))
            for t in meta['tiles']:
                self.assertGreaterEqual(t['native'][0],t['w']);self.assertGreaterEqual(t['native'][1],t['h'])
        self.assertEqual(len(hashes),3)
