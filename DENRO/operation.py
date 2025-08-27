# operation.py
from django.contrib import messages
from django.db import connection, DatabaseError, transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# =========================
# LOGIN via Postgres function
# =========================
def login_user(request):
    if request.method != "POST":
        return redirect("login")

    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""

    if not username or not password:
        messages.error(request, "Please enter username and password.")
        return redirect("login")

    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, role, first_name, last_name, region_id, penro_id, cenro_id
                FROM auth_login(%s, %s);
                """,
                [username, password],
            )
            row = cur.fetchone()
    except DatabaseError as e:
        # Show detailed DB error only when DEBUG=True, to make troubleshooting easy
        if settings.DEBUG:
            logger.exception("DB error during auth_login()")
            msg = getattr(e, "pgerror", None) or str(e)
            messages.error(request, f"DB error: {msg}")
        else:
            messages.error(request, "Login service is temporarily unavailable.")
        return redirect("login")

    if not row:
        messages.error(request, "Username or password is incorrect.")
        return redirect("login")

    # Unpack and set session (matches auth_login RETURNS)
    user_id, uname, role, first_name, last_name, region_id, penro_id, cenro_id = row
    request.session["user_id"]    = user_id
    request.session["username"]   = uname
    request.session["role"]       = (role or "").strip().lower()
    request.session["first_name"] = first_name
    request.session["last_name"]  = last_name
    request.session["region_id"]  = region_id
    request.session["penro_id"]   = penro_id
    request.session["cenro_id"]   = cenro_id

    # Route by role (stored as 'Super Admin','Admin','PENRO','CENRO','Evaluator')
    r = request.session["role"]  # e.g. "super admin","admin","penro","cenro","evaluator"
    if r == "super admin":
        return redirect("SA-dashboard")
    elif r == "admin":
        return redirect("Admin-dashboard")
    elif r == "penro":
        return redirect("PENRO-dashboard")
    elif r == "cenro":
        return redirect("CENRO-dashboard")
    else:
        messages.error(request, "Undefined role. Contact support.")
        request.session.flush()
        return redirect("login")


# =========================
# LOGOUT
# =========================
def logout_user(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect("login")


# =========================
# Helpers: fetch options (SQL)
# =========================
def _fetch_regions():
    with connection.cursor() as cur:
        cur.execute("SELECT id, name FROM regions ORDER BY name;")
        return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]


# =========================
# CREATE ACCOUNT (calls Postgres create_user)
# =========================
def create_account(request):
    if request.method == "POST":
        # Required
        first_name   = (request.POST.get("first_name") or "").strip()
        last_name    = (request.POST.get("last_name") or "").strip()
        gender       = (request.POST.get("gender") or "").strip()
        email        = (request.POST.get("email") or "").strip()
        role         = (request.POST.get("role") or "").strip()
        username     = (request.POST.get("username") or "").strip()
        password     = request.POST.get("password") or ""
        # Optional
        phone_number = (request.POST.get("phone_number") or "").strip() or None
        profile_pic  = (request.POST.get("profile_pic") or "").strip() or None

        # Office selections (cascading)
        region_id = request.POST.get("region_id") or None
        penro_id  = request.POST.get("penro_id") or None
        cenro_id  = request.POST.get("cenro_id") or None

        # Basic validation
        errors = []
        if not first_name: errors.append("First name is required.")
        if not last_name:  errors.append("Last name is required.")
        if gender not in ("Male", "Female", "Other"):
            errors.append("Please pick a valid gender.")
        if not email:     errors.append("Email is required.")
        if role not in ("Super Admin", "Admin", "PENRO", "CENRO", "Evaluator"):
            errors.append("Please choose a valid role.")
        if not username:  errors.append("Username is required.")
        if not password:  errors.append("Password is required.")
        if errors:
            for e in errors: messages.error(request, e)
            return redirect("account-create")

        def to_int_or_none(v):
            try:
                return int(v) if v not in (None, "", "null") else None
            except Exception:
                return None

        r = to_int_or_none(region_id)
        p = to_int_or_none(penro_id)
        c = to_int_or_none(cenro_id)

        # Match office IDs to role rules before calling DB func
        if role == "Super Admin":
            r = p = c = None
        elif role == "Admin":
            if not r:
                messages.error(request, "Admin must be assigned to a Region.")
                return redirect("account-create")
            p = c = None
        elif role == "PENRO":
            if not p:
                messages.error(request, "PENRO must be assigned to a PENRO.")
                return redirect("account-create")
            r = c = None
        elif role == "CENRO":
            if not c:
                messages.error(request, "CENRO must be assigned to a CENRO.")
                return redirect("account-create")
            r = p = None
        elif role == "Evaluator":
            if not any([r, p, c]):
                messages.error(request, "Evaluator must be assigned to Region OR PENRO OR CENRO.")
                return redirect("account-create")
            if c:
                r = p = None
            elif p:
                r = c = None
            else:
                p = c = None

        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        SELECT create_user(
                            %s, %s, %s, %s,   -- first_name, last_name, gender, email
                            %s,               -- role
                            %s, %s,           -- username, password
                            %s, %s,           -- phone_number, profile_pic
                            %s, %s, %s,       -- region_id, penro_id, cenro_id
                            %s                -- p_hash_password (True)
                        );
                        """,
                        [
                            first_name, last_name, gender, email,
                            role, username, password,
                            phone_number, profile_pic,
                            r, p, c,
                            True,
                        ],
                    )
                    new_id = cur.fetchone()[0]

            messages.success(request, f"Account created (ID: {new_id}). You can now log in.")
            return redirect("login")

        except DatabaseError as e:
            msg = getattr(e, "pgerror", None) or str(e)
            if "exists" in msg.lower():
                messages.error(request, "Email or username already exists.")
            else:
                messages.error(request, f"DB error: {msg}")
            return redirect("account-create")

    # GET → show form with Regions
    context = {
        "regions": _fetch_regions(),
        "roles":   ["Super Admin", "Admin", "PENRO", "CENRO", "Evaluator"],
        "genders": ["Male", "Female", "Other"],
    }
    return render(request, "create_account.html", context)


# =========================
# AJAX APIs for cascading selects (pure SQL)
# =========================
def api_penros_by_region(request, region_id):
    try:
        rid = int(region_id)
    except Exception:
        return HttpResponseBadRequest("Invalid region id")

    with connection.cursor() as cur:
        cur.execute("SELECT id, name FROM penros WHERE region_id=%s ORDER BY name;", [rid])
        items = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    return JsonResponse({"items": items})


def api_cenros_by_penro(request, penro_id):
    try:
        pid = int(penro_id)
    except Exception:
        return HttpResponseBadRequest("Invalid penro id")

    with connection.cursor() as cur:
        cur.execute("SELECT id, name FROM cenros WHERE penro_id=%s ORDER BY name;", [pid])
        items = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    return JsonResponse({"items": items})
