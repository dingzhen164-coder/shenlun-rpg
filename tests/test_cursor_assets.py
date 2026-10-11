"""鼠标ZIP读取：合成PNG/DLL验证正常导入、损坏、重复与体积限制，不用第三方素材。"""
import base64
import io
import struct
import unittest
import zipfile
import zlib
from rpg.cursor_assets import read_pack


def png(size):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress((b'\0' + b'\x20\xd9\xf3\xff' * size) * size)) + chunk(b'IEND', b'')


def pack(data=None, duplicate=False):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('2825183299/plugins/WikiCursor.dll', data if data is not None else b'MZ' + png(32) + png(64) + png(64))
        if duplicate:
            z.writestr('other/WikiCursor.dll', b'MZ')
    return out.getvalue()


class CursorAssetsTest(unittest.TestCase):
    def test_import(self):
        result = read_pack({'zip': base64.b64encode(pack()).decode()})
        self.assertEqual(set(result), {'pointer', 'inner', 'outer'})
        self.assertTrue(all(v.startswith('data:image/png;base64,') for v in result.values()))

    def test_bad_zip_and_limits(self):
        for value in ['bad!', base64.b64encode(b'bad').decode(), 'A' * 2800001]:
            with self.assertRaises(ValueError):
                read_pack({'zip': value})
        for data in [pack(b'MZ'), pack(b'MZ' + png(64) * 3), pack(duplicate=True), pack(b'x' * 2000001)]:
            with self.assertRaises(ValueError):
                read_pack({'zip': base64.b64encode(data).decode()})

    def test_crc_and_truncation(self):
        image = bytearray(png(32)); image[40] ^= 1
        for data in [b'MZ' + image + png(64) * 2, b'MZ' + png(32)[:-12]]:
            with self.assertRaises(ValueError):
                read_pack({'zip': base64.b64encode(pack(data)).decode()})
