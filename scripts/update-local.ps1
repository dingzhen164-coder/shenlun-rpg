# 申论官途：安装 / 更新（Windows PowerShell）。
# 程序装在 <申论库>\训练\程序\，你的数据（训练\采分点、作答、存档……）在 程序 文件夹外面，更新不会碰。
# 流程：先下载并检查 → 备份旧程序到 训练\更新备份\ → 替换程序；出错自动恢复旧程序。
# 用法：
#   默认从 GitHub 直接下载：      powershell -ExecutionPolicy Bypass -File update-local.ps1
#   用浏览器下载到“下载”文件夹的 zip： 加参数 -Local（取下载文件夹里最新的 shenlun-rpg*.zip）
param(
    [string]$TrainPath = 'C:\Users\29356\Desktop\申论obsidian\申论\训练',
    [string]$Revision = 'claude/dazzling-fermat-0n9kbc',
    [switch]$Local
)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ($Revision -notmatch '^[A-Za-z0-9._/-]+$') { throw '版本（分支名）里有不允许的字符。' }
if (-not (Test-Path -LiteralPath $TrainPath -PathType Container)) {
    New-Item -ItemType Directory -Path $TrainPath -Force | Out-Null   # 第一次安装：自动建训练文件夹
}
$TrainPath = (Resolve-Path -LiteralPath $TrainPath).Path
$program = Join-Path $TrainPath '程序'
$running = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'python3.exe' OR Name = 'py.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and ($_.CommandLine.Replace('/', '\').Contains($program)) }
if ($running) { throw '请先关闭申论官途的黑色窗口（终端），再运行更新。' }
$stage = Join-Path $TrainPath ('.更新临时-' + [Guid]::NewGuid().ToString('N'))
$backupRoot = Join-Path $TrainPath '更新备份'
$oldProgram = Join-Path $stage '旧程序'
$utf8 = New-Object System.Text.UTF8Encoding($false)
try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    $zip = Join-Path $stage 'source.zip'
    if ($Local) {
        $found = Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE 'Downloads') -Filter 'shenlun-rpg*.zip' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $found) { throw '“下载”文件夹里没有 shenlun-rpg*.zip，请先在 GitHub 页面点 Code → Download ZIP。' }
        Write-Host "使用本地文件：$($found.FullName)"
        Copy-Item -LiteralPath $found.FullName -Destination $zip
    } else {
        $url = "https://github.com/dingzhen164-coder/shenlun-rpg/archive/refs/heads/$Revision.zip"
        Write-Host "正在下载：$url"
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    }
    $unpack = Join-Path $stage '解压'
    Expand-Archive -LiteralPath $zip -DestinationPath $unpack
    $source = Get-ChildItem -LiteralPath $unpack -Directory | Select-Object -First 1
    if (-not $source) { throw '下载内容无效。' }
    foreach ($required in @('server.py', 'rpg\api.py', 'rpg\subjects.py', 'rpg\shenlun_grader.py', 'web\app.js')) {
        if (-not (Test-Path -LiteralPath (Join-Path $source.FullName $required))) { throw "下载内容缺少 $required，没有修改本地程序。" }
    }
    # 备份旧程序（只有代码，很小）；只留最近 5 份
    if (Test-Path -LiteralPath $program) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        $backup = Join-Path $backupRoot ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-程序')
        Copy-Item -LiteralPath $program -Destination $backup -Recurse -Force
        Get-ChildItem -LiteralPath $backupRoot -Directory | Sort-Object Name -Descending | Select-Object -Skip 5 |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
        Move-Item -LiteralPath $program -Destination $oldProgram
    }
    $swapped = $false
    try {
        Move-Item -LiteralPath $source.FullName -Destination $program
        $swapped = $true
        [IO.File]::WriteAllText((Join-Path $program '更新版本.txt'), $Revision + "`n", $utf8)
    } catch {
        if ($swapped -and (Test-Path -LiteralPath $program)) { Remove-Item -LiteralPath $program -Recurse -Force }
        if (Test-Path -LiteralPath $oldProgram) { Move-Item -LiteralPath $oldProgram -Destination $program }
        throw
    }
    $ver = (Get-Content -LiteralPath (Join-Path $program 'VERSION') -ErrorAction SilentlyContinue | Select-Object -First 1)
    Write-Host "安装/更新成功（版本 $ver）。" -ForegroundColor Green
    Write-Host "程序位置：$program"
    Write-Host '启动：双击 程序\启动申论官途.bat，或在终端运行：'
    Write-Host "  python `"$(Join-Path $program 'server.py')`""
} finally {
    if ((Test-Path -LiteralPath $oldProgram) -and -not (Test-Path -LiteralPath $program)) {
        Write-Warning "原程序保留在 $oldProgram ，请从 更新备份 恢复。"
    } elseif (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
