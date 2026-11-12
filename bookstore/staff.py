"""Staff workspace (Administrator only).

F1: create accounts (US-11), lock/unlock (US-19).
F2: add/edit books (US-09), soft delete (US-21), categories (US-22), authors (US-23),
    fixed three-store stock (US-14, CR-03 MVP).
"""
import os
import re
import unicodedata
import uuid

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .auth import create_user, email_exists
from .db import STATUS_ACTIVE, STATUS_LOCKED, STORES, get_db, now_iso
from .security import admin_required
from .validation import parse_int, validate_account

bp = Blueprint("staff", __name__, url_prefix="/staff")

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp"}


@bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    stats = {
        "books": db.execute("SELECT COUNT(*) FROM books WHERE is_deleted = 0").fetchone()[0],
        "hidden": db.execute("SELECT COUNT(*) FROM books WHERE is_deleted = 1").fetchone()[0],
        "categories": db.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        "authors": db.execute("SELECT COUNT(*) FROM authors").fetchone()[0],
        "accounts": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "locked": db.execute("SELECT COUNT(*) FROM users WHERE status = 'LOCKED'").fetchone()[0],
    }
    return render_template("staff/dashboard.html", stats=stats)


# ---------------------------------------------------------------- accounts (US-11, US-19)

def _accounts():
    return get_db().execute("SELECT * FROM users ORDER BY created_at DESC, id DESC").fetchall()


@bp.route("/accounts", methods=["GET", "POST"])
@admin_required
def accounts():
    form, errors, status = {}, {}, 200
    if request.method == "POST":
        data, errors, bad_role = validate_account(request.form, with_role=True)
        form = {"full_name": data["full_name"], "email": data["email"], "role": request.form.get("role", "")}
        if not errors.get("email") and data["email"] and email_exists(data["email"]):
            errors["email"] = "This email is already registered."
        if not errors and not create_user(data, data["role"]):
            errors["email"] = "This email is already registered."
        if not errors:
            flash(f"Account {data['email']} created with status ACTIVE.", "success")
            return redirect(url_for("staff.accounts"))
        only_duplicate = errors == {"email": "This email is already registered."}
        status = 409 if only_duplicate and not bad_role else 400
    return render_template("staff/accounts.html", users=_accounts(), form=form, errors=errors), status


def _set_status(user_id, new_status):
    if user_id == g.user["id"]:
        # US-19 AC4: an administrator can never lock their own account (UI or direct request).
        abort(400, description="You cannot lock or unlock your own account.")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)
    db.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    db.commit()
    return user


@bp.route("/accounts/<int:user_id>/lock", methods=["POST"])
@admin_required
def lock_account(user_id):
    user = _set_status(user_id, STATUS_LOCKED)
    flash(f"{user['email']} is now LOCKED.", "success")
    return redirect(url_for("staff.accounts"))


@bp.route("/accounts/<int:user_id>/unlock", methods=["POST"])
@admin_required
def unlock_account(user_id):
    user = _set_status(user_id, STATUS_ACTIVE)
    flash(f"{user['email']} is ACTIVE again.", "success")
    return redirect(url_for("staff.accounts"))


# ---------------------------------------------------------------- books (US-09, US-14, US-21)

def _lookups():
    db = get_db()
    return (
        db.execute("SELECT id, name FROM authors ORDER BY name COLLATE NOCASE").fetchall(),
        db.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall(),
    )


def _save_upload(file_storage, errors):
    filename = secure_filename(file_storage.filename or "")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        errors["cover"] = "Cover must be a JPG, PNG, GIF or WEBP image."
        return None
    name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
    return url_for("static", filename=f"uploads/{name}")


def validate_book(form, files, existing=None):
    errors = {}
    db = get_db()
    title = unicodedata.normalize("NFC", (form.get("title") or "").strip())
    if not title:
        errors["title"] = "Title is required."
    elif len(title) > 200:
        errors["title"] = "Title must be at most 200 characters."

    author_id = parse_int(form.get("author_id"), field="author_id", errors=errors, minimum=1, label="Author")
    if "author_id" in errors or author_id is None:
        errors["author_id"] = "Please choose an author."
    elif db.execute("SELECT 1 FROM authors WHERE id = ?", (author_id,)).fetchone() is None:
        errors["author_id"] = "Selected author does not exist."

    category_id = parse_int(form.get("category_id"), field="category_id", errors=errors, minimum=1, label="Category")
    if "category_id" in errors or category_id is None:
        errors["category_id"] = "Please choose a category."
    elif db.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone() is None:
        errors["category_id"] = "Selected category does not exist."

    price = None
    raw_price = (form.get("price") or "").strip()
    if not raw_price:
        errors["price"] = "Price is required."
    elif not re.fullmatch(r"-?\d+", raw_price):
        errors["price"] = "Price must be a whole number of VND."
    elif int(raw_price) <= 0:
        errors["price"] = "Price must be greater than 0."
    else:
        price = int(raw_price)

    description = (form.get("description") or "").strip()
    if len(description) > 5000:
        errors["description"] = "Description must be at most 5000 characters."

    stocks = {}
    for field, label in STORES:
        stocks[field] = parse_int(form.get(field, "0"), field=field, errors=errors, minimum=0,
                                  label=f"Stock at {label}")

    cover_url = existing["cover_url"] if existing else None
    upload = files.get("cover_file") if files else None
    url_in = (form.get("cover_url") or "").strip()
    if not errors:
        if upload and upload.filename:
            cover_url = _save_upload(upload, errors) or cover_url
        elif url_in:
            if re.match(r"^(https?://|/)\S+$", url_in) and not url_in.startswith("//"):
                cover_url = url_in
            else:
                errors["cover"] = "Cover URL must start with http://, https:// or /."
    if not cover_url and "cover" not in errors:
        errors["cover"] = "A cover image (upload or URL) is required."

    data = {"title": title, "author_id": author_id, "category_id": category_id, "price": price,
            "description": description, "cover_url": cover_url, **stocks}
    return data, errors


@bp.route("/books")
@admin_required
def books():
    show = request.args.get("show", "all")
    where = {"visible": "WHERE b.is_deleted = 0", "hidden": "WHERE b.is_deleted = 1"}.get(show, "")
    rows = get_db().execute(
        """SELECT b.*, a.name AS author_name, c.name AS category_name
           FROM books b JOIN authors a ON a.id = b.author_id JOIN categories c ON c.id = b.category_id """
        + where + " ORDER BY b.created_at DESC, b.id DESC"
    ).fetchall()
    return render_template("staff/books.html", books=rows, show=show)


@bp.route("/books/new", methods=["GET", "POST"])
@admin_required
def book_new():
    authors, categories = _lookups()
    form, errors = {}, {}
    if request.method == "POST":
        data, errors = validate_book(request.form, request.files)
        form = request.form
        if not errors:
            ts = now_iso()
            db = get_db()
            cur = db.execute(
                """INSERT INTO books (title, author_id, category_id, price, description, cover_url,
                                      stock_d1, stock_d3, stock_td, created_at, updated_at)
                   VALUES (:title, :author_id, :category_id, :price, :description, :cover_url,
                           :stock_d1, :stock_d3, :stock_td, :ts, :ts)""",
                {**data, "ts": ts},
            )
            db.commit()
            flash(f"Book \"{data['title']}\" was added to the catalogue.", "success")
            return redirect(url_for("staff.book_edit", book_id=cur.lastrowid))
        return render_template("staff/book_form.html", book=None, form=form, errors=errors,
                               authors=authors, categories=categories), 400
    return render_template("staff/book_form.html", book=None, form=form, errors=errors,
                           authors=authors, categories=categories)


@bp.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@admin_required
def book_edit(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        abort(404)
    authors, categories = _lookups()
    form, errors = dict(book), {}
    if request.method == "POST":
        data, errors = validate_book(request.form, request.files, existing=book)
        form = request.form
        if not errors:
            db.execute(
                """UPDATE books SET title=:title, author_id=:author_id, category_id=:category_id, price=:price,
                       description=:description, cover_url=:cover_url, stock_d1=:stock_d1, stock_d3=:stock_d3,
                       stock_td=:stock_td, updated_at=:ts WHERE id=:id""",
                {**data, "ts": now_iso(), "id": book_id},
            )
            db.commit()
            flash("Book details were saved.", "success")
            return redirect(url_for("staff.book_edit", book_id=book_id))
        return render_template("staff/book_form.html", book=book, form=form, errors=errors,
                               authors=authors, categories=categories), 400
    return render_template("staff/book_form.html", book=book, form=form, errors=errors,
                           authors=authors, categories=categories)


@bp.route("/books/<int:book_id>/delete", methods=["POST"])
@admin_required
def book_delete(book_id):
    """US-21: soft delete - hide from the store, keep the record."""
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if book is None:
        abort(404)
    if not book["is_deleted"]:
        db.execute("UPDATE books SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE id = ?",
                   (now_iso(), now_iso(), book_id))
        db.commit()
    flash(f"\"{book['title']}\" is hidden from the store. The record is kept.", "success")
    return redirect(url_for("staff.books"))


# ---------------------------------------------------------------- categories (US-22)

def _validate_named(form, *, table, field_label, current_id=None, unique=False):
    errors = {}
    name = unicodedata.normalize("NFC", (form.get("name") or "").strip())
    extra_field = "description" if table == "categories" else "bio"
    extra = (form.get(extra_field) or "").strip()
    if not name:
        errors["name"] = f"{field_label} name is required."
    elif len(name) > 100:
        errors["name"] = f"{field_label} name must be at most 100 characters."
    elif unique:
        dup = get_db().execute(
            f"SELECT id FROM {table} WHERE pylower(name) = ? AND id != ?",  # table is a fixed literal
            (name.lower(), current_id or 0),
        ).fetchone()
        if dup:
            errors["name"] = f"A {field_label.lower()} with this name already exists."
    if len(extra) > 2000:
        errors[extra_field] = "Text must be at most 2000 characters."
    return {"name": name, extra_field: extra}, errors


@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    db = get_db()
    form, errors, status = {}, {}, 200
    if request.method == "POST":
        data, errors = _validate_named(request.form, table="categories", field_label="Category", unique=True)
        form = data
        if not errors:
            db.execute("INSERT INTO categories (name, description, created_at) VALUES (?,?,?)",
                       (data["name"], data["description"], now_iso()))
            db.commit()
            flash(f"Category \"{data['name']}\" created.", "success")
            return redirect(url_for("staff.categories"))
        status = 400
    rows = db.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM books b WHERE b.category_id = c.id AND b.is_deleted = 0) AS book_count
           FROM categories c ORDER BY c.name COLLATE NOCASE"""
    ).fetchall()
    return render_template("staff/categories.html", categories=rows, form=form, errors=errors), status


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def category_edit(category_id):
    db = get_db()
    row = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row is None:
        abort(404)
    form, errors = dict(row), {}
    if request.method == "POST":
        data, errors = _validate_named(request.form, table="categories", field_label="Category",
                                       current_id=category_id, unique=True)
        form = data
        if not errors:
            db.execute("UPDATE categories SET name = ?, description = ? WHERE id = ?",
                       (data["name"], data["description"], category_id))
            db.commit()
            flash("Category saved.", "success")
            return redirect(url_for("staff.categories"))
        return render_template("staff/named_edit.html", kind="category", item=row, form=form, errors=errors), 400
    return render_template("staff/named_edit.html", kind="category", item=row, form=form, errors=errors)


# ---------------------------------------------------------------- authors (US-23)

@bp.route("/authors", methods=["GET", "POST"])
@admin_required
def authors():
    db = get_db()
    form, errors, status = {}, {}, 200
    if request.method == "POST":
        data, errors = _validate_named(request.form, table="authors", field_label="Author")
        form = data
        if not errors:
            db.execute("INSERT INTO authors (name, bio, created_at) VALUES (?,?,?)",
                       (data["name"], data["bio"], now_iso()))
            db.commit()
            flash(f"Author \"{data['name']}\" created.", "success")
            return redirect(url_for("staff.authors"))
        status = 400
    rows = db.execute(
        """SELECT a.*, (SELECT COUNT(*) FROM books b WHERE b.author_id = a.id) AS book_count
           FROM authors a ORDER BY a.name COLLATE NOCASE"""
    ).fetchall()
    return render_template("staff/authors.html", authors=rows, form=form, errors=errors), status


@bp.route("/authors/<int:author_id>/edit", methods=["GET", "POST"])
@admin_required
def author_edit(author_id):
    db = get_db()
    row = db.execute("SELECT * FROM authors WHERE id = ?", (author_id,)).fetchone()
    if row is None:
        abort(404)
    form, errors = dict(row), {}
    if request.method == "POST":
        data, errors = _validate_named(request.form, table="authors", field_label="Author")
        form = data
        if not errors:
            db.execute("UPDATE authors SET name = ?, bio = ? WHERE id = ?", (data["name"], data["bio"], author_id))
            db.commit()
            flash("Author saved. Linked books now show the updated name.", "success")
            return redirect(url_for("staff.authors"))
        return render_template("staff/named_edit.html", kind="author", item=row, form=form, errors=errors), 400
    return render_template("staff/named_edit.html", kind="author", item=row, form=form, errors=errors)
