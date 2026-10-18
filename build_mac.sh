#!/bin/bash
# build_mac.sh
# -------------
# macOS 版的 build_protected.bat：用 PyArmor 混淆原始碼、用 PyInstaller
# 打包成 ClubLedger.app，並自動整理出一個「可以直接壓縮、交給社團端使用者」
# 的發行資料夾（跟 Windows 版一樣，只放 .app、使用手冊、手機記帳範本，
# 不含 README、原始碼、救援工具）。
#
# 用法：在終端機裡，切換到這個資料夾，執行：
#     bash build_mac.sh
#
# 重要：PyArmor、PyInstaller 都必須在「目標要跑的那個平台」上執行才會產生
# 對應平台能跑的檔案——也就是說，這支腳本一定要在 Mac 上執行，才能做出
# Mac 可以雙擊開啟的 .app；不能在 Windows 或這個雲端環境裡跑這支腳本來
# 生出 Mac 版，道理跟 build_protected.bat 只能在 Windows 上跑出 .exe 一樣。

set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  Club Ledger - Protected Build (PyArmor) - macOS"
echo "============================================"
echo
echo "這會用 PyArmor 混淆 Python 原始碼、用 PyInstaller 打包成"
echo "ClubLedger.app，並整理出一份可以直接壓縮、交給使用者的發行"
echo "資料夾（只有 .app、使用手冊、手機記帳範本，沒有 README、原始碼、"
echo "救援工具）。"
echo

if [ ! -d "venv" ]; then
    echo "[ERROR] 找不到虛擬環境，請先執行 bash setup_mac.sh"
    exit 1
fi

source venv/bin/activate

echo "安裝/更新 PyArmor 與 PyInstaller..."
pip install -U pyarmor pyinstaller

echo
echo "檢查 PyArmor 授權/註冊狀態..."
pyarmor --version
echo
echo "重要：如果上面出現試用/到期的提示，今天打包出來的 .app 可能在試用期"
echo "結束後就無法執行。正式要大量發行前，請先看 README.md「受保護打包"
echo "（PyArmor）」那一節。"
read -p "按 Enter 繼續..." _

echo "清除舊的混淆建置資料夾（如果有的話）..."
rm -rf dist_obf

echo "用 PyArmor 混淆 backend/ 和 main.py..."
pyarmor gen -O dist_obf -r backend main.py

echo "把 frontend/ 複製進混淆後的建置資料夾（不是 Python 檔案，不用混淆）..."
mkdir -p dist_obf/frontend
cp -R frontend/. dist_obf/frontend/

ICON_ARG=""
if [ -f "assets/icon.icns" ]; then
    echo "找到 assets/icon.icns，.app 會使用這個圖示。"
    ICON_ARG="--icon $(pwd)/assets/icon.icns"
else
    echo "沒有找到 assets/icon.icns，將使用預設圖示。"
    echo "（如果想要自訂圖示，需要準備一份 .icns 格式的檔案，放在"
    echo "assets/icon.icns；.ico 檔案在 Mac 上不能直接用，需要另外轉檔。）"
fi

echo
echo "執行 PyInstaller（在混淆後的原始碼上）..."
(
  cd dist_obf
  # macOS 上 --add-data 的來源與目的地之間用冒號(:)分隔，跟 Windows 用分號(;)不同。
  # --windowed 在 macOS 上會自動產生 .app 應用程式包，不需要額外參數。
  pyinstaller --noconfirm --onefile --windowed \
    --add-data "frontend:frontend" \
    $ICON_ARG \
    --name ClubLedger main.py
)

echo
echo "整理發行資料夾（這是唯一需要壓縮、交給使用者的資料夾）..."
RELEASE_DIR="../ClubLedger_Release_Mac"
mkdir -p "$RELEASE_DIR/templates"

rm -rf "$RELEASE_DIR/ClubLedger.app"
cp -R "dist_obf/dist/ClubLedger.app" "$RELEASE_DIR/ClubLedger.app"
cp docs/*.html "$RELEASE_DIR/" 2>/dev/null || true
cp -R templates/. "$RELEASE_DIR/templates/"

echo
echo "============================================"
echo "  完成！可以直接壓縮分享的發行資料夾在："
echo "  $RELEASE_DIR"
echo
echo "  請先自己打開 $RELEASE_DIR/ClubLedger.app 測試一輪"
echo "  （建立帳本、登入、新增一筆交易、備份還原）再分享出去。"
echo
echo "  如果使用者打開時看到「無法確認開發者」的警告（macOS"
echo "  Gatekeeper 攔截未簽章的 App，沒有付費的 Apple 開發者憑證"
echo "  的話幾乎一定會遇到），請在 README.md 的「macOS 使用者"
echo "  打不開 App」那一節找處理方式。"
echo
echo "  之後每次重新打包，直接重跑這支腳本即可，會自動用最新的"
echo "  程式碼跟文件覆蓋發行資料夾。"
echo "============================================"
