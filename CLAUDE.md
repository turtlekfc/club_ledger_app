# 交接清冊 — Club Ledger App（社團帳本 App）

給「下一個接手這個專案的 Claude」看的完整交接資料。新開一個聊天室、把這個
repo 接上之後，請先讀完這份文件再開始動作。內容包含：專案概況、合作慣例、
目前進度、已知待辦事項、技術細節與注意事項。

最後更新：2026-11-25（session: `session_011Nssj5XYaRfN5cdqWWp6bJ`）

---

## 1. 專案概況

- **這是什麼**：給學生社團用的 Python/pywebview 桌面記帳 App，社長/會計/出納/
  指導老師等不同角色登入，管理收支、專案/活動、部門/組別、預算、報表、補助
  款追蹤等。
- **使用者身份**：社團端使用者本人（非工程師），用 Traditional Chinese 溝通，
  習慣簡潔條列式回覆。
- **兩個 repo**：
  - `turtlekfc/clubledger`（**私有**）：放「原始碼」，這個 repo。
  - `turtlekfc/club_ledger_app`（**公開**）：**只放打包好的 Release**，不放
    原始碼，給使用者下載安裝檔用。平常開發只動 `clubledger`，不要搞混。
- **主要檔案**：
  - `frontend/index.html`：整個前端，單一檔案、vanilla JS + 內嵌 `<script>`，
    目前約 3400+ 行。沒有建置流程，改完存檔就是成品。
  - `backend/api.py`：pywebview 的 JS-API class `Api`，前端透過
    `window.pywebview.api.xxx()` 呼叫這裡的 Python 方法。
  - `backend/db.py`：SQLite key-value store。**`db.get(key)` 回傳的是原始 JSON
    字串**，要自己 `json.loads()`，不是已經反序列化好的物件。
  - `backend/ledger_manager.py`：多帳本管理（同一台電腦上可以開很多本帳本）。
  - `backend/version.py`：`APP_VERSION`，發新版時要跟 club_ledger_app 的 Release
    tag 版號一致（檔案內有完整流程說明；注意：沒有「推 tag 自動打包」這回事，
    Mac 版靠 `[build-mac]` commit 或手動觸發 Actions，Windows 版在使用者電腦打包）。
  - `docs/使用手冊.html`：給使用者看的完整操作手冊，**每個功能都要跟著更新**
    （App 本身的 UI 文字刻意精簡，詳細說明都寫在手冊裡）。

---

## 2. 合作慣例（務必遵守）

這是這個使用者養成的固定合作模式，不是我自己猜的，請照著做：

1. **先討論、再確認、使用者說「開始製作」才動手改程式。** 遇到新需求，先逐項
   跟使用者確認規格（可以用條列式整理成「最終規劃總覽」請對方過目），對方
   明確說可以開始、或打「開始製作」四個字之後，才能開始改 code。不要還沒確
   認完就先動手。
2. **使用者的回覆通常很精簡**（例如「3.沒關係，會計可以新增會計角色」這種編
   號對應式的簡短回覆），要自己對照前面列的問題編號去理解在回答哪一條。
3. **不要在規格已經確認後，又回頭問不必要的問題。** 範圍定了就照著做，有疑
   慮的細節盡量自己做合理判斷並在交付時說明，而不是每個小地方都停下來問。
4. **溝通一律用繁體中文**，條列式、精簡，不要長篇大論。
5. **每個功能完成後都主動做一次「自我檢查」**（程式/邏輯 bug 複查），這個使用
   者會直接問「請自我檢查有沒有程式或邏輯上的bug」，複查時要老實講真正發現
   的問題，不用的話就說沒發現，不用硬找東西講。
6. **使用者偶爾會說「先記下，等日後有調整時一起調整」**——這種就只需要記錄
   （例如寫進本文件的「待辦事項」），不要自己當場動手改。目前已經有兩筆這
   種記錄，見第 4 節。

---

## 3. 技術慣例（務必遵守）

### 3.1 state 管理 pattern（前端）
- 全域 `state` 物件（`frontend/index.html` 裡搜尋 `let state = {`），
  `state.config` 放帳本層級設定。
- `loadAll()` 負責「讀取 + 輕量 migration」：每次新增一個 `state.config` 底下
  的欄位，**兩個地方都要改**：
  1. `state.config` 初始物件字面量（寫 default 值）。
  2. `loadAll()` 裡 `Object.assign(state.config, config, {...})` 裡面補上
     `欄位: Object.assign({default}, config.欄位||{})` 或等效的「舊資料沒這個
     欄位時給合理預設值」寫法。
- 新增 `state` 底下的頂層陣列/物件（例如這次新增的 `state.subsidyCases`）：
  要在 `loadAll()` 的 `Promise.all([...sGet(...)...])` 加對應的讀取、並在
  `state.xxx = ...` 指派，否則重開 App 資料會消失。
- **舊資料遷移原則**：永遠「保守預設」，不要讓舊資料因為新欄位而無中生有數
  字（例如這次「補助/自籌拆分」的舊資料一律預設整筆視為「自籌」，不會憑空
  冒出補助金額）。

### 3.2 每次改完 `frontend/index.html` 一定要驗證語法（commit 前）
```bash
python3 - <<'EOF'
import re, subprocess
html = open('frontend/index.html', encoding='utf-8').read()
scripts = re.findall(r'<script(?:(?! src)[^>])*>(.*?)</script>', html, re.S)
js = "\n".join(scripts)
open('/tmp/check.js','w',encoding='utf-8').write(js)
r = subprocess.run(['node','--check','/tmp/check.js'], capture_output=True, text=True)
print(r.returncode, r.stdout, r.stderr)
from html.parser import HTMLParser
class P(HTMLParser): pass
P().feed(html)
print("HTML OK")
EOF
```
改 `backend/api.py` 則用：
```bash
python3 -c "import ast; ast.parse(open('backend/api.py').read())"
```
改 `docs/使用手冊.html` 也要跑一次 HTMLParser 檢查（同上面那段 Python 的
`P().feed(html)` 部分，把路徑換掉）。

**自動化測試**（語法檢查之外再跑，兩者互補）：
```bash
python tests/run_all.py     # 後端 pytest + 前端 node，全過才 commit
```
- `tests/test_mobile_import.py`：手機匯入驗證規則（假 DB、假試算表，不連網）。
- `tests/frontend_helpers.test.js`：從 `index.html` 抽出 `csvCell`、
  `fundingParts`、`sumFunding`、`escapeHtml` 直接測，不需要瀏覽器。函式改名或
  搬位置時測試會提示找不到。
- 新增**純函式**（不碰 DOM、不碰 `state`）時請順手補測試；要測的前端函式要放
  在 `escapeHtml` 附近那段連續的 helper 區塊，或自行調整測試的抽取範圍。
- 目前沒有涵蓋：畫面（DOM）互動、報表 HTML 輸出、pywebview 實機行為，這些仍靠
  人工開 App 確認。

### 3.3 Git 工作流程
- 工作目錄：`/home/claude/clubledger`（透過
  `mcp__claude-code-remote__add_repo` + `git clone --depth 1` 取得；是 shallow
  clone）。
- **每次 push 前先 `git fetch origin main`**，避免 shallow clone 太舊造成
  413 / 衝突錯誤。
- Commit message：繁體中文、完整描述改了什麼跟為什麼，不是流水帳；結尾固定
  加 `Co-Authored-By:` 與 `Claude-Session:` 兩行（內容請用**當下 session 系統
  提供的 attribution 提示**，每個 session 的模型名稱與網址都不同，不要照抄舊
  的 commit）。
- 每個功能/修正**各自一個 commit**，不要把好幾個不相關的東西擠在一起；完成
  一項就 commit + push + 回報使用者一次，不要全部做完才一次交代。
- 只有使用者明確要求才 commit；沒說的話做完程式修改後要先讓對方確認。

### 3.3.1 前端共用 helper（新增功能時請沿用，不要重寫）
- **輸出 CSV 一律用 `csvCell()`**：自動加雙引號並防公式注入。不要自己拼
  `"${v}"`。
- **補助/自籌金額一律用 `fundingParts(t)` / `sumFunding(list)` 讀取**，不要直接
  加總 `t.fundingSubsidyAmount`：helper 會夾限並讓「補助＋自籌＝總支出」恆成
  立。資金來源字串用 `FUND.SELF/SUBSIDY/MIXED`，不要手寫中文字串。
- 手機匯入（`api.py` 的 `fetch_pending_mobile_entries`）驗證規則：類別不可空白、
  依收支類型比對對應分類清單、經手人有填才比對；讀不到清單時只略過「清單比
  對」，空白仍擋。

### 3.4 Edit 工具的已知地雷
- 之前遇過：某些行含有 `﻿`（BOM）字元，`old_string` 打進去會因為位元組
  對不上而比對失敗。遇到這種狀況改用附近「沒有 BOM 的唯一字串」當錨點
  （例如用函式簽名那行），不要死磕含 BOM 的那一行。

---

## 4. 目前已知待辦事項（使用者說「先記下，之後一起調整」）

這兩筆**還沒動工**，之後使用者說要一起處理時再做（session 內也建立了對應的
Task #44 / #45，但 Task 清單不會跨 session 保留，請以這份文件為準）：

1. **說明文字字級縮小兩號**：畫面上 `.desc` / `.hint` 這類說明文字，使用者覺
   得偏大，之後要統一縮小兩號（CSS 層級調整，影響面廣，建議先抓幾個典型畫
   面讓使用者確認效果再全面套用）。
2. **列印報表要加上日期範圍標示**：`doPrintReport()` / `renderPrintDoc()`
   產生的列印版報表，目前看不出這份報表涵蓋的日期區間，列印出來之後分不清
   楚是哪個區間的報表。要在列印版加上區間文字（字級可以比表頭小，或跟表頭
   一樣大都可以，使用者沒有堅持哪種）。

---

## 5. 這次 session 完成的工作（2026-10-22 ~ 2026-10-26）

### 背景
使用者原本問「手機記帳匯入的類別，如果帳本裡沒有，會不會出錯」，討論之後
延伸出 5 大項新需求，逐項確認後使用者打「開始製作」授權開始改 code，接著
依序完成，過程中使用者又追加 2 筆事後修正。以下照時間序列出，commit hash
可以直接 `git log` 對照：

| Commit | 內容摘要 |
|---|---|
| `bcf3346` | 手機匯入新增「類別／經手人」格式檢查，不符合清單就不匯入、列出錯誤訊息 |
| `e918fdb` | 新增期初餘額（分現金/銀行兩個數字），帳本啟用時可填，之後僅管理員可改，納入結餘計算 |
| `7331aaf` | 開放「會計」角色管理「這本帳本的帳號」（本地帳號，非跨帳本的管理員帳號），含可指派會計角色 |
| `b0a19a5` | 登入畫面記住「最後一次登入成功的帳號」，自動預選＋聚焦密碼欄，**不**做自動登入（密碼仍要手動輸入） |
| `515282d` | 新增「補助案」管理清單（管理中心）；部門/專案「設定預算」拆成補助金額＋自籌金額兩欄（加總仍存進原本的 `budget` 欄位，相容既有功能） |
| `00a44b2` | 支出記帳新增「資金來源」欄位（自籌/補助/混合），選補助或混合要選補助案，混合要再填兩個金額且必須加總等於總金額 |
| `4755bde` | 報表新增：收支明細表的補助/自籌總覽、新報表類型「補助案統計」、專案/部門報表與預算頁的補助/自籌執行率拆分、CSV 匯出新增四欄 |
| `f5e0363` | Code Review 修正：手機匯入類別檢查改依收支類型比對（收入列只能用收入分類）、類別空白明確報錯（不再預設「未分類」）；使用手冊同步更正 |
| `f11f40a` | Code Review 修正：CSV 匯出新增 `csvCell()` 防公式注入（= + - @ 開頭補單引號）、不再把備註的逗號改全形 |
| `25f5727` | Code Review 修正：補助/自籌加總集中成 `fundingParts()`/`sumFunding()`，並新增 `FUND` 常數 |
| `3df422b` | Code Review 修正：登入同一帳號不再重複寫入 config；編輯指向已刪除補助案的帳目不再卡關，刪除補助案時顯示使用筆數 |
| `653b1ca` | 新增 `tests/`：後端 pytest（手機匯入驗證）＋前端 node（csvCell、fundingParts 等），`python tests/run_all.py` 一次跑完 |
| `94a79a0` | 自我檢查後修正兩點：①會計角色不再提供「唯讀」選項（因為原本勾了也沒有實際限制效果，徒增誤導）②進階預算書「儲存為部門正式預算」會覆蓋掉手動分過的補助/自籌拆分，現在存檔前會先明確警示 |

### 這次新增的 state 欄位（重要，之後改東西要知道這些存在）
- `state.config.openingBalance = {cash, bank}`：期初餘額，僅管理員可改
  （`settingsBasic()` / `saveBasicSettings()`）。
- `state.config.lastLoginAccount = {scope:'admin'|'local', id} | null`：登入畫
  面預選用，`rememberLastLoginAccount()` 在登入成功時寫入。
- `state.subsidyCases = [{id, name, cap, deadline, note}]`：補助案清單，全社
  團共用、不分學期。CRUD 在 `manageSubsidyCases()` / `openSubsidyCaseModal()`
  / `saveSubsidyCase()` / `removeSubsidyCase()`。
- `project.subsidyAmount` / `project.selfAmount`：兩者相加＝`project.budget`
  （`openProjectModal()` / `saveProject()`）。
- `department.subsidyAmount` / `department.selfAmount`：兩者相加＝
  `department.budget`（`openDeptBudgetModal()` / `saveDeptBudgetOnly()`）。
- `transaction.fundingSource`：`'自籌'|'補助'|'混合'|null`（只有 `type==='支出'`
  才有意義，收入/轉帳一律 `null`）。
- `transaction.subsidyCaseId`：對應 `state.subsidyCases` 的 id，`fundingSource`
  非自籌時才必填。
- `transaction.fundingSubsidyAmount` / `transaction.fundingSelfAmount`：兩者相
  加必須等於 `transaction.amount`（混合時由使用者填，補助/自籌時系統自動算）。

### 權限相關的重要邏輯
- `canOpenSettings()` = 角色是「管理員」或「會計」（不看 `canEdit` 旗標）。這
  個 helper 決定了整個「系統設定」分頁（含「帳號與權限」子頁）能不能進去。
- `isAdmin()` = 角色是「管理員」。「帳冊管理員帳號」（橫跨所有帳本那種）的新
  增/編輯/刪除永遠限定 `isAdmin()`，不會對會計開放。
- **角色「會計」的帳號，`canEdit` 固定視為 `true`，UI 上不提供「唯讀」選項**
  （`openAccountModal()` 裡 `accCanEdit` checkbox 在角色為會計時會被
  disabled+強制勾選，`saveAccount()` 後端也會強制覆蓋，`loadAll()` 也會修正
  舊資料）。原因：會計本來就能進系統設定管理所有帳號，把它設唯讀並不會真的
  限制住這個人，徒增誤導，所以 2026-10-26 這次直接拿掉這個選項（commit
  `94a79a0`，使用者親口確認「的確沒意義，請移除唯讀選項」）。

---

## 6. 已知的設計取捨 / 注意事項（不是 bug，但未來改東西要留意）

1. **進階預算書「儲存為部門正式預算」分配工具不分補助/自籌**：它存檔時一律
   把對應部門的 `subsidyAmount` 重設為 0、整筆記為自籌，**會覆蓋掉手動分過
   的補助/自籌拆分**。2026-10-26 已加上存檔前的明確警示（偵測到有部門已手
   動分過補助金額時，警示文字會不一樣），但邏輯本身（整個覆蓋）維持原樣，
   沒有改成「合併」或「保留」，因為這個分配工具本來就是「一次性覆蓋整個部
   門預算」的設計。如果使用者反應這樣不夠用，可以考慮之後讓這個工具也支援
   補助/自籌比例。
2. **手機記帳（雲端暫存匯入）沒有資金來源欄位**，匯入進來的支出一律視為
   「自籌」。如果使用者想追蹤補助款，要提醒對方改用電腦版記帳時手動選。
3. **刪除補助案不會動到已經記錄的帳目**，`subsidyCaseId` 會變成「指到不存在
   的 id」，報表（`reportSubsidyCases()`）會把這些抓出來另外提示筆數；刪除前
   會顯示使用筆數並二次確認，編輯這類帳目時補助案下拉選單會顯示「（已刪除的
   補助案）」，不會擋住存檔。
4. **期初餘額只影響「整本帳本目前結餘」**（儀表板、現金/銀行圓餅圖），不會
   加進報表頁篩選特定區間/專案時看到的「結餘」數字（那些是該區間/專案自己
   的淨收支）。這是刻意設計，不要誤改。
5. **`db.get(key)` 回傳原始 JSON 字串**，`backend/api.py` 裡任何新增的讀取都
   要記得 `json.loads()`，忘記的話會在執行期才爆掉（沒有型別檢查）。
6. **兩個 repo 不要搞混**：`club_ledger_app`（public）只放 Release 產物，不
   要把原始碼 commit 進去；日常開發永遠在 `clubledger`（private）這個 repo。
7. **Code Review（2026-11-07）後刻意沒處理的低優先項目**（不是漏掉，之後要動
   請先跟使用者討論）：
   - `confirm()`/`alert()` 改成自訂 modal：全 App 到處都在用，是統一風格的大
     改動，單獨改一處反而不一致。
   - 把 `index.html`（3400+ 行）拆成多個檔案：沒有建置流程，拆檔會增加打包/載入
     路徑的風險，等真的需要再做。
   - 更新檢查改用帶 token 的 GitHub API：目前未登入限額（每 IP 每小時 60 次）
     被擋時會安靜略過，不影響使用，只是可能偶爾收不到更新提醒。
   - 預算頁對每個部門/專案各掃一次交易（O(部門×交易)）：社團規模沒有效能問題。
8. **`dist_obf/`、`venv/` 已不再被 git 追蹤**（使用者的打包 commit `07123b9`
   已移除並加進 `.gitignore`）。它們是本機打包產物，不是原始碼；改程式請改
   `backend/` 與 `frontend/`。
9. **Mac 版曾因缺 SSL 憑證讀不到啟用試算表**（2026-11-25 修，commit `7f30895`）：
   `api.py` 的 `_make_ssl_context()` 統一給所有 `urlopen` 使用，新增任何對外
   連線都要沿用，不要直接呼叫 `urlopen` 不帶 context。修正後尚待 Mac 使用者
   實測回報；若仍失敗，畫面與 `app.log` 會顯示具體原因。
10. **離線驗證碼啟用：評估後暫不採用**（使用者 2026-11-25 決定）。驗證碼放試算表
    讀不到就無用；若真要做，只能用「依信箱算出的簽章碼」離線驗證（密鑰會在
    App 內），建議加 30 天到期、連網後仍以試算表為準。除非使用者再提，不要主動做。

---

## 7. 下次接手時的建議開場

1. 先 `git log --oneline -20` 看一下有沒有在這份文件更新之後、又有新的
   commit（代表這份文件可能沒跟上最新進度，要用 git log 為準）。
2. 看第 4 節「已知待辦事項」，問使用者要不要處理。
3. 有新需求時，照第 2 節的合作慣例走：先討論確認、使用者說「開始製作」才動
   手。
4. 做完功能後主動問要不要「自我檢查」一次（或直接做一次，複查完才回報完
   成）。
