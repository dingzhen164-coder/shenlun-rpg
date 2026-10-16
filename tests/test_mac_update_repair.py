"""一次性工具入口测试：仅替身模块/假路径，不启动真实App、不访问用户资料或网络。"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch


class RepairTest(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('repair_test',Path(__file__).resolve().parents[1]/'tools/mac_update_repair.py')
        self.repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.repair)

    def test_old_app_uses_bootstrap_downloader_and_existing_update_flow(self):
        from rpg import paths,version
        updater=SimpleNamespace(check=lambda:dict(current='3.3.0',latest='3.3.1',newer=True),apply=Mock(return_value={'version':'3.3.1'}))
        with patch.object(self.repair.sys,'platform','darwin'),patch.object(paths,'FROZEN',True),patch.object(version,'REPO','dingzhen164-coder/shenlun-rpg'),patch.object(self.repair,'load_module',side_effect=[SimpleNamespace(archive=Mock()),updater]) as load,patch.object(self.repair.time,'sleep'):
            import rpg
            previous=getattr(rpg,'download',None)
            try:self.repair.main()
            finally:
                if previous is not None:rpg.download=previous
                else:delattr(rpg,'download')
            self.assertEqual(load.call_args_list[0].args[0],'rpg.download')
            updater.apply.assert_called_once_with()

    def test_system_python_is_rejected_before_any_module_replacement(self):
        from rpg import paths
        with patch.object(self.repair.sys,'platform','darwin'),patch.object(paths,'FROZEN',False),patch.object(self.repair,'load_module') as load:
            with self.assertRaisesRegex(RuntimeError,'不要使用系统Python'):self.repair.main()
            load.assert_not_called()


if __name__=='__main__':unittest.main()
