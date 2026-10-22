"""随包美术清单、单张人物、科目隔离与用户覆盖；只用临时文件。"""
import json
import tempfile
import unittest
from pathlib import Path
from rpg import art, paths


class BuiltinArtTest(unittest.TestCase):
    def test_packaged_assets_and_budget(self):
        assets = paths.WEB_DIR / 'assets'
        raw = json.loads((assets / 'beauty/builtin-art.json').read_text(encoding='utf-8'))
        expected = ['法考'] if (assets / 'academy').is_dir() and not (assets / 'sect').is_dir() else ['行测', '申论']
        self.assertEqual(set(raw), set(expected))
        unique = set()
        from PIL import Image
        for subject in expected:
            manifest = art.builtin_map(subject)
            self.assertEqual(set(raw[subject]), set(manifest), '清单不能含缺图')
            for key, _name in art.REGIONS[subject]:
                self.assertIn('beauty/page/train-%s.webp' % key, manifest)
            for key, _name in art.DWELLING_TABS[subject]:
                self.assertIn('beauty/page/dwelling-%s.webp' % key, manifest)
            for rel in manifest:
                p = art.builtin_asset(subject, rel); unique.add(p)
                with Image.open(p) as im:
                    im.verify()
            for _name, cid in art.PEERS.get(subject, []):
                self.assertEqual(set(art.character_portraits(None, subject, cid)), {'calm'})
            self.assertIsNone(art.builtin_asset(subject, '../../etc/passwd'))
        # 公考高清扩绘全景不再按350KiB压缩；独立夜景仍保留原预算。
        self.assertLess(sum(p.stat().st_size for p in unique), (128 if '行测' in expected else 10) * 1024 * 1024)
        if '申论' in expected:
            people = {k: v for k, v in raw['申论'].items() if k.startswith('beauty/portrait/')}
            self.assertEqual(len(people), 9)
            self.assertTrue(all(k.endswith('-calm.webp') for k in people))
            for cid in dict(art.SL_CHARS).values():
                self.assertEqual(set(art.character_portraits(None, '申论', cid)), {'calm'})
                with Image.open(art.builtin_asset('申论', 'beauty/portrait/sl-%s-calm.webp' % cid)) as im:
                    self.assertEqual(im.getchannel('A').getextrema(), (0, 255))

    def test_override_export_and_subject_isolation(self):
        manifest = json.loads((paths.WEB_DIR/'assets/beauty/builtin-art.json').read_text(encoding='utf-8'))
        subject = next(iter(manifest))
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)/'库'; (vault/'copilot/skills').mkdir(parents=True)
            p = paths.Paths(vault); p.ensure_train_dir()
            d = art.art_dir(p)/'子地图背景'; d.mkdir(parents=True)
            name = art.PLACES[subject][0]
            own = d/(name+'.png'); own.write_bytes(b'user artwork')
            rel = 'beauty/page/dwelling.webp'
            self.assertEqual(art.lookup(p, subject, rel), own)
            self.assertEqual(dict(art.available(p, subject))[rel], own.stat().st_mtime_ns)
            other = '法考' if subject != '法考' else '行测'
            self.assertIsNone(art.lookup(p, other, rel))
            before = own.read_bytes()
            art.export(p, subject, paths.WEB_DIR/'assets')
            self.assertEqual(own.read_bytes(), before)
            for key, label in art.REGIONS[subject]:
                self.assertTrue((d/(label+'.webp')).is_file())

    def test_dedicated_night_coverage(self):
        from PIL import Image
        if not art.builtin_map('行测'):
            self.skipTest('本科美术独立，法考不包含公考夜景')
        assets = paths.WEB_DIR / 'assets'
        unique = set()
        for subject in ('行测', '申论'):
            manifest = art.builtin_map(subject)
            for view in art.VIEWS:
                unique.add(assets / manifest['beauty/page/%s-night.webp' % view])
            for key, dest in manifest.items():
                if key.startswith('beauty/page/') and not key.endswith('-night.webp'):
                    night = manifest[key[:-5] + '-night.webp']
                    self.assertNotEqual(night, dest)
                    unique.add(assets / night)
        for kind in ('tower', 'gate', 'landscape'):
            p = art.builtin_asset('行测', 'beauty/trial/%s-night.webp' % kind)
            self.assertIsNotNone(p)
            unique.add(p)
            if kind != 'landscape':
                with Image.open(p) as im:
                    self.assertEqual(im.getchannel('A').getextrema(), (0, 255))
        self.assertEqual(len(unique), 28)
        for p in unique:
            with Image.open(p) as im:
                self.assertGreaterEqual(max(im.size), 1152)
            self.assertLessEqual(p.stat().st_size, 350 * 1024)
        for color in ('jade', 'vermilion', 'indigo'):
            with Image.open(assets / ('beauty/fx/sword-chibi-%s.webp' % color)) as im:
                self.assertEqual(im.getchannel('A').getextrema(), (0, 255))
        panoramas = [art.builtin_asset('行测', 'beauty/home/xingce-%s-%s.webp' % (season, time))
                     for season in ('spring', 'summer', 'autumn', 'winter') for time in ('day', 'night')]
        self.assertEqual(len(set(p.read_bytes() for p in panoramas)), 8)
        for p in panoramas:
            with Image.open(p) as im:
                self.assertEqual(im.size, (3840, 2880))
            self.assertIn('/hd/', p.as_posix())
            self.assertLessEqual(p.stat().st_size, 12 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
