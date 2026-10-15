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
