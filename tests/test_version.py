"""版本号与更新记录一致：VERSION 必须等于 changelog.md 最新一节的版本号，忘了写更新说明就会失败。"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class VersionTest(unittest.TestCase):
    def test_changelog_matches_version(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        m = re.search(r"^## 版本 (\d+\.\d+\.\d+) · \d{4}-\d{2}-\d{2}", (ROOT / "changelog.md").read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(m, "changelog.md 里没有“## 版本 x.y.z · 日期”")
        self.assertEqual(m.group(1), version, "VERSION 和 changelog.md 最新一节不一致")


if __name__ == "__main__":
    unittest.main()
