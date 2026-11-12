"""E-Commercial Book Store - Team 3 (Release 1.0, F1-F5)."""
import os

from flask import Flask, g, redirect, render_template, request, url_for

from . import db
from .security import csrf_token, load_current_user, verify_csrf


def format_vnd(value):
    try:
        return f"{int(value):,}".replace(",", ".") + " ₫"
    except (TypeError, ValueError):
        return value


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "bookstore.sqlite3")),
        UPLOAD_FOLDER=os.path.join(app.root_path, "static", "uploads"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        SEED_DEMO_DATA=os.environ.get("SEED_DEMO_DATA", "1") == "1",
        PAGE_SIZE=12,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_db(app)
    app.teardown_appcontext(db.close_db)
    app.jinja_env.filters["vnd"] = format_vnd
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["STORES"] = db.STORES

    @app.before_request
    def _before():
        load_current_user()
        verify_csrf()

    @app.after_request
    def _no_cache(response):
        # US-02 AC3: after sign-out, the browser Back button must not show a cached private page.
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    from .auth import bp as auth_bp
    from .catalog import bp as catalog_bp
    from .staff import bp as staff_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(staff_bp)

    @app.errorhandler(400)
    def _bad_request(err):
        return render_template("error.html", code=400, title="Bad request", message=err.description), 400

    @app.errorhandler(403)
    def _forbidden(err):
        return render_template("error.html", code=403, title="Access denied",
                               message="You do not have permission to perform this action."), 403

    @app.errorhandler(404)
    def _not_found(err):
        return render_template("error.html", code=404, title="Page not found",
                               message="The page you are looking for does not exist."), 404

    @app.errorhandler(413)
    def _too_large(err):
        return render_template("error.html", code=413, title="File too large",
                               message="Cover images must be 5 MB or smaller."), 413

    @app.route("/home")
    def home():
        if g.user and g.user["role"] == db.ROLE_ADMIN:
            return redirect(url_for("staff.dashboard"))
        return redirect(url_for("catalog.index"))

    return app
