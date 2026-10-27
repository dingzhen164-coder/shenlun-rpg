"""整卷拆分·版面版：把一份模拟试卷PDF（题目+选项，约130题）拆成“每题一张图”的板块复盘，不依赖外部拆分脚本。

为什么要有它：外部脚本 xingce-mokao-split 只认粉笔模考的文字版式；用户的四海/花生套题是“整页是一张图、没有文字层”的扫描PDF
（PDF里一个字都读不出来），旧拆分只会报“共解析0题”。这里改成：
  1. 每页取“文字行 + 位置”：有文字层就直接读；没有就用系统自带OCR（Mac：Vision；Windows：Windows.Media.Ocr；开发机：rapidocr）。
  2. 按版面找出：第N部分（共M题）、小节标题（一、图形推理）、“根据所给材料，回答a～b题”、题号（必须按顺序接续）。
  3. 题的范围 = 从本题题号行到下一个边界（下一题/小节/材料/部分结尾）；跨页就分段。每段从页面上裁成图，空白裁掉。
  4. 写成和旧拆分一样的 训练/模考复盘/第N季/NN-板块.md：每题 `### N. ⚪` + 图片 + 答案栏（正确答案未知），
     资料分析的材料写成 `## 材料（第a-b题）` + 图片。答题、批改、记大比全都沿用原来的文件格式。
题干和A~D四个选项都认出来、题目区域里没有文字框以外的深色内容（图、表、没识别出的公式）的题，写成文字（和粉笔模考卷一样），
同时留一份原图（O题号-n.jpg），答题页“对照原图”可看；图形推理、资料分析材料、带图/表/公式的题、没认全选项的题仍整题裁成原图。
题号按顺序接续，认不出的题号会在报告里列出来。
"""
import json
import os
import re
import subprocess
import sys
import tempfile

PAGE_BOTTOM = .915           # 页脚（“第N页 共M页”）从这里往下
PAD = .004
DPI = 150
DEFAULT_PARTS = [("政治理论", 20), ("常识判断", 15), ("言语理解", 30), ("数量关系", 10), ("判断推理", 35), ("资料分析", 20)]
PART_BOARD = {"政治": "政治理论", "常识": "常识判断", "言语": "逻辑填空", "数量": "数量关系", "判断": "论证逻辑", "资料": "资料分析"}

SKIPPED = []                                                                     # 本次没有文字行的页（0起）
PROGRESS = {"stage": "", "page": 0, "total": 0, "question": 0}        # 网页轮询用：当前做到哪一步


class ScanError(ValueError):
    pass


def set_progress(stage, page=0, total=0, question=0):
    PROGRESS.update(stage=stage, page=page, total=total, question=question)


# ---------------------------------------------------------------- 文字行（文字层 / OCR）
def _clean(text):
    text = str(text or "").strip()
    return re.sub(r"(?<=[^\x00-\x7f])\s+(?=[^\x00-\x7f])", "", text)           # 中文字符之间的空格是OCR/排版留下的


def lines_from_text_layer(page):
    out = []
    w, h = page.rect.width, page.rect.height
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = _clean("".join(s["text"] for s in line["spans"]))
            if text:
                x0, y0, x1, y1 = line["bbox"]
                out.append({"t": text, "x0": x0/w, "y0": y0/h, "x1": x1/w, "y1": y1/h})
    return out


def _ocr_mac(path):
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        raise ScanError("这台 Mac 缺认字组件：请用 Mac App 版（自带），或在终端运行 pip3 install pyobjc-framework-Vision")
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(path), None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(0)
    req.setRecognitionLanguages_(["zh-Hans", "en-US"])
    req.setUsesLanguageCorrection_(False)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise ScanError("Mac 认字失败：%s" % err)
    out = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        box = obs.boundingBox()                         # 原点在左下，0~1
        out.append({"t": _clean(cand[0].string()), "x0": box.origin.x, "y0": 1-(box.origin.y+box.size.height),
                    "x1": box.origin.x+box.size.width, "y1": 1-box.origin.y})
    return out


_WIN_PS = r'''
param([string]$Dir)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('zh-Hans-CN'))
if ($engine -eq $null) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($engine -eq $null) { Write-Error 'NO_OCR_LANGUAGE' }
Get-ChildItem -Path $Dir -Filter *.png | Sort-Object Name | ForEach-Object {
  $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($_.FullName)) ([Windows.Storage.StorageFile])
  $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $W = [double]$bitmap.PixelWidth; $H = [double]$bitmap.PixelHeight
  $items = @()
  foreach ($line in $result.Lines) {
    $x0 = 1e9; $y0 = 1e9; $x1 = 0; $y1 = 0
    foreach ($w in $line.Words) { $r = $w.BoundingRect
      if ($r.X -lt $x0) { $x0 = $r.X }; if ($r.Y -lt $y0) { $y0 = $r.Y }
      if (($r.X + $r.Width) -gt $x1) { $x1 = $r.X + $r.Width }; if (($r.Y + $r.Height) -gt $y1) { $y1 = $r.Y + $r.Height } }
    $items += @{ t = $line.Text; x0 = $x0 / $W; y0 = $y0 / $H; x1 = $x1 / $W; y1 = $y1 / $H }
  }
  $obj = @{ page = $_.BaseName; lines = $items }
  [Console]::WriteLine(($obj | ConvertTo-Json -Compress -Depth 5))
}
'''


def _ocr_windows(paths, progress):
    """整页图片目录交给一次PowerShell处理（每页单开进程太慢），按页流式读回。"""
    d = os.path.dirname(paths[0])
    script = os.path.join(d, "ocr_pages.ps1")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(_WIN_PS)
    try:
        proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Dir", d],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        raise ScanError("调用 Windows OCR 失败：%s" % e)
    result = {}
    for raw in proc.stdout:
        try:
            obj = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            continue
        lines = obj.get("lines") or []
        if isinstance(lines, dict):
            lines = [lines]
        result[obj.get("page")] = [dict(l, t=_clean(l.get("t"))) for l in lines]
        progress(len(result))
    err = proc.stderr.read().decode("utf-8", errors="replace")
    proc.wait()
    if proc.returncode != 0 or not result:
        if "NO_OCR_LANGUAGE" in err:
            raise ScanError("Windows 没装中文 OCR：设置 → 时间和语言 → 语言 → 中文（简体）→ 语言选项 里装上“光学字符识别”")
        raise ScanError("Windows OCR 没认出字：%s" % (err.strip()[-300:] or "没有输出"))
    return [result.get(os.path.splitext(os.path.basename(p))[0], []) for p in paths]


def _ocr_rapid(path):
    from PIL import Image                      # rapidocr 的依赖里自带
    width, height = Image.open(path).size
    from rapidocr_onnxruntime import RapidOCR
    global _RAPID
    try:
        _RAPID
    except NameError:
        _RAPID = RapidOCR()
    res, _ = _RAPID(path)
    out = []
    for box, text, _conf in (res or []):
        xs, ys = [b[0] for b in box], [b[1] for b in box]
        out.append({"t": _clean(text), "x0": min(xs)/width, "y0": min(ys)/height, "x1": max(xs)/width, "y1": max(ys)/height})
    return out


def ocr_engine_name():
    """这台电脑能用哪种OCR：返回名字，没有返回''"""
    if sys.platform == "darwin":
        try:
            import Vision  # noqa: F401
            return "mac"
        except ImportError:
            pass
    if os.name == "nt":
        return "windows"
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return "rapid"
    except ImportError:
        return ""


def ocr_pages(doc, engine=None, only=None):
    """每页的文字行：[[{t,x0,y0,x1,y1}, …], …]。engine给了就用它（测试用），否则文字层优先、没有再用系统OCR。"""
    n = len(doc)
    pages = [None]*n
    need = []
    SKIPPED[:] = []
    for i, page in enumerate(doc):
        if only is not None and i not in only:
            pages[i] = []
            continue
        if len(page.get_text().strip()) >= 30:
            pages[i] = lines_from_text_layer(page)
        else:
            need.append(i)
    set_progress("识别页面文字", n-len(need), n)
    if not need:
        return pages
    with tempfile.TemporaryDirectory() as tmp:
        files = {}
        for i in need:
            f = os.path.join(tmp, "p%03d.png" % i)
            doc[i].get_pixmap(dpi=DPI).save(f)
            files[i] = f
        kind = "custom" if engine else ocr_engine_name()
        if not kind and len(need) <= .4*n:
            # 用户已经先用别的软件做过文字识别（带文字层的PDF）：个别纯图片页（图形题）没有文字，本机又没有OCR时，这些页当作没有文字行，
            # 它们仍会被包含在相邻题目的图片范围里，只是不能在这几页上找题号。
            for i in need:
                pages[i] = []
            SKIPPED[:] = need
            set_progress("识别页面文字", n, n)
            return pages
        if not kind:
            raise ScanError("这份试卷PDF是扫描图片（没有文字层），需要系统自带OCR来认题号：Mac 需要 Mac App 版（自带Vision），Windows 需要装中文OCR；"
                            "其他环境请先把PDF转成带文字的PDF再导入")
        done = n-len(need)
        if kind == "windows":
            lines = _ocr_windows([files[i] for i in need], lambda k: set_progress("识别页面文字", done+k, n))
            for i, ls in zip(need, lines):
                pages[i] = ls
        else:
            for i in need:
                pages[i] = engine(files[i]) if engine else (_ocr_mac(files[i]) if kind == "mac" else _ocr_rapid(files[i]))
                done += 1
                set_progress("识别页面文字", done, n)
    return pages


# ---------------------------------------------------------------- 版面分析
FOOTER = re.compile(r"^第\s*\d+\s*页\s*(?:共\s*\d+\s*页)?$")
PART = re.compile(r"^第\s*([一二三四五六七八九十]+)\s*部分\s*(.*)$")
COUNT = re.compile(r"共\s*(\d+)\s*[小道]?\s*题")
RANGE = r"(\d{1,3})\s*[~～\-—–至到]+\s*(\d{1,3})\s*题"
GROUP = re.compile(r"^[一二三四五六七八九十]?\s*[、，,.]?\s*根据.{0,14}材料.{0,8}回答\s*" + RANGE)
MARK = re.compile(r"请回答\s*" + RANGE)
SUB = re.compile(r"^[一二三四五六七八九十]?\s*[、，,.]\s*(.{2,16})$")
END = re.compile(r"^[※\*＊]{1,}.*(?:结束|到此)")
QSTART = re.compile(r"^(\d{1,3})\s*[.．。、,，·]\s*(.*)$")
SUB_BOARD = (("图形", "图形推理"), ("定义", "定义判断"), ("类比", "类比推理"), ("逻辑填空", "逻辑填空"), ("填空", "逻辑填空"), ("语句", "语句排序"),
             ("排序", "语句排序"), ("阅读", "片段阅读"), ("中心", "片段阅读"), ("逻辑", "论证逻辑"), ("论证", "论证逻辑"))
NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _order(lines):
    """按视觉行排序：中心相差不到半个行高算同一行，同一行按x。"""
    rows = []
    for line in sorted(lines, key=lambda l: (l["y0"]+l["y1"])/2):
        yc, h = (line["y0"]+line["y1"])/2, max(line["y1"]-line["y0"], .008)
        if rows and abs(yc-rows[-1]["yc"]) <= .5*max(h, rows[-1]["h"]):
            rows[-1]["items"].append(line)
        else:
            rows.append({"yc": yc, "h": h, "items": [line]})
    return [l for r in rows for l in sorted(r["items"], key=lambda l: l["x0"])]


VERBAL = ("逻辑填空", "片段阅读", "语句排序")


def classify_verbal(text):
    """言语理解没有小节标题时，按题干里的话认是哪一种；没有任何线索返回None（OCR把题干认乱了）"""
    if re.search(r"填入画横线|填入横线|依次填入|横线处", text) or "____" in text or "＿＿" in text:
        return "逻辑填空"
    if re.search(r"语序|排序|重新排列|排列", text):
        return "语句排序"
    if re.search(r"概括|主旨|意在|理解|表述|文段|文章|作者|观点|不正确|正确的是|推断", text):
        return "片段阅读"
    return None


def _monotone(labels):
    """言语理解里的题型是按 逻辑填空 → 片段阅读 → 语句排序 的顺序排的：在这个顺序约束下，选和各题线索最吻合的分法
    （个别题被OCR认乱了，线索是None，不影响整体）。"""
    n = len(labels)
    best = [[0]*3 for _ in range(n+1)]
    back = [[0]*3 for _ in range(n+1)]
    for i, lab in enumerate(labels):
        for s in range(3):
            cost = 0 if lab is None or VERBAL.index(lab) == s else 1
            prev = min(range(s+1), key=lambda p: best[i][p]) if i else 0
            best[i+1][s] = (best[i][prev] if i else 0)+cost
            back[i+1][s] = prev
    s = min(range(3), key=lambda x: best[n][x])
    out = [None]*n
    for i in range(n, 0, -1):
        out[i-1] = VERBAL[s]
        s = back[i][s]
    return out


D_OPTION = re.compile(r"^[Dd]\s*[.．、,，:：]")


def _next_start(seq, a, b):
    """seq[a]是第a题的开头，seq[b]是后面一题的开头：找出夹在中间、题号没认出来的那一题从哪一行开始。
    做法：先走过第a题自己的选项（到D选项为止，含D选项折行），之后的第一行就是下一题。"""
    d = next((i for i in range(a, b) if D_OPTION.match(seq[i]["t"])), None)
    if d is None:
        return None
    i = d+1
    pitch = max(.012, seq[d]["y1"]-seq[d]["y0"])*1.0
    last = seq[d]
    while i < b:
        line = seq[i]
        same_row = abs((line["y0"]+line["y1"])/2-(last["y0"]+last["y1"])/2) < .5*pitch+.004 and line["page"] == last["page"]
        wrapped = line["x0"] >= .165 and line["page"] == last["page"] and line["y0"]-last["y1"] < 1.2*pitch
        if same_row or wrapped:
            last = line
            i += 1
            continue
        return i
    return None


def _start_y(seq, at):
    """补出来的那一题从哪里开始裁：它的第一行（带题号）可能被OCR丢了，所以从上一行的下沿往下开始，别把题号行切掉。"""
    line, prev = seq[at], seq[at-1] if at else None
    if prev and prev["page"] == line["page"] and 0 < line["y0"]-prev["y1"] < .06:
        return max(prev["y1"]+.002, line["y0"]-.045)
    return line["y0"]


def _fill_gaps(seq, questions, parts, boundaries, ends=()):
    """只差一题、中间那题的题号被OCR丢了（常见于带下划线的填空题）：按“选项之后就是下一题”补上。"""
    questions.sort(key=lambda q: q["pos"])
    k = 0
    while k < len(questions)-1:
        a, b = questions[k], questions[k+1]
        if b["num"]-a["num"] == 2 and a["part"] == b["part"]:
            at = _next_start(seq, a["pos"], b["pos"])
            if at is not None and at > a["pos"]:
                line = seq[at]
                y0 = _start_y(seq, at)
                q = {"num": a["num"]+1, "board": a["board"], "page": line["page"], "y0": y0, "lines": [line["t"]], "part": a["part"],
                     "virtual": True, "pos": at}
                questions.insert(k+1, q)
                boundaries.append((line["page"], y0, "q"))
        k += 1
    # 一个部分的最后一题的题号丢了：它夹在倒数第二题和“第N部分结束”之间
    for idx, part in enumerate(parts, 1):
        mine = [q for q in questions if q["part"] == idx]
        if mine and part.get("end") and mine[-1]["num"] == part["end"]-1:
            stop = next((e for e in sorted(ends) if e > mine[-1]["pos"]), len(seq))
            at = _next_start(seq, mine[-1]["pos"], stop)
            if at is not None and at > mine[-1]["pos"] and at < stop:
                line = seq[at]
                y0 = _start_y(seq, at)
                questions.append({"num": part["end"], "board": mine[-1]["board"], "page": line["page"], "y0": y0, "lines": [line["t"]],
                                  "part": idx, "virtual": True, "pos": at})
                boundaries.append((line["page"], y0, "q"))
    questions.sort(key=lambda q: q["pos"])


def analyze(pages, part_sizes=None):
    """pages：每页文字行。返回 {questions, materials, parts, missing}；questions里每题带 segments=[(页, y0, y1)]。"""
    seq = []
    for pi, lines in enumerate(pages):
        kept = [dict(l, t=_clean(l.get("t")), page=pi) for l in lines if _clean(l.get("t"))]
        kept = [l for l in kept if not FOOTER.match(l["t"]) and l["y0"] < PAGE_BOTTOM]
        seq.extend(_order(kept))
    sizes = list(part_sizes or [n for _, n in DEFAULT_PARTS])
    parts, questions, materials, marks, ends = [], [], [], [], []
    part = None
    board = ""
    expected = 1
    cur = None                      # 正在收集内容的区域：题目或材料
    boundaries = []                 # 所有“会截断上一块”的位置：(页, y0)
    pending_first = None            # 本部分第一条内容行（第1题的题号没认出来时用来补）
    after_part_row = None
    group_open = None

    def close():
        nonlocal cur
        cur = None

    def start_question(num, line, text, virtual=False):
        nonlocal cur, expected
        q = {"num": num, "board": board, "page": line["page"], "y0": line["y0"], "lines": [text], "part": len(parts), "virtual": virtual, "pos": line["pos"]}
        questions.append(q)
        boundaries.append((line["page"], line["y0"], "q"))
        cur = q
        expected = num+1
        return q

    for pos, line in enumerate(seq):
        line["pos"] = pos
        t = line["t"]
        m = PART.match(t)
        if m and len(t) <= 24 and not COUNT.search(t[:3]):
            idx = NUM.get(m.group(1)[:1], len(parts)+1)
            if parts and parts[-1]["end"] is None:
                # 上一个“第N部分”一直没等到“共M题”：是封面/目录里的一行，不是真正的开头，丢掉（过去在这里 None+1 直接报错）
                parts.pop()
                for i in range(len(boundaries)-1, -1, -1):
                    if boundaries[i][2] == "part":
                        del boundaries[i]
                        break
            part = {"idx": idx, "name": COUNT.sub("", m.group(2)).strip("（）() ，,、 "), "count": None, "start": expected if not parts else parts[-1]["end"]+1, "end": None,
                    "page": line["page"], "y0": line["y0"]}
            parts.append(part)
            boundaries.append((line["page"], line["y0"], "part"))
            close()
            after_part_row = line
            pending_first = None
            group_open = None
            board = ""
            hc = COUNT.search(m.group(2))
            if hc:                                    # 部分名称和“共M题”写在同一行
                part["count"] = int(hc.group(1)) or (sizes[idx-1] if 0 < idx <= len(sizes) else 0)
                part["end"] = part["start"]+part["count"]-1
                expected = part["start"]
                board = next((b for k, b in PART_BOARD.items() if k in part["name"]), "")
            continue
        if part and after_part_row is not None and part["count"] is None and abs((line["y0"]+line["y1"])/2-(after_part_row["y0"]+after_part_row["y1"])/2) < .012 and not COUNT.search(t):
            part["name"] = (part["name"]+t).strip()        # 同一行右边是部分名称（“第五部分” “判断推理”）
            after_part_row = line
            continue
        c = COUNT.search(t)
        if part and part["count"] is None and c:
            part["count"] = int(c.group(1))
            default = sizes[part["idx"]-1] if 0 < part["idx"] <= len(sizes) else part["count"]
            part["count"] = part["count"] or default
            part["end"] = part["start"]+part["count"]-1
            expected = part["start"]
            board = next((b for k, b in PART_BOARD.items() if k in part["name"]), "")
            continue
        if part and part["end"] is None:
            continue
        if not part:
            continue
        if END.match(t):
            ends.append(line["pos"])
            boundaries.append((line["page"], line["y0"], "end"))
            close()
            continue
        g = GROUP.match(t)
        if g:
            group_open = {"a": int(g.group(1)), "b": int(g.group(2)), "page": line["page"], "y0": line["y0"], "lines": [t]}
            materials.append(group_open)
            boundaries.append((line["page"], line["y0"], "group"))
            board = "资料分析"
            cur = group_open
            continue
        s = SUB.match(t)
        if s and line["x0"] < .3 and len(t) <= 20 and not QSTART.match(t):
            name = s.group(1)
            hit = next((b for k, b in SUB_BOARD if k in name), None)
            if hit and not (group_open and cur is group_open and False):
                board = hit
                boundaries.append((line["page"], line["y0"], "sub"))
                close()
                continue
        q = QSTART.match(t)
        if q:
            num = int(q.group(1))
            ok = num == expected or (expected < num <= expected+2 and (part["end"] is None or num <= part["end"]) and cur is not None)
            if num == part["start"]+1 and not any(x["part"] == len(parts) for x in questions) and pending_first is not None:
                start_question(part["start"], pending_first, "", virtual=True)       # 第1题的题号没认出来：从本部分第一条内容开始
                ok = True
            if ok and (part["end"] is None or num <= part["end"]):
                start_question(num, line, q.group(2))
                continue
        if pending_first is None and not any(x["part"] == len(parts) for x in questions) and not MARK.search(t):
            pending_first = line
        if cur is not None:
            cur["lines"].append(t)
    if not questions:
        raise ScanError("没有认出任何题号：这份试卷的版式可能和“第N部分（共M题）+ 题号 1.”不同，请把这份PDF发给开发者看看")
    _fill_gaps(seq, questions, parts, boundaries, ends)
    # 题的范围
    boundaries.sort()
    tops, bottoms = {}, {}
    for pi, lines in enumerate(pages):
        kept = [l for l in lines if _clean(l.get("t")) and not FOOTER.match(_clean(l["t"])) and l["y0"] < PAGE_BOTTOM]
        tops[pi] = max(0.0, (min((l["y0"] for l in kept), default=.05))-.02)

    def segments(page, y0, end_page, end_y):
        segs = []
        for pi in range(page, end_page+1):
            a = max(0.0, y0-PAD) if pi == page else tops.get(pi, .04)
            b = max(a, end_y-PAD) if pi == end_page else PAGE_BOTTOM
            if b-a > .012:
                segs.append((pi, a, b))
        return segs

    def next_boundary(page, y0, kinds=None):
        for bp, by, kind in boundaries:
            if (bp, by) > (page, y0) and (kinds is None or kind in kinds):
                return bp, by
        return len(pages)-1, PAGE_BOTTOM

    for q in questions:
        ep, ey = next_boundary(q["page"], q["y0"])
        q["segments"] = segments(q["page"], q["y0"], ep, ey)
    for mat in materials:
        ep, ey = next_boundary(mat["page"], mat["y0"], {"q"})
        mat["segments"] = segments(mat["page"], mat["y0"], ep, ey)
    for idx, part in enumerate(parts, 1):
        if part["name"].startswith("言语"):
            mine = [q for q in questions if q["part"] == idx]
            for q, board in zip(mine, _monotone([classify_verbal(" ".join(q["lines"])) for q in mine])):
                q["board"] = board
    for q in questions:
        if not q["board"]:
            q["board"] = parts[q["part"]-1]["name"] if q["part"] else "政治理论"
    found = {q["num"] for q in questions}
    last = max(found)
    total = parts[-1]["end"] if parts and parts[-1]["end"] else last
    return {"questions": questions, "materials": materials, "parts": parts, "total": total, "seq": seq,
            "missing": [n for n in range(1, total+1) if n not in found]}


# ---------------------------------------------------------------- 裁图
def _trim(page, rect, dpi=60):
    """低分辨率灰度看一遍，把上下的空白去掉（留一点边）。返回新的rect；整块都是空白返回None。"""
    import pymupdf as fitz
    pix = page.get_pixmap(clip=rect, dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
    w, h, data = pix.width, pix.height, pix.samples
    stride = pix.stride
    rows = [min(data[r*stride:r*stride+w]) < 185 for r in range(h)]           # 水印是很浅的灰，不算有内容
    if not any(rows):
        return None
    first, last = rows.index(True), len(rows)-1-rows[::-1].index(True)
    scale = rect.height/h
    margin = 5*scale
    return fitz.Rect(rect.x0, max(rect.y0, rect.y0+first*scale-margin), rect.x1, min(rect.y1, rect.y0+(last+1)*scale+margin))


def crop_segments(doc, segments, folder, stem, dpi=DPI):
    """每段裁成一张jpg写进folder，返回文件名列表"""
    import pymupdf as fitz
    names = []
    for k, (pi, a, b) in enumerate(segments, 1):
        page = doc[pi]
        rect = fitz.Rect(page.rect.x0, page.rect.y0+a*page.rect.height, page.rect.x1, page.rect.y0+b*page.rect.height)
        rect = _trim(page, rect)
        if rect is None or rect.height < 6:
            continue
        pix = page.get_pixmap(clip=rect, dpi=dpi, alpha=False)
        name = "%s-%d.jpg" % (stem, len(names)+1)
        pix.save(os.path.join(folder, name), jpg_quality=88)
        names.append(name)
    return names


# ---------------------------------------------------------------- 文字题 / 图片题
OPTION = re.compile(r"^[（(]?([A-D])\s*[.．、:：)）]\s*(.*)$")
ITEM = re.compile(r"^(?:[①-⑩⑴-⒇]|[（(]\s*\d+\s*[）)]|\d+\s*[.．、]|[一二三四五六七八九十]+\s*[、.．]|[甲乙丙丁][.．、:：])")
SENTENCE_END = re.compile(r"[。！？；：:?!）)”’]$")
FIGURE_RATIO = .005                # 文字框以外的深色像素占题目区域的比例超过它，认为题里有图/表/公式没识别出来
MIN_STEM = 6


def segment_lines(seq, segments):
    """题目各段范围内的文字行（按阅读顺序）"""
    out = []
    for pi, a, b in segments:
        out += [l for l in seq if l["page"] == pi and a-.004 <= (l["y0"]+l["y1"])/2 <= b+.004]
    return out


def split_choices(lines):
    """文字行 → (题干段落, {A..D: 文字})；认不全 A~D 四个选项、或题干太短就返回None（改用原图）。"""
    texts = [l["t"] for l in lines]
    if texts and (m := QSTART.match(texts[0])):
        texts[0] = m.group(2)
    stem, options, label = [], {}, None
    for t in texts:
        if not t.strip():
            continue
        m = OPTION.match(t)
        want = "ABCD"[len(options)] if len(options) < 4 else None
        if m and m.group(1) == want:
            label = m.group(1)
            options[label] = m.group(2).strip()
            continue
        if label:
            options[label] = (options[label]+t).strip()
        else:
            stem.append(t)
    paragraphs = []
    for t in stem:
        if paragraphs and not ITEM.match(t) and not SENTENCE_END.search(paragraphs[-1]):
            paragraphs[-1] += t
        else:
            paragraphs.append(t)
    if len(options) < 4 or any(not v for v in options.values()) or len("".join(paragraphs)) < MIN_STEM:
        return None
    return paragraphs, options


def has_figure(doc, seq, segments, dpi=60):
    """题目区域里有没有“文字框以外”的深色内容（图形、表格、没识别出来的公式）。有就整题保留原图，宁可用图也不显示识别错的字。"""
    import pymupdf as fitz
    dark = total = 0
    for pi, a, b in segments:
        page = doc[pi]
        rect = fitz.Rect(page.rect.x0, page.rect.y0+a*page.rect.height, page.rect.x1, page.rect.y0+b*page.rect.height)
        pix = page.get_pixmap(clip=rect, dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
        w, h, data, stride = pix.width, pix.height, pix.samples, pix.stride
        covered = bytearray(w*h)
        for l in seq:
            if l["page"] != pi or not a-.004 <= (l["y0"]+l["y1"])/2 <= b+.004:
                continue
            x0, x1 = max(0, int(l["x0"]*w)-3), min(w, int(l["x1"]*w)+3)
            y0, y1 = max(0, int((l["y0"]-a)/(b-a)*h)-3), min(h, int((l["y1"]-a)/(b-a)*h)+3)
            for y in range(y0, y1):
                covered[y*w+x0:y*w+x1] = b"\x01"*(x1-x0)
        for y in range(h):
            row = data[y*stride:y*stride+w]
            base = y*w
            dark += sum(1 for x in range(w) if row[x] < 150 and not covered[base+x])
        total += w*h
    return total > 0 and dark/total > FIGURE_RATIO


def text_body(paragraphs, options):
    return "\n".join(paragraphs+["- **%s.** %s" % (k, v) for k, v in options.items()])


# ---------------------------------------------------------------- 写成复盘文件
BOARD_ORDER = ("政治理论", "常识判断", "逻辑填空", "片段阅读", "语句排序", "数量关系", "图形推理", "定义判断", "类比推理", "论证逻辑", "资料分析")


def write_review(folder, doc, result):
    """folder：训练/模考复盘/第N季。返回 {board: [题号…]}。已有的板块文件不覆盖（保留你的笔记）——调用方先判断。"""
    att = os.path.join(folder, "attachments")
    os.makedirs(att, exist_ok=True)
    mats = {m["a"]: m for m in result["materials"]}
    by_board = {}
    for q in sorted(result["questions"], key=lambda q: q["num"]):
        by_board.setdefault(q["board"] or "政治理论", []).append(q)
    written = {}
    texted = result.setdefault("texted", [])
    ordered = sorted(by_board, key=lambda b: (min(q["num"] for q in by_board[b])))
    for k, board in enumerate(ordered, 1):
        text = []
        for q in by_board[board]:
            set_progress("裁剪题目图片", question=q["num"])
            mat = mats.get(q["num"])
            if mat:
                names = crop_segments(doc, mat["segments"], att, "M%03d-%03d" % (mat["a"], mat["b"]))
                text.append("## 材料（第%d-%d题）\n%s\n" % (mat["a"], mat["b"], "\n".join("![[%s]]" % n for n in names)))
            parsed = None
            if q["board"] != "图形推理":
                parsed = split_choices(segment_lines(result.get("seq", []), q["segments"]))
                if parsed and has_figure(doc, result["seq"], q["segments"]):
                    parsed = None
            if parsed:
                crop_segments(doc, q["segments"], att, "O%03d" % q["num"], dpi=110)     # 留一份原图，页面上“对照原图”用
                body = text_body(*parsed)
                texted.append(q["num"])
            else:
                names = crop_segments(doc, q["segments"], att, "Q%03d" % q["num"])
                body = "\n".join("![[%s]]" % n for n in names) or "（这题没有截到图，请对照原卷）"
            text.append("### %d. ⚪\n%s\n> [!check]- 答案\n> 正确答案：**?**　我的答案：**—**　未作答\n---\n" % (q["num"], body))
        with open(os.path.join(folder, "%02d-%s.md" % (k, board)), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(text))
        written[board] = [q["num"] for q in by_board[board]]
    return written


def split(paths, pdf_file, season, engine=None, part_sizes=None):
    """拆分入口：pdf_file是本机上的试卷PDF；写到 训练/模考复盘/第N季/。返回报告。"""
    try:
        import pymupdf as fitz
    except ImportError:
        raise ScanError("缺少 pymupdf：请使用完整电脑安装包")
    folder = paths.train / "模考复盘" / ("第%d季" % season)
    if any(folder.glob("[0-9][0-9]-*.md")):
        raise ScanError("第%d季已经有复盘文件，先在宗门大比里删除再重新导入" % season)
    with fitz.open(str(pdf_file)) as doc:
        if doc.needs_pass:
            raise ScanError("请先解密PDF")
        set_progress("读取PDF", 0, len(doc))
        pages = ocr_pages(doc, engine)
        set_progress("分析版面")
        result = analyze(pages, part_sizes)
        folder.mkdir(parents=True, exist_ok=True)
        written = write_review(str(folder), doc, result)
    set_progress("完成", len(pages), len(pages), result["total"])
    modules = {}
    from . import mock
    for board, nums in written.items():
        modules[mock.MODULE_OF.get(board, board)] = modules.get(mock.MODULE_OF.get(board, board), 0)+len(nums)
    return {"season": season, "total": result["total"], "found": len(result["questions"]), "missing": result["missing"],
            "modules": modules, "boards": {b: len(n) for b, n in written.items()}, "materials": len(result["materials"]),
            "skipped_pages": [i+1 for i in SKIPPED], "texted": len(result.get("texted", [])),
            "split_log": "按版面拆分：认出 %d/%d 题（%d 题转成文字，其余保留原图），%d 组材料%s" % (len(result["questions"]), result["total"], len(result.get("texted", [])), len(result["materials"]),
                                                    ("；第%s页没有文字（本机也没有文字识别），这些页上的题号没法认" % "、".join(str(i+1) for i in SKIPPED)) if SKIPPED else "")}
