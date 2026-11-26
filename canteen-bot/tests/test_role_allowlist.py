import web_server


def test_unlisted_telegram_account_has_no_privileged_role(monkeypatch):
    monkeypatch.delenv("STAFF_TELEGRAM_IDS", raising=False)
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)

    assert web_server._configured_demo_role("12345") is None


def test_staff_role_requires_server_side_allowlist(monkeypatch):
    monkeypatch.setenv("STAFF_TELEGRAM_IDS", "12345, 67890")
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)

    assert web_server._configured_demo_role("67890") == "staff"
    assert web_server._configured_demo_role("99999") is None


def test_admin_allowlist_takes_precedence(monkeypatch):
    monkeypatch.setenv("STAFF_TELEGRAM_IDS", "12345")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "12345")

    assert web_server._configured_demo_role("12345") == "admin"
