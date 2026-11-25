"""手機匯入驗證（backend/api.py 的 fetch_pending_mobile_entries）。

不需要網路、也不需要 pywebview：用假的 DB 與假的試算表資料，直接測驗證規則。
執行：python -m pytest tests -q
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.api import Api  # noqa: E402


class FakeDB:
    def __init__(self, store):
        self.store = store

    def get(self, key):
        return self.store.get(key)


HEADER = ["時間", "日期", "類型", "金額", "類別", "備註", "記錄人"]
CATEGORIES = {"income": [{"name": "社費/會費"}], "expense": [{"name": "場地費"}]}


def make_api(store, rows):
    api = object.__new__(Api)
    api._db = FakeDB(store)
    api._fetch_sheet_rows = lambda sheet_id, sheet_name: rows
    api._load_mobile_import_counts = lambda data_rows: {}
    return api


def run(rows, categories=CATEGORIES, handlers=("小明",)):
    store = {
        "categories": json.dumps(categories) if categories is not None else "not json",
        "handlers": json.dumps([{"name": h} for h in handlers]),
    }
    result = make_api(store, [HEADER] + rows).fetch_pending_mobile_entries("sheet", "name")
    ok_rows = [e["row_no"] for e in result["entries"]]
    error_text = " ".join(
        e["message"] if isinstance(e, dict) else str(e) for e in result["errors"]
    )
    return ok_rows, error_text


def row(tx_type="支出", amount="100", category="場地費", handler="", date="2026-11-01"):
    return ["t", date, tx_type, amount, category, "", handler]


def test_valid_expense_and_income_rows_pass():
    ok, err = run([row("支出", category="場地費"), row("收入", category="社費/會費")])
    assert ok == [1, 2]
    assert err == ""


def test_blank_category_is_rejected_not_defaulted():
    ok, err = run([row(category="")])
    assert ok == []
    assert "類別不可空白" in err


def test_expense_row_with_income_category_is_rejected():
    ok, err = run([row("支出", category="社費/會費")])
    assert ok == []
    assert "支出類別" in err


def test_income_row_with_expense_category_is_rejected():
    ok, err = run([row("收入", category="場地費")])
    assert ok == []
    assert "收入類別" in err


def test_unknown_handler_rejected_blank_handler_allowed():
    ok, err = run([row(handler="路人"), row(handler=""), row(handler="小明")])
    assert ok == [2, 3]
    assert "經手人" in err


def test_unreadable_category_list_skips_list_check_but_blank_still_rejected():
    ok, err = run([row(category="任何類別"), row(category="")], categories=None)
    assert ok == [1]
    assert "類別不可空白" in err


@pytest.mark.parametrize("bad_amount", ["abc", "-5", "0", ""])
def test_bad_amount_rejected(bad_amount):
    ok, _ = run([row(amount=bad_amount)])
    assert ok == []


def test_one_bad_row_does_not_block_good_rows():
    ok, err = run([row(category=""), row(), row(category="不存在")])
    assert ok == [2]
    assert err
