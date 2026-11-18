"""F3 catalogue (US-03), F4 book details (US-04/15/16), F5 search & filters (US-05/17/18)."""
import math
import re
import textwrap
import unicodedata
from urllib.parse import urlencode

from flask import Blueprint, Response, abort, current_app, render_template, request, url_for
from markupsafe import escape

from .db import get_db
from .security import safe_next

bp = Blueprint("catalog", __name__)

BOOK_SELECT = """
SELECT b.*, a.name AS author_name, c.name AS category_name,
       (b.stock_d1 + b.stock_d3 + b.stock_td) AS total_stock
FROM books b
JOIN authors a ON a.id = b.author_id
JOIN categories c ON c.id = b.category_id
"""


def _parse_price(raw, label, errors):
    raw = (raw or "").strip()
    if raw == "":
        return None
    if not re.fullmatch(r"-?\d+", raw):
        errors.append(f"{label} must be a whole number.")
        return None
    value = int(raw)
    if value < 0:
        errors.append(f"{label} cannot be negative.")
        return None
    return value


def read_filters(args):
    """Read and validate catalogue criteria from the query string."""
    errors = []
    q = unicodedata.normalize("NFC", (args.get("q") or "").strip())[:100]
    category_id = None
    raw_cat = (args.get("category") or "").strip()
    if raw_cat:
        if raw_cat.isdigit():
            category_id = int(raw_cat)
        else:
            errors.append("Unknown category.")
    min_price = _parse_price(args.get("min_price"), "Minimum price", errors)
    max_price = _parse_price(args.get("max_price"), "Maximum price", errors)
    if min_price is not None and max_price is not None and min_price > max_price:
        errors.append("Minimum price cannot be greater than maximum price.")
    raw_page = (args.get("page") or "1").strip()
    page = int(raw_page) if raw_page.isdigit() and int(raw_page) > 0 else 1
    return {
        "q": q,
        "category": category_id,
        "min_price": min_price,
        "max_price": max_price,
        "page": page,
        "raw": {
            "q": q,
            "category": raw_cat,
            "min_price": (args.get("min_price") or "").strip(),
            "max_price": (args.get("max_price") or "").strip(),
        },
    }, errors


def query_books(filters, page_size):
    where = ["b.is_deleted = 0"]
    params = []
    if filters["q"]:
        like = "%" + filters["q"].lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(pylower(b.title) LIKE ? ESCAPE '\\' OR pylower(a.name) LIKE ? ESCAPE '\\')")
        params += [like, like]
    if filters["category"] is not None:
        where.append("b.category_id = ?")
        params.append(filters["category"])
    if filters["min_price"] is not None:
        where.append("b.price >= ?")
        params.append(filters["min_price"])
    if filters["max_price"] is not None:
        where.append("b.price <= ?")
        params.append(filters["max_price"])
    clause = " WHERE " + " AND ".join(where)
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) FROM books b JOIN authors a ON a.id = b.author_id" + clause, params
    ).fetchone()[0]
    pages = max(1, math.ceil(total / page_size))
    page = min(filters["page"], pages)
    rows = db.execute(
        BOOK_SELECT + clause + " ORDER BY b.created_at DESC, b.id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, total, page, pages


def list_url(raw, page):
    params = {k: v for k, v in raw.items() if v}
    if page > 1:
        params["page"] = page
    return url_for("catalog.index") + ("?" + urlencode(params) if params else "")


@bp.route("/books")
@bp.route("/")  # registered first -> canonical URL for url_for
def index():
    filters, errors = read_filters(request.args)
    categories = get_db().execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE").fetchall()
    page_size = current_app.config["PAGE_SIZE"]
    if errors:
        # US-18 AC2: invalid criteria are rejected before any query runs.
        return render_template(
            "catalog/index.html", books=[], total=0, page=1, pages=1, errors=errors,
            filters=filters, categories=categories, page_links=[], current_url=list_url(filters["raw"], 1),
        ), 400
    books, total, page, pages = query_books(filters, page_size)
    page_links = [(n, list_url(filters["raw"], n)) for n in range(1, pages + 1)]
    return render_template(
        "catalog/index.html", books=books, total=total, page=page, pages=pages, errors=[],
        filters=filters, categories=categories, page_links=page_links,
        current_url=list_url(filters["raw"], page),
    )


def _back_url():
    """US-16: return to the exact catalogue page/filters the customer came from."""
    back = safe_next(request.args.get("back"), default=url_for("catalog.index"))
    if not (back == "/" or back.startswith("/?") or back.startswith("/books")):
        back = url_for("catalog.index")
    return back


@bp.route("/books/<book_id>")
def detail(book_id):
    back = _back_url()
    book = None
    if book_id.isdigit() and len(book_id) < 19:
        book = get_db().execute(BOOK_SELECT + " WHERE b.id = ? AND b.is_deleted = 0", (int(book_id),)).fetchone()
    if book is None:
        # US-15 / US-04 AC3: friendly message for missing or hidden books.
        return render_template("catalog/not_found.html", back=back), 404
    return render_template("catalog/detail.html", book=book, back=back)


PALETTE = ["#173A33", "#6E2430", "#1F3550", "#7A5A1E", "#3F3356", "#1E4F57", "#5A3A24", "#33403C"]


@bp.route("/covers/<int:book_id>.svg")
def cover(book_id):
    """Generated placeholder cover for demo books without an uploaded image."""
    row = get_db().execute(
        "SELECT b.title, a.name AS author FROM books b JOIN authors a ON a.id = b.author_id WHERE b.id = ?",
        (book_id,),
    ).fetchone()
    if row is None:
        abort(404)
    color = PALETTE[book_id % len(PALETTE)]
    lines = textwrap.wrap(row["title"], 15)[:5]
    top = 150 - (len(lines) - 1) * 14
    title_svg = "".join(
        f'<text x="120" y="{top + i * 28}" text-anchor="middle" font-size="21" font-weight="700" fill="#F7F1DF">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    # Cloth-bound look: fine weave texture, brass double rules and an ornament (the brand's "stamping").
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 360" width="240" height="360">
<defs><pattern id="w" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 0h4M0 2h4" stroke="rgba(255,255,255,.05)" stroke-width="1"/></pattern></defs>
<rect width="240" height="360" fill="{color}"/><rect width="240" height="360" fill="url(#w)"/>
<g stroke="#C9962B" fill="none"><path d="M24 40h192M24 46h192M24 314h192M24 320h192" stroke-width="1.5"/>
<path d="M108 {top + len(lines) * 28 + 6}l12 -8l12 8l-12 8z" fill="#C9962B" stroke="none"/></g>
<g font-family="'Segoe UI', Arial, 'Noto Sans', sans-serif">{title_svg}
<text x="120" y="296" text-anchor="middle" font-size="14" fill="#E9D9AE">{escape(row["author"])}</text></g>
</svg>"""
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=300"})
