#!/usr/bin/env python3
"""把 web/assets/beauty/icons/svg/*.svg 合成 sprite.svg（供 web/beauty_icons.js 使用）。

换图标的做法：把同名 svg 覆盖进 svg/ 文件夹（建议 24×24 视图框、描边或填充都用 currentColor），
想让别的 emoji 显示成别的图标，改 emoji-map.json（emoji → 文件名不带 .svg），然后运行本脚本。
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "assets", "beauty", "icons")
SVG_DIR = os.path.join(ROOT, "svg")


def build():
    names = sorted(f[:-4] for f in os.listdir(SVG_DIR) if f.endswith(".svg"))
    out = ['<svg xmlns="http://www.w3.org/2000/svg" style="display:none">']
    for n in names:
        s = open(os.path.join(SVG_DIR, n + ".svg"), encoding="utf-8").read()
        s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
        m = re.search(r"<svg([^>]*)>(.*)</svg>", s, flags=re.S)
        if not m:
            print("跳过（不是有效svg）：", n, file=sys.stderr)
            continue
        vb = re.search(r'viewBox="([^"]+)"', m.group(1))
        # 描边/填充属性放在 symbol 上，<use> 继承
        attrs = " ".join(re.findall(r'(?:fill|stroke|stroke-width|stroke-linecap|stroke-linejoin)="[^"]+"', m.group(1)))
        out.append(f'<symbol id="ic-{n}" viewBox="{vb.group(1) if vb else "0 0 24 24"}" {attrs}>{m.group(2).strip()}</symbol>')
    out.append("</svg>")
    open(os.path.join(ROOT, "sprite.svg"), "w", encoding="utf-8").write("\n".join(out))
    mp = json.load(open(os.path.join(ROOT, "emoji-map.json"), encoding="utf-8"))
    bad = sorted({v for v in mp.values() if v not in names})
    if bad:
        print("emoji-map.json 引用了不存在的图标：", bad, file=sys.stderr)
        return 1
    print(f"sprite.svg：{len(names)} 个图标")
    return 0


if __name__ == "__main__":
    sys.exit(build())
