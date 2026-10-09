#!/bin/bash
# 申论官途启动（Mac）。双击运行；关掉终端窗口就退出。
cd "$(dirname "$0")" || exit 1
python3 server.py
