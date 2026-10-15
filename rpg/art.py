"""
美术文件夹（3.2.x）：库里的 训练/外观/美术/ 专门放“外观设计文件”，程序优先用这里的文件，没有才用程序自带的。
这样想换首页全景、每个子地图的背景、人物立绘、背景音乐、音效，都不用动源代码：把文件按下面的中文名放进对应子文件夹，刷新网页就生效；
想看看程序自带的长什么样、当模板改，点 设置 → 外观与音乐 → “导出程序自带美术”，会把自带文件按这些名字复制进来（已有的不覆盖）。

子文件夹与文件名（扩展名随意：图片 webp/png/jpg，音频 ogg/mp3/wav/m4a/opus）：
  首页全景/      白天、夜晚
  子地图背景/    <地点名>、<地点名>-白天、<地点名>-夜晚      （地点名随科目：行测 洞府/问道群峰/试炼塔/…，申论 办公室/知识办理中心/…，法考 营地/冒险大厅/…）
  人物立绘/      平静、鼓励、讲解、关切、欣慰、眨眼          （只对有半身立绘的科目；眨眼图的位置由程序固定，换图请保持同样的取景）
  音乐/          地图白天、地图夜晚、洞府、学习、突破仪式、对话
  音效/          点击、悬停、打开弹窗、关闭弹窗、翻页、答对、答错、连击、奖励、升级、突破、接取任务、完成任务、打字、环境声白天、环境声夜晚、环境声流水
子地图背景的优先级：<地点>-白天/夜晚（按亮暗主题）→ <地点> → 程序默认的淡透全景。

实现：网页请求 assets/<相对路径> 时，api.py 先问 art.lookup()；网页首页（index.html）里注入 window.ART_FILES（有覆盖的文件及修改时间）供前端判断。
所有名字写死在下面的表里，不接受任意路径，不会读到美术文件夹以外的文件。
"""
import shutil

FOLDER_REL = ("外观", "美术")
IMG = (".webp", ".png", ".jpg", ".jpeg")
AUD = (".ogg", ".mp3", ".wav", ".m4a", ".opus")
VIEWS = ["dwelling", "train", "bank", "contest", "skeleton", "notes", "tianji", "settings"]
PLACES = {
    "行测": ["洞府", "问道群峰", "试炼塔", "演武场", "藏经阁", "灵台手札", "天机台", "设置"],
    "申论": ["办公室", "知识办理中心", "实操训练中心", "年度考核", "档案室", "公务手账", "天机台", "设置"],
    "法考": ["营地", "冒险大厅", "试炼塔", "竞技场", "咒文书馆", "魔法手记", "天机台", "设置"],
}
HOME = {"行测": ("sect/xc-sect-day.webp", "sect/xc-sect-night.webp"), "申论": ("shenlun/hall.webp", None),
        "法考": ("academy/scene/mg-academy-day.webp", "academy/scene/mg-academy-night.webp")}
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
    """[(子文件夹, 文件名主干, 网页资源相对路径 assets/ 之后, 程序自带文件相对路径或 None, 'image'|'audio')]"""
    out = []
    day, night = HOME.get(subject, HOME["行测"])
    out.append(("首页全景", "白天", day, day, "image"))
    out.append(("首页全景", "夜晚", night or "beauty/page/home-night.webp", night, "image"))
    for view, place in zip(VIEWS, PLACES.get(subject, PLACES["行测"])):
        out.append(("子地图背景", place, "beauty/page/%s.webp" % view, None, "image"))
        out.append(("子地图背景", place + "-白天", "beauty/page/%s-day.webp" % view, None, "image"))
        out.append(("子地图背景", place + "-夜晚", "beauty/page/%s-night.webp" % view, None, "image"))
    if subject in PORTRAIT:
        for key, cn in EXPR:
            rel = PORTRAIT[subject] % key
            out.append(("人物立绘", cn, rel, rel, "image"))
    for key, cn in BGM:
        rel = "beauty/audio/bgm/%s.ogg" % key
        out.append(("音乐", cn, rel, rel, "audio"))
    for key, cn in SFX:
        rel = "beauty/audio/sfx/%s.ogg" % key
        out.append(("音效", cn, rel, rel, "audio"))
    return out


def _find(paths, folder, stem, kind):
    d = art_dir(paths) / folder
    if not d.is_dir():
        return None
    exts = IMG if kind == "image" else AUD
    for ext in exts:
        p = d / (stem + ext)
        if p.is_file():
            return p
    return None


def known(subject):
    """网页资源相对路径的集合（先用它快速判断，避免每个静态文件都去找库）"""
    return {s[2] for s in slots(subject)}


def lookup(paths, subject, asset_rel):
    if not paths or not paths.vault or not paths.train:
        return None
    for folder, stem, rel, _b, kind in slots(subject):
        if rel == asset_rel:
            return _find(paths, folder, stem, kind)
    return None


def files(paths, subject):
    """有覆盖的资源：[[相对路径, 修改时间ns], …]"""
    if not paths or not paths.vault or not paths.train:
        return []
    out = []
    for folder, stem, rel, _b, kind in slots(subject):
        p = _find(paths, folder, stem, kind)
        if p:
            out.append([rel, p.stat().st_mtime_ns])
    return out


README = """美术文件夹说明
================
这里放“外观设计文件”。程序优先使用这里的文件，没有就用程序自带的；放进去后刷新网页即可，不需要改源代码、不需要重装。

首页全景/      白天、夜晚                         （地图首页的全景图）
子地图背景/    <地点名>、<地点名>-白天、<地点名>-夜晚   （每个子页面背后的背景；不放就用程序默认的淡透全景）
人物立绘/      平静、鼓励、讲解、关切、欣慰、眨眼     （引导人物半身立绘；眨眼图只含眼部，位置由程序固定）
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
    for folder, stem, rel, builtin, kind in slots(subject):
        (root / folder).mkdir(parents=True, exist_ok=True)
        if not builtin:
            continue
        src = assets_dir / builtin
        if not src.is_file():
            missing += 1
            continue
        if _find(paths, folder, stem, kind):
            skipped += 1
            continue
        shutil.copyfile(src, root / folder / (stem + src.suffix.lower()))
        copied += 1
    readme = root / "说明.txt"
    if not readme.exists():
        readme.write_text(README, encoding="utf-8")
    return {"copied": copied, "skipped": skipped, "missing": missing, "folder": "训练/外观/美术/"}
