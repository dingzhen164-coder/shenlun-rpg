"""题图排版元数据，供vault/trainer调用；标准库读取尺寸，缓存绑定文件版本。
小公式保留在文字块中，大图仍独占图片块；不修改图片、原文或题库文件。
"""
import re
import struct
from functools import lru_cache


@lru_cache(maxsize=512)
def _size(name,mtime,size):
    try:
        with open(name,'rb') as f:data=f.read(65536)
        if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>=24:return struct.unpack('>II',data[16:24])
        if data[:6] in (b'GIF87a',b'GIF89a') and len(data)>=10:return struct.unpack('<HH',data[6:10])
        if data[:4]==b'RIFF' and data[8:12]==b'WEBP':
            if data[12:16]==b'VP8X' and len(data)>=30:return (1+int.from_bytes(data[24:27],'little'),1+int.from_bytes(data[27:30],'little'))
            if data[12:16]==b'VP8 ' and data[23:26]==b'\x9d\x01\x2a':return tuple(x&0x3fff for x in struct.unpack('<HH',data[26:30]))
            if data[12:16]==b'VP8L' and len(data)>=25:
                n=int.from_bytes(data[21:25],'little');return (1+(n&0x3fff),1+((n>>14)&0x3fff))
        if data[:2]==b'\xff\xd8':
            i=2
            while i+8<len(data):
                if data[i]!=255:break
                while i<len(data) and data[i]==255:i+=1
                mark=data[i];i+=1
                if mark in (1,216) or 208<=mark<=215:continue
                n=int.from_bytes(data[i:i+2],'big')
                if n<2:break
                if mark in (192,193,194,195,197,198,199,201,202,203,205,206,207):return tuple(reversed(struct.unpack('>HH',data[i+3:i+7])))
                i+=n
    except (OSError,ValueError,struct.error):pass
    return None


def small(paths,relative):
    try:
        file=(paths.vault/relative).resolve();file.relative_to(paths.vault.resolve());st=file.stat()
        size=_size(str(file),st.st_mtime_ns,st.st_size)
    except (OSError,ValueError,TypeError):return None
    return bool(0<size[0]<=420 and 0<size[1]<=96) if size else None


def before(buffer):
    # 裁图器在一条句子里插入的单换行可接回去；段落与选项边界保留。
    return buffer.rstrip(' \t\n') if re.search(r'\n[ \t\n]*$',buffer) and not re.search(r'[。！？；.!?]\s*$',buffer) else buffer


def after(text,pos):
    m=re.match(r'[ \t]*(?:\n[ \t]*)+',text[pos:])
    if m and not re.match(r'[ \t]*(?:[-*#>]|[A-D][.．、])',text[pos+m.end():]):return pos+m.end()
    return pos
