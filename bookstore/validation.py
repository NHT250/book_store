"""Server-side validation shared by the browser forms and direct HTTP requests."""
import re

from .db import ROLES

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 8
PASSWORD_MAX = 64


def normalize_email(value):
    """US-02 AC4: trim surrounding spaces and ignore letter case."""
    return (value or "").strip().lower()


def validate_account(form, *, with_role=False):
    """Validate registration / admin-create input (US-01 AC3-AC4, US-11 AC2-AC3).

    Returns (data, errors, bad_role) where bad_role is True when a role value outside
    the allowed set was sent (must be answered with HTTP 400 and nothing created).
    """
    errors = {}
    full_name = (form.get("full_name") or "").strip()
    email = normalize_email(form.get("email"))
    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""

    if not full_name:
        errors["full_name"] = "Full name is required."
    elif len(full_name) > 100:
        errors["full_name"] = "Full name must be at most 100 characters."

    if not email:
        errors["email"] = "Email is required."
    elif len(email) > 254 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."

    if not password:
        errors["password"] = "Password is required."
    elif not (PASSWORD_MIN <= len(password) <= PASSWORD_MAX):
        errors["password"] = f"Password must be between {PASSWORD_MIN} and {PASSWORD_MAX} characters."

    if not confirm:
        errors["confirm_password"] = "Please confirm the password."
    elif confirm != password:
        errors["confirm_password"] = "Password confirmation does not match."

    role = None
    bad_role = False
    if with_role:
        raw_role = (form.get("role") or "").strip()
        if not raw_role:
            errors["role"] = "Please select a role."
        elif raw_role.upper() not in ROLES:
            errors["role"] = "Role must be Administrator or Customer."
            bad_role = True
        else:
            role = raw_role.upper()

    return {"full_name": full_name, "email": email, "password": password, "role": role}, errors, bad_role


def parse_int(value, *, field, errors, minimum=None, required=True, label=None):
    label = label or field
    raw = (value if value is not None else "").strip() if isinstance(value, str) or value is None else str(value)
    if raw == "":
        if required:
            errors[field] = f"{label} is required."
        return None
    if not re.fullmatch(r"-?\d+", raw):
        errors[field] = f"{label} must be a whole number."
        return None
    number = int(raw)
    if minimum is not None and number < minimum:
        errors[field] = f"{label} must be at least {minimum}." if minimum > 0 else f"{label} cannot be negative."
        return None
    return number
