"""
version.py
----------
這個程式「目前這份原始碼」的版本號。純粹是您自己手動維護的標籤，跟
程式真正的功能無關，唯一用途是讓 App 啟動時跟 GitHub 上最新 Release
的版本號比對，不同就提醒使用者有新版可以下載（見 api.py 的
check_for_update()）。

之後要發新版時的流程（實際做法，2026-11-25 更正；舊版說明提到的
.github/workflows/build.yml 與「推 tag 自動打包」並不存在）：
1. 改下面這行的數字，例如 "1.0.2" -> "1.0.3"（build_config.json 的 version
   會優先採用這裡的值，不用另外改）
2. 正常 commit、push
3. Windows 版：在自己的電腦用 build_protected.bat（或 build_app.bat）打包
   Mac 版：commit 訊息含 [build-mac] 的 push，或在 GitHub Actions 手動執行
   「Build macOS (ClubLedger)」（見 .github/workflows/build_mac.yml），
   打包結果會出現在該次執行的 Artifacts（保留 14 天）
4. 到公開 repo turtlekfc/club_ledger_app 建立 Release（tag 用 v 加版號，
   例如 v1.0.3），把 Windows / Mac 的安裝檔附上去

App 啟動時查的是 club_ledger_app「最新 Release」的 tag，所以真正會觸發使用者
更新提醒的動作是「在 club_ledger_app 發布新的 Release」，不是改這個檔案，
也不是在 clubledger 打 tag。
"""
APP_VERSION = "1.0.3"
