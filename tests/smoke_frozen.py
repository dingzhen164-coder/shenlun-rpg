"""打包后的 exe / Mac App 自检（CI 用）：xingce-xiuxian.exe --run-script tests/smoke_frozen.py
确认 exe 里带齐了 pymupdf、segno、网页文件和程序模块。"""
import sys

import pymupdf  # noqa: F401
import segno  # noqa: F401
import webview  # noqa: F401

from rpg import api, lan, update, zhenti  # noqa: F401
from rpg.paths import DEFAULTS_DIR, FROZEN, WEB_DIR

assert FROZEN, "not frozen"
assert (WEB_DIR / "index.html").exists(), WEB_DIR
assert (WEB_DIR / "device.js").exists()
for name in ('political_atlas.html', 'atlas.js', 'atlas.css', 'atlas_theme.css', 'word_notes.js', 'word_notes.css', 'wanxiang.css'):
    assert (WEB_DIR / name).is_file(), name
import json
import hashlib
from rpg.paths import RES_DIR
seed = RES_DIR / 'rpg/data/political_atlas.json'
spec = json.loads((RES_DIR / 'rpg/data/political_atlas_seed.json').read_text(encoding='utf-8'))
assert seed.is_file(), '缺少离线时政资料'
assert hashlib.sha256(seed.read_bytes()).hexdigest() == spec['sha256'], '时政资料摘要不符'
atlas_data = json.loads(seed.read_text(encoding='utf-8'))
assert len(atlas_data['materials']) == 38 and len(atlas_data['questions']) == 135, '时政资料不完整'
assert (WEB_DIR / 'wanxiang_art.js').is_file()
assert (WEB_DIR / 'wanxiang_art.css').is_file()
assert (WEB_DIR / 'assets/beauty/wanxiang/scholarly-instruments.png').is_file()
assert DEFAULTS_DIR.exists(), DEFAULTS_DIR
from PIL import Image
portraits=list((DEFAULTS_DIR/'人物'/'行测').glob('xc-*/立绘/*.png'))
assert len(portraits)==24, '人物双立绘打包不完整'
for portrait in portraits:
    with Image.open(portrait) as img:
        img.verify()
assert zhenti.FIX_FILE.exists(), zhenti.FIX_FILE
assert "<svg" in lan.qr_svg("http://192.168.1.2:8765/")
if sys.platform == "darwin":                   # Mac：苹果 Vision 能认出成绩截图里的中文和数字
    from rpg import report
    doc = pymupdf.open()
    page = doc.new_page(width=640, height=220)
    page.insert_text((30, 90), "得分 64.5  共30题答对25题", fontname="china-s", fontsize=30)
    out = report.ocr(page.get_pixmap(dpi=144).tobytes("png"))
    print(out)
    assert "64.5" in out and "得分" in out, out
print("SMOKE-OK", sys.version.split()[0])
