"""
认字（OCR）：手写 / 截图 → 文字。公务手账“领导编纂”（手写转 Markdown）用。

认字用系统自带的 OCR：Windows 用 Windows.Media.Ocr（PowerShell 调，不装东西；Windows 10/11 装了中文语言就有），
Mac 用苹果的 Vision（Mac App 里带着 pyobjc；源码版要 pip install pyobjc-framework-Vision）。
都不行时，也可以把文字复制粘贴进来。出错抛 OcrError，消息直接给用户看。
谁调用：rpg/notes.py。
"""
import os
import re
import subprocess
import sys
import tempfile

PS = r'''
param([string]$Path)
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
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('zh-Hans-CN'))
if ($engine -eq $null) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($engine -eq $null) { Write-Error 'NO_OCR_LANGUAGE' }
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
foreach ($line in $result.Lines) { [Console]::WriteLine($line.Text) }
'''


class OcrError(Exception):
    pass


def ocr_mac(path):
    """Mac：苹果 Vision 认字。按从上到下、从左到右排成一行一行（和 Windows OCR 的输出一样给解析器用）"""
    try:
        import Vision
        from Foundation import NSURL
    except ImportError:
        raise OcrError("这台 Mac 缺认字组件：用 Mac App 版，或在终端运行 pip3 install pyobjc-framework-Vision；也可以把文字粘贴进来")
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(path), None)
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(0)                     # 0 = 准确优先
    req.setRecognitionLanguages_(["zh-Hans", "en-US"])
    req.setUsesLanguageCorrection_(False)           # 数字、百分比别被“纠正”
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise OcrError("Mac 认字失败（%s）：把文字粘贴进来也行" % err)
    items = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        box = obs.boundingBox()                     # 原点在左下，0~1
        items.append((1 - (box.origin.y + box.size.height / 2), box.origin.x, box.size.height, str(cand[0].string())))
    items.sort()
    rows = []                                       # 中线差不到半个字高的算同一行
    for y, x, h, t in items:
        if rows and abs(rows[-1][0] - y) < h / 2:
            rows[-1][1].append((x, t))
        else:
            rows.append([y, [(x, t)]])
    return "\n".join(" ".join(t for _, t in sorted(r)) for _, r in rows) + "\n"


def ocr(data):
    """一张图 → 文字（一行一行）。Windows、Mac 能用"""
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "ocr.png")
            with open(img, "wb") as f:
                f.write(data)
            out = ocr_mac(img)
        if not out.strip():
            raise OcrError("Mac 没认出字：截图清楚吗？也可以把文字粘贴进来")
        return out
    if os.name != "nt":
        raise OcrError("这台电脑没有能用的自带 OCR：把图片里的文字复制粘贴进来也行")
    with tempfile.TemporaryDirectory() as d:
        img = os.path.join(d, "ocr.png")
        with open(img, "wb") as f:
            f.write(data)
        script = os.path.join(d, "ocr.ps1")
        with open(script, "w", encoding="utf-8-sig") as f:
            f.write(PS)
        try:
            r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Path", img],
                               capture_output=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise OcrError("调用 Windows OCR 失败（%s）：把报告文字复制粘贴进来也行" % e)
        out = r.stdout.decode("utf-8", errors="replace")
        if r.returncode != 0 or not out.strip():
            err = r.stderr.decode("utf-8", errors="replace")
            if "NO_OCR_LANGUAGE" in err:
                raise OcrError("Windows 没装中文 OCR：设置 → 时间和语言 → 语言 → 中文（简体）→ 语言选项 里装上“光学字符识别”，或者把文字粘贴进来")
            raise OcrError("Windows OCR 没认出字：%s" % (err.strip()[-300:] or "没有输出"))
        return out


# ---------------------------------------------------------------- 解析报告文字
MODULES = {"政治理论": "政治理论", "常识判断": "常识判断", "言语理解与表达": "言语理解", "言语理解": "言语理解",
           "数量关系": "数量关系", "判断推理": "判断推理", "资料分析": "资料分析"}
SUBS = {"图形推理": "判断推理", "定义判断": "判断推理", "类比推理": "判断推理", "逻辑判断": "判断推理",
        "逻辑填空": "言语理解", "片段阅读": "言语理解", "语句表达": "言语理解"}
STAT = re.compile(r"共(\d+)题[,，]?答对(\d+)题[,，]?(?:正确率(\d+)%?[,，]?)?(?:用时(\d+)分钟?)?")
NUM = r"(\d{1,3}(?:\.\d{1,2})?)"
