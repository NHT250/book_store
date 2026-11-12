"""F3 catalogue (US-03), F4 details (US-04/15/16), F5 search & filters (US-05/17/18)."""
import html
import re
from datetime import datetime, timedelta

from conftest import book_ids_on_page


def visible_count(db):
    return db.execute("SELECT COUNT(*) FROM books WHERE is_deleted = 0").fetchone()[0]


def keep_visible(db, n):
    """Hide all but the n newest seed books so boundary cases are exact."""
    keep = [r[0] for r in db.execute("SELECT id FROM books ORDER BY created_at DESC, id DESC LIMIT ?", (n,))]
    db.execute(f"UPDATE books SET is_deleted = 1 WHERE id NOT IN ({','.join('?' * len(keep))})", keep)
    db.commit()


def add_qa_books(db, n, *, prefix="QA Book", price=100000, category=None, author_name="QA Author"):
    author = db.execute("SELECT id FROM authors WHERE name = ?", (author_name,)).fetchone()
    author = author[0] if author else db.execute(
        "INSERT INTO authors (name, bio, created_at) VALUES (?, '', '2026-01-01 00:00:00')", (author_name,)).lastrowid
    category = category or db.execute("SELECT id FROM categories WHERE name='Technology'").fetchone()[0]
    base = datetime(2027, 1, 1)
    for i in range(n):
        ts = (base + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
        p = price[i] if isinstance(price, (list, tuple)) else price
        db.execute("""INSERT INTO books (title, author_id, category_id, price, description, cover_url,
                      created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
                   (f"{prefix} {i + 1:02d}", author, category, p, "", "/x.svg", ts, ts))
    db.commit()


# ---------------------------------------------------------------- US-03
def test_TC_03_01_grid_shows_cover_title_author_price(browser, db):
    page = browser.get("/").data.decode()
    assert 'class="book-grid"' in page
    row = db.execute("""SELECT b.*, a.name AS an FROM books b JOIN authors a ON a.id=b.author_id
                        WHERE is_deleted=0 ORDER BY created_at DESC LIMIT 1""").fetchone()
    for text in (row["title"], row["an"], row["cover_url"], f"{row['price']:,}".replace(",", ".")):
        assert html.escape(text) in page


def test_TC_03_02_newest_first(browser, db):
    expected = [r[0] for r in db.execute(
        "SELECT id FROM books WHERE is_deleted=0 ORDER BY created_at DESC, id DESC LIMIT 12")]
    assert book_ids_on_page(browser.get("/").data.decode()) == expected


def test_TC_03_03_max_12_per_page_and_pagination(browser, db):
    keep_visible(db, 25)
    seen = []
    for p in (1, 2, 3):
        ids = book_ids_on_page(browser.get(f"/?page={p}").data.decode())
        assert len(ids) <= 12
        seen += ids
    assert len(seen) == 25 and len(set(seen)) == 25


def test_TC_03_04_exact_12_and_13_boundaries(browser, db):
    keep_visible(db, 13)
    assert len(book_ids_on_page(browser.get("/").data.decode())) == 12
    assert len(book_ids_on_page(browser.get("/?page=2").data.decode())) == 1
    keep_visible(db, 12)
    page = browser.get("/").data.decode()
    assert len(book_ids_on_page(page)) == 12 and 'class="pagination"' not in page


def test_TC_03_05_last_page_has_remaining_books(browser, db):
    keep_visible(db, 25)
    page = browser.get("/?page=3").data.decode()
    assert len(book_ids_on_page(page)) == 1 and 'aria-current="page" class="current">3<' in page


def test_TC_03_06_responsive_layout(browser, app):
    page = browser.get("/").data.decode()
    assert 'name="viewport" content="width=device-width, initial-scale=1"' in page
    css = browser.get("/static/style.css").data.decode()
    assert "@media (max-width: 900px)" in css and "@media (max-width: 600px)" in css
    assert "repeat(auto-fill, minmax(180px, 1fr))" in css


# ---------------------------------------------------------------- US-04 / 15 / 16
def test_TC_04_01_details_show_all_fields(browser, db):
    b = db.execute("""SELECT b.*, a.name an, c.name cn FROM books b JOIN authors a ON a.id=b.author_id
                      JOIN categories c ON c.id=b.category_id WHERE b.is_deleted=0 LIMIT 1""").fetchone()
    page = browser.get(f"/books/{b['id']}").data.decode()
    for text in (b["title"], b["an"], b["cn"], b["description"], b["cover_url"]):
        assert html.escape(text) in page
    assert f"{b['price']:,}".replace(",", ".") in page
    for label in ("District 1", "District 3", "Thu Duc City", "Total"):
        assert label in page
    assert f">{b['stock_d1'] + b['stock_d3'] + b['stock_td']}<" in page


def test_TC_04_02_detail_responsive(browser, db):
    bid = db.execute("SELECT id FROM books WHERE is_deleted=0 LIMIT 1").fetchone()[0]
    page = browser.get(f"/books/{bid}").data.decode()
    assert 'class="detail"' in page and "width=device-width" in page
    assert ".detail { grid-template-columns: 1fr;" in browser.get("/static/style.css").data.decode()


def test_TC_04_03_hidden_book_not_public(admin, browser, db):
    b = db.execute("SELECT id, title FROM books WHERE is_deleted=0 LIMIT 1").fetchone()
    admin.post(f"/staff/books/{b['id']}/delete")
    r = browser.get(f"/books/{b['id']}")
    assert r.status_code == 404 and b"Book not found" in r.data
    assert html.escape(b["title"]).encode() not in r.data


def test_TC_15_01_missing_book_friendly_message(browser):
    for bad in ("999999999", "abc", "99999999999999999999999"):
        r = browser.get(f"/books/{bad}")
        assert r.status_code == 404 and b"Book not found" in r.data and b"Traceback" not in r.data


def test_TC_15_02_back_to_books_link(browser):
    page = browser.get("/books/999999999").data.decode()
    m = re.search(r'<a class="btn btn-primary" href="([^"]+)">Back to books</a>', page)
    assert m and m.group(1) == "/"
    assert browser.get(m.group(1)).status_code == 200


def _back_href(page):
    return html.unescape(re.search(r'<a class="back-link" href="([^"]+)"', page).group(1))


def test_TC_16_01_return_to_page_3(browser, db):
    assert visible_count(db) >= 25
    list_page = browser.get("/?page=3").data.decode()
    link = html.unescape(re.search(r'href="(/books/\d+\?back=[^"]+)"', list_page).group(1))
    back = _back_href(browser.get(link).data.decode())
    assert back == "/?page=3"
    assert 'aria-current="page" class="current">3<' in browser.get(back).data.decode()


def test_TC_16_02_filters_and_page_retained(browser, db):
    add_qa_books(db, 15)
    tech = db.execute("SELECT id FROM categories WHERE name='Technology'").fetchone()[0]
    list_page = browser.get(f"/?category={tech}&page=2").data.decode()
    link = html.unescape(re.search(r'href="(/books/\d+\?back=[^"]+)"', list_page).group(1))
    back = _back_href(browser.get(link).data.decode())
    assert f"category={tech}" in back and "page=2" in back


def test_back_param_cannot_redirect_offsite(browser, db):
    bid = db.execute("SELECT id FROM books WHERE is_deleted=0 LIMIT 1").fetchone()[0]
    for evil in ("https://evil.example", "//evil.example", "/staff/"):
        assert _back_href(browser.get(f"/books/{bid}", query_string={"back": evil}).data.decode()) == "/"


# ---------------------------------------------------------------- US-05 search
def test_TC_05_01_search_title_and_author(browser, db):
    add_qa_books(db, 1, prefix="Algorithms QA", author_name="Mai QA")
    add_qa_books(db, 1, prefix="Databases QA", author_name="Bao QA")
    page = browser.get("/?q=algorithms").data.decode()
    assert "Algorithms QA 01" in page and "Databases QA" not in page
    page = browser.get("/?q=bao qa").data.decode()
    assert "Databases QA 01" in page and "Algorithms QA" not in page
    # Unicode (Vietnamese) author search is case-insensitive too.
    assert "Mắt Biếc" in browser.get("/?q=NGUYỄN NHẬT").data.decode()


def test_TC_05_02_empty_results_state(browser):
    page = browser.get("/?q=zz-no-match-qa-2026").data.decode()
    assert "No books found" in page and "book-grid" not in page


def test_TC_05_03_search_kept_across_pages(browser, db):
    add_qa_books(db, 25, prefix="Paging QA")
    page1 = browser.get("/?q=QA").data.decode()
    assert "q=QA" in html.unescape(re.search(r'href="([^"]+)" rel="next"', page1).group(1))
    page2 = browser.get("/?q=QA&page=2").data.decode()
    titles = re.findall(r'<h3 class="book-title">([^<]+)</h3>', page2)
    assert titles and all("QA" in t for t in titles)


# ---------------------------------------------------------------- US-17 category filter
def test_TC_17_01_only_selected_category(browser, db, admin):
    lit = db.execute("SELECT id FROM categories WHERE name='Literature'").fetchone()[0]
    hidden = db.execute("SELECT id, title FROM books WHERE category_id=? LIMIT 1", (lit,)).fetchone()
    admin.post(f"/staff/books/{hidden['id']}/delete")
    page = browser.get(f"/?category={lit}").data.decode()
    shown = book_ids_on_page(page)
    expected = {r[0] for r in db.execute("SELECT id FROM books WHERE category_id=? AND is_deleted=0", (lit,))}
    assert shown and set(shown) <= expected and hidden["id"] not in shown


def test_TC_17_02_category_kept_across_pages(browser, db):
    sci = db.execute("SELECT id FROM categories WHERE name='Science'").fetchone()[0]
    add_qa_books(db, 25, prefix="Sci QA", category=sci)
    page1 = browser.get(f"/?category={sci}").data.decode()
    assert f"category={sci}" in html.unescape(re.search(r'href="([^"]+)" rel="next"', page1).group(1))
    ids = book_ids_on_page(browser.get(f"/?category={sci}&page=2").data.decode())
    cats = {db.execute("SELECT category_id FROM books WHERE id=?", (i,)).fetchone()[0] for i in ids}
    assert ids and cats == {sci}


# ---------------------------------------------------------------- US-18 price range
def test_TC_18_01_inclusive_price_range(browser, db):
    db.execute("UPDATE books SET is_deleted=1")
    db.commit()
    add_qa_books(db, 5, prefix="Price QA", price=[49999, 50000, 100000, 150000, 150001])
    page = browser.get("/?min_price=50000&max_price=150000").data.decode()
    titles = sorted(re.findall(r'<h3 class="book-title">([^<]+)</h3>', page))
    assert titles == ["Price QA 02", "Price QA 03", "Price QA 04"]


def test_TC_18_02_negative_bound_rejected(browser):
    r = browser.get("/?min_price=-1")
    assert r.status_code == 400 and b"cannot be negative" in r.data and b"book-grid" not in r.data
    page = browser.get("/").data.decode()
    assert 'name="min_price" type="number" min="0"' in page and "data-price-form" in page


def test_TC_18_03_min_greater_than_max_rejected(browser):
    r = browser.get("/?min_price=150000&max_price=50000")
    assert r.status_code == 400 and b"Minimum price cannot be greater than maximum price." in r.data


def test_TC_18_04_all_criteria_kept_across_pages(browser, db):
    tech = db.execute("SELECT id FROM categories WHERE name='Technology'").fetchone()[0]
    add_qa_books(db, 20, prefix="Combo QA", price=80000, category=tech)
    add_qa_books(db, 5, prefix="Combo QA expensive", price=900000, category=tech)
    url = f"/?q=QA&category={tech}&min_price=50000&max_price=150000"
    page1 = browser.get(url).data.decode()
    nxt = html.unescape(re.search(r'href="([^"]+)" rel="next"', page1).group(1))
    for part in ("q=QA", f"category={tech}", "min_price=50000", "max_price=150000", "page=2"):
        assert part in nxt
    page2 = browser.get(nxt).data.decode()
    titles = re.findall(r'<h3 class="book-title">([^<]+)</h3>', page2)
    assert len(titles) == 8 and not any("expensive" in t for t in titles)
