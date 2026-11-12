"""SQLite data layer: schema, connection handling and demo seed data."""
import sqlite3
from datetime import datetime, timedelta

from flask import current_app, g
from werkzeug.security import generate_password_hash

ROLE_ADMIN = "ADMIN"
ROLE_CUSTOMER = "CUSTOMER"
ROLES = (ROLE_ADMIN, ROLE_CUSTOMER)
STATUS_ACTIVE = "ACTIVE"
STATUS_LOCKED = "LOCKED"

# US-14 / CR-03 MVP: three FIXED stores only (dynamic stores are out of scope, CCB pending).
STORES = (
    ("stock_d1", "District 1"),
    ("stock_d3", "District 3"),
    ("stock_td", "Thu Duc City"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('ADMIN', 'CUSTOMER')),
    status        TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'LOCKED')),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_categories_name ON categories (name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS authors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    bio        TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author_id   INTEGER NOT NULL REFERENCES authors (id),
    category_id INTEGER NOT NULL REFERENCES categories (id),
    price       INTEGER NOT NULL CHECK (price > 0),
    description TEXT NOT NULL DEFAULT '',
    cover_url   TEXT NOT NULL,
    stock_d1    INTEGER NOT NULL DEFAULT 0 CHECK (stock_d1 >= 0),
    stock_d3    INTEGER NOT NULL DEFAULT 0 CHECK (stock_d3 >= 0),
    stock_td    INTEGER NOT NULL DEFAULT 0 CHECK (stock_td >= 0),
    is_deleted  INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_books_public ON books (is_deleted, created_at DESC);
"""


def now_iso(dt=None):
    return (dt or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _py_lower(value):
    # SQLite's lower() only folds ASCII; this handles Vietnamese and other Unicode text.
    return value.lower() if isinstance(value, str) else value


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("pylower", 1, _py_lower, deterministic=True)
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    conn = connect(app.config["DATABASE"])
    try:
        conn.executescript(SCHEMA)
        if app.config.get("SEED_DEMO_DATA", True):
            seed(conn)
        conn.commit()
    finally:
        conn.close()


SEED_CATEGORIES = [
    ("Technology", "Programming, software and computer science."),
    ("Literature", "Novels, short stories and poetry."),
    ("Business", "Management, finance and entrepreneurship."),
    ("Science", "Physics, biology and popular science."),
    ("Self-help", "Personal growth and productivity."),
]

SEED_AUTHORS = [
    ("Nguyễn Nhật Ánh", "Vietnamese author of many beloved novels."),
    ("Robert C. Martin", "Software engineer and author known as Uncle Bob."),
    ("Yuval Noah Harari", "Historian and author."),
    ("Dale Carnegie", "Writer and lecturer on self-improvement."),
    ("Martin Kleppmann", "Researcher in distributed systems."),
    ("Tô Hoài", "Vietnamese novelist."),
    ("Stephen Hawking", "Theoretical physicist."),
    ("Peter Thiel", "Entrepreneur and investor."),
]

# (title, author index, category index, price VND, D1, D3, Thu Duc)
SEED_BOOKS = [
    ("Clean Code", 1, 0, 289000, 5, 2, 7),
    ("Clean Architecture", 1, 0, 315000, 3, 0, 4),
    ("Designing Data-Intensive Applications", 4, 0, 520000, 2, 1, 0),
    ("The Clean Coder", 1, 0, 245000, 4, 4, 4),
    ("Sapiens: A Brief History of Humankind", 2, 3, 299000, 10, 6, 8),
    ("Homo Deus", 2, 3, 279000, 3, 2, 1),
    ("21 Lessons for the 21st Century", 2, 3, 259000, 0, 2, 5),
    ("A Brief History of Time", 6, 3, 189000, 6, 3, 2),
    ("The Universe in a Nutshell", 6, 3, 210000, 1, 0, 0),
    ("How to Win Friends and Influence People", 3, 4, 99000, 20, 15, 12),
    ("How to Stop Worrying and Start Living", 3, 4, 109000, 7, 5, 9),
    ("The Art of Public Speaking", 3, 4, 129000, 2, 2, 2),
    ("Zero to One", 7, 2, 159000, 8, 4, 6),
    ("Mắt Biếc", 0, 1, 110000, 12, 8, 10),
    ("Tôi Thấy Hoa Vàng Trên Cỏ Xanh", 0, 1, 125000, 9, 7, 11),
    ("Cho Tôi Xin Một Vé Đi Tuổi Thơ", 0, 1, 85000, 14, 10, 6),
    ("Cô Gái Đến Từ Hôm Qua", 0, 1, 95000, 4, 0, 3),
    ("Kính Vạn Hoa", 0, 1, 150000, 2, 2, 0),
    ("Dế Mèn Phiêu Lưu Ký", 5, 1, 65000, 25, 18, 20),
    ("Vợ Chồng A Phủ", 5, 1, 55000, 6, 2, 1),
    ("Refactoring Notes", 1, 0, 199000, 3, 3, 3),
    ("Distributed Systems Primer", 4, 0, 330000, 1, 1, 1),
    ("Leadership Lessons", 7, 2, 175000, 5, 0, 2),
    ("Startup Playbook", 7, 2, 189000, 4, 4, 0),
    ("Mindset for Success", 3, 4, 119000, 8, 8, 8),
    ("Cosmos Explained", 6, 3, 225000, 2, 5, 1),
    ("Lịch Sử Loài Người Tóm Tắt", 2, 3, 239000, 3, 1, 2),
    ("Business Strategy Basics", 7, 2, 205000, 6, 1, 3),
    ("Cà Phê Cùng Tony", 3, 4, 89000, 10, 10, 10),
    ("Software Craftsmanship", 1, 0, 265000, 2, 0, 1),
    ("Truyện Ngắn Chọn Lọc", 5, 1, 72000, 7, 3, 4),
    ("Stars and Galaxies", 6, 3, 198000, 0, 0, 3),
]


def seed(conn):
    """Insert demo accounts and catalogue only when the database is empty."""
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    ts = now_iso()
    conn.executemany(
        "INSERT INTO users (full_name, email, password_hash, role, status, created_at) VALUES (?,?,?,?,?,?)",
        [
            ("Store Administrator", "admin@bookstore.test", generate_password_hash("Admin@12345"), ROLE_ADMIN, STATUS_ACTIVE, ts),
            ("Demo Customer", "customer@bookstore.test", generate_password_hash("Customer@123"), ROLE_CUSTOMER, STATUS_ACTIVE, ts),
        ],
    )
    conn.executemany(
        "INSERT INTO categories (name, description, created_at) VALUES (?,?,?)",
        [(n, d, ts) for n, d in SEED_CATEGORIES],
    )
    conn.executemany(
        "INSERT INTO authors (name, bio, created_at) VALUES (?,?,?)",
        [(n, b, ts) for n, b in SEED_AUTHORS],
    )
    cat_ids = [r[0] for r in conn.execute("SELECT id FROM categories ORDER BY id")]
    author_ids = [r[0] for r in conn.execute("SELECT id FROM authors ORDER BY id")]
    base = datetime.now() - timedelta(days=len(SEED_BOOKS))
    for i, (title, a, c, price, d1, d3, td) in enumerate(SEED_BOOKS):
        created = now_iso(base + timedelta(days=i))
        cur = conn.execute(
            """INSERT INTO books (title, author_id, category_id, price, description, cover_url,
                                  stock_d1, stock_d3, stock_td, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (title, author_ids[a], cat_ids[c], price,
             f"{title} is part of the Book Store demo catalogue.", "", d1, d3, td, created, created),
        )
        conn.execute("UPDATE books SET cover_url = ? WHERE id = ?", (f"/covers/{cur.lastrowid}.svg", cur.lastrowid))
