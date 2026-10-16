"""
美术文件夹（3.2.x）：库里的 训练/外观/美术/ 专门放“外观设计文件”，程序优先用这里的文件，没有才用程序自带的。
这样想换首页全景、每个子地图的背景、人物立绘、背景音乐、音效，都不用动源代码：把文件按下面的中文名放进对应子文件夹，刷新网页就生效；
想看看程序自带的长什么样、当模板改，点 设置 → 外观与音乐 → “导出程序自带美术”，会把自带文件按这些名字复制进来（已有的不覆盖）。

子文件夹与文件名（扩展名随意：图片 webp/png/jpg，音频 ogg/mp3/wav/m4a/opus）：
  首页全景/      白天、夜晚
  子地图背景/    <地点名>、<地点名>-白天、<地点名>-夜晚；洞府另有每个页签一套：洞府-<页签名>[-白天|-夜晚]；修炼页选中的分区（行测五峰、申论五题型、法考八科）也各一套：<分区名>[-白天|-夜晚]      （地点名随科目：行测 洞府/问道群峰/试炼塔/…，申论 办公室/知识办理中心/…，法考 营地/冒险大厅/…）
  人物立绘/      平静、鼓励、讲解、关切、欣慰、眨眼          （行测沈清禾、法考艾琳：眨眼图只含眼部，位置由程序固定，换图请保持同样的取景）
                 申论：<姓名>-<表情>，如 周静宜-平静、周静宜-眨眼（九位：周静宜 陈知微 林清岚 秦书瑶 韩明慧 沈清妍 顾清宁 许知宁 林悦；眨眼图是整幅同取景的闭眼图）
                 生成时用纯色底（洋红或绿）的图会自动去底并缩放（需要 Pillow；打包好的程序自带）；申论清单里的英文编号名（sl-zhoujingyi-calm.png、sl-hall-day.png）也认，
                 并且这些文件直接放在美术文件夹根目录也行，不用分子文件夹、不用改名
  音乐/          地图白天、地图夜晚、洞府、学习、突破仪式、对话
  音效/          点击、悬停、打开弹窗、关闭弹窗、翻页、答对、答错、连击、奖励、升级、突破、接取任务、完成任务、打字、环境声白天、环境声夜晚、环境声流水
子地图背景的优先级：<地点>[-页签]-白天/夜晚（按亮暗主题）→ <地点>[-页签] → 洞府页签回退到洞府整体背景 → 程序默认的淡透全景。

实现：网页请求 assets/<相对路径> 时，api.py 先问 art.lookup()；网页首页（index.html）里注入 window.ART_FILES（有覆盖的文件及修改时间）供前端判断。
所有名字写死在下面的表里，不接受任意路径，不会读到美术文件夹以外的文件。
"""
import shutil

FOLDER_REL = ("外观", "美术")
IMG = (".webp", ".png", ".jpg", ".jpeg")
AUD = (".ogg", ".mp3", ".wav", ".m4a", ".opus")
# 洞府（个人空间）的页签：每页可以有自己的背景（beauty_art.js 读 .fx-tab 的当前页签名对应到下面的 key）
DWELLING_TABS = {
    "行测": [("growth", "修为与突破"), ("shier", "十二经"), ("records", "修行记录"), ("bag", "储物袋"), ("diary", "修行日志")],
    "申论": [("growth", "仕途与晋升"), ("daily", "学时与出勤"), ("records", "学习记录")],
    "法考": [("growth", "成长与晋升"), ("daily", "时辰与日课"), ("records", "学习记录")],
}
# 修炼页选中某个分区后的页面：行测五峰、申论五个题型、法考八科，每个可以单独配背景（beauty_art.js 读 STUDY_REGIONS.title() 对应到 key）
REGIONS = {
    "行测": [("chang", "万象峰"), ("yan", "辨言峰"), ("li", "明理峰"), ("shu", "演数峰"), ("zi", "观星峰")],
    "申论": [("guina", "归纳概括"), ("zonghe", "综合分析"), ("duice", "提出对策"), ("guanche", "贯彻执行"), ("dazuowen", "大作文")],
    "法考": [("minfa", "民法"), ("xingfa", "刑法"), ("minsu", "民诉"), ("xingsu", "刑诉"), ("xingzheng", "行政法"), ("shangjing", "商经知"), ("sanguo", "三国法"), ("lilun", "理论法")],
}
VIEWS = ["dwelling", "train", "bank", "contest", "skeleton", "notes", "tianji", "settings"]
PLACES = {
    "行测": ["洞府", "问道群峰", "试炼塔", "宗门大比", "藏经阁", "灵台手札", "天机台", "设置"],
    "申论": ["办公室", "知识办理中心", "实操训练中心", "年度考核", "档案室", "公务手账", "天机台", "设置"],
    "法考": ["营地", "冒险大厅", "试炼塔", "竞技场", "咒文书馆", "魔法手记", "天机台", "设置"],
}
HOME = {"行测": ("sect/xc-sect-day.webp", "sect/xc-sect-night.webp"), "申论": ("shenlun/hall.webp", None),
        "法考": ("academy/scene/mg-academy-day.webp", "academy/scene/mg-academy-night.webp")}
# 申论的人物：七位阶段领导（按职务履历里的领导姓名对应）与两位同事（同伴支线）
SL_CHARS = [("周静宜", "zhoujingyi"), ("陈知微", "chenzhiwei"), ("林清岚", "linqinglan"), ("秦书瑶", "qinshuyao"), ("韩明慧", "hanminghui"),
            ("沈清妍", "shenqingyan"), ("顾清宁", "guqingning"), ("许知宁", "xuzhining"), ("林悦", "linyue")]
EXPR = [("calm", "平静"), ("cheer", "鼓励"), ("explain", "讲解"), ("concern", "关切"), ("proud", "欣慰"), ("blink", "眨眼")]
PORTRAIT = {"行测": "guide/xc-qinghe-%s.webp", "法考": "academy/portrait/mg-eileen-%s.webp"}
BGM = [("map-day", "地图白天"), ("map-night", "地图夜晚"), ("dongfu", "洞府"), ("study", "学习"), ("ceremony", "突破仪式"), ("dialog", "对话")]
SFX = [("click", "点击"), ("hover", "悬停"), ("open", "打开弹窗"), ("close", "关闭弹窗"), ("page", "翻页"), ("correct", "答对"), ("wrong", "答错"),
       ("combo", "连击"), ("reward", "奖励"), ("levelup", "升级"), ("breakthrough", "突破"), ("quest-accept", "接取任务"), ("quest-done", "完成任务"),
       ("type", "打字"), ("ambient-day", "环境声白天"), ("ambient-night", "环境声夜晚"), ("ambient-water", "环境声流水")]


def art_dir(paths):
    d = paths.train
    for x in FOLDER_REL:
        d = d / x
    return d


def slots(subject):
    """[(子文件夹, 文件名主干, 网页资源相对路径 assets/ 之后, 程序自带文件相对路径或 None, 'image'|'audio', 别名主干元组)]
    别名：申论图片清单里用的英文编号（sl-zhoujingyi-calm、sl-hall-day…）也认，所以可以直接把生成的文件放进美术文件夹，不用改名。"""
    out = []
    day, night = HOME.get(subject, HOME["行测"])
    sl = subject == "申论"
    out.append(("首页全景", "白天", day, day, "image", ("sl-hall-day",) if sl else ()))
    out.append(("首页全景", "夜晚", night or "beauty/page/home-night.webp", night, "image", ("sl-hall-night",) if sl else ()))
    for view, place in zip(VIEWS, PLACES.get(subject, PLACES["行测"])):
        legacy = '演武场' if subject == '行测' and view == 'contest' else ''
        for suffix, rel in [('', 'beauty/page/%s.webp' % view), ('-白天', 'beauty/page/%s-day.webp' % view), ('-夜晚', 'beauty/page/%s-night.webp' % view)]:
            out.append(("子地图背景", place + suffix, rel, None, "image", (legacy + suffix,) if legacy else ()))
    for key, name in REGIONS.get(subject, []):
        out.append(("子地图背景", name, "beauty/page/train-%s.webp" % key, None, "image", ()))
        out.append(("子地图背景", name + "-白天", "beauty/page/train-%s-day.webp" % key, None, "image", ()))
        out.append(("子地图背景", name + "-夜晚", "beauty/page/train-%s-night.webp" % key, None, "image", ()))
    place0 = PLACES.get(subject, PLACES["行测"])[0]
    for key, label in DWELLING_TABS.get(subject, []):
        n = "%s-%s" % (place0, label)
        out.append(("子地图背景", n, "beauty/page/dwelling-%s.webp" % key, None, "image", ()))
        out.append(("子地图背景", n + "-白天", "beauty/page/dwelling-%s-day.webp" % key, None, "image", ()))
        out.append(("子地图背景", n + "-夜晚", "beauty/page/dwelling-%s-night.webp" % key, None, "image", ()))
    if subject in PORTRAIT:
        for key, cn in EXPR:
            rel = PORTRAIT[subject] % key
            out.append(("人物立绘", cn, rel, rel, "image", ()))
    if subject == "申论":
        for cname, cid in SL_CHARS:
            for key, cn in EXPR:
                out.append(("人物立绘", "%s-%s" % (cname, cn), "beauty/portrait/sl-%s-%s.webp" % (cid, key), None, "image", ("sl-%s-%s" % (cid, key),)))
    for key, cn in BGM:
        rel = "beauty/audio/bgm/%s.ogg" % key
        out.append(("音乐", cn, rel, rel, "audio", ()))
    for key, cn in SFX:
        rel = "beauty/audio/sfx/%s.ogg" % key
        out.append(("音效", cn, rel, rel, "audio", ()))
    return out


def _find(paths, folder, stem, kind, aliases=()):
    """先在对应子文件夹找，再在美术文件夹根目录找（方便直接把一批文件丢进来）；主干名或别名都行"""
    exts = IMG if kind == "image" else AUD
    for d in (art_dir(paths) / folder, art_dir(paths)):
        if not d.is_dir():
            continue
        for st in (stem,) + tuple(aliases):
            for ext in exts:
                p = d / (st + ext)
                if p.is_file():
                    return p
    return None


def known(subject):
    """网页资源相对路径的集合（先用它快速判断，避免每个静态文件都去找库）"""
    return {s[2] for s in slots(subject)}


def lookup(paths, subject, asset_rel):
    if not paths or not paths.vault or not paths.train:
        return None
    for folder, stem, rel, _b, kind, al in slots(subject):
        if rel == asset_rel:
            return _find(paths, folder, stem, kind, al)
    return None


def files(paths, subject):
    """有覆盖的资源：[[相对路径, 修改时间ns], …]"""
    if not paths or not paths.vault or not paths.train:
        return []
    out = []
    for folder, stem, rel, _b, kind, al in slots(subject):
        p = _find(paths, folder, stem, kind, al)
        if p:
            out.append([rel, p.stat().st_mtime_ns])
    return out


README = """美术文件夹说明
================
这里放“外观设计文件”。程序优先使用这里的文件，没有就用程序自带的；放进去后刷新网页即可，不需要改源代码、不需要重装。

首页全景/      白天、夜晚                         （地图首页的全景图）
子地图背景/    <地点名>、<地点名>-白天、<地点名>-夜晚   （每个子页面背后的背景；不放就用程序默认的淡透全景）
               洞府还可以每个页签单独一张：洞府-<页签名>、洞府-<页签名>-白天、洞府-<页签名>-夜晚（行测页签：修为与突破、十二经、修行记录、储物袋、修行日志）
人物立绘/      平静、鼓励、讲解、关切、欣慰、眨眼     （引导人物半身立绘；行测、法考的眨眼图只含眼部，位置由程序固定）
               申论每个人单独一套：<姓名>-<表情>，例如 周静宜-平静.png（九位人物见 rpg/art.py）。纯色底（洋红/绿）的图会自动去底。
               小技巧：把图片清单生成的文件（sl-zhoujingyi-calm.png、sl-hall-day.png 这样的英文名）整批直接丢进美术文件夹根目录就行。
音乐/          地图白天、地图夜晚、洞府、学习、突破仪式、对话
音效/          点击、悬停、打开弹窗、关闭弹窗、翻页、答对、答错、连击、奖励、升级、突破、接取任务、完成任务、打字、环境声白天、环境声夜晚、环境声流水

文件名要和上面一致（扩展名随意：图片 webp/png/jpg，音频 ogg/mp3/wav/m4a/opus）。
建议：背景 16:9、1672×941 以上；每张 ≤ 1MB 更流畅；音乐用 ogg/mp3。
想恢复程序自带的：删掉对应文件即可。
“设置 → 外观与音乐 → 导出程序自带美术”会把自带文件按这些名字复制进来当模板（已有的不覆盖）。
"""


def export(paths, subject, assets_dir):
    """把程序自带的对应文件复制进美术文件夹（已有同名主干的文件不覆盖）；创建空的子地图背景文件夹说明"""
    root = art_dir(paths)
    root.mkdir(parents=True, exist_ok=True)
    copied = skipped = missing = 0
    for folder, stem, rel, builtin, kind, al in slots(subject):
        (root / folder).mkdir(parents=True, exist_ok=True)
        if not builtin:
            continue
        src = assets_dir / builtin
        if not src.is_file():
            missing += 1
            continue
        if _find(paths, folder, stem, kind, al):
            skipped += 1
            continue
        shutil.copyfile(src, root / folder / (stem + src.suffix.lower()))
        copied += 1
    readme = root / "说明.txt"
    if not readme.exists():
        readme.write_text(README, encoding="utf-8")
    return {"copied": copied, "skipped": skipped, "missing": missing, "folder": "训练/外观/美术/"}


# ---------------------------------------------------------------- 人物立绘的去底与缩放
def is_portrait(subject, asset_rel):
    return any(rel == asset_rel and folder == "人物立绘" for folder, _s, rel, _b, _k, _a in slots(subject))


def processed(path):
    """立绘（表情图、眨眼图）：生成时背景是纯色（洋红 #FF00FF / 绿 #00FF00）而不是透明的，这里自动去底，并缩到最长边 1200 以内。
    返回 (字节, content-type)；结果缓存在 美术/.cache/ 里（文件改了自动重做）。没有 Pillow、图本来带透明、四角不是同一种纯色时，原样返回（None 表示用原文件）。"""
    try:
        from PIL import Image, ImageChops, ImageFilter
    except Exception:
        return None
    cache = path.parent / ".cache"
    key = cache / ("%s-v2-%d-%d.webp" % (path.stem, path.stat().st_mtime_ns, path.stat().st_size))     # v2：改了算法后旧缓存作废
    if key.is_file():
        return key.read_bytes(), "image/webp"
    try:
        im = Image.open(path)
        im.load()
    except Exception:
        return None
    im = im.convert("RGBA")
    w, h = im.size
    if min(im.getchannel("A").getextrema()) < 250:                 # 本来就有透明：只缩放
        out = im
    else:
        n = max(3, min(w, h) // 100)
        pts = [(x, y) for x0, y0 in ((0, 0), (w - n, 0), (0, h - n), (w - n, h - n)) for x in range(x0, x0 + n) for y in range(y0, y0 + n)]
        cols = sorted(im.getpixel(p)[:3] for p in pts)
        bg = cols[len(cols) // 2]
        if max(max(abs(c[i] - bg[i]) for i in range(3)) for c in (im.getpixel(p)[:3] for p in pts[::max(1, len(pts) // 16)])) > 40:
            out = im                                                  # 四角颜色不一致：不是纯色背景，不去底
        else:
            rgb = im.convert("RGB")
            d = None
            for ch, v in zip(rgb.split(), bg):
                diff = ImageChops.difference(ch, Image.new("L", (w, h), v))
                d = diff if d is None else ImageChops.lighter(d, diff)
            alpha = d.point(lambda v: 0 if v < 38 else 255 if v > 96 else int((v - 38) * 255 / 58))
            alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))     # 收一圈再羽化，去掉底色毛边
            out = im.copy()
            out.putalpha(alpha)
            if bg[0] > 180 and bg[2] > 180 and bg[1] < 90:               # 洋红底：只在半透明的边缘去粉紫色溢出（人物内部颜色一概不动，否则肤色会发绿）
                r, g, b, a = out.split()
                excess = ImageChops.subtract(ImageChops.add(r, b, scale=2.0), g).point(lambda v: int(v * 0.6))     # 红蓝平均比绿多出来的部分＝洋红溢出
                r2 = ImageChops.subtract(r, excess)
                b2 = ImageChops.subtract(b, excess)
                edge = a.point(lambda v: 255 if v < 250 else 0).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.0))
                out = Image.merge("RGBA", (Image.composite(r2, r, edge), g, Image.composite(b2, b, edge), a))
    if max(out.size) > 1200:
        s = 1200 / max(out.size)
        out = out.resize((max(1, round(out.size[0] * s)), max(1, round(out.size[1] * s))), Image.LANCZOS)
    import io
    buf = io.BytesIO()
    out.save(buf, "WEBP", quality=88)
    data = buf.getvalue()
    try:
        cache.mkdir(exist_ok=True)
        for old in cache.glob(path.stem + "-*.webp"):
            old.unlink()
        key.write_bytes(data)
    except OSError:
        pass
    return data, "image/webp"


def character_portraits(paths, subject, cid):
    """申论某个人物的立绘表：{calm, cheer, …, blink:{src,x,y,w,h}}；没有 calm（基础图）就返回 None。
    眨眼图是整幅同取景的闭眼图（不是只含眼部），所以叠满整个画面。"""
    if not paths or not paths.vault or not paths.train:
        return None
    got = {}
    for key, _cn in EXPR:
        rel = "beauty/portrait/sl-%s-%s.webp" % (cid, key)
        p = lookup(paths, subject, rel)
        if p:
            got[key] = "assets/%s?v=%d" % (rel, p.stat().st_mtime_ns)
    if "calm" not in got:
        return None
    blink = got.pop("blink", None)
    if blink:
        got["blink"] = {"src": blink, "x": 0, "y": 0, "w": 1, "h": 1}
    return got


def diagnose(paths, subject):
    """给设置页看的自检：各申论人物立绘找到几张、是否装了 Pillow（去底要用）"""
    try:
        import PIL  # noqa: F401
        pillow = True
    except Exception:
        pillow = False
    chars = []
    if subject == "申论" and paths and paths.vault and paths.train:
        for cname, cid in SL_CHARS:
            n = sum(1 for key, _cn in EXPR if lookup(paths, subject, "beauty/portrait/sl-%s-%s.webp" % (cid, key)))
            if n:
                chars.append("%s %d/6" % (cname, n))
    return {"pillow": pillow, "characters": chars}
