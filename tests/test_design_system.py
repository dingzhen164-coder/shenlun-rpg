"""3.1.2设计系统检查（fakao-rpg、shenlun-rpg共用同一份）：不跑浏览器，只读web/下的CSS/JS/HTML。
检查什么：
  1. 令牌齐全：页面与组件用到的var(--ds-*)都在tokens.css/ds.css里定义；主题块覆盖的令牌必须在基础块里有默认值。
  2. 类名规范：ds-类只在ds.css里定义；ds.css只定义ds-类（动效开关等属性选择器除外）；JS/HTML里用到的ds-类都存在。
  3. 裸值只降不升：除tokens.css外，各CSS文件的“裸颜色、硬编码px字号、px圆角”数量不得超过tests/ds_baseline.json；
     ds.css必须为0。减少后用 DS_UPDATE_BASELINE=1 python -m unittest tests.test_design_system 刷新基线。
  4. 加载顺序：index.html里tokens.css在最前，ds.css紧跟style.css之后、各页面CSS之前。
测试只读文件，不碰用户数据。"""
import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
BASELINE = os.path.join(ROOT, "tests", "ds_baseline.json")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def css_files():
    return sorted(glob.glob(os.path.join(WEB, "*.css")))


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def declarations(text):
    """依次产出声明文本（属性: 值），跳过选择器与@规则头。"""
    buf = []
    for ch in strip_comments(text):
        if ch == "{":
            buf = []
        elif ch in ";}":
            decl = "".join(buf).strip()
            buf = []
            if ":" in decl:
                yield decl
        else:
            buf.append(ch)


COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)")
FONT_PX = re.compile(r"^font-size\s*:\s*\d+(?:\.\d+)?px")
RADIUS = re.compile(r"^border-radius\s*:(.*)$")


def measure(text):
    colors = fonts = radii = 0
    for decl in declarations(text):
        prop, _, value = decl.partition(":")
        if prop.strip().startswith("--"):
            # 自定义属性里的裸色值也算裸值（令牌文件除外，本函数不用于tokens.css）
            colors += len(COLOR.findall(value))
            continue
        colors += len(COLOR.findall(value))
        if FONT_PX.match(decl):
            fonts += 1
        m = RADIUS.match(decl)
        if m:
            radii += len(re.findall(r"\b\d+(?:\.\d+)?px", m.group(1)))
    return {"colors": colors, "font_px": fonts, "radius_px": radii}


def current_counts():
    out = {}
    for path in css_files():
        name = os.path.basename(path)
        if name == "tokens.css":
            continue
        out[name] = measure(read(path))
    return out


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.tokens = read(os.path.join(WEB, "tokens.css"))
        self.ds = read(os.path.join(WEB, "ds.css"))

    def defined(self, text):
        return set(re.findall(r"(--ds-[\w-]+)\s*:", strip_comments(text)))

    def test_used_tokens_are_defined(self):
        defined = self.defined(self.tokens) | self.defined(self.ds)
        used = set()
        for path in css_files() + glob.glob(os.path.join(WEB, "*.js")) + [os.path.join(WEB, "index.html")]:
            used |= set(re.findall(r"var\((--ds-[\w-]+)\s*\)", read(path)))  # 带回退值的var(--x, 默认)是可选上下文变量，不要求定义
        missing = sorted(used - defined)
        self.assertEqual(missing, [], "用到但未定义的令牌：%s" % missing)

    def test_theme_blocks_extend_base_tokens(self):
        """带选择器的覆盖块（body.guantu、[data-theme=dark]…）里的令牌，必须在基础块有默认值。"""
        text = strip_comments(self.tokens)
        base = set()
        override = set()
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
            names = set(re.findall(r"(--ds-[\w-]+)\s*:", body))
            sel = sel.strip()
            if sel in (":root", ":root, body", "body"):
                base |= names
            else:
                override |= names
        self.assertEqual(sorted(override - base), [], "覆盖块令牌缺基础默认值")

    def test_dark_blocks_cover_every_theme(self):
        """纸笺与状态牌：暗色必须为三个主题（默认/guantu/xuanhuan）都给值。"""
        text = strip_comments(self.tokens)
        for key in ("--ds-paper:", "--ds-plate-ink:"):
            for theme in ("body.guantu", "body.xuanhuan"):
                pattern = r"\[data-theme=\"dark\"\] %s[^{]*\{[^}]*%s" % (re.escape(theme), re.escape(key.rstrip(":")))
                if key == "--ds-paper:" or key == "--ds-plate-ink:":
                    self.assertRegex(text, pattern, "%s 缺少 %s 暗色" % (theme, key))


class ClassTests(unittest.TestCase):
    def test_ds_classes_only_in_ds_css(self):
        for path in css_files():
            name = os.path.basename(path)
            if name in ("ds.css", "tokens.css"):
                continue
            text = strip_comments(read(path))
            selectors = re.findall(r"([^{}]+)\{", text)
            for sel in selectors:
                self.assertNotRegex(sel, r"\.ds-", "%s 里定义了ds-类：%s" % (name, sel.strip()[:60]))

    def test_ds_css_only_defines_ds_classes(self):
        text = strip_comments(read(os.path.join(WEB, "ds.css")))
        for sel in re.findall(r"([^{}@]+)\{", text):
            for cls in re.findall(r"\.([A-Za-z_][\w-]*)", sel):
                self.assertTrue(cls.startswith("ds-"), "ds.css里出现非ds-类：." + cls)

    def test_used_ds_classes_exist(self):
        defined = set(re.findall(r"\.(ds-[\w-]+)", read(os.path.join(WEB, "ds.css"))))
        used = set()
        for path in glob.glob(os.path.join(WEB, "*.js")) + [os.path.join(WEB, "index.html")]:
            for chunk in re.findall(r'class(?:Name)?\s*=\s*["\'`]([^"\'`]*)', read(path)):
                used |= set(re.findall(r"\bds-[\w-]+", chunk))
        self.assertEqual(sorted(used - defined), [], "JS/HTML用到了未定义的ds-类")


class OrderTests(unittest.TestCase):
    def test_stylesheet_order(self):
        links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', read(os.path.join(WEB, "index.html")))
        self.assertEqual(links[0], "tokens.css")
        self.assertEqual(links[1], "style.css")
        self.assertEqual(links[2], "ds.css")


class RatchetTests(unittest.TestCase):
    def test_ds_css_has_no_bare_values(self):
        counts = measure(read(os.path.join(WEB, "ds.css")))
        # ds.css里按钮内边距等少量px属于组件私有变量，不算字号/圆角/颜色
        self.assertEqual(counts, {"colors": 0, "font_px": 0, "radius_px": 0})

    def test_bare_values_do_not_grow(self):
        now = current_counts()
        if os.environ.get("DS_UPDATE_BASELINE"):
            with open(BASELINE, "w", encoding="utf-8") as f:
                json.dump(now, f, ensure_ascii=False, indent=1, sort_keys=True)
                f.write("\n")
        base = json.loads(read(BASELINE))
        grown = []
        for name, c in now.items():
            b = base.get(name, {"colors": 0, "font_px": 0, "radius_px": 0})
            for k in c:
                if c[k] > b[k]:
                    grown.append("%s %s: %d > 基线 %d" % (name, k, c[k], b[k]))
        self.assertEqual(grown, [], "裸值只降不升（新增请改用var(--ds-*)）：\n" + "\n".join(grown))


if __name__ == "__main__":
    unittest.main()
