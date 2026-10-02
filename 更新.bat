@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 update.py
  goto done
)
where python >nul 2>nul
if %errorlevel%==0 (
  python update.py
  goto done
)
echo.
echo 没有找到 Python。请先安装 Python 3.8 或更高版本：
echo https://www.python.org/downloads/
echo 安装时务必勾选 "Add Python to PATH"，装完再双击本文件。
:done
echo.
pause
