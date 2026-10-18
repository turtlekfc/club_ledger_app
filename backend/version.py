"""
version.py
----------
這個程式「目前這份原始碼」的版本號。純粹是您自己手動維護的標籤，跟
程式真正的功能無關，唯一用途是讓 App 啟動時跟 GitHub 上最新 Release
的版本號比對，不同就提醒使用者有新版可以下載（見 api.py 的
check_for_update()）。

之後要發新版時的流程：
1. 改下面這行的數字，例如 "1.0.0" -> "1.0.1"（小修正加最後一碼、加新
   功能加中間一碼、大改版加第一碼，順序不是強制規定，自己掌握就好）
2. 正常 commit、push
3. 打一個「同樣版號、前面加 v」的 git tag 並推上去，例如：
       git tag v1.0.1
       git push origin v1.0.1
   這個 tag 會觸發 .github/workflows/build.yml 自動打包 Windows/Mac
   兩邊的版本、並建立同版號的 GitHub Release。

兩個地方都要記得改：這裡的 APP_VERSION，跟推上去的 git tag，兩者版號
建議保持一致，之後比對才看得懂。如果忘記打 tag，CI 就不會建立新的
Release，App 也就查不到「有更新」這件事——所以真正會觸發提醒的關鍵
動作是「打 tag 並推上去」，不是改這個檔案本身。
"""
APP_VERSION = "1.0.0"
