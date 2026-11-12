"""F1 Account management: register (US-01), sign in / sign out (US-02)."""
import sqlite3

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import ROLE_ADMIN, ROLE_CUSTOMER, STATUS_ACTIVE, STATUS_LOCKED, get_db, now_iso
from .security import login_required, safe_next
from .validation import normalize_email, validate_account

bp = Blueprint("auth", __name__)

GENERIC_LOGIN_ERROR = "Invalid email or password"
LOCKED_MESSAGE = "Your account has been locked. Please contact the store administrator."


def landing_url(user):
    """US-02 AC1: Customer -> storefront, Administrator -> Staff workspace."""
    return url_for("staff.dashboard") if user["role"] == ROLE_ADMIN else url_for("catalog.index")


def email_exists(email):
    return get_db().execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone() is not None


def create_user(data, role):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (full_name, email, password_hash, role, status, created_at) VALUES (?,?,?,?,?,?)",
            (data["full_name"], data["email"], generate_password_hash(data["password"]), role, STATUS_ACTIVE, now_iso()),
        )
        db.commit()
        return True
    except sqlite3.IntegrityError:  # race on the UNIQUE email constraint
        db.rollback()
        return False


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(landing_url(g.user))
    form = {}
    errors = {}
    if request.method == "POST":
        data, errors, _ = validate_account(request.form)
        form = {"full_name": data["full_name"], "email": data["email"]}
        if not errors and email_exists(data["email"]):
            errors["email"] = "This email is already registered."
        if not errors and not create_user(data, ROLE_CUSTOMER):
            errors["email"] = "This email is already registered."
        if not errors:
            flash("Your reader account has been created. Please sign in.", "success")
            return redirect(url_for("auth.login"))
        status = 409 if errors.get("email") == "This email is already registered." else 400
        return render_template("auth/register.html", form=form, errors=errors), status
    return render_template("auth/register.html", form=form, errors=errors)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(landing_url(g.user))
    next_url = request.values.get("next", "")
    error = None
    email_value = ""
    if request.args.get("locked") and request.method == "GET":
        error = LOCKED_MESSAGE
    if request.method == "POST":
        email_value = (request.form.get("email") or "").strip()
        email = normalize_email(email_value)
        password = request.form.get("password") or ""
        user = None
        if email and password:
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            # US-02 AC2: same generic message for every failure, no session created.
            return render_template("auth/login.html", error=GENERIC_LOGIN_ERROR, email=email_value, next=next_url), 401
        if user["status"] == STATUS_LOCKED:
            return render_template("auth/login.html", error=LOCKED_MESSAGE, email=email_value, next=next_url), 403
        session.clear()
        session["user_id"] = user["id"]
        session.permanent = False
        target = safe_next(next_url, default=landing_url(user))
        if user["role"] != ROLE_ADMIN and target.startswith("/staff"):
            target = landing_url(user)
        return redirect(target)
    return render_template("auth/login.html", error=error, email=email_value, next=next_url)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/account")
@login_required
def account():
    return render_template("auth/account.html")
