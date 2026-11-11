"""2026-11-11 用户需求：申论每日学习目标 300 → 120 分钟，每分钟政绩 1 → 2.5（学满仍是 300 政绩，综合评价不跳）。
只迁移一次、只改仍是默认值的项；行测不动；新装默认就是 2 小时。隔离临时库。"""
import os
import tempfile
import unittest
from pathlib import Path
from rpg import config, paths


OLD = ("- 每日目标分钟: 300  # 每天 办理 + 听课（在其他平台看网课的时间，办公室页记录）合计\n"
       "- 每日理想经验: 300\n- 经验.办理每分钟: 1  # 有效办理\n- 经验.听课每分钟: 1  # 听课\n- 经验.静修每分钟: 1  # 自习\n- 经验.自练每分钟: 1\n")


class TwoHoursTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SHENLUN_SUBJECT"] = "申论"

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("SHENLUN_SUBJECT", None)
        paths.NOTICES.clear()

    def _paths(self, subject, text):
        p = paths.Paths(Path(self.tmp.name), subject)
        p.ensure_train_dir()
        p.rules.write_text(text, encoding="utf-8")
        p._migrate_rules()
        return p, config.Rules(p.rules.read_text(encoding="utf-8"), subject)

    def test_default_values_migrate_once_and_score_pace_unchanged(self):
        p, r = self._paths("申论", OLD)
        self.assertEqual(r.num("每日目标分钟"), 120)
        for key in ("经验.修炼每分钟", "经验.听道每分钟", "经验.静修每分钟", "经验.自练每分钟"):
            self.assertEqual(r.num(key), 2.5, key)
        self.assertEqual(r.num("每日目标分钟") * r.num("经验.修炼每分钟"), r.num("每日理想经验"))   # 学满 2 小时 = 300
        self.assertTrue(any("120 分钟" in n for n in paths.NOTICES))
        # 之后用户自己改回 300：不再被改回去
        text = p.rules.read_text(encoding="utf-8").replace("每日目标分钟: 120", "每日目标分钟: 300")
        p.rules.write_text(text, encoding="utf-8")
        p._migrate_rules()
        self.assertIn("每日目标分钟: 300", p.rules.read_text(encoding="utf-8"))

    def test_custom_values_untouched(self):
        _, r = self._paths("申论", OLD.replace("每日目标分钟: 300", "每日目标分钟: 240"))
        self.assertEqual(r.num("每日目标分钟"), 240)
        self.assertEqual(r.num("经验.修炼每分钟"), 1)          # 目标不是默认值：汇率也不动，避免每天政绩翻倍
        _, r = self._paths("申论", OLD.replace("经验.听课每分钟: 1", "经验.听课每分钟: 3"))
        self.assertEqual((r.num("每日目标分钟"), r.num("经验.听道每分钟"), r.num("经验.修炼每分钟")), (120, 3, 2.5))

    def test_xingce_unchanged_and_new_install_defaults(self):
        os.environ["SHENLUN_SUBJECT"] = "行测"
        _, r = self._paths("行测", "- 每日目标分钟: 300\n- 经验.修炼每分钟: 1\n")
        self.assertEqual((r.num("每日目标分钟"), r.num("经验.修炼每分钟")), (300, 1))
        self.assertEqual(config.Rules("", "申论").num("每日目标分钟"), 120)        # 规则文件缺项时的科目默认
        self.assertEqual(config.Rules("", "行测").num("每日目标分钟"), 300)
        fresh = (Path(__file__).resolve().parent.parent / "defaults/申论/规则.md").read_text(encoding="utf-8")
        r = config.Rules(fresh, "申论")
        self.assertEqual((r.num("每日目标分钟"), r.num("经验.修炼每分钟"), r.num("每日理想经验")), (120, 2.5, 300))
        self.assertIn(paths.SHENLUN_2H_MARK, fresh)                                 # 新装的不会被再迁移一次


if __name__ == "__main__":
    unittest.main()
