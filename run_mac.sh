#!/bin/bash
# run_mac.sh
# -----------
# macOS 版的 run.bat：平常要開啟程式時執行這個。
# 用法：bash run_mac.sh  （或先 chmod +x run_mac.sh 之後用 ./run_mac.sh）

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "尚未執行過安裝。請先執行：bash setup_mac.sh"
    exit 1
fi

source venv/bin/activate
python3 main.py "$@"
