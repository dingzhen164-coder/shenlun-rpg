"""美术文件夹（rpg/art.py）：名字表、只认写死的名字、导出不覆盖、按科目区分。"""
import tempfile
import unittest
from pathlib import Path

from rpg import art, paths


class ArtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        v = Path(self.tmp.name) / "库"
        (v / "copilot/skills").mkdir(parents=True)
        self.p = paths.Paths(v)
        self.p.ensure_train_dir()
        self.assets = Path(self.tmp.name) / "assets"
        for rel in ("sect/xc-sect-day.webp", "guide/xc-qinghe-calm.webp", "beauty/audio/bgm/map-day.ogg"):
            f = self.assets / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b"builtin")

    def tearDown(self):
        self.tmp.cleanup()

    def test_slots_per_subject(self):
        for s in ("行测", "申论", "法考"):
            rels = [x[2] for x in art.slots(s)]
            self.assertEqual(len(rels), len(set(rels)), s + " 资源路径不能重复")
        self.assertIn("beauty/page/dwelling.webp", art.known("行测"))
        self.assertNotIn("guide/xc-qinghe-calm.webp", art.known("申论"))     # 申论还没有立绘
        self.assertIn("academy/portrait/mg-eileen-calm.webp", art.known("法考"))

    def test_lookup_uses_fixed_names_only(self):
        d = art.art_dir(self.p)
        (d / "首页全景").mkdir(parents=True)
        (d / "首页全景" / "白天.png").write_bytes(b"mine")
        (d / "首页全景" / "随便.png").write_bytes(b"x")
        hit = art.lookup(self.p, "行测", "sect/xc-sect-day.webp")
        self.assertEqual(hit.read_bytes(), b"mine")
        self.assertIsNone(art.lookup(self.p, "行测", "sect/xc-sect-night.webp"))
        self.assertIsNone(art.lookup(self.p, "行测", "../../etc/passwd"))      # 不在名字表里
        self.assertEqual([x[0] for x in art.files(self.p, "行测")], ["sect/xc-sect-day.webp"])

    def test_page_backgrounds_and_audio_ext(self):
        d = art.art_dir(self.p)
        (d / "子地图背景").mkdir(parents=True)
        (d / "子地图背景" / "洞府-夜晚.jpg").write_bytes(b"n")
        (d / "音乐").mkdir()
        (d / "音乐" / "地图白天.mp3").write_bytes(b"m")
        rels = {x[0] for x in art.files(self.p, "行测")}
        self.assertEqual(rels, {"beauty/page/dwelling-night.webp", "beauty/audio/bgm/map-day.ogg"})
        self.assertEqual(art.lookup(self.p, "行测", "beauty/audio/bgm/map-day.ogg").suffix, ".mp3")
        # 申论的地点名不同：行测的“洞府”不会被申论读到
        self.assertEqual({x[0] for x in art.files(self.p, "申论")}, {"beauty/audio/bgm/map-day.ogg"})

    def test_export_does_not_overwrite(self):
        d = art.art_dir(self.p)
        (d / "首页全景").mkdir(parents=True)
        (d / "首页全景" / "白天.jpg").write_bytes(b"mine")
        r = art.export(self.p, "行测", self.assets)
        self.assertEqual(r["copied"], 2)                       # 立绘 calm、音乐 map-day；首页白天已有
        self.assertGreaterEqual(r["skipped"], 1)
        self.assertEqual((d / "首页全景" / "白天.jpg").read_bytes(), b"mine")
        self.assertTrue((d / "人物立绘" / "平静.webp").is_file() and (d / "音乐" / "地图白天.ogg").is_file())
        self.assertTrue((d / "说明.txt").is_file() and (d / "子地图背景").is_dir())
        again = art.export(self.p, "行测", self.assets)
        self.assertEqual(again["copied"], 0)


if __name__ == "__main__":
    unittest.main()


class PortraitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        v = Path(self.tmp.name) / "库"
        (v / "copilot/skills").mkdir(parents=True)
        self.p = paths.Paths(v)
        self.p.ensure_train_dir()

    def tearDown(self):
        self.tmp.cleanup()

    def _fig(self, name, bg=(255, 0, 255)):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (300, 400), bg)
        ImageDraw.Draw(im).ellipse((80, 60, 220, 340), fill=(40, 90, 120))
        d = art.art_dir(self.p)
        d.mkdir(parents=True, exist_ok=True)           # 根目录也能放，别名英文编号也认
        im.save(d / name)
        return d / name

    def test_alias_in_root_and_chroma_key(self):
        f = self._fig("sl-zhoujingyi-calm.png")
        self.assertEqual(art.lookup(self.p, "申论", "beauty/portrait/sl-zhoujingyi-calm.webp"), f)
        self.assertIsNone(art.lookup(self.p, "行测", "beauty/portrait/sl-zhoujingyi-calm.webp"))
        data, ct = art.processed(f)
        self.assertEqual(ct, "image/webp")
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        self.assertEqual(im.getpixel((5, 5))[3], 0)               # 洋红底变透明
        self.assertEqual(im.getpixel((150, 200))[3], 255)         # 人物不透明
        self.assertTrue((f.parent / ".cache").is_dir())

    def test_green_background_and_no_key_for_busy_corners(self):
        g = self._fig("g.png", (0, 255, 0))
        from PIL import Image, ImageDraw
        import io
        im = Image.open(io.BytesIO(art.processed(g)[0])).convert("RGBA")
        self.assertEqual(im.getpixel((5, 5))[3], 0)
        busy = Image.new("RGB", (200, 200), (255, 255, 255))
        ImageDraw.Draw(busy).rectangle((0, 0, 99, 199), fill=(10, 10, 10))   # 四角颜色不一致
        f = art.art_dir(self.p) / "b.png"
        busy.save(f)
        out = Image.open(io.BytesIO(art.processed(f)[0])).convert("RGBA")
        self.assertEqual(out.getpixel((5, 5))[3], 255)

    def test_character_portraits_needs_calm(self):
        self._fig("sl-zhoujingyi-cheer.png")
        self.assertIsNone(art.character_portraits(self.p, "申论", "zhoujingyi"))
        self._fig("sl-zhoujingyi-calm.png")
        self._fig("sl-zhoujingyi-blink.png")
        por = art.character_portraits(self.p, "申论", "zhoujingyi")
        self.assertIn("calm", por)
        self.assertIn("cheer", por)
        self.assertEqual(por["blink"]["w"], 1)
