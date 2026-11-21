"""行测库目录整理与迁移回归：
1. 7 个旧平铺时政目录自动无损迁入 训练/万象峰/；
2. 外部 FB模考试卷复盘 只读复制到 训练/模考复盘 与 训练/模考试卷，原件不动；
3. 删除外部 FB模考试卷复盘 后，looks_like_vault 仍正确识别行测库且不误判申论库。
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from rpg import paths, wanxiang_journal


def setUpModule():
    os.environ["SHENLUN_SUBJECT"] = "行测"


def tearDownModule():
    os.environ.pop("SHENLUN_SUBJECT", None)


class XingceMigrateTest(unittest.TestCase):
    def test_wanxiang_seven_to_one_and_fb_readonly_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = Path(tmp) / "行测库"
            # 构造外部 FB模考试卷复盘
            (v / "FB模考试卷复盘/板块复盘/第33季").mkdir(parents=True)
            (v / "FB模考试卷复盘/板块复盘/第33季/01-言语.md").write_text("# 第33季言语\n", encoding="utf-8")
            (v / "FB模考试卷复盘/模考试卷").mkdir(parents=True)
            (v / "FB模考试卷复盘/模考试卷/第33季.pdf").write_bytes(b"%PDF-1.4 fake")

            # 构造 7 个旧平铺时政目录
            train = v / "训练"
            (train / "万象时政/月半时政").mkdir(parents=True)
            (train / "万象时政/原文").mkdir(parents=True)
            (train / "万象时政/原文/月半时政-2026-10-上.pdf").write_bytes(b"%PDF-1.4 j")
            (train / "万象时政/月半时政/2026-10-上.json").write_text(
                json.dumps({"id": "2026-10-上", "kind": "month", "title": "2026年10月上",
                            "pdf": "训练/万象时政/原文/月半时政-2026-10-上.pdf", "news": [], "cloze": [], "questions": []},
                           ensure_ascii=False),
                encoding="utf-8",
            )
            (train / "时政知识地图").mkdir(parents=True)
            (train / "时政知识地图/进度.json").write_text('{"ok":1}', encoding="utf-8")
            (train / "时政消化").mkdir(parents=True)
            (train / "时政消化/a.json").write_text('{"d":1}', encoding="utf-8")
            (train / "时政重点").mkdir(parents=True)
            (train / "时政重点/h.json").write_text('{"added":[]}', encoding="utf-8")
            (train / "词义批注").mkdir(parents=True)
            (train / "词义批注/n.json").write_text('{"k":{}}', encoding="utf-8")
            (train / "天机简报").mkdir(parents=True)
            (train / "天机简报/old.txt").write_text("old", encoding="utf-8")
            (train / "时政回收").mkdir(parents=True)
            (train / "时政回收/rec.txt").write_text("rec", encoding="utf-8")

            # 构造其余 4 大类的旧平铺目录与文件
            (train / "题库").mkdir(parents=True)
            (train / "题库/言语真题.md").write_text("# 言语\n", encoding="utf-8")
            (train / "卡片").mkdir(parents=True)
            (train / "卡片/资料分析.md").write_text("# 资料\n", encoding="utf-8")
            (train / "试炼记录").mkdir(parents=True)
            (train / "试炼记录/2026-11.md").write_text("# 试炼\n", encoding="utf-8")
            (train / "规则.md").write_text("- 每日目标分钟: 300\n- 配置版本: 3\n", encoding="utf-8")
            (train / "师尊.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (train / "存档").mkdir(parents=True)
            (train / "存档/存档.json").write_text('{"xp":88}', encoding="utf-8")
            (train / "词录备份").mkdir(parents=True)
            (train / "词录备份/bak.md").write_text("bak", encoding="utf-8")

            p = paths.Paths(v, "行测")
            p.ensure_train_dir()

            # 7 个旧时政目录均已收拢进 训练/万象峰/
            for old_name, sub in paths.WANXIANG_SUBS:
                self.assertFalse((train / old_name).exists(), f"旧目录 {old_name} 应已迁出")
                self.assertTrue((train / "万象峰" / sub).is_dir(), f"新目录 万象峰/{sub} 应存在")
            self.assertEqual((train / "万象峰/知识地图/进度.json").read_text(encoding="utf-8"), '{"ok":1}')
            self.assertEqual((train / "万象峰/消化/a.json").read_text(encoding="utf-8"), '{"d":1}')
            self.assertEqual((train / "万象峰/重点标红/h.json").read_text(encoding="utf-8"), '{"added":[]}')
            self.assertEqual((train / "万象峰/词义批注/n.json").read_text(encoding="utf-8"), '{"k":{}}')

            # 其余 4 大类（藏经阁、试炼与大比、规则与设定、系统）均已收拢到位
            self.assertTrue((train / "藏经阁/题库/言语真题.md").is_file())
            self.assertTrue((train / "藏经阁/卡片/资料分析.md").is_file())
            self.assertTrue((train / "试炼与大比/试炼记录/2026-11.md").is_file())
            self.assertTrue((train / "规则与设定/规则.md").is_file())
            self.assertTrue((train / "规则与设定/师尊.png").is_file())
            self.assertEqual((train / "系统/存档/存档.json").read_text(encoding="utf-8"), '{"xp":88}')
            self.assertTrue((train / "系统/历史备份/词录备份/bak.md").is_file())

            # 旧期刊 JSON 里的 pdf 相对路径加载时自动映射到新位置
            loaded = wanxiang_journal.load(p, "month", "2026-10-上")
            self.assertEqual(loaded["pdf"], "训练/万象峰/期刊/原文/月半时政-2026-10-上.pdf")

            # FB模考试卷复盘 只读复制到 训练/试炼与大比/，外部原目录完好不动
            self.assertTrue((train / "试炼与大比/模考复盘/第33季/01-言语.md").is_file())
            self.assertTrue((train / "试炼与大比/模考试卷/第33季.pdf").is_file())
            self.assertTrue((v / "FB模考试卷复盘/板块复盘/第33季/01-言语.md").is_file())

            # 删除外部 FB模考试卷复盘 后，仍能正确识别为行测库，不误判为申论库
            shutil.rmtree(v / "FB模考试卷复盘")
            (v / "copilot/skills").mkdir(parents=True)
            self.assertTrue(paths.looks_like_vault(v, "行测"))
            self.assertFalse(paths.looks_like_vault(v, "申论"))

            # 纯申论库仍被正确识别为申论库
            sl = Path(tmp) / "申论库"
            (sl / "copilot/skills").mkdir(parents=True)
            self.assertTrue(paths.looks_like_vault(sl, "申论"))
            self.assertFalse(paths.looks_like_vault(sl, "行测"))


if __name__ == "__main__":
    unittest.main()
