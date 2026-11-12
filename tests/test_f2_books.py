"""Sprint 2 - F2 Book management (US-09, US-21, US-22, US-23) and US-14 three-store stock."""
import io

from conftest import count


def ids(db):
    author = db.execute("SELECT id FROM authors ORDER BY id LIMIT 1").fetchone()[0]
    cat = db.execute("SELECT id FROM categories ORDER BY id LIMIT 1").fetchone()[0]
    return author, cat


def book_form(db, **over):
    author, cat = ids(db)
    data = {"title": "QA Book A", "author_id": author, "category_id": cat, "price": "120000",
            "description": "QA description", "cover_url": "https://example.test/QA.jpg",
            "stock_d1": "2", "stock_d3": "0", "stock_td": "0"}
    data.update(over)
    return data


def add_book(admin, db, **over):
    r = admin.post("/staff/books/new", book_form(db, **over))
    assert r.status_code == 302, r.data[:500]
    return db.execute("SELECT * FROM books ORDER BY id DESC LIMIT 1").fetchone()


# ---------------------------------------------------------------- US-09
def test_TC_09_01_add_book_visible_in_catalogue(admin, browser, db):
    book = add_book(admin, db)
    assert book["title"] == "QA Book A" and book["price"] == 120000
    page = browser.get("/").data.decode()
    assert "QA Book A" in page  # newest first -> page 1


def test_TC_09_01b_add_book_with_uploaded_cover(admin, db):
    data = book_form(db, cover_url="", title="QA Upload Cover")
    data["cover_file"] = (io.BytesIO(b"\xff\xd8\xff fake jpeg"), "QA.jpg")
    r = admin.post("/staff/books/new", data, content_type="multipart/form-data")
    assert r.status_code == 302
    cover = db.execute("SELECT cover_url FROM books WHERE title='QA Upload Cover'").fetchone()[0]
    assert cover.startswith("/static/uploads/") and cover.endswith(".jpg")


def test_TC_09_02_edit_book_saved_and_displayed(admin, browser, db):
    book = add_book(admin, db)
    r = admin.post(f"/staff/books/{book['id']}/edit", book_form(db, title="QA Book A edited", price="150000"))
    assert r.status_code == 302
    page = browser.get(f"/books/{book['id']}").data.decode()
    assert "QA Book A edited" in page and "150.000" in page


def test_TC_09_03_missing_required_rejected_client_and_server(admin, db):
    form_html = admin.get("/staff/books/new").data.decode()
    assert 'id="title" name="title"' in form_html and "required" in form_html and "data-validate" in form_html
    before = count(db, "SELECT COUNT(*) FROM books")
    r = admin.post("/staff/books/new", {"title": "", "author_id": "", "category_id": "", "price": "", "cover_url": ""})
    assert r.status_code == 400
    for msg in (b"Title is required.", b"Please choose an author.", b"Please choose a category.",
                b"Price is required.", b"A cover image (upload or URL) is required."):
        assert msg in r.data
    assert count(db, "SELECT COUNT(*) FROM books") == before


def test_TC_09_04_price_zero_and_negative_rejected_on_add(admin, db):
    before = count(db, "SELECT COUNT(*) FROM books")
    for price in ("0", "-1"):
        r = admin.post("/staff/books/new", book_form(db, price=price))
        assert r.status_code == 400 and b"Price must be greater than 0." in r.data
    assert count(db, "SELECT COUNT(*) FROM books") == before
    assert add_book(admin, db, price="1")["price"] == 1


def test_TC_09_05_negative_price_on_edit_changes_nothing(admin, db):
    book = add_book(admin, db)
    r = admin.post(f"/staff/books/{book['id']}/edit", book_form(db, title="Should not save", price="-1"))
    assert r.status_code == 400
    after = db.execute("SELECT title, price FROM books WHERE id=?", (book["id"],)).fetchone()
    assert tuple(after) == ("QA Book A", 120000)


# ---------------------------------------------------------------- US-21 soft delete
def test_TC_21_01_deleted_book_hidden_from_public(admin, browser, db):
    book = add_book(admin, db)
    assert admin.post(f"/staff/books/{book['id']}/delete").status_code == 302
    assert b"QA Book A" not in browser.get("/").data
    assert b"No books found" in browser.get("/?q=QA+Book+A").data  # the search box still echoes the keyword


def test_TC_21_02_record_retained(admin, db):
    book = add_book(admin, db)
    admin.post(f"/staff/books/{book['id']}/delete")
    row = db.execute("SELECT * FROM books WHERE id=?", (book["id"],)).fetchone()
    assert row is not None and row["is_deleted"] == 1 and row["deleted_at"]
    assert b"QA Book A" in admin.get("/staff/books?show=hidden").data


def test_TC_21_03_customer_delete_denied(customer, db):
    bid = db.execute("SELECT id FROM books WHERE is_deleted=0 LIMIT 1").fetchone()[0]
    r = customer.post(f"/staff/books/{bid}/delete")
    assert r.status_code == 403
    assert db.execute("SELECT is_deleted FROM books WHERE id=?", (bid,)).fetchone()[0] == 0


def test_anonymous_delete_redirects_to_login(browser, db):
    bid = db.execute("SELECT id FROM books LIMIT 1").fetchone()[0]
    r = browser.post(f"/staff/books/{bid}/delete")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


# ---------------------------------------------------------------- US-22 categories
def test_TC_22_01_category_created_appears_in_form(admin):
    r = admin.post("/staff/categories", {"name": "QA Technology 2026", "description": ""})
    assert r.status_code == 302
    assert b"QA Technology 2026" in admin.get("/staff/categories").data
    assert b"QA Technology 2026" in admin.get("/staff/books/new").data


def test_TC_22_02_category_edit_saved(admin, db):
    admin.post("/staff/categories", {"name": "QA Technology 2026"})
    cid = db.execute("SELECT id FROM categories WHERE name='QA Technology 2026'").fetchone()[0]
    r = admin.post(f"/staff/categories/{cid}/edit", {"name": "QA Computing 2026", "description": "x"})
    assert r.status_code == 302
    assert db.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone()[0] == "QA Computing 2026"


def test_TC_22_03_empty_or_duplicate_category_rejected(admin, db):
    before = count(db, "SELECT COUNT(*) FROM categories")
    r = admin.post("/staff/categories", {"name": "   "})
    assert r.status_code == 400 and b"Category name is required." in r.data
    r = admin.post("/staff/categories", {"name": "technology"})  # duplicate, different case
    assert r.status_code == 400 and b"already exists" in r.data
    assert count(db, "SELECT COUNT(*) FROM categories") == before


def test_TC_22_04_categories_usable_for_filtering(browser, db):
    page = browser.get("/").data.decode()
    assert 'name="category"' in page and "Technology" in page and "Literature" in page


# ---------------------------------------------------------------- US-23 authors
def test_TC_23_01_author_available_for_linking(admin):
    assert admin.post("/staff/authors", {"name": "QA Author A", "bio": ""}).status_code == 302
    assert b"QA Author A" in admin.get("/staff/books/new").data


def test_TC_23_02_author_edit_reflected_on_linked_books(admin, browser, db):
    admin.post("/staff/authors", {"name": "QA Author A"})
    aid = db.execute("SELECT id FROM authors WHERE name='QA Author A'").fetchone()[0]
    b1 = add_book(admin, db, title="QA Linked 1", author_id=aid)
    b2 = add_book(admin, db, title="QA Linked 2", author_id=aid)
    admin.post(f"/staff/authors/{aid}/edit", {"name": "QA Author Renamed", "bio": ""})
    for b in (b1, b2):
        assert b"QA Author Renamed" in browser.get(f"/books/{b['id']}").data


def test_TC_23_03_missing_author_name_rejected(admin, db):
    before = count(db, "SELECT COUNT(*) FROM authors")
    r = admin.post("/staff/authors", {"name": "", "bio": "bio only"})
    assert r.status_code == 400 and b"Author name is required." in r.data
    assert count(db, "SELECT COUNT(*) FROM authors") == before


def test_TC_23_04_book_refers_to_author_record(admin, db):
    author_id, _ = ids(db)
    book = add_book(admin, db, author_id=author_id)
    assert book["author_id"] == author_id
    r = admin.post("/staff/books/new", book_form(db, author_id="999999"))
    assert r.status_code == 400 and b"Selected author does not exist." in r.data


# ---------------------------------------------------------------- US-14 stock per store (CR-03 MVP)
def test_TC_14_01_three_store_fields_present(admin):
    page = admin.get("/staff/books/new").data.decode()
    for label in ("District 1", "District 3", "Thu Duc City"):
        assert label in page
    for name in ("stock_d1", "stock_d3", "stock_td"):
        assert f'name="{name}"' in page


def test_TC_14_02_quantities_stored_separately(admin, db):
    book = add_book(admin, db, stock_d1="5", stock_d3="0", stock_td="2")
    assert (book["stock_d1"], book["stock_d3"], book["stock_td"]) == (5, 0, 2)


def test_TC_14_03_negative_stock_rejected_nothing_saved(admin, db):
    book = add_book(admin, db, stock_d1="5", stock_d3="2", stock_td="7")
    r = admin.post(f"/staff/books/{book['id']}/edit", book_form(db, stock_d1="9", stock_d3="-1", stock_td="7"))
    assert r.status_code == 400 and b"Stock at District 3 cannot be negative." in r.data
    row = db.execute("SELECT stock_d1, stock_d3, stock_td FROM books WHERE id=?", (book["id"],)).fetchone()
    assert tuple(row) == (5, 2, 7)


def test_TC_14_04_zero_allowed_negative_rejected(admin, db):
    assert add_book(admin, db, stock_d1="0", stock_d3="0", stock_td="0")["stock_td"] == 0
    before = count(db, "SELECT COUNT(*) FROM books")
    r = admin.post("/staff/books/new", book_form(db, stock_td="-1"))
    assert r.status_code == 400
    assert count(db, "SELECT COUNT(*) FROM books") == before


def test_TC_14_05_editing_one_store_keeps_others(admin, db):
    book = add_book(admin, db, stock_d1="5", stock_d3="2", stock_td="7")
    r = admin.post(f"/staff/books/{book['id']}/edit", book_form(db, stock_d1="5", stock_d3="4", stock_td="7"))
    assert r.status_code == 302
    row = db.execute("SELECT stock_d1, stock_d3, stock_td FROM books WHERE id=?", (book["id"],)).fetchone()
    assert tuple(row) == (5, 4, 7)
