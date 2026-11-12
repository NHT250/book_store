"""Sprint 1 - F1 Account management. Test IDs follow the Team 3 TestCase workbook (BM2)."""
from conftest import ADMIN, CUSTOMER, count


def reg(email, pw="SafeDemo8!", confirm=None, name="QA Reader"):
    return {"full_name": name, "email": email, "password": pw, "confirm_password": pw if confirm is None else confirm}


# ---------------------------------------------------------------- US-01 register
def test_TC_01_01_register_creates_one_hashed_active_customer(browser, db):
    r = browser.post("/register", reg("qa-new-01@example.test"))
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    rows = db.execute("SELECT * FROM users WHERE email = ?", ("qa-new-01@example.test",)).fetchall()
    assert len(rows) == 1
    assert rows[0]["role"] == "CUSTOMER" and rows[0]["status"] == "ACTIVE"
    assert rows[0]["password_hash"] != "SafeDemo8!" and "SafeDemo8!" not in rows[0]["password_hash"]
    assert rows[0]["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def test_TC_01_02_duplicate_email_rejected(browser, db):
    browser.post("/register", reg("qa-existing@example.test"))
    before = count(db, "SELECT COUNT(*) FROM users")
    r = browser.post("/register", reg("QA-Existing@example.test"))
    assert r.status_code == 409
    assert b"This email is already registered." in r.data
    assert count(db, "SELECT COUNT(*) FROM users") == before


def test_TC_01_03_field_errors_and_server_400_when_browser_bypassed(browser, db):
    before = count(db, "SELECT COUNT(*) FROM users")
    r = browser.post("/register", {"full_name": "", "email": "", "password": "", "confirm_password": ""})
    assert r.status_code == 400
    for msg in (b"Full name is required.", b"Email is required.", b"Password is required."):
        assert msg in r.data
    r = browser.post("/register", reg("bad@"))
    assert r.status_code == 400 and b"Enter a valid email address." in r.data
    r = browser.post("/register", reg("qa-mismatch@example.test", confirm="Different9!"))
    assert r.status_code == 400 and b"Password confirmation does not match." in r.data
    assert count(db, "SELECT COUNT(*) FROM users") == before


def test_TC_01_04_password_boundaries_7_8(browser, db):
    r = browser.post("/register", reg("qa-pw7@example.test", "A" * 7))
    assert r.status_code == 400 and b"between 8 and 64" in r.data
    r = browser.post("/register", reg("qa-pw8@example.test", "A" * 8))
    assert r.status_code == 302
    assert count(db, "SELECT COUNT(*) FROM users WHERE email LIKE 'qa-pw%'") == 1


def test_TC_01_05_password_boundaries_64_65(browser, db):
    r = browser.post("/register", reg("qa-pw65@example.test", "B" * 65))
    assert r.status_code == 400
    r = browser.post("/register", reg("qa-pw64@example.test", "B" * 64))
    assert r.status_code == 302
    assert count(db, "SELECT COUNT(*) FROM users WHERE email = 'qa-pw64@example.test'") == 1
    assert count(db, "SELECT COUNT(*) FROM users WHERE email = 'qa-pw65@example.test'") == 0


# ---------------------------------------------------------------- US-02 sign in / out
def test_TC_02_01_role_based_landing(make_browser):
    c = make_browser()
    r = c.login(*CUSTOMER)
    assert r.status_code == 302 and r.headers["Location"] == "/"
    a = make_browser()
    r = a.login(*ADMIN)
    assert r.status_code == 302 and r.headers["Location"] == "/staff/"
    assert b"Staff workspace" in a.get("/staff/").data


def _has_session(b):
    with b.c.session_transaction() as s:
        return "user_id" in s


def test_TC_02_02_wrong_password_generic_message(browser):
    r = browser.login(CUSTOMER[0], "WrongPass99")
    assert r.status_code == 401 and b"Invalid email or password" in r.data
    assert not _has_session(browser)


def test_TC_02_03_unknown_or_blank_email_same_message(browser):
    r1 = browser.login("nobody@example.test", "Whatever123")
    r2 = browser.login("", "Whatever123")
    r3 = browser.login(CUSTOMER[0], "")
    for r in (r1, r2, r3):
        assert r.status_code == 401 and b"Invalid email or password" in r.data
    assert not _has_session(browser)


def test_TC_02_04_logout_then_back_or_protected_url_redirects(customer):
    assert customer.get("/account").status_code == 200
    r = customer.logout()
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    r = customer.get("/account")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    # Pages are never cached, so the browser Back button re-requests and gets redirected.
    assert "no-store" in customer.get("/").headers["Cache-Control"]


def test_TC_02_05_email_normalised(browser):
    r = browser.login("  CUSTOMER@BOOKSTORE.TEST  ", CUSTOMER[1])
    assert r.status_code == 302 and _has_session(browser)


# ---------------------------------------------------------------- US-11 admin creates accounts
def acct(email, role="CUSTOMER", pw="SafeDemo8!"):
    return {"full_name": "QA User", "email": email, "role": role, "password": pw, "confirm_password": pw}


def test_TC_11_01_admin_creates_customer_and_admin(admin, make_browser, db):
    for email, role in (("qa-c@example.test", "CUSTOMER"), ("qa-a@example.test", "ADMIN")):
        r = admin.post("/staff/accounts", acct(email, role))
        assert r.status_code == 302
        row = db.execute("SELECT role, status FROM users WHERE email = ?", (email,)).fetchone()
        assert (row["role"], row["status"]) == (role, "ACTIVE")
        assert email.encode() in admin.get("/staff/accounts").data
        assert make_browser().login(email, "SafeDemo8!").status_code == 302


def test_TC_11_02_duplicate_or_missing_role(admin, db):
    before = count(db, "SELECT COUNT(*) FROM users")
    r = admin.post("/staff/accounts", acct(CUSTOMER[0]))
    assert r.status_code == 409 and b"already registered" in r.data
    r = admin.post("/staff/accounts", acct("qa-norole@example.test", role=""))
    assert r.status_code == 400 and b"Please select a role." in r.data
    assert count(db, "SELECT COUNT(*) FROM users") == before


def test_TC_11_03_invalid_role_returns_400(admin, db):
    before = count(db, "SELECT COUNT(*) FROM users")
    r = admin.post("/staff/accounts", acct("qa-super@example.test", role="superadmin"))
    assert r.status_code == 400
    assert count(db, "SELECT COUNT(*) FROM users") == before


def test_customer_cannot_create_accounts(customer):
    assert customer.post("/staff/accounts", acct("qa-x@example.test")).status_code == 403


# ---------------------------------------------------------------- US-19 lock / unlock
def _uid(db, email):
    return db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]


def test_TC_19_01_lock_blocks_sign_in(admin, make_browser, db):
    uid = _uid(db, CUSTOMER[0])
    # "Cancel" in the dialog means no request is sent: the account stays ACTIVE.
    assert db.execute("SELECT status FROM users WHERE id=?", (uid,)).fetchone()[0] == "ACTIVE"
    page = admin.get("/staff/accounts").data
    assert b"data-confirm=" in page  # the Lock form asks for confirmation first
    assert admin.post(f"/staff/accounts/{uid}/lock").status_code == 302
    assert db.execute("SELECT status FROM users WHERE id=?", (uid,)).fetchone()[0] == "LOCKED"
    r = make_browser().login(*CUSTOMER)
    assert r.status_code == 403 and b"locked" in r.data


def test_TC_19_02_signed_in_user_kicked_out_when_locked(admin, customer, db):
    assert customer.get("/account").status_code == 200
    admin.post(f"/staff/accounts/{_uid(db, CUSTOMER[0])}/lock")
    r = customer.get("/account")
    assert r.status_code == 302 and "locked=1" in r.headers["Location"]
    page = customer.get(r.headers["Location"]).data
    assert b"Your account has been locked" in page
    assert customer.get("/account").status_code == 302


def test_TC_19_03_unlock_restores_access(admin, make_browser, db):
    uid = _uid(db, CUSTOMER[0])
    admin.post(f"/staff/accounts/{uid}/lock")
    assert admin.post(f"/staff/accounts/{uid}/unlock").status_code == 302
    assert db.execute("SELECT status FROM users WHERE id=?", (uid,)).fetchone()[0] == "ACTIVE"
    assert make_browser().login(*CUSTOMER).status_code == 302


def test_TC_19_04_admin_cannot_lock_self(admin, db):
    uid = _uid(db, ADMIN[0])
    assert f"/staff/accounts/{uid}/lock".encode() not in admin.get("/staff/accounts").data
    r = admin.post(f"/staff/accounts/{uid}/lock")  # direct request to the server
    assert r.status_code == 400
    assert db.execute("SELECT status FROM users WHERE id=?", (uid,)).fetchone()[0] == "ACTIVE"


def test_post_without_csrf_token_is_rejected(admin, db):
    uid = _uid(db, CUSTOMER[0])
    r = admin.post(f"/staff/accounts/{uid}/lock", csrf=False)
    assert r.status_code == 400
    assert db.execute("SELECT status FROM users WHERE id=?", (uid,)).fetchone()[0] == "ACTIVE"
