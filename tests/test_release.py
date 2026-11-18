"""Release 1.0 hosting support: health check and configurable demo passwords."""
from bookstore import create_app


def test_healthz_reports_ok(browser):
    r = browser.get("/healthz")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_demo_passwords_can_be_set_by_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "Hosted-Admin-2026")
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "h.sqlite3"), "UPLOAD_FOLDER": str(tmp_path / "u")})
    c = app.test_client()
    with c.session_transaction() as s:
        s["_csrf"] = "t"
    bad = c.post("/login", data={"email": "admin@bookstore.test", "password": "Admin@12345", "csrf_token": "t"})
    assert bad.status_code == 401
    ok = c.post("/login", data={"email": "admin@bookstore.test", "password": "Hosted-Admin-2026", "csrf_token": "t"})
    assert ok.status_code == 302 and ok.headers["Location"] == "/staff/"
