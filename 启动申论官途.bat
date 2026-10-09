@echo off
rem 申论官途启动（Windows）。双击运行；关掉这个窗口就退出。
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (python server.py) else (py server.py)
pause
