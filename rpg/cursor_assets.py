"""本机鼠标Mod素材读取：API接收ZIP的base64，仅读PNG资源，返回data URL。
不执行DLL，不落盘，不加载游戏代码。仅支持用户提供的WikiCursor三图布局。
"""
import base64
import io
import struct
import zipfile
import zlib


def read_pack(body):
    value = body.get("zip")
    if not isinstance(value, str) or len(value) > 2800000:
        raise ValueError("请选择2MB以内的鼠标Mod ZIP")
    try:
        raw = base64.b64decode(value, validate=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as pack:
            files = [f for f in pack.infolist() if f.filename.replace("\\", "/").split("/")[-1] == "WikiCursor.dll"]
            if len(files) != 1 or files[0].file_size > 2000000 or files[0].flag_bits & 1:
                raise ValueError("压缩包中需有一个WikiCursor.dll")
            data = pack.read(files[0])
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError) as e:
        raise ValueError("无法读取鼠标Mod ZIP：" + str(e)) from e
    images = []
    pos = 0
    while True:
        start = data.find(b"\x89PNG\r\n\x1a\n", pos)
        if start < 0:
            break
        end = start + 8
        size = None
        while end + 12 <= len(data):
            n = struct.unpack(">I", data[end:end + 4])[0]
            kind = data[end + 4:end + 8]
            limit = end + n + 12
            if n > 1000000 or limit > len(data) or limit - start > 1000000:
                raise ValueError("鼠标PNG资源已损坏或过大")
            if zlib.crc32(data[end + 4:end + 8 + n]) & 0xffffffff != struct.unpack(">I", data[end + 8 + n:limit])[0]:
                raise ValueError("鼠标PNG资源校验失败")
            if kind == b"IHDR":
                if end != start + 8 or n != 13:
                    raise ValueError("鼠标PNG头格式错误")
                size = struct.unpack(">II", data[end + 8:end + 16])
            end = limit
            if kind == b"IEND":
                break
        else:
            raise ValueError("鼠标PNG不完整")
        if not size or min(size) < 1 or max(size) > 2048:
            raise ValueError("鼠标图片尺寸不支持")
        images.append((size, "data:image/png;base64," + base64.b64encode(data[start:end]).decode("ascii")))
        if len(images) > 3:
            raise ValueError("鼠标资源数量不支持")
        pos = end
    if len(images) != 3 or images[0][0] != (32, 32) or any(w != h or w < 64 for (w, h), _ in images[1:]):
        raise ValueError("未找到完整的指针和两张法阵图片")
    return dict(zip(("pointer", "inner", "outer"), (s for _, s in images)))
