#!/bin/bash
# 只寻找用户已安装的公考App，调用其内置Python；不修改存档和本机API设置。
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
APP="/Applications/公考模拟器.app"
if [ ! -d "$APP" ]; then APP="$HOME/Applications/公考模拟器.app"; fi
if [ ! -d "$APP" ]; then
  APP=$(/usr/bin/osascript -e 'POSIX path of (choose application with prompt "选择已安装的公考模拟器" as alias)')
  APP="${APP%/}"
fi
IDENTITY=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP/Contents/Info.plist")
if [ "$IDENTITY" != 'com.shenlun.guantu' ]; then
  echo '选择的不是公考模拟器，未作修改。'; exit 1
fi
BIN=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP/Contents/Info.plist")
case "$BIN" in ''|*/*|.|..) echo '应用程序入口不正确，未作修改。'; exit 1;; esac
echo '请先在公考模拟器中按Command+Q完全退出，以免旧进程影响更新。'
read -r -p '退出完成后，回到此窗口按回车开始：' ANSWER
echo '使用现有App的运行环境进行更新，无需安装Python。'
if "$APP/Contents/MacOS/$BIN" --run-script "$SCRIPT_DIR/mac_update_repair.py"; then
  echo '流程结束。如果下载成功，应用会自动重新打开；如果已是最新版则保持不变。'
else
  echo '更新未完成，请保留上方报错。旧应用和学习资料未删除。'
fi
read -r -p '按回车关闭此窗口：' ANSWER
