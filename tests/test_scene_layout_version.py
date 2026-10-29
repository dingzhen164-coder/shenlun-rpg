"""主页排布：地图换新插画时用 desktopVersion 丢弃旧版横屏位置；服务端只保留合法版本号。"""
import unittest
from rpg import scene_layout


class SceneLayoutVersionTest(unittest.TestCase):
    def test_desktop_version_is_kept_and_validated(self):
        state = {}
        out = scene_layout.save(state, {'map': 'mage', 'layout': {'desktop': {'dwelling': {'x': 10, 'y': 20}}, 'narrow': {}, 'names': {},
                                                                    'desktopVersion': 'fit-v1'}})
        self.assertEqual(out['desktopVersion'], 'fit-v1')
        bad = scene_layout.save({}, {'map': 'mage', 'layout': {'desktop': {}, 'narrow': {}, 'names': {}, 'desktopVersion': '<script>'}})
        self.assertNotIn('desktopVersion', bad)
        old = scene_layout.save({}, {'map': 'mage', 'layout': {'desktop': {}, 'narrow': {}, 'names': {}}})
        self.assertNotIn('desktopVersion', old)           # 旧存档没有版本号：前端按新默认位置处理


if __name__ == '__main__':
    unittest.main()
