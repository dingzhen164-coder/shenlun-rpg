"""已撤下的台词：默认台词库里没有，用户台词库副本里还留着也不会再被抽到。"""
import unittest
from pathlib import Path

from rpg import config


class RetiredLinesTest(unittest.TestCase):
    def test_retired_line_never_picked_even_from_a_users_old_copy(self):
        old = "## 试炼·复盘错题\n- 又是 {你的答案}……为师没教过你吗？先读解析，不懂再问。\n- 选了 {你的答案}？答案是 {正确答案}。\n"
        lines = config.Lines(old, "")
        picks = {lines.pick("试炼·复盘错题", 你的答案="C", 正确答案="A") for _ in range(40)}
        self.assertEqual(picks, {"选了 C？答案是 A。"})
        defaults = (Path(config.__file__).resolve().parent.parent / "defaults" / "台词库.md").read_text(encoding="utf-8")
        self.assertNotIn("为师没教过你吗", defaults)


if __name__ == "__main__":
    unittest.main()
