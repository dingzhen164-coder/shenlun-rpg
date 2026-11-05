"""3.8.1原生分时4K清单与无放大来源契约；不依赖开发机原生块路径。"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from rpg import art, paths


class Art381Test(unittest.TestCase):
    def test_old_export_does_not_hide_native_but_custom_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / '库'
            (vault / 'copilot/skills').mkdir(parents=True)
            p = paths.Paths(vault, '行测')
            p.ensure_train_dir()
            folder = art.art_dir(p) / '子地图背景'
            folder.mkdir(parents=True)
            own = folder / '洞府-修为与突破.webp'
            legacy = paths.WEB_DIR / 'assets/beauty/scenes/xingce/dwelling-growth.webp'
            own.write_bytes(legacy.read_bytes())
            before = own.read_bytes()
            self.assertIsNone(art.lookup(p, '行测', 'beauty/page/dwelling-growth.webp'))
            self.assertNotIn('beauty/page/dwelling-growth.webp', dict(art.files(p, '行测')))
            self.assertEqual(own.read_bytes(), before, '不删除或修改旧导出模板')
            own.write_bytes(b'user original scene')
            self.assertEqual(art.lookup(p, '行测', 'beauty/page/dwelling-growth.webp'), own)

    def test_native_scenes_and_slots(self):
        assets = paths.WEB_DIR / 'assets'
        manifest = art.builtin_map('行测')
        if not manifest:
            self.skipTest('公考场景不随法考打包')
        names = {scene + '-' + phase for scene in ('dwelling', 'bank', 'contest', 'skeleton', 'settings') for phase in ('day', 'dusk', 'night')}
        names |= {'bank-dawn'} | {'selection-' + phase for phase in ('dawn', 'day', 'dusk', 'night')}
        folder = assets / 'beauty/scenes/xingce/hd/381'
        self.assertEqual({p.stem for p in folder.glob('*.webp')}, names)
        slots = {row[2] for row in art.slots('行测')}
        hashes = set()
        for name in names:
            rel = ('beauty/trial/' if name.startswith('selection') else 'beauty/page/') + name + '.webp'
            self.assertIn(rel, slots)
            image = folder / (name + '.webp')
            self.assertEqual(assets / manifest[rel], image)
            with Image.open(image) as im:
                self.assertEqual(im.size, (3840, 2880))
            meta = json.loads(image.with_suffix('.provenance.json').read_text(encoding='utf-8'))
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            self.assertEqual(meta['sha256'], digest)
            self.assertEqual(meta['bytes'], image.stat().st_size)
            self.assertFalse(meta['interpolated_upscale'])
            self.assertEqual(len(meta['tiles']), 8)
            for tile in meta['tiles']:
                self.assertGreaterEqual(tile['native'][0], tile['w'])
                self.assertGreaterEqual(tile['native'][1], tile['h'])
                self.assertRegex(tile['sha256'], r'^[0-9a-f]{64}$')
            self.assertLessEqual(image.stat().st_size, 8 * 1024 * 1024)
            hashes.add(digest)
        self.assertEqual(len(hashes), 20, '时段必须是独立重绘文件而非别名复用（2026-11 天机台三张改为思过崖，见下一项）')

    def test_siguo_cliff_scene_replaces_tianji(self):
        """行测天机台改为思过崖：页面背景指向悬崖昼/夜图（横屏，黄橙像素很少），不再有黄昏专图。"""
        assets = paths.WEB_DIR / 'assets'
        manifest = art.builtin_map('行测')
        if not manifest:
            self.skipTest('公考场景不随法考打包')
        for rel, phase in (('beauty/page/tianji-day.webp', 'day'), ('beauty/page/tianji-night.webp', 'night'), ('beauty/page/tianji.webp', 'day')):
            self.assertEqual(manifest[rel], 'beauty/scenes/xingce/hd/siguo/siguo-%s.webp' % phase)
            with Image.open(assets / manifest[rel]) as im:
                self.assertTrue(1.33 <= im.size[0] / im.size[1] <= 1.78)
        self.assertNotIn('beauty/page/tianji-dusk.webp', manifest)


if __name__ == '__main__':
    unittest.main()
