"""新本地内容模板在 Python 3.8/3.9 的 pathlib 写入接口下仍能创建并保留用户修改。"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rpg import question_bank, siguo, wordbook


class TemplateCompatibilityTest(unittest.TestCase):
    def test_templates_work_with_python38_pathlib(self):
        original = Path.write_text
        # Python 3.8/3.9 的真实签名不接受 newline；磁盘写入仍用真实实现。
        def legacy_write(path, data, encoding=None, errors=None):
            return original(path, data, encoding=encoding, errors=errors)
        for module, folder in ((question_bank, '题库'), (siguo, '思过崖'), (wordbook, '成语实词录')):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as tmp:
                paths = SimpleNamespace(train=Path(tmp))
                with patch.object(Path, 'write_text', legacy_write):
                    module.ensure_template(paths)
                    template = Path(tmp) / folder / '_模板.md'
                    self.assertTrue(template.is_file())
                    self.assertIn('# ', template.read_text(encoding='utf-8'))
                    template.write_text('用户自己的说明', encoding='utf-8')
                    module.ensure_template(paths)
                    self.assertEqual(template.read_text(encoding='utf-8'), '用户自己的说明')
