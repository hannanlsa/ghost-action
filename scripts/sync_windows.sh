#!/bin/bash
# sync_windows.sh - 同步Mac代码到Windows VM (通过Parallels共享文件夹)
# 用法: bash scripts/sync_windows.sh

set -e

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)/src"
SYNC_DIR="$HOME/Desktop/ga_sync"
WIN_DIR="C:\\GhostAction-build\\src"

echo "=== GhostAction Mac -> Windows 同步 ==="

# 1. 复制到Desktop共享目录
mkdir -p "$SYNC_DIR"
count=0
for f in "$SRC_DIR"/*.py; do
    cp "$f" "$SYNC_DIR/"
    count=$((count + 1))
done
echo "已复制 $count 个文件到 $SYNC_DIR"

# 2. 通过Parallels共享文件夹同步到Windows
echo "正在同步到Windows VM..."
prlctl exec "Windows 11" cmd /c "xcopy \\\\mac\\Home\\Desktop\\ga_sync\\*.py $WIN_DIR\\ /Y" 2>&1

# 3. 验证
echo "验证Windows端文件..."
prlctl exec "Windows 11" cmd /c "dir $WIN_DIR\\gui.py" 2>&1 | tail -3

echo "=== 同步完成 ==="