"""
api.py
-------
The single object exposed to the frontend via pywebview's js_api.
Every public method here becomes callable from JavaScript as
    await window.pywebview.api.<method_name>(...)

Kept intentionally thin: argument validation + delegating to
ledger_manager / db.LedgerDB. No business logic lives here (that stays
in the frontend JS, unchanged from the browser prototype).
"""
import hashlib
import json
import logging
import math
import re
from datetime import datetime
from pathlib import Path
from .db import LedgerDB
from .ledger_manager import LedgerManager

log = logging.getLogger("club_ledger.api")

# 目前前端 sGet/sSet 實際用到的 key 都是單純英文小寫（config/accounts/...），
# 這裡白名單限制格式，純粹是防呆：擋掉奇怪的 key（太長、帶特殊符號）在
# storage_get/storage_set/storage_delete/storage_list 這幾個對外開放的入口
# 被誤用或塞進壞資料，不影響現有任何一個 key 的正常存取。
_STORAGE_KEY_RE = re.compile(r"[A-Za-z0-9_.:-]{1,100}")
_MAX_STORAGE_VALUE_BYTES = 20 * 1024 * 1024  # 20MB，正常帳本資料不可能到這個量級


def _valid_storage_key(key) -> bool:
    return isinstance(key, str) and _STORAGE_KEY_RE.fullmatch(key) is not None


class Api:
    def __init__(self, ledger_manager: LedgerManager = None):
        self.lm = ledger_manager or LedgerManager()
        self._active_ledger_id = None
        self._db: LedgerDB | None = None
        self._window = None  # set via set_window() once main.py creates the pywebview window

        # Auto-open the default ledger (if one is set) so the frontend can
        # skip straight to the login screen instead of the ledger picker.
        default_id = self.lm.get_default_ledger_id()
        if default_id and self.lm.get_ledger(default_id):
            self._open(default_id)

    def set_window(self, window):
        """Called once from main.py right after webview.create_window(),
        so file-dialog methods below have a window to anchor the dialog to."""
        self._window = window

    # ---------------------------------------------------------------- #
    # Ledger management (the "帳本管理" screen)
    # ---------------------------------------------------------------- #
    def list_ledgers(self):
        return self.lm.list_ledgers()

    def get_active_ledger(self):
        if not self._active_ledger_id:
            return None
        info = self.lm.get_ledger(self._active_ledger_id)
        return info

    def create_ledger(self, name: str):
        entry = self.lm.create_ledger(name)
        return entry

    def rename_ledger(self, ledger_id: str, new_name: str):
        return self.lm.rename_ledger(ledger_id, new_name)

    def open_ledger(self, ledger_id: str):
        """Switch the active ledger. Returns the ledger info on success,
        or None if the ledger id is unknown."""
        if not self.lm.get_ledger(ledger_id):
            return None
        self._open(ledger_id)
        return self.lm.get_ledger(ledger_id)

    def set_default_ledger(self, ledger_id: str, enabled: bool = True):
        if enabled:
            return self.lm.set_default(ledger_id)
        return self.lm.clear_default()

    def delete_ledger(self, ledger_id: str):
        if self._active_ledger_id == ledger_id and self._db:
            self._db.close()
            self._db = None
            self._active_ledger_id = None
        return self.lm.delete_ledger(ledger_id)

    # ---------------------------------------------------------------- #
    # 帳冊層級的管理員帳號（橫跨這個 APP 安裝底下所有「帳本」，不用先開啟
    # 某一本帳本也能讀取/寫入——在帳本選擇畫面、或任何一本帳本的登入畫面，
    # 都要能看到同一份管理員帳號清單）
    # ---------------------------------------------------------------- #
    def get_admin_accounts(self):
        return self.lm.get_admin_accounts()

    def set_admin_accounts(self, accounts):
        return self.lm.set_admin_accounts(accounts)

    def close_ledger(self):
        """Return to the ledger picker without deleting anything."""
        if self._db:
            self._db.close()
        self._db = None
        self._active_ledger_id = None
        return True

    def _open(self, ledger_id: str):
        if self._db:
            self._db.close()
        db_path = self.lm.db_path_for(ledger_id)
        self._db = LedgerDB(db_path)
        self._active_ledger_id = ledger_id

    # ---------------------------------------------------------------- #
    # Generic key/value storage for the ACTIVE ledger
    # (drop-in replacement for the old window.storage.get/set/delete/list)
    # ---------------------------------------------------------------- #
    def storage_get(self, key: str):
        if not self._db:
            return None
        if not _valid_storage_key(key):
            return None
        return self._db.get(key)

    def storage_set(self, key: str, value):
        if not self._db:
            return False
        if not _valid_storage_key(key):
            log.warning("Rejected invalid storage key: %r", key)
            return False
        # value arrives from JS already JSON.stringify'd by the frontend
        # bridge, but accept dict/list too for safety if called elsewhere.
        if not isinstance(value, str):
            try:
                value = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                return False
        if len(value.encode("utf-8")) > _MAX_STORAGE_VALUE_BYTES:
            log.warning("Rejected oversized storage value for key %s", key)
            return False
        return self._db.set(key, value)

    def storage_delete(self, key: str):
        if not self._db:
            return False
        if not _valid_storage_key(key):
            return False
        return self._db.delete(key)

    def storage_list(self, prefix: str = ""):
        if not self._db:
            return []
        prefix = prefix or ""
        if not isinstance(prefix, str) or len(prefix) > 100 or not re.fullmatch(r"[A-Za-z0-9_.:-]*", prefix):
            return []
        return self._db.list_keys(prefix)

    # ---------------------------------------------------------------- #
    # Backup / restore
    # ---------------------------------------------------------------- #
    def export_active_ledger_json(self):
        """Full dump of the active ledger's data, for a manual backup /
        'save a copy' feature. Returns a JSON string."""
        if not self._db:
            return None
        return json.dumps(self._db.export_all(), ensure_ascii=False, indent=2)

    def import_active_ledger_json(self, json_text: str, mode: str = "merge"):
        """Restore from a backup produced by export_active_ledger_json().
        mode='merge' (default) overwrites/adds the keys present in the
        backup file but leaves any other existing keys untouched.
        mode='replace' first wipes every existing key in this ledger, then
        writes the backup — use with care, this is the "全部取代" option."""
        if not self._db:
            return {"ok": False, "message": "沒有已開啟的帳本"}
        if mode not in ("merge", "replace"):
            return {"ok": False, "message": "還原模式不正確"}
        try:
            data = json.loads(json_text)
            if not isinstance(data, dict):
                raise ValueError("備份檔格式不正確（不是一個物件）")
            if len(data) > 1000:
                raise ValueError("備份檔資料項目過多")
            for key, value in data.items():
                if not _valid_storage_key(key):
                    raise ValueError(f"備份檔含有不合法的資料鍵：{key!r}")
                json.dumps(value, ensure_ascii=False)  # 確保每個 value 都能被序列化，壞掉的提早擋下來
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            log.exception("Backup file parse failed")
            return {"ok": False, "message": f"備份檔案讀取失敗：{e}"}

        try:
            # 整個還原包在同一個 SQLite 交易裡：中途任何一步出錯就整批回滾，
            # 不會留下「刪了一半、寫了一半」的殘缺帳本（尤其是「全部取代」模式）。
            self._db.restore_all(data, replace=(mode == "replace"))
            return {"ok": True, "key_count": len(data)}
        except Exception as e:
            log.exception("Backup restore failed")
            return {"ok": False, "message": f"還原時發生錯誤：{e}"}

    def save_backup_file(self):
        """Native 'Save As' dialog + write the backup directly from Python.
        Preferred over shuttling a possibly-large JSON string through the
        JS bridge just to trigger a browser-style download."""
        if not self._db:
            return {"ok": False, "message": "沒有已開啟的帳本"}
        if not self._window:
            return {"ok": False, "message": "視窗尚未就緒，請稍後再試"}
        import webview
        ledger = self.lm.get_ledger(self._active_ledger_id) or {}
        safe_name = "".join(c for c in ledger.get("name", "ledger") if c.isalnum() or c in " _-") or "ledger"
        default_name = f"{safe_name}_備份.json"
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name,
                file_types=("JSON 檔案 (*.json)", "所有檔案 (*.*)"),
            )
        except Exception as e:
            log.exception("save dialog failed")
            return {"ok": False, "message": f"開啟存檔視窗失敗：{e}"}
        if not result:
            return {"ok": False, "message": "已取消"}
        path = result if isinstance(result, str) else result[0]
        try:
            data = self._db.export_all()
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "path": str(path)}
        except Exception as e:
            log.exception("save_backup_file write failed")
            return {"ok": False, "message": f"寫入檔案失敗：{e}"}

    def load_backup_file(self, mode: str = "merge"):
        """Native 'Open' dialog + read + restore, all from Python."""
        if not self._db:
            return {"ok": False, "message": "沒有已開啟的帳本"}
        if not self._window:
            return {"ok": False, "message": "視窗尚未就緒，請稍後再試"}
        import webview
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG, file_types=("JSON 檔案 (*.json)", "所有檔案 (*.*)")
            )
        except Exception as e:
            log.exception("open dialog failed")
            return {"ok": False, "message": f"開啟選檔視窗失敗：{e}"}
        if not result:
            return {"ok": False, "message": "已取消"}
        path = result[0] if isinstance(result, (list, tuple)) else result
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            return {"ok": False, "message": f"讀取檔案失敗：{e}"}
        return self.import_active_ledger_json(text, mode)

    # ---------------------------------------------------------------- #
    # 帳本啟用信箱檢查 (activation gate)
    # Runs from Python (urllib) instead of the webview's JS fetch() —
    # more reliable across different OS webview engines, and much easier
    # to debug via the app.log file than a silent JS fetch failure.
    # ---------------------------------------------------------------- #
    def check_email_in_sheet(self, email: str, sheet_id: str, sheet_name: str):
        try:
            rows = self._fetch_sheet_rows(sheet_id, sheet_name)
        except Exception as e:
            log.warning("check_email_in_sheet failed: %s", e)
            return {"ok": False, "found": False, "error": True, "message": str(e)}
        target = (email or "").strip().lower()
        for row in rows:
            a = (row[0] if len(row) > 0 else "").strip().lower()
            b = (row[1] if len(row) > 1 else "").strip()
            if a == target:
                return {"ok": b == "啟用", "found": True}
        return {"ok": False, "found": False}

    def test_sheet_connection(self, sheet_id: str, sheet_name: str):
        try:
            rows = self._fetch_sheet_rows(sheet_id, sheet_name)
            return {"ok": True, "row_count": len(rows)}
        except Exception as e:
            log.warning("test_sheet_connection failed: %s", e)
            return {"ok": False, "message": str(e)}

    def check_feature_tier(self, email: str, sheet_id: str, sheet_name: str):
        """讀同一份試算表的 C 欄——這欄原本是給舊版「功能」下拉選單用的，
        現在改放簡短代號 T1~T6，代表這個社團被授權用到哪個「累加式方案」
        （T1=基本，每往上一級多開一項功能，到 T6=全部功能）。對照表與
        累加規則見 README「功能分級怎麼用」，實際展開成布林值的邏輯刻意
        放在前端（跟其他業務邏輯一起），這裡只負責讀原始代號，不做判斷。"""
        try:
            rows = self._fetch_sheet_rows(sheet_id, sheet_name)
        except Exception as e:
            log.warning("check_feature_tier failed: %s", e)
            return {"ok": False, "error": True, "message": str(e)}
        target = (email or "").strip().lower()
        for row in rows:
            a = (row[0] if len(row) > 0 else "").strip().lower()
            c = (row[2] if len(row) > 2 else "").strip().upper()
            if a == target:
                return {"ok": True, "tier": c}
        return {"ok": True, "tier": ""}

    def check_password_reset_request(self, email: str, sheet_id: str, sheet_name: str):
        """跟 check_email_in_sheet 讀的是同一份試算表，多看第6欄（F欄）：
        實際欄位配置是 A:Email, B:狀態, C:功能, D:到期日, E:備註（這幾欄
        已經被既有的 setupSheetValidation() Apps Script／既有機制用掉了），
        所以密碼重設標記刻意放在再後面一欄的 F 欄，避免跟 C 欄的「功能」
        下拉選單衝突。發行者/系統管理者要幫某個社團重設密碼，就在該社團
        那一列的F欄填上要重設的登入帳號；平常留空。回傳該欄目前的值
        （可能是空字串），實際要不要真的重設、要不要跳過（已處理過同一個
        值），由前端自行用本機存的 marker 判斷——這裡只負責讀，不碰任何
        本機或雲端資料。"""
        try:
            rows = self._fetch_sheet_rows(sheet_id, sheet_name)
        except Exception as e:
            log.warning("check_password_reset_request failed: %s", e)
            return {"ok": False, "error": True, "message": str(e)}
        target = (email or "").strip().lower()
        for row in rows:
            a = (row[0] if len(row) > 0 else "").strip().lower()
            f = (row[5] if len(row) > 5 else "").strip()
            if a == target:
                return {"ok": True, "reset_username": f}
        return {"ok": True, "reset_username": ""}

    @staticmethod
    def _fetch_sheet_rows(sheet_id: str, sheet_name: str):
        import csv
        import io
        import urllib.parse
        import urllib.request

        if not sheet_id:
            raise ValueError("尚未設定 Google Sheet ID")
        url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
            f"?tqx=out:csv&sheet={urllib.parse.quote(sheet_name or '帳號')}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "ClubLedger/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            raw = resp.read().decode("utf-8-sig", errors="replace")
        return list(csv.reader(io.StringIO(raw)))

    # ---------------------------------------------------------------- #
    # 手機記帳：簡易雲端暫存 (Option 2, Phase 2 規劃項目)
    # ------------------------------------------------------------------
    # 設計刻意避開需要 OAuth/寫入權限的 Google Sheets API：手機端用 Google
    # 表單（回覆會自動附加成試算表的新列），桌面端只用「唯讀」的 CSV 匯出
    # 連結讀取（跟帳本啟用檢查完全同一條技術路線），**從不寫回或清空該
    # 試算表**。要匯入到哪一列為止，記錄在本機帳本自己的 kv_store 裡
    # （key: mobile_import_marker），所以：
    #   1. 雲端暫存表本身永遠是「只增不減」的提交紀錄，不會被誤刪
    #   2. 匯入前一定先在本機做一次自動快照備份（見 _auto_backup_snapshot）
    #   3. 只有使用者在前端確認「確定匯入」之後，才會真的寫進 transactions
    #      並往前推進 marker；確認之前重覆呼叫 fetch 都是安全、可重試的
    # ---------------------------------------------------------------- #
    def test_mobile_sheet_connection(self, sheet_id: str, sheet_name: str):
        """跟 test_sheet_connection 一樣，只是給手機暫存表單用，訊息分開顯示。"""
        try:
            rows = self._fetch_sheet_rows(sheet_id, sheet_name)
            return {"ok": True, "row_count": max(0, len(rows) - 1)}
        except Exception as e:
            log.warning("test_mobile_sheet_connection failed: %s", e)
            return {"ok": False, "message": str(e)}

    @staticmethod
    def _mobile_row_hash(row):
        """用「內容」而不是「這一列目前排第幾」識別一筆手機暫存資料，這樣
        不管使用者事後有沒有在試算表裡刪除/排序/插入列，同一筆內容永遠對應
        同一個雜湊值。欄位固定取 A~G（index 0~6，缺的補空字串），A 欄是
        Google 表單自動產生的 Timestamp，精確到秒，這是讓兩筆欄位值完全
        相同的「不同次」提交，彼此雜湊值仍然不一樣的關鍵——如果改用範本
        手動填寫、A 欄留空，則完全相同內容的列會算成同一種雜湊，但下面
        `_load_mobile_import_counts`／呼叫端是用「出現次數」比對（不是單純
        看雜湊值存不存在），所以就算真的有兩列一模一樣的內容，也會各自被
        正確地視為兩筆獨立資料，不會互相誤判或漏接。"""
        cells = [str(row[i]).strip() if i < len(row) else "" for i in range(7)]
        raw = "\x1f".join(cells)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_mobile_import_counts(self, data_rows):
        """回傳 {row_hash: 已匯入次數} 字典。相容讀取舊版「純數字＝已經處理到
        第幾列」格式的 marker：只在記憶體裡換算成新格式回傳，不會自動寫回
        資料庫，真正落地要等 confirm_mobile_import 實際被呼叫時才會存檔，
        這個方法本身維持「只讀、可以放心重複呼叫」。"""
        marker = self._db.get("mobile_import_marker")
        if not marker:
            return {}
        try:
            data = json.loads(marker)
        except (TypeError, json.JSONDecodeError):
            log.warning("Invalid mobile_import_marker %r; treating as empty", marker)
            return {}
        if isinstance(data, dict) and isinstance(data.get("counts"), dict):
            return {k: int(v) for k, v in data["counts"].items() if isinstance(v, (int, float)) and v > 0}
        if isinstance(data, int) and data > 0:
            # 舊版格式：這個數字代表「目前這次抓到的試算表裡，從上面數下來
            # 前 N 列算已經處理過」。用這次實際抓到的內容把那 N 列的雜湊值
            # 算出來，當成換算後的起始值，避免升級格式那一刻讓舊紀錄整批
            # 被誤判成新資料重新冒出來。
            counts = {}
            for row in data_rows[:data]:
                h = self._mobile_row_hash(row)
                counts[h] = counts.get(h, 0) + 1
            return counts
        return {}

    def fetch_pending_mobile_entries(self, sheet_id: str, sheet_name: str):
        """讀取雲端暫存表裡「尚未匯入」的列，解析成交易草稿讓前端預覽，
        但完全不會寫入任何東西（本機或雲端皆不會），可以放心重複呼叫。
        預期的欄位順序（第一列為 Google 表單自動加的標題，略過不用）：
            A: Timestamp（表單自動產生，忽略）
            B: 日期            C: 收支類型（收入/支出）
            D: 金額            E: 類別/科目
            F: 備註（選填）     G: 記錄人姓名（選填）

        「這一列算不算已經匯入過」是用內容雜湊值（見 _mobile_row_hash）比對，
        不是看它目前排在表格第幾列，所以使用者事後在試算表裡刪除已處理過
        的列、調整順序、或在中間插入新列，都不會讓後面原本沒處理過的資料
        被誤判成「已處理過」而永遠撈不到，也不會把已經處理過的資料重新當
        成新資料（因此重複匯入）——實際是否真的寫入帳本，前端在匯入時還有
        另一層「跟既有交易內容比對」的防重複檢查，雙重保險。"""
        if not self._db:
            return {"ok": False, "message": "沒有已開啟的帳本"}
        try:
            rows = self._fetch_sheet_rows(sheet_id, sheet_name)
        except Exception as e:
            log.warning("fetch_pending_mobile_entries failed: %s", e)
            return {"ok": False, "message": str(e)}

        data_rows = rows[1:] if len(rows) > 1 else []  # 第0列是表單產生的標題列
        imported_counts = self._load_mobile_import_counts(data_rows)
        seen_counts = {}

        entries, errors = [], []
        for idx, row in enumerate(data_rows):
            row_hash = self._mobile_row_hash(row)
            seen_counts[row_hash] = seen_counts.get(row_hash, 0) + 1
            if seen_counts[row_hash] <= imported_counts.get(row_hash, 0):
                continue  # 這一筆（依內容比對）上次已經處理過了
            row_no = idx + 1  # 給使用者看的列號，從1開始（不含標題列）；
            # 只是這次預覽畫面上的顯示用途，不影響「算不算已處理過」的判斷
            try:
                date = (row[1] if len(row) > 1 else "").strip()
                type_raw = (row[2] if len(row) > 2 else "").strip()
                amount_raw = (row[3] if len(row) > 3 else "").strip()
                category = (row[4] if len(row) > 4 else "").strip() or "未分類"
                note = (row[5] if len(row) > 5 else "").strip()
                handler = (row[6] if len(row) > 6 else "").strip()

                # 嚴格比對（不再用 "支" in type_raw 這種子字串判斷），避免備註之類
                # 的欄位只要剛好含有「支」或「收」字就被誤判成支出/收入。
                if type_raw not in ("收入", "支出"):
                    raise ValueError(f"收支類型不正確：「{type_raw}」（請填「收入」或「支出」）")
                tx_type = type_raw
                amount = float(amount_raw.replace(",", "").strip()) if amount_raw else 0
                if not math.isfinite(amount) or amount <= 0:
                    raise ValueError(f"金額不正確：「{amount_raw}」")
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"日期格式不正確：「{date}」（請使用 YYYY-MM-DD）")
                if len(category) > 200 or len(note) > 2000 or len(handler) > 100:
                    raise ValueError("文字欄位過長")

                entries.append({
                    "row_no": row_no, "row_hash": row_hash, "date": date, "type": tx_type, "amount": amount,
                    "category": category, "note": note, "handler": handler,
                })
            except Exception as e:
                errors.append({"row_no": row_no, "row_hash": row_hash, "raw": row, "message": str(e)})

        return {
            "ok": True, "entries": entries, "errors": errors,
            "already_imported": sum(imported_counts.values()), "total_rows": len(data_rows),
        }

    # 手機記帳自動快照備份只保留最近這麼多份，避免長期使用後 auto_backups/
    # 資料夾裡的 JSON 檔案越積越多、一直占用磁碟空間。
    _AUTO_BACKUP_KEEP = 30

    def auto_backup_before_mobile_import(self):
        """匯入手機暫存資料前一定要先呼叫這個：產生一份帶時間戳記的本機
        快照備份（寫到帳本資料夾下的 auto_backups/，不會跳存檔視窗打斷
        使用者），失敗就回傳 ok:False，前端應該要中止匯入、不要繼續。"""
        if not self._db or not self._active_ledger_id:
            return {"ok": False, "message": "沒有已開啟的帳本"}
        try:
            backups_dir = self.lm.app_dir / "auto_backups" / self._active_ledger_id
            backups_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            path = backups_dir / f"mobile_import_{now.strftime('%Y%m%d_%H%M%S')}.json"
            data = self._db.export_all()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._cleanup_old_auto_backups(backups_dir)
            return {"ok": True, "path": str(path), "time": now.strftime("%Y-%m-%d %H:%M:%S")}
        except Exception as e:
            log.exception("auto_backup_before_mobile_import failed")
            return {"ok": False, "message": f"自動備份失敗：{e}"}

    def _cleanup_old_auto_backups(self, backups_dir: Path):
        """只保留最近 _AUTO_BACKUP_KEEP 份快照，多的（依檔名時間戳排序，
        最舊的排最前面）直接刪掉。清理失敗不影響本次備份是否成功，所以
        這裡把例外整個吞掉，只記錄警告。"""
        try:
            files = sorted(backups_dir.glob("mobile_import_*.json"))
            extra = files[:-self._AUTO_BACKUP_KEEP] if len(files) > self._AUTO_BACKUP_KEEP else []
            for f in extra:
                try:
                    f.unlink()
                except OSError:
                    log.warning("Failed to remove old auto backup: %s", f)
        except Exception:
            log.warning("auto backup cleanup failed", exc_info=True)

    def confirm_mobile_import(self, row_hashes, sheet_id: str = None, sheet_name: str = None):
        """前端把草稿加進 state.transactions、存檔成功之後才呼叫這個：把
        `row_hashes`（預覽畫面上使用者看到的「每一列」的內容雜湊值，不管
        是成功匯入還是被標記為格式錯誤而跳過的都要包含在內）各自的「已匯入
        次數」+1。

        改成用內容雜湊值、而不是舊版的「列數」當 key，是為了讓這份雲端
        暫存表可以安全地被刪除/排序/插入列：雜湊值只跟內容有關，不管那
        一列現在實際排在表格的第幾列，都認得出「這筆內容算不算處理過」，
        不會再因為使用者事後整理表格（刪掉已匯入或已訂正的列）而讓後面
        新資料的位置跟著往前移、被誤判成「已經處理過」而永遠撈不到；也
        不會因為同一批裡有錯誤列而讓後面正常的列被重複匯入——每一列都是
        各自獨立判斷，不互相影響。
        （交易資料本身維持原架構，由前端寫回 transactions，這裡不碰。）

        `sheet_id`／`sheet_name` 是選填的：只有在偵測到舊版「純數字」格式
        的 marker、需要升級成新格式時才會用到，重新抓一次試算表內容來把
        舊的「前 N 列」換算成對應的雜湊值，避免升級那一刻讓舊紀錄整批被
        誤判成新資料。如果沒給、或剛好抓取失敗，就不嘗試升級、沿用空白
        起始值——寧可這次多讓使用者在畫面上看到幾筆看起來重複的待確認
        資料、自己判斷要不要跳過，也不要默默弄丟任何資料。"""
        if not self._db:
            return {"ok": False, "message": "沒有已開啟的帳本"}
        if not isinstance(row_hashes, list) or not all(isinstance(h, str) and h for h in row_hashes):
            return {"ok": False, "message": "匯入進度資料格式不正確"}

        marker = self._db.get("mobile_import_marker")
        counts, is_legacy = {}, False
        if marker:
            try:
                data = json.loads(marker)
            except (TypeError, ValueError, json.JSONDecodeError):
                data = None
            if isinstance(data, dict) and isinstance(data.get("counts"), dict):
                counts = {k: int(v) for k, v in data["counts"].items() if isinstance(v, (int, float)) and v > 0}
            elif isinstance(data, int) and data > 0:
                is_legacy = True

        if is_legacy and sheet_id:
            try:
                rows = self._fetch_sheet_rows(sheet_id, sheet_name)
                data_rows = rows[1:] if len(rows) > 1 else []
                counts = self._load_mobile_import_counts(data_rows)
            except Exception:
                log.exception("confirm_mobile_import: legacy marker migration fetch failed")

        for h in row_hashes:
            counts[h] = counts.get(h, 0) + 1

        try:
            self._db.set("mobile_import_marker", json.dumps({"v": 2, "counts": counts}, ensure_ascii=False))
            return {"ok": True, "processed_count": len(row_hashes)}
        except Exception as e:
            log.exception("confirm_mobile_import failed")
            return {"ok": False, "message": f"更新匯入進度失敗：{e}"}
