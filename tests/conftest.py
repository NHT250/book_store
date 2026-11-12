import re
import sqlite3

import pytest

from bookstore import create_app
from bookstore.db import connect

ADMIN = ("admin@bookstore.test", "Admin@12345")
CUSTOMER = ("customer@bookstore.test", "Customer@123")


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE": str(tmp_path / "test.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    return app


@pytest.fixture
def db(app):
    conn = connect(app.config["DATABASE"])
    yield conn
    conn.close()


class Browser:
    """Small helper around the Flask test client that handles the CSRF token."""

    def __init__(self, client):
        self.c = client

    def token(self):
        with self.c.session_transaction() as s:
            if "_csrf" not in s:
                s["_csrf"] = "tok-" + str(id(self))
            return s["_csrf"]

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, data=None, csrf=True, **kw):
        data = dict(data or {})
        if csrf:
            data.setdefault("csrf_token", self.token())
        return self.c.post(url, data=data, **kw)

    def login(self, email, password):
        return self.post("/login", {"email": email, "password": password})

    def logout(self):
        return self.post("/logout")


@pytest.fixture
def browser(app):
    return Browser(app.test_client())


@pytest.fixture
def make_browser(app):
    return lambda: Browser(app.test_client())


@pytest.fixture
def admin(make_browser):
    b = make_browser()
    assert b.login(*ADMIN).status_code == 302
    return b


@pytest.fixture
def customer(make_browser):
    b = make_browser()
    assert b.login(*CUSTOMER).status_code == 302
    return b


def count(db, sql, *args):
    return db.execute(sql, args).fetchone()[0]


def book_ids_on_page(html):
    return [int(x) for x in re.findall(r'href="/books/(\d+)\?', html)]
