#!/bin/bash
# setup_mac.sh
# -------------
# macOS 版的 setup.bat：第一次使用前執行一次，建立虛擬環境、安裝套件。
# 用法：在終端機（Terminal）裡，切換到這個資料夾，執行：
#     bash setup_mac.sh
# 或先給執行權限再直接執行：
#     chmod +x setup_mac.sh
#     ./setup_mac.sh

set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  Club Ledger - Setup (macOS)"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] 找不到 python3。請先安裝 Python 3.10 以上版本："
    echo "        https://www.python.org/downloads/"
    echo "        （或用 Homebrew：brew install python）"
    exit 1
fi

echo "Python 版本：$(python3 --version)"
echo

echo "建立虛擬環境 venv ..."
python3 -m venv venv

echo "安裝套件中，請稍候..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "============================================"
echo "  安裝完成！之後要開啟程式，執行 ./run_mac.sh 即可"
echo "============================================"
