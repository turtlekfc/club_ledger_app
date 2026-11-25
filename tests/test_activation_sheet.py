"""啟用登記表讀取（backend/api.py）：SSL 憑證、登入頁偵測、分頁錯誤偵測、錯誤原因說明。

不連網：用假的 urlopen / 假的試算表資料。
"""
import io
import ssl
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend.api as api_mod  # noqa: E402
from backend.api import Api  # noqa: E402


class FakeResp:
    def __init__(self, body, status=200):
        self.body, self.status = body.encode("utf-8"), status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def patch_urlopen(monkeypatch, body=None, exc=None):
    seen = {}

    def fake(req, timeout=None, context=None):
        seen["context"] = context
        if exc:
            raise exc
        return FakeResp(body)

    monkeypatch.setattr("urllib.request.urlopen", fake)
    return seen


REGISTRY = "Email,狀態,功能,到期日,備註,密碼重設帳號\nflyk@gmail.com,啟用,T6,,,\nb@mail.com,停用,T2,,,\n"


def test_ssl_context_is_passed_to_urlopen(monkeypatch):
    seen = patch_urlopen(monkeypatch, REGISTRY)
    Api._fetch_sheet_rows("id", "帳號")
    assert isinstance(seen["context"], ssl.SSLContext)


def test_activation_ok_and_tier(monkeypatch):
    patch_urlopen(monkeypatch, REGISTRY)
    api = object.__new__(Api)
    assert api.check_email_in_sheet("FLYK@gmail.com", "id", "帳號") == {"ok": True, "found": True}
    assert api.check_email_in_sheet("b@mail.com", "id", "帳號")["ok"] is False
    assert api.check_email_in_sheet("nobody@x.com", "id", "帳號") == {"ok": False, "found": False}
    assert api.check_feature_tier("flyk@gmail.com", "id", "帳號") == {"ok": True, "tier": "T6"}


def test_login_page_html_is_error_not_unregistered(monkeypatch):
    patch_urlopen(monkeypatch, "<!DOCTYPE html><html><body>Sign in</body></html>")
    api = object.__new__(Api)
    r = api.check_email_in_sheet("a@b.com", "id", "帳號")
    assert r["error"] is True and "分享" in r["message"]
    assert api.check_feature_tier("a@b.com", "id", "帳號")["ok"] is False


def test_wrong_tab_is_error(monkeypatch):
    # Google 找不到分頁名稱時會回第一個分頁（例如表單回應，A1 是時間戳記）
    patch_urlopen(monkeypatch, "時間戳記,姓名\n2026/1/1,王\n")
    api = object.__new__(Api)
    r = api.check_email_in_sheet("a@b.com", "id", "帳號")
    assert r["error"] is True and "分頁名稱" in r["message"]


def test_ssl_error_message(monkeypatch):
    exc = urllib.error.URLError(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"))
    patch_urlopen(monkeypatch, exc=exc)
    api = object.__new__(Api)
    r = api.check_feature_tier("a@b.com", "id", "帳號")
    assert r["ok"] is False and "憑證" in r["message"]


def test_generic_sheet_does_not_require_email_header(monkeypatch):
    # 手機記帳用的 Google 表單回應表，A1 是「時間戳記」，不該被登記表的檢查擋掉
    patch_urlopen(monkeypatch, "時間戳記,日期\n1,2\n")
    assert len(Api._fetch_sheet_rows("id", "表單回應 1")) == 2
