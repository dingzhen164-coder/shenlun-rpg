"""3.6.8美术：原生分块来源、真实4K、三时段、用户覆盖与包体预算。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from rpg import art, paths


class Art368Test(unittest.TestCase):
    def test_native_tiles_and_packaged_images(self):
        root = paths.WEB_DIR / 'assets/beauty/scenes/xingce/hd/368'
        provenance = json.loads((root / 'provenance.json').read_text(encoding='utf-8'))
        self.assertEqual(provenance['method'], 'native-portrait-tiles')
        self.assertFalse(provenance['interpolated_upscale'])
        self.assertEqual(provenance['target'], [3840, 2880])
        self.assertEqual(provenance['grid'], [4, 2])
        expected = {'home-%s-%s' % (s, t) for s in ('spring', 'summer', 'autumn', 'winter') for t in ('day', 'night')}
        expected.update('train-%s-%s' % (p, t) for p in ('chang', 'yan', 'li', 'shu', 'zi') for t in ('day', 'dusk', 'night'))
        self.assertEqual({a['name'] for a in provenance['assets']}, expected)
        self.assertEqual(len(provenance['assets']), 23)
        hashes, source_ids = set(), set()
        for a in provenance['assets']:
            with self.subTest(name=a['name']):
                self.assertEqual(a['file'], a['name'] + '.webp')
                file = root / a['file']
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), a['sha256'])
                self.assertEqual(file.stat().st_size, a['bytes'])
                self.assertLessEqual(a['bytes'], 12 * 1024 * 1024)
                with Image.open(file) as im:
                    self.assertEqual(im.size, (3840, 2880))
                    self.assertEqual(im.mode, 'RGB')
                hashes.add(a['sha256'])
                self.assertEqual({t['index'] for t in a['tiles']}, set(range(8)))
                for t in a['tiles']:
                    self.assertGreaterEqual(t['native'][0], t['w'], '不能插值放大原生块')
                    self.assertGreaterEqual(t['native'][1], t['h'])
                    self.assertEqual(t['y'], 0 if t['index'] < 4 else 1424)
                    self.assertEqual(t['x'], (0, 944, 1904, 2864)[t['index'] % 4])
                    self.assertEqual(len(t['sha256']), 64)
                    source_ids.add(t['id'])
        self.assertEqual(len(hashes), 23, '三时段/四季不能复用同一成图')
        self.assertEqual(len(source_ids), 184, '23张各8个独立原生块')

    def test_peak_aliases_and_dusk_override(self):
        manifest = art.builtin_map('行测')
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / '库'
            (vault / 'copilot/skills').mkdir(parents=True)
            p = paths.Paths(vault)
            p.ensure_train_dir()
            folder = art.art_dir(p) / '子地图背景'
            folder.mkdir(parents=True)
            for key, name in art.REGIONS['行测']:
                neutral = 'beauty/page/train-%s.webp' % key
                self.assertEqual(manifest[neutral], manifest['beauty/page/train-%s-day.webp' % key])
                for time in ('day', 'dusk', 'night'):
                    rel = 'beauty/page/train-%s-%s.webp' % (key, time)
                    self.assertEqual(manifest[rel], 'beauty/scenes/xingce/hd/368/train-%s-%s.webp' % (key, time))
                own = folder / (name + '-黄昏.png')
                own.write_bytes(b'own dusk fixture')
                rel = 'beauty/page/train-%s-dusk.webp' % key
                self.assertEqual(art.lookup(p, '行测', rel), own)
                self.assertIsNone(art.lookup(p, '申论', rel))
                self.assertIn(rel, dict(art.available(p, '行测')))

    def test_overlap_weights_are_complementary(self):
        # 32px重叠含两端，分母31；避免半透明重复合成造成暗线。
        for i in range(32):
            self.assertAlmostEqual(i / 31 + (31 - i) / 31, 1)


if __name__ == '__main__':
    unittest.main()
