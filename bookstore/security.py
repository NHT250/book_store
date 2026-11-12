"""Session loading, role guards and CSRF protection."""
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, redirect, request, session, url_for

from .db import ROLE_ADMIN, STATUS_LOCKED, get_db


def load_current_user():
    """Re-read the signed-in user on every request so a lock takes effect immediately (US-19 AC2)."""
    g.user = None
    g.locked_out = False
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        session.clear()
        return
    if user["status"] == STATUS_LOCKED:
        session.clear()
        g.locked_out = True
        return
    g.user = user


def safe_next(target, default="/"):
    """Only allow same-site relative paths (no open redirects)."""
    if not target:
        return default
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return default
    return target


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            params = {"next": request.full_path.rstrip("?")}
            if g.get("locked_out"):
                params["locked"] = 1
            return redirect(url_for("auth.login", **params))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != ROLE_ADMIN:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def verify_csrf():
    if request.method != "POST":
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    expected = session.get("_csrf")
    if not expected or not sent or not secrets.compare_digest(sent, expected):
        abort(400, description="Invalid or missing CSRF token. Reload the page and try again.")
