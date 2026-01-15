# operation.py
from django.contrib import messages
from django.db import connection, DatabaseError, transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.conf import settings
import logging
from supabase import create_client
import os
import io
import base64
import time

logger = logging.getLogger(__name__)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # ⚠️ service role key, never expose to frontend
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
# =========================
# LOGIN via Postgres function (UPDATED to match your schema)
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

    # Unpack and set session (matches updated auth_login RETURNS)
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
# Helper: Check if user is logged in and get current user role
# =========================
def get_current_user_info(request):
    """Returns tuple of (user_role, region_id, penro_id, cenro_id) or (None, None, None, None)"""
    if not request.session.get("user_id"):
        return None, None, None, None
    
    role = request.session.get("role", "").lower()
    region_id = request.session.get("region_id")
    penro_id = request.session.get("penro_id")
    cenro_id = request.session.get("cenro_id")
    
    return role, region_id, penro_id, cenro_id

# =========================
# Helper: Get allowed roles for current user
# =========================
def get_allowed_roles_for_user(current_role):
    """Returns list of roles that current user can create"""
    role_hierarchy = {
        "super admin": ["Super Admin", "Admin"],
        "admin": ["Admin", "PENRO"],
        "penro": ["PENRO", "CENRO"],
        "cenro": ["CENRO", "Evaluator"],
        "evaluator": []  # Evaluators cannot create users
    }
    return role_hierarchy.get(current_role, [])

# =========================
# Helper: Get available offices based on current user's role and assignments
# =========================
def get_available_offices_for_user(current_role, current_region_id, current_penro_id, current_cenro_id):
    """Returns dict with available regions, penros, and cenros based on current user's permissions"""
    regions = []
    penros = []
    cenros = []
    
    with connection.cursor() as cur:
        if current_role == "super admin":
            # Super Admin can see all regions
            cur.execute("SELECT id, name FROM regions ORDER BY name;")
            regions = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
            
        elif current_role == "admin":
            # Admin can only see their assigned region and its PENROs
            if current_region_id:
                cur.execute("SELECT id, name FROM regions WHERE id = %s;", [current_region_id])
                regions = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
                
                cur.execute("SELECT id, name FROM penros WHERE region_id = %s ORDER BY name;", [current_region_id])
                penros = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
                
        elif current_role == "penro":
            # PENRO can only see their assigned PENRO and its CENROs
            if current_penro_id:
                cur.execute("SELECT id, name FROM penros WHERE id = %s;", [current_penro_id])
                penros = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
                
                cur.execute("SELECT id, name FROM cenros WHERE penro_id = %s ORDER BY name;", [current_penro_id])
                cenros = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
                
        elif current_role == "cenro":
            # CENRO can only see their assigned CENRO
            if current_cenro_id:
                cur.execute("SELECT id, name FROM cenros WHERE id = %s;", [current_cenro_id])
                cenros = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    
    return {
        "regions": regions,
        "penros": penros,
        "cenros": cenros
    }

# =========================
# Helper: Validate office assignment based on role and current user permissions
# =========================
def validate_office_assignment(target_role, region_id, penro_id, cenro_id, current_user):
    """Validates if the current user can assign the target role to the specified offices"""
    current_role, current_region_id, current_penro_id, current_cenro_id = current_user
    
    # Convert string IDs to integers or None
    def to_int_or_none(v):
        try:
            return int(v) if v not in (None, "", "null") else None
        except Exception:
            return None
    
    r = to_int_or_none(region_id)
    p = to_int_or_none(penro_id)
    c = to_int_or_none(cenro_id)
    
    # Check role-specific office requirements
    if target_role == "Super Admin":
        if r or p or c:
            return False, "Super Admin cannot be assigned to any office."
    elif target_role == "Admin":
        if not r or p or c:
            return False, "Admin must be assigned to exactly one Region."
        # Check if current user can assign to this region
        if current_role == "super admin":
            pass  # Super admin can assign to any region
        elif current_role == "admin" and current_region_id == r:
            pass  # Admin can assign to their own region
        else:
            return False, "You don't have permission to assign Admin to this region."
    elif target_role == "PENRO":
        if r or not p or c:
            return False, "PENRO must be assigned to exactly one PENRO office."
        # Check if current user can assign to this PENRO
        if current_role == "super admin":
            pass  # Super admin can assign to any PENRO
        elif current_role == "admin":
            # Check if this PENRO belongs to admin's region
            with connection.cursor() as cur:
                cur.execute("SELECT region_id FROM penros WHERE id = %s;", [p])
                row = cur.fetchone()
                if not row or row[0] != current_region_id:
                    return False, "You can only assign PENRO within your region."
        elif current_role == "penro" and current_penro_id == p:
            pass  # PENRO can assign to their own office
        else:
            return False, "You don't have permission to assign PENRO to this office."
    elif target_role == "CENRO":
        if r or p or not c:
            return False, "CENRO must be assigned to exactly one CENRO office."
        # Check if current user can assign to this CENRO
        if current_role == "super admin":
            pass  # Super admin can assign to any CENRO
        elif current_role == "admin":
            # Check if this CENRO belongs to admin's region
            with connection.cursor() as cur:
                cur.execute("""
                    SELECT p.region_id 
                    FROM cenros c 
                    JOIN penros p ON c.penro_id = p.id 
                    WHERE c.id = %s;
                """, [c])
                row = cur.fetchone()
                if not row or row[0] != current_region_id:
                    return False, "You can only assign CENRO within your region."
        elif current_role == "penro":
            # Check if this CENRO belongs to PENRO's office
            with connection.cursor() as cur:
                cur.execute("SELECT penro_id FROM cenros WHERE id = %s;", [c])
                row = cur.fetchone()
                if not row or row[0] != current_penro_id:
                    return False, "You can only assign CENRO within your PENRO."
        elif current_role == "cenro" and current_cenro_id == c:
            pass  # CENRO can assign to their own office
        else:
            return False, "You don't have permission to assign CENRO to this office."
    elif target_role == "Evaluator":
        if not any([r, p, c]) or sum([bool(r), bool(p), bool(c)]) != 1:
            return False, "Evaluator must be assigned to exactly one office (Region OR PENRO OR CENRO)."
        # Check permissions based on which office is assigned
        if c:  # Assigned to CENRO
            if current_role == "cenro" and current_cenro_id == c:
                pass  # CENRO can assign evaluator to their office
            else:
                return False, "You can only assign Evaluator to your own CENRO office."
        elif p:  # Assigned to PENRO
            if current_role == "penro" and current_penro_id == p:
                pass  # PENRO can assign evaluator to their office
            else:
                return False, "You can only assign Evaluator to your own PENRO office."
        elif r:  # Assigned to Region
            if current_role == "admin" and current_region_id == r:
                pass  # Admin can assign evaluator to their region
            else:
                return False, "You can only assign Evaluator to your own region."
    
    return True, None

# =========================
# Helpers: fetch options (SQL) - Updated for hierarchical access
# =========================
def _fetch_regions():
    with connection.cursor() as cur:
        cur.execute("SELECT id, name FROM regions ORDER BY name;")
        return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]

# =========================
# CREATE ACCOUNT (Updated with hierarchical permissions and auto-assignment)
# =========================
def create_account(request):
    # Check if user is logged in
    current_role, current_region_id, current_penro_id, current_cenro_id = get_current_user_info(request)
    if not current_role:
        messages.error(request, "You must be logged in to create accounts.")
        return redirect("login")
    
    # Check if user has permission to create accounts
    allowed_roles = get_allowed_roles_for_user(current_role)
    if not allowed_roles:
        messages.error(request, "You don't have permission to create user accounts.")
        return redirect("login")  # or appropriate dashboard
    
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
        protected_area_id = request.POST.get("protected_area_id") or None
        if protected_area_id:
            try:
                protected_area_id = int(protected_area_id)
            except:
                protected_area_id = None

        # Basic validation
        errors = []
        if not first_name: errors.append("First name is required.")
        if not last_name:  errors.append("Last name is required.")
        if gender not in ("Male", "Female", "Other"):
            errors.append("Please pick a valid gender.")
        if not email:     errors.append("Email is required.")
        if role not in allowed_roles:
            errors.append(f"You can only create users with these roles: {', '.join(allowed_roles)}")
        if not username:  errors.append("Username is required.")
        if not password:  errors.append("Password is required.")
        if errors:
            for e in errors: messages.error(request, e)
            return redirect("account-create")

        # Auto-assign office IDs based on current user's role and target role
        r = None  # region_id
        p = None  # penro_id  
        c = None  # cenro_id

        if role == "Super Admin":
            # Super Admin has no office assignments
            r = p = c = None
            
        elif current_role == "super admin":
            # Super Admin creating other roles - get from form
            if role == "Admin":
                # For Admin creation by Super Admin, require region selection from form
                region_id_from_form = request.POST.get("region_id")
                try:
                    r = int(region_id_from_form) if region_id_from_form not in (None, "", "null") else None
                except:
                    r = None
                
                if not r:
                    messages.error(request, "Please select a region for the Admin user.")
                    return redirect("account-create")
                
                p = c = None
            elif role == "PENRO":
                # Super Admin can also create PENRO - get penro_id from form
                penro_id_from_form = request.POST.get("penro_id")
                try:
                    p = int(penro_id_from_form) if penro_id_from_form not in (None, "", "null") else None
                except:
                    p = None
                
                if not p:
                    messages.error(request, "Please select a PENRO office.")
                    return redirect("account-create")
                
                r = c = None
            
        elif current_role == "admin":
            # Admin can create Admin or PENRO - both should inherit admin's region
            if role == "Admin":
                r = current_region_id
                p = c = None
            elif role == "PENRO":
                # For PENRO creation, get penro_id from form and inherit admin's region
                penro_id_from_form = request.POST.get("penro_id")
                try:
                    p = int(penro_id_from_form) if penro_id_from_form not in (None, "", "null") else None
                except:
                    p = None
                
                if not p:
                    messages.error(request, "Please select a PENRO office.")
                    return redirect("account-create")
                    
                # Verify this PENRO belongs to admin's region
                with connection.cursor() as cur:
                    cur.execute("SELECT region_id FROM penros WHERE id = %s;", [p])
                    row = cur.fetchone()
                    if not row or row[0] != current_region_id:
                        messages.error(request, "Selected PENRO does not belong to your region.")
                        return redirect("account-create")
                
                # PENRO should inherit admin's region AND have penro assignment
                r = current_region_id  # Inherit region from admin
                c = None
                
        elif current_role == "penro":
            # PENRO can create PENRO or CENRO - both should inherit penro's assignments
            if role == "PENRO":
                # Inherit both region and penro from current PENRO user
                r = current_region_id
                p = current_penro_id
                c = None
            elif role == "CENRO":
                # For CENRO creation, get cenro_id from form and inherit penro's region
                cenro_id_from_form = request.POST.get("cenro_id")
                try:
                    c = int(cenro_id_from_form) if cenro_id_from_form not in (None, "", "null") else None
                except:
                    c = None
                    
                if not c:
                    messages.error(request, "Please select a CENRO office.")
                    return redirect("account-create")
                    
                # Verify this CENRO belongs to penro's office
                with connection.cursor() as cur:
                    cur.execute("SELECT penro_id FROM cenros WHERE id = %s;", [c])
                    row = cur.fetchone()
                    if not row or row[0] != current_penro_id:
                        messages.error(request, "Selected CENRO does not belong to your PENRO.")
                        return redirect("account-create")
                
                # Get the region_id for this CENRO through PENRO
                with connection.cursor() as cur:
                    cur.execute("""
                        SELECT p.region_id 
                        FROM cenros c 
                        JOIN penros p ON c.penro_id = p.id 
                        WHERE c.id = %s;
                    """, [c])
                    row = cur.fetchone()
                    if row:
                        r = row[0]  # Inherit region through PENRO
                
                # CENRO should inherit region, penro, AND have cenro assignment
                p = current_penro_id  # Inherit penro from current user
                
        elif current_role == "cenro":
            # CENRO can create CENRO or Evaluator - both should inherit cenro's full hierarchy
            if role == "CENRO":
                # Inherit full hierarchy: region, penro, and cenro
                r = current_region_id
                p = current_penro_id  
                c = current_cenro_id
            elif role == "Evaluator":
                # Evaluator assigned to current CENRO inherits full hierarchy
                r = current_region_id
                p = current_penro_id
                c = current_cenro_id

        try:
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (
                            first_name, last_name, gender, email, phone_number,
                            role, username, password, profile_pic,
                            region_id, penro_id, cenro_id, protected_area_id
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, crypt(%s, gen_salt('bf')), %s,
                            %s, %s, %s, %s
                        ) RETURNING id;
                        """,
                        [
                            first_name, last_name, gender, email, phone_number,
                            role, username, password, profile_pic,
                            r, p, c, protected_area_id
                        ],
                    )
                    new_id = cur.fetchone()[0]

            messages.success(request, f"Account successfully created! User can now log in.")
            return redirect("account-create")  # Stay on page to create more users

        except DatabaseError as e:
            msg = getattr(e, "pgerror", None) or str(e)
            if "exists" in msg.lower():
                messages.error(request, "Email or username already exists.")
            else:
                messages.error(request, f"DB error: {msg}")
            return redirect("account-create")

    # GET → show form with appropriate options based on current user's role
    available_offices = get_available_offices_for_user(current_role, current_region_id, current_penro_id, current_cenro_id)
    
    # Get protected areas list
    protected_areas = get_protected_areas()
    
    # Get current user's office names for display
    current_user_region_name = None
    current_user_penro_name = None
    current_user_cenro_name = None
    
    with connection.cursor() as cur:
        if current_region_id:
            cur.execute("SELECT name FROM regions WHERE id = %s;", [current_region_id])
            row = cur.fetchone()
            if row:
                current_user_region_name = row[0]
        
        if current_penro_id:
            cur.execute("SELECT name FROM penros WHERE id = %s;", [current_penro_id])
            row = cur.fetchone()
            if row:
                current_user_penro_name = row[0]
        
        if current_cenro_id:
            cur.execute("SELECT name FROM cenros WHERE id = %s;", [current_cenro_id])
            row = cur.fetchone()
            if row:
                current_user_cenro_name = row[0]
    
    context = {
        "regions": available_offices["regions"],
        "penros": available_offices["penros"],
        "cenros": available_offices["cenros"],
        "protected_areas": protected_areas,
        "roles": allowed_roles,
        "genders": ["Male", "Female", "Other"],
        "current_user_role": current_role.title(),
        # Current user's office assignments for auto-inheritance
        "current_user_region_id": current_region_id,
        "current_user_penro_id": current_penro_id,
        "current_user_cenro_id": current_cenro_id,
        "current_user_region_name": current_user_region_name,
        "current_user_penro_name": current_user_penro_name,
        "current_user_cenro_name": current_user_cenro_name,
    }
    return render(request, "create_account.html", context)

# =========================
# AJAX APIs for cascading selects (Updated with permission checks)
# =========================
def api_penros_by_region(request, region_id):
    current_role, current_region_id, current_penro_id, current_cenro_id = get_current_user_info(request)
    if not current_role:
        return HttpResponseBadRequest("Not authenticated")
    
    try:
        rid = int(region_id)
    except Exception:
        return HttpResponseBadRequest("Invalid region id")
    
    # Check if user has access to this region
    if current_role == "admin" and current_region_id != rid:
        return HttpResponseBadRequest("Access denied to this region")
    
    with connection.cursor() as cur:
        if current_role in ["super admin", "admin"]:
            cur.execute("SELECT id, name FROM penros WHERE region_id=%s ORDER BY name;", [rid])
        else:
            # For other roles, return empty list
            return JsonResponse({"items": []})
        
        items = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    return JsonResponse({"items": items})

def api_cenros_by_penro(request, penro_id):
    current_role, current_region_id, current_penro_id, current_cenro_id = get_current_user_info(request)
    if not current_role:
        return HttpResponseBadRequest("Not authenticated")
    
    try:
        pid = int(penro_id)
    except Exception:
        return HttpResponseBadRequest("Invalid penro id")
    
    # Check if user has access to this PENRO
    if current_role == "admin":
        # Check if this PENRO belongs to admin's region
        with connection.cursor() as cur:
            cur.execute("SELECT region_id FROM penros WHERE id = %s;", [pid])
            row = cur.fetchone()
            if not row or row[0] != current_region_id:
                return HttpResponseBadRequest("Access denied to this PENRO")
    elif current_role == "penro" and current_penro_id != pid:
        return HttpResponseBadRequest("Access denied to this PENRO")
    
    with connection.cursor() as cur:
        if current_role in ["super admin", "admin", "penro"]:
            cur.execute("SELECT id, name FROM cenros WHERE penro_id=%s ORDER BY name;", [pid])
        else:
            # For other roles, return empty list
            return JsonResponse({"items": []})
        
        items = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
    return JsonResponse({"items": items})
# =========================
# GET ENUMERATOR REPORTS (WITH ALL FILTERS)
# =========================
def get_enumerator_reports(submitter_role=None, from_date=None, to_date=None, establishment_type=None, pa_id=None, establishment_status=None, cenro_id=None, penro_id=None):
    """
    Fetch enumerator reports filtered by submitter role.
    
    Args:
        submitter_role: Filter by role of user who submitted report (CENRO, PENRO, Admin)
        from_date: Start date (datetime.date object or None)
        to_date: End date (datetime.date object or None)
        establishment_type: Filter by establishment type (None for all)
        pa_id: Filter by protected area ID (None for all)
        establishment_status: Filter by establishment status (None for all)
        cenro_id: Filter by CENRO office (None for all)
        penro_id: Filter by PENRO office (None for all)
    
    Returns:
        List of report dictionaries
    """
    reports = []
    
    try:
        with connection.cursor() as cur:
            query = """
                SELECT 
                    er.id,
                    er.establishment_name,
                    er.proponent_name,
                    er.pa_name,
                    er.enumerator_name,
                    er.report_date,
                    er.informant_name,
                    er.remarks,
                    er.created_at,
                    u.first_name || ' ' || u.last_name as enumerator_full_name,
                    u.cenro_id,
                    ep.establishment_type,
                    er.pa_id,
                    ep.establishment_status,
                    CASE 
                        WHEN an.attested_by_signature IS NOT NULL 
                        AND an.noted_by_signature IS NOT NULL 
                        AND TRIM(an.attested_by_signature) != '' 
                        AND TRIM(an.noted_by_signature) != '' 
                        THEN TRUE 
                        ELSE FALSE 
                    END as is_completed
                FROM enumerators_report er
                LEFT JOIN users u ON er.enumerator_id = u.id
                LEFT JOIN establishment_profile ep ON er.establishment_id = ep.id
                LEFT JOIN attestation_notations an ON er.attestation_id = an.id
                WHERE 1=1
            """
            
            params = []
            
            if submitter_role:
                query += " AND LOWER(CAST(u.role AS TEXT)) = LOWER(%s)"
                params.append(submitter_role)
            
            if cenro_id:
                query += " AND u.cenro_id = %s"
                params.append(cenro_id)
            
            if penro_id:
                query += " AND u.penro_id = %s"
                params.append(penro_id)
            
            if from_date:
                query += " AND er.report_date >= %s"
                params.append(from_date)
            
            if to_date:
                query += " AND er.report_date <= %s"
                params.append(to_date)
            
            if establishment_type:
                query += " AND LOWER(TRIM(ep.establishment_type)) = LOWER(TRIM(%s))"
                params.append(establishment_type)
            
            if pa_id:
                query += " AND er.pa_id = %s"
                params.append(pa_id)
            
            if establishment_status:
                query += " AND LOWER(TRIM(ep.establishment_status)) = LOWER(TRIM(%s))"
                params.append(establishment_status)
            
            # Hide completed reports (both attested and noted)
            query += " AND NOT (an.attested_by_signature IS NOT NULL AND an.noted_by_signature IS NOT NULL AND TRIM(an.attested_by_signature) != '' AND TRIM(an.noted_by_signature) != '')"
            
            query += " ORDER BY er.report_date DESC, er.created_at DESC;"
            
            cur.execute(query, params)
            
            columns = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                reports.append(dict(zip(columns, row)))
                
    except DatabaseError as e:
        logger.error(f"Error fetching enumerator reports: {e}")
        
    return reports


def get_establishment_types_for_cenro(cenro_id):
    """
    Get list of establishment types for a specific CENRO.
    
    Args:
        cenro_id: The CENRO office ID
    
    Returns:
        List of establishment type strings
    """
    establishment_types = []
    
    try:
        with connection.cursor() as cur:
            query = """
                SELECT DISTINCT ep.establishment_type
                FROM enumerators_report er
                LEFT JOIN users u ON er.enumerator_id = u.id
                LEFT JOIN establishment_profile ep ON er.establishment_id = ep.id
                WHERE u.cenro_id = %s
                AND ep.establishment_type IS NOT NULL
                ORDER BY ep.establishment_type;
            """
            
            cur.execute(query, [cenro_id])
            
            for row in cur.fetchall():
                if row[0]:
                    establishment_types.append(row[0])
                
    except DatabaseError as e:
        logger.error(f"Error fetching establishment types: {e}")
        
    return establishment_types


def get_protected_areas_for_cenro(cenro_id):
    """
    Get list of all protected areas from Supabase.
    
    Args:
        cenro_id: The CENRO office ID (not used, kept for compatibility)
    
    Returns:
        List of dictionaries with id and name
    """
    protected_areas = []
    
    try:
        # Fetch all PA details from Supabase
        result = supabase.table('protected_areas').select('id, name').order('name').execute()
        protected_areas = result.data if result.data else []
                
    except Exception as e:
        logger.error(f"Error fetching protected areas: {e}")
        
    return protected_areas


def get_report_details(report_id, cenro_id=None):
    """
    Get detailed information about a specific enumerator report.
    
    Args:
        report_id: The report ID
        cenro_id: Optional CENRO ID to verify access
    
    Returns:
        Dictionary with complete report details or None if not found
    """
    try:
        with connection.cursor() as cur:
            # Select all enumerators_report columns and relevant joined fields. Using er.* makes it easier
            # to return every report column even if NULL, satisfying the requirement to "get all the form".
            query = """
                SELECT
                    er.*, 
                    u.first_name || ' ' || u.last_name AS enumerator_full_name,
                    u.cenro_id,
                    ep.establishment_type,
                    ep.establishment_status,
                    ep.description,
                    
                    ep.lot_status,
                    ep.land_classification,
                    ep.title_no,
                    ep.lot_no,
                    ep.lot_owner,
                    ep.area_covered,
                    ep.pa_zone,
                    ep.within_easement,
                    ep.tax_declaration_no,
                    ep.mayor_permit_no,
                    ep.mayor_permit_issued,
                    ep.mayor_permit_exp,
                    ep.business_permit_no,
                    ep.business_permit_issued,
                    ep.business_permit_exp,
                    ep.building_permit_no,
                    ep.building_permit_issued,
                    ep.building_permit_exp,
                    ep.pamb_resolution_no,
                    ep.pamb_date_issued,
                    ep.sapa_no,
                    ep.sapa_date_issued,
                    ep.pacbrma_no,
                    ep.pacbrma_date_issued,
                    ep.ecc_no,
                    ep.ecc_date_issued,
                    ep.discharge_permit_no,
                    ep.discharge_date_issued,
                    ep.pto_no,
                    ep.pto_date_issued,
                    ep.other_emb,
                    gti.image AS geo_image_url,
                    gti.latitude AS geo_latitude,
                    gti.longitude AS geo_longitude,
                    gti.location AS geo_location,
                    gti.captured_at AS geo_captured_at,
                    an.attested_by_name,
                    an.attested_by_position,
                    an.attested_by_signature,
                    an.noted_by_name,
                    an.noted_by_position,
                    an.noted_by_signature
                FROM enumerators_report er
                LEFT JOIN users u ON er.enumerator_id = u.id
                LEFT JOIN establishment_profile ep ON er.establishment_id = ep.id
                LEFT JOIN geo_tagged_images gti ON er.geo_tagged_image_id = gti.id
                LEFT JOIN attestation_notations an ON er.attestation_id = an.id
                WHERE er.id = %s
            """

            params = [report_id]

            if cenro_id:
                query += " AND u.cenro_id = %s"
                params.append(cenro_id)

            cur.execute(query, params)
            row = cur.fetchone()

            if not row:
                return None

            # Build dictionary using cursor description so every column from er.* is present
            columns = [desc[0] for desc in cur.description]
            data = dict(zip(columns, row))

            # If proponent_name is missing, try plausible fallbacks in order:
            # 1) If report links to a leased property profile (profile_id), use its proponent_name
            # 2) If report has proponent_id, fetch from proponents table
            if (not data.get('proponent_name') or str(data.get('proponent_name')).strip() == ''):
                # Try leased property profile (common in this schema)
                profile_id = data.get('profile_id') or data.get('profile')
                if profile_id:
                    try:
                        cur.execute("SELECT proponent_name FROM leasedpropertyprofile WHERE id = %s;", [profile_id])
                        p_row = cur.fetchone()
                        if p_row and p_row[0]:
                            data['proponent_name'] = p_row[0]
                    except Exception:
                        # ignore lookup errors and continue to next fallback
                        pass

                # Fallback: try proponents table if still missing
                if (not data.get('proponent_name') or str(data.get('proponent_name')).strip() == '') and data.get('proponent_id'):
                    try:
                        cur.execute("SELECT name FROM proponents WHERE id = %s;", [data.get('proponent_id')])
                        p_row = cur.fetchone()
                        if p_row and p_row[0]:
                            data['proponent_name'] = p_row[0]
                    except Exception:
                        # ignore lookup errors - leave proponent_name as-is
                        pass

            # Build permits array using keys that may be present from ep.*
            permits = []
            if data.get('mayor_permit_no') or data.get('mayor_permit_issued') or data.get('mayor_permit_exp'):
                permits.append({
                    'name': "Mayor's Permit",
                    'number': data.get('mayor_permit_no'),
                    'issued': data.get('mayor_permit_issued').isoformat() if data.get('mayor_permit_issued') else None,
                    'expiry': data.get('mayor_permit_exp').isoformat() if data.get('mayor_permit_exp') else None
                })

            if data.get('business_permit_no') or data.get('business_permit_issued') or data.get('business_permit_exp'):
                permits.append({
                    'name': 'Business Permit',
                    'number': data.get('business_permit_no'),
                    'issued': data.get('business_permit_issued').isoformat() if data.get('business_permit_issued') else None,
                    'expiry': data.get('business_permit_exp').isoformat() if data.get('business_permit_exp') else None
                })

            if data.get('building_permit_no') or data.get('building_permit_issued') or data.get('building_permit_exp'):
                permits.append({
                    'name': 'Building Permit',
                    'number': data.get('building_permit_no'),
                    'issued': data.get('building_permit_issued').isoformat() if data.get('building_permit_issued') else None,
                    'expiry': data.get('building_permit_exp').isoformat() if data.get('building_permit_exp') else None
                })

            if data.get('pamb_resolution_no') or data.get('pamb_date_issued'):
                permits.append({
                    'name': 'PAMB Resolution',
                    'number': data.get('pamb_resolution_no'),
                    'issued': data.get('pamb_date_issued').isoformat() if data.get('pamb_date_issued') else None,
                    'expiry': None
                })

            if data.get('sapa_no') or data.get('sapa_date_issued'):
                permits.append({
                    'name': 'SAPA',
                    'number': data.get('sapa_no'),
                    'issued': data.get('sapa_date_issued').isoformat() if data.get('sapa_date_issued') else None,
                    'expiry': None
                })

            if data.get('pacbrma_no') or data.get('pacbrma_date_issued'):
                permits.append({
                    'name': 'PACBRMA',
                    'number': data.get('pacbrma_no'),
                    'issued': data.get('pacbrma_date_issued').isoformat() if data.get('pacbrma_date_issued') else None,
                    'expiry': None
                })

            if data.get('ecc_no') or data.get('ecc_date_issued'):
                permits.append({
                    'name': 'Environmental Compliance Certificate (ECC)',
                    'number': data.get('ecc_no'),
                    'issued': data.get('ecc_date_issued').isoformat() if data.get('ecc_date_issued') else None,
                    'expiry': None
                })

            if data.get('discharge_permit_no') or data.get('discharge_date_issued'):
                permits.append({
                    'name': 'Discharge Permit',
                    'number': data.get('discharge_permit_no'),
                    'issued': data.get('discharge_date_issued').isoformat() if data.get('discharge_date_issued') else None,
                    'expiry': None
                })

            if data.get('pto_no') or data.get('pto_date_issued'):
                permits.append({
                    'name': 'Permit to Operate (PTO)',
                    'number': data.get('pto_no'),
                    'issued': data.get('pto_date_issued').isoformat() if data.get('pto_date_issued') else None,
                    'expiry': None
                })

            # Helper to build full URL for signatures stored as relative paths
            def build_signature_url(sig_path):
                if not sig_path:
                    return None
                # If already absolute URL, return as-is
                if sig_path.startswith('http://') or sig_path.startswith('https://') or sig_path.startswith('data:'):
                    return sig_path
                # Build Supabase public URL
                bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
                return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{sig_path}"

            # Prepare response ensuring key names expected by frontend are present
            report_details = {
                # fields coming from er.* - ensure presence even if None
                'id': data.get('id'),
                'establishment_id': data.get('establishment_id'),
                'establishment_name': data.get('establishment_name'),
                'proponent_id': data.get('proponent_id') or data.get('proponent_id'),
                'proponent_name': data.get('proponent_name'),
                'pa_id': data.get('pa_id'),
                'pa_name': data.get('pa_name'),
                'enumerator_id': data.get('enumerator_id'),
                'enumerator_name': data.get('enumerator_name') or data.get('enumerator_full_name'),
                'geo_tagged_image_id': data.get('geo_tagged_image_id'),
                'report_date': data.get('report_date').isoformat() if data.get('report_date') else None,
                'enumerator_signature_date': data.get('enumerator_signature_date').isoformat() if data.get('enumerator_signature_date') else None,
                'informant_signature_date': data.get('informant_signature_date').isoformat() if data.get('informant_signature_date') else None,
                'enumerator_signature': build_signature_url(data.get('enumerator_signature')),
                'informant_signature': build_signature_url(data.get('informant_signature')),
                'informant_name': data.get('informant_name'),
                'remarks': data.get('remarks'),
                'created_at': data.get('created_at').isoformat() if data.get('created_at') else None,
                'updated_at': data.get('updated_at').isoformat() if data.get('updated_at') else None,

                # establishment_profile derived fields
                'establishment_type': data.get('establishment_type'),
                'establishment_status': data.get('establishment_status'),
                'description': data.get('description'),
                'lot_status': data.get('lot_status'),
                'land_classification': data.get('land_classification'),
                'title_no': data.get('title_no'),
                'lot_no': data.get('lot_no'),
                'lot_owner': data.get('lot_owner'),
                'area_covered': data.get('area_covered'),
                'pa_zone': data.get('pa_zone'),
                'within_easement': data.get('within_easement'),
                'tax_declaration_no': data.get('tax_declaration_no'),

                'permits': permits,
                'other_emb': data.get('other_emb'),

                # geo image fields
                'geo_image_url': data.get('geo_image_url'),
                'latitude': data.get('geo_latitude') or data.get('latitude'),
                'longitude': data.get('geo_longitude') or data.get('longitude'),
                'location': data.get('geo_location') or data.get('location'),
                'geo_captured_at': data.get('geo_captured_at').isoformat() if data.get('geo_captured_at') else None,

                # attestation fields - build full URLs
                'attestation_id': data.get('attestation_id'),
                'attested_by_name': data.get('attested_by_name'),
                'attested_by_position': data.get('attested_by_position'),
                'attested_by_signature': build_signature_url(data.get('attested_by_signature')),
                'noted_by_name': data.get('noted_by_name'),
                'noted_by_position': data.get('noted_by_position'),
                'noted_by_signature': build_signature_url(data.get('noted_by_signature'))
            }

            # Fetch images for this report
            report_details['images'] = get_report_images(report_id)

            return report_details
                
    except DatabaseError as e:
        logger.error(f"Error fetching report details: {e}")
        return None
    

def get_report_images(report_id):
    """
    Fetch images related to a report from Supabase storage/join table.

    Returns a list of dicts with keys: id, image, latitude, longitude, location,
    captured_at, qr_code, is_primary, image_sequence
    """
    images = []
    if not report_id:
        return images

    try:
        resp = supabase.table("reported_images") \
            .select("image_id,is_primary,image_sequence,geo_tagged_images(id,image,latitude,longitude,location,captured_at,qr_code)") \
            .eq("report_id", report_id) \
            .eq("report_type", "enumerator") \
            .execute()

        reported = getattr(resp, 'data', None) or []

        # Some Supabase client versions return unsorted results; sort by image_sequence if available
        try:
            reported.sort(key=lambda x: (x.get('image_sequence') is None, x.get('image_sequence') or 0))
        except Exception:
            pass

        for ri in reported:
            geo = ri.get('geo_tagged_images')
            if not geo:
                continue
            images.append({
                'id': geo.get('id'),
                'image': geo.get('image'),
                'latitude': geo.get('latitude'),
                'longitude': geo.get('longitude'),
                'location': geo.get('location'),
                'captured_at': geo.get('captured_at'),
                'qr_code': geo.get('qr_code'),
                'is_primary': ri.get('is_primary', False),
                'image_sequence': ri.get('image_sequence', None),
            })

    except Exception as e:
        logger.exception(f"Error fetching report images for report_id=%s: %s", report_id, e)

    return images


def save_notation(report_id, noted_by_name, noted_by_position, signature_dataurl, current_user_id=None):
    """Save notation record and upload signature image to Supabase storage.

    Returns (True, public_url, added_to_history) on success, or (False, error_message, False) on failure.
    """
    try:
        if not report_id:
            return False, 'Invalid report id', False

        if not signature_dataurl or not signature_dataurl.startswith('data:'):
            return False, 'Invalid signature data', False

        header, encoded = signature_dataurl.split(',', 1)
        try:
            data = base64.b64decode(encoded)
        except Exception as e:
            return False, f'Decoding error: {e}', False

        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        filename = f"attestation/report_{report_id}_noted_{int(time.time())}.png"

        try:
            from_call = supabase.storage.from_(bucket)
            upload_resp = from_call.upload(filename, data, {"content-type": "image/png"})
            signature_url_to_store = filename
        except Exception as e:
            logger.exception('Supabase upload failed: %s', e)
            return False, f'Upload failed: {str(e)}', False

        added_to_history = False
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("SELECT attestation_id FROM enumerators_report WHERE id = %s;", [report_id])
                row = cur.fetchone()
                existing_id = row[0] if row else None

                if existing_id:
                    cur.execute(
                        """
                        UPDATE attestation_notations
                        SET noted_by_name = %s,
                            noted_by_position = %s,
                            noted_by_signature = %s
                        WHERE id = %s
                        RETURNING id;
                        """,
                        [noted_by_name, noted_by_position, signature_url_to_store, existing_id]
                    )
                    cur.fetchone()
                else:
                    cur.execute(
                        """
                        INSERT INTO attestation_notations (noted_by_name, noted_by_position, noted_by_signature)
                        VALUES (%s, %s, %s)
                        RETURNING id;
                        """,
                        [noted_by_name, noted_by_position, signature_url_to_store]
                    )
                    new_id = cur.fetchone()[0]
                    cur.execute("UPDATE enumerators_report SET attestation_id = %s WHERE id = %s;", [new_id, report_id])

                # Check if both attested and noted are complete
                added_to_history = _check_and_add_to_history(report_id, current_user_id)

        full_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{signature_url_to_store}"
        return True, full_url, added_to_history

    except DatabaseError as e:
        logger.exception('DB error saving notation: %s', e)
        return False, str(e), False
    except Exception as e:
        logger.exception('Unexpected error saving notation: %s', e)
        return False, str(e), False


def save_attestation(report_id, attested_by_name, attested_by_position, signature_dataurl, current_user_id=None):
    """Save attestation record and upload signature image to Supabase storage.

    Returns (True, public_url, added_to_history) on success, or (False, error_message, False) on failure.
    """
    try:
        if not report_id:
            return False, 'Invalid report id', False

        # Decode data URL
        if not signature_dataurl or not signature_dataurl.startswith('data:'):
            return False, 'Invalid signature data', False

        header, encoded = signature_dataurl.split(',', 1)
        try:
            data = base64.b64decode(encoded)
        except Exception as e:
            return False, f'Decoding error: {e}', False

        # Prepare file path in attestation folder
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        filename = f"attestation/report_{report_id}_attested_{int(time.time())}.png"

        # Upload to Supabase storage
        try:
            from_call = supabase.storage.from_(bucket)
            upload_resp = from_call.upload(filename, data, {"content-type": "image/png"})
            signature_url_to_store = filename
        except Exception as e:
            logger.exception('Supabase upload failed: %s', e)
            return False, f'Upload failed: {str(e)}', False

        # Insert or update attestation_notations and link to enumerators_report
        added_to_history = False
        with transaction.atomic():
            with connection.cursor() as cur:
                # Check existing attestation_id
                cur.execute("SELECT attestation_id FROM enumerators_report WHERE id = %s;", [report_id])
                row = cur.fetchone()
                existing_id = row[0] if row else None

                if existing_id:
                    cur.execute(
                        """
                        UPDATE attestation_notations
                        SET attested_by_name = %s,
                            attested_by_position = %s,
                            attested_by_signature = %s
                        WHERE id = %s
                        RETURNING id;
                        """,
                        [attested_by_name, attested_by_position, signature_url_to_store, existing_id]
                    )
                    cur.fetchone()
                else:
                    cur.execute(
                        """
                        INSERT INTO attestation_notations (attested_by_name, attested_by_position, attested_by_signature)
                        VALUES (%s, %s, %s)
                        RETURNING id;
                        """,
                        [attested_by_name, attested_by_position, signature_url_to_store]
                    )
                    new_id = cur.fetchone()[0]
                    cur.execute("UPDATE enumerators_report SET attestation_id = %s WHERE id = %s;", [new_id, report_id])

                # Check if both attested and noted are complete
                added_to_history = _check_and_add_to_history(report_id, current_user_id)

        # Return full URL for response
        full_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{signature_url_to_store}"
        return True, full_url, added_to_history

    except DatabaseError as e:
        logger.exception('DB error saving attestation: %s', e)
        return False, str(e), False
    except Exception as e:
        logger.exception('Unexpected error saving attestation: %s', e)
        return False, str(e), False




def _check_and_add_to_history(report_id, updated_by):
    """Check if report is fully attested and noted, then add to establishment history.
    Returns True if added to history, False otherwise.
    """
    try:
        with connection.cursor() as cur:
            # Check if both attested and noted signatures exist and get attestation_id
            cur.execute("""
                SELECT an.attested_by_signature, an.noted_by_signature, er.establishment_id, er.attestation_id
                FROM enumerators_report er
                LEFT JOIN attestation_notations an ON er.attestation_id = an.id
                WHERE er.id = %s;
            """, [report_id])
            row = cur.fetchone()
            
            if not row:
                return False
            
            attested_sig, noted_sig, establishment_id, attestation_id = row
            
            # Only proceed if both signatures exist and are not empty
            if not attested_sig or not noted_sig or not establishment_id:
                return False
            
            if not attested_sig.strip() or not noted_sig.strip():
                return False
            
            # Check if already added to history for this report
            cur.execute("""
                SELECT COUNT(*) FROM establishment_history
                WHERE establishment_id = %s 
                AND change_reason LIKE %s;
            """, [establishment_id, f'%Report {report_id}%'])
            
            if cur.fetchone()[0] > 0:
                return False  # Already added
            
            # Get current establishment profile data (only essential fields, no signatures)
            cur.execute("""
                SELECT establishment_name, lot_status, land_classification, title_no, 
                       tax_declaration_no, lot_no, lot_owner, area_covered, pa_zone, 
                       within_easement, establishment_status, establishment_type, description,
                       mayor_permit_no, mayor_permit_issued, mayor_permit_exp,
                       business_permit_no, business_permit_issued, business_permit_exp,
                       building_permit_no, building_permit_issued, building_permit_exp,
                       pamb_resolution_no, pamb_date_issued, sapa_no, sapa_date_issued,
                       pacbrma_no, pacbrma_date_issued, ecc_no, ecc_date_issued,
                       discharge_permit_no, discharge_date_issued, pto_no, pto_date_issued,
                       other_emb
                FROM establishment_profile
                WHERE id = %s;
            """, [establishment_id])
            profile_row = cur.fetchone()
            
            if not profile_row:
                return False
            
            # Get next version number
            cur.execute("""
                SELECT COALESCE(MAX(version), 0) + 1
                FROM establishment_history
                WHERE establishment_id = %s;
            """, [establishment_id])
            next_version = cur.fetchone()[0]
            
            # Triggers handle this automatically - skip Python insert
            return True
            
            logger.info(f'Added establishment {establishment_id} to history (version {next_version}) from report {report_id}')
            return True
            
    except Exception as e:
        logger.exception(f'Error adding to establishment history: {e}')
        return False


def get_activity_logs():
    """Fetch activity logs via DB function `get_activity_logs()` using Django connection."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT * FROM get_activity_logs();")
            logs = cur.fetchall()

            log_list = []
            for row in logs:
                log_list.append({
                    "task": row[0],
                    "user_id": row[1],
                    "name": row[2],
                    "timestamp": row[3],
                })

            return log_list
    except Exception as e:
        logger.exception("Error fetching activity logs: %s", e)
        return []


# =========================
# PROTECTED AREAS MANAGEMENT
# =========================
def add_protected_area(name, file_obj, jurisdiction_level=None, region_id=None, penro_id=None, cenro_id=None):
    """Add protected area with file upload to Supabase and jurisdiction assignment."""
    try:
        # Validate jurisdiction assignment
        if jurisdiction_level not in ['region', 'penro', 'cenro']:
            return False, 'Invalid jurisdiction level. Must be region, penro, or cenro.'
        
        # Validate jurisdiction IDs based on level
        if jurisdiction_level == 'region':
            if not region_id:
                return False, 'Region ID is required for region-level jurisdiction.'
            penro_id = cenro_id = None
        elif jurisdiction_level == 'penro':
            if not penro_id:
                return False, 'PENRO ID is required for PENRO-level jurisdiction.'
            region_id = cenro_id = None
        elif jurisdiction_level == 'cenro':
            if not cenro_id:
                return False, 'CENRO ID is required for CENRO-level jurisdiction.'
            region_id = penro_id = None
        
        # Determine file type
        file_name = file_obj.name.lower()
        if file_name.endswith('.kml'):
            file_type = 'kml'
        elif file_name.endswith('.zip'):
            file_type = 'shp'
        else:
            return False, 'Invalid file type. Upload KML or ZIP (containing shapefile).'

        # Upload file to Supabase storage
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        file_path = f"protected-areas/{int(time.time())}_{file_obj.name}"
        
        try:
            file_data = file_obj.read()
            from_call = supabase.storage.from_(bucket)
            upload_resp = from_call.upload(file_path, file_data, {"content-type": file_obj.content_type or "application/octet-stream"})
        except Exception as e:
            logger.exception('Supabase file upload failed: %s', e)
            return False, f'File upload failed: {str(e)}'

        # Insert into Supabase table with jurisdiction
        try:
            result = supabase.table('protected_areas').insert({
                'name': name,
                'file_type': file_type,
                'file_path': file_path,
                'jurisdiction_level': jurisdiction_level,
                'region_id': region_id,
                'penro_id': penro_id,
                'cenro_id': cenro_id
            }).execute()
            
            return True, 'Protected area added successfully'
        except Exception as e:
            logger.exception('Supabase insert failed: %s', e)
            return False, f'Database insert failed: {str(e)}'

    except Exception as e:
        logger.exception('Error adding protected area: %s', e)
        return False, str(e)


def get_protected_areas():
    """Fetch all protected areas from Supabase."""
    try:
        result = supabase.table('protected_areas').select('*').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.exception('Error fetching protected areas: %s', e)
        return []


def delete_protected_area(pa_id):
    """Delete protected area and its file from Supabase."""
    try:
        # Get file path before deleting
        result = supabase.table('protected_areas').select('file_path').eq('id', pa_id).execute()
        
        if result.data and len(result.data) > 0:
            file_path = result.data[0].get('file_path')
            
            # Delete file from storage
            if file_path:
                try:
                    bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
                    supabase.storage.from_(bucket).remove([file_path])
                except Exception as e:
                    logger.warning('Failed to delete file from storage: %s', e)
            
            # Delete from table
            supabase.table('protected_areas').delete().eq('id', pa_id).execute()
            return True, 'Protected area deleted successfully'
        else:
            return False, 'Protected area not found'
            
    except Exception as e:
        logger.exception('Error deleting protected area: %s', e)
        return False, str(e)


def get_reports_context(request, submitter_role):
    """Get reports and context for a specific role."""
    from datetime import datetime
    
    from_date_str = request.GET.get('from_date', None)
    to_date_str = request.GET.get('to_date', None)
    establishment_type = request.GET.get('establishment_type', None)
    pa_id_str = request.GET.get('pa_id', None)
    establishment_status = request.GET.get('establishment_status', None)
    
    from_date = None
    to_date = None
    
    if from_date_str:
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            from_date = None
    
    if to_date_str:
        try:
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            to_date = None
    
    pa_id = None
    if pa_id_str:
        try:
            pa_id = int(pa_id_str)
        except (ValueError, TypeError):
            pa_id = None
    
    reports = get_enumerator_reports(
        submitter_role=submitter_role,
        from_date=from_date,
        to_date=to_date,
        establishment_type=establishment_type,
        pa_id=pa_id,
        establishment_status=establishment_status
    )
    
    office_id = request.session.get('region_id') or request.session.get('penro_id') or request.session.get('cenro_id')
    establishment_types = get_establishment_types_for_cenro(office_id) if office_id else []
    protected_areas = get_protected_areas_for_cenro(office_id) if office_id else []
    
    return {
        'reports': reports,
        'from_date': from_date,
        'to_date': to_date,
        'establishment_type': establishment_type,
        'establishment_types': establishment_types,
        'pa_id': pa_id,
        'protected_areas': protected_areas,
        'establishment_status': establishment_status,
        'supabase_url': os.getenv('SUPABASE_URL'),
        'supabase_bucket': os.getenv('SUPABASE_BUCKET', 'images'),
    }

def get_all_users(current_role=None, penro_id=None):
    """Fetch users from database filtered by current user's role.
    - Admin: All users except Super Admin
    - PENRO: PENRO and CENRO users only within their jurisdiction
    - CENRO: CENRO users only
    """
    try:
        with connection.cursor() as cur:
            query = """
                SELECT u.id, u.first_name, u.last_name, u.role, u.username, u.email,
                       COALESCE(r.name, p.name, c.name, 'N/A') as office,
                       r.name as region_name, p.name as penro_name, c.name as cenro_name
                FROM users u
                LEFT JOIN regions r ON u.region_id = r.id
                LEFT JOIN penros p ON u.penro_id = p.id
                LEFT JOIN cenros c ON u.cenro_id = c.id
                WHERE 1=1
            """
            
            params = []
            
            if current_role == 'admin':
                query += " AND LOWER(u.role) != 'super admin'"
            elif current_role == 'penro':
                query += " AND LOWER(u.role) IN ('penro', 'cenro')"
                if penro_id:
                    query += " AND u.penro_id = %s"
                    params.append(penro_id)
            elif current_role == 'cenro':
                query += " AND LOWER(u.role) = 'cenro'"
            
            query += " ORDER BY u.id DESC;"
            
            cur.execute(query, params)
            
            users = []
            for row in cur.fetchall():
                users.append({
                    'user_id': row[0],
                    'first_name': row[1],
                    'last_name': row[2],
                    'role': row[3],
                    'username': row[4],
                    'email': row[5],
                    'office': row[6],
                    'region_name': row[7] or '—',
                    'penro_name': row[8] or '—',
                    'cenro_name': row[9] or '—'
                })
            return users
    except Exception as e:
        logger.exception('Error fetching users: %s', e)
        return []

def export_reports(reports, format_type):
    """Export detailed reports to PDF, Word, or Excel format"""
    from io import BytesIO
    from django.http import HttpResponse, JsonResponse
    
    # Fetch detailed data for each report
    detailed_reports = []
    for report in reports:
        detail = get_report_details(report.get('id'))
        if detail:
            detailed_reports.append(detail)
    
    if format_type == 'excel':
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment
            from openpyxl.drawing.image import Image as XLImage
        except ImportError:
            return JsonResponse({'error': 'Excel export requires openpyxl. Install with: pip install openpyxl'}, status=500)
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Detailed Reports'
        
        for detail in detailed_reports:
            ws.append(['ENUMERATOR REPORT #' + str(detail.get('id', ''))])
            ws.append([])
            ws.append(['Protected Area:', detail.get('pa_name', '')])
            ws.append(['Report Date:', str(detail.get('report_date', ''))])
            ws.append(['Created At:', str(detail.get('created_at', ''))])
            ws.append([])
            ws.append(['Establishment Name:', detail.get('establishment_name', '')])
            ws.append(['Proponent/Owner:', detail.get('proponent_name', '')])
            ws.append(['Contact Number:', detail.get('contact_number', '')])
            ws.append(['Location:', detail.get('location', '')])
            ws.append([])
            ws.append(['PROPERTY DETAILS'])
            ws.append(['Lot Status:', detail.get('lot_status', '')])
            ws.append(['Land Classification:', detail.get('land_classification', '')])
            ws.append(['Title No:', str(detail.get('title_no', ''))])
            ws.append(['Lot No:', str(detail.get('lot_no', ''))])
            ws.append(['Lot Owner:', detail.get('lot_owner', '')])
            ws.append(['Tax Declaration No:', detail.get('tax_declaration_no', '')])
            ws.append([])
            ws.append(['COORDINATES'])
            ws.append(['Latitude:', str(detail.get('latitude', ''))])
            ws.append(['Longitude:', str(detail.get('longitude', ''))])
            ws.append([])
            ws.append(['Area Covered (sq.m):', str(detail.get('area_covered', ''))])
            ws.append(['PA Zone:', detail.get('pa_zone', '')])
            ws.append(['Within Easement:', 'Yes' if detail.get('within_easement') else 'No'])
            ws.append([])
            ws.append(['ESTABLISHMENT DETAILS'])
            ws.append(['Type:', detail.get('establishment_type', '')])
            ws.append(['Status:', detail.get('establishment_status', '')])
            ws.append(['Description:', detail.get('description', '')])
            ws.append([])
            ws.append(['PERMITS FROM LGUs:'])
            lgu_permits = [p for p in detail.get('permits', []) if any(x in p.get('name', '') for x in ['Mayor', 'Business', 'Building'])]
            for permit in lgu_permits:
                ws.append([permit.get('name', ''), permit.get('number', ''), permit.get('issued', ''), permit.get('expiry', '')])
            ws.append([])
            ws.append(['PERMITS FROM DENR/EMB:'])
            denr_permits = [p for p in detail.get('permits', []) if not any(x in p.get('name', '') for x in ['Mayor', 'Business', 'Building'])]
            for permit in denr_permits:
                ws.append([permit.get('name', ''), permit.get('number', ''), permit.get('issued', ''), permit.get('expiry', '')])
            ws.append([])
            ws.append(['Remarks:', detail.get('remarks', '')])
            ws.append([])
            ws.append(['SIGNATURES'])
            ws.append(['Enumerator:', detail.get('enumerator_name', ''), 'Date:', str(detail.get('enumerator_signature_date', ''))])
            ws.append(['Informant:', detail.get('informant_name', ''), 'Date:', str(detail.get('informant_signature_date', ''))])
            ws.append([])
            ws.append(['ATTESTATION'])
            ws.append(['Attested by:', detail.get('attested_by_name', ''), detail.get('attested_by_position', '')])
            ws.append(['Noted by:', detail.get('noted_by_name', ''), detail.get('noted_by_position', '')])
            ws.append([])
            ws.append(['GEO-TAGGED IMAGES'])
            current_row = ws.max_row + 1
            images = detail.get('images', [])
            for idx, img in enumerate(images, 1):
                try:
                    import requests  # type: ignore
                    from io import BytesIO as ImgBytesIO
                    img_url = img.get('image', '') or img.get('image_url', '') or img.get('image_path', '')
                    logger.info(f"Excel: Processing image {idx}: {img_url}")
                    if img_url:
                        if not img_url.startswith('http'):
                            supabase_url = os.getenv('SUPABASE_URL', '')
                            bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
                            img_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{img_url.lstrip('/')}"
                        logger.info(f"Excel: Fetching from: {img_url}")
                        response = requests.get(img_url, timeout=15)
                        logger.info(f"Excel: Response status: {response.status_code}")
                        if response.status_code == 200:
                            img_buffer = ImgBytesIO(response.content)
                            xl_img = XLImage(img_buffer)
                            xl_img.width = 300
                            xl_img.height = 225
                            ws.add_image(xl_img, f'A{current_row}')
                            ws.row_dimensions[current_row].height = 170
                            ws.append([])
                            current_row = ws.max_row
                            ws.append([f'Image {idx} - Location:', img.get('location', '') or img.get('location_name', '')])
                            ws.append(['Captured:', img.get('captured_at', '')])
                            ws.append([])
                            current_row = ws.max_row + 1
                        else:
                            ws.append([f'Image {idx} (HTTP {response.status_code}):', img_url])
                            ws.append(['Location:', img.get('location', '')])
                            current_row = ws.max_row + 1
                except Exception as e:
                    logger.exception(f"Excel: Error embedding image {idx}: {e}")
                    ws.append([f'Image {idx} URL:', img.get('image', '')])
                    ws.append(['Location:', img.get('location', '')])
                    ws.append(['Error:', str(e)])
                    ws.append([])
                    current_row = ws.max_row + 1
            ws.append([])
            ws.append(['='*50])
            ws.append([])
        
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="detailed_reports.xlsx"'
        return response
    
    elif format_type == 'word':
        try:
            from docx import Document
            from docx.shared import Pt, Inches
        except ImportError:
            return JsonResponse({'error': 'Word export requires python-docx. Install with: pip install python-docx'}, status=500)
        
        doc = Document()
        doc.add_heading('Enumerator Reports - Detailed', 0)
        
        for detail in detailed_reports:
            doc.add_heading(f"ENUMERATOR REPORT #{detail.get('id', '')}", level=1)
            doc.add_paragraph(f"Protected Area: {detail.get('pa_name', '')}")
            doc.add_paragraph(f"Report Date: {detail.get('report_date', '')}")
            doc.add_paragraph(f"Created At: {detail.get('created_at', '')}")
            
            doc.add_heading('Basic Information', level=2)
            doc.add_paragraph(f"Establishment: {detail.get('establishment_name', '')}")
            doc.add_paragraph(f"Proponent/Owner: {detail.get('proponent_name', '')}")
            doc.add_paragraph(f"Contact Number: {detail.get('contact_number', '')}")
            doc.add_paragraph(f"Location: {detail.get('location', '')}")
            
            doc.add_heading('Property Details', level=2)
            doc.add_paragraph(f"Lot Status: {detail.get('lot_status', '')}")
            doc.add_paragraph(f"Land Classification: {detail.get('land_classification', '')}")
            doc.add_paragraph(f"Title No: {detail.get('title_no', '')}")
            doc.add_paragraph(f"Lot No: {detail.get('lot_no', '')}")
            doc.add_paragraph(f"Lot Owner: {detail.get('lot_owner', '')}")
            doc.add_paragraph(f"Tax Declaration No: {detail.get('tax_declaration_no', '')}")
            
            doc.add_heading('Coordinates', level=2)
            doc.add_paragraph(f"Latitude: {detail.get('latitude', '')}")
            doc.add_paragraph(f"Longitude: {detail.get('longitude', '')}")
            
            doc.add_heading('Area Information', level=2)
            doc.add_paragraph(f"Area Covered (sq.m): {detail.get('area_covered', '')}")
            doc.add_paragraph(f"PA Zone: {detail.get('pa_zone', '')}")
            doc.add_paragraph(f"Within Easement: {'Yes' if detail.get('within_easement') else 'No'}")
            
            doc.add_heading('Establishment Details', level=2)
            doc.add_paragraph(f"Type: {detail.get('establishment_type', '')}")
            doc.add_paragraph(f"Status: {detail.get('establishment_status', '')}")
            doc.add_paragraph(f"Description: {detail.get('description', '')}")
            
            doc.add_heading('Permits from LGUs', level=2)
            lgu_permits = [p for p in detail.get('permits', []) if any(x in p.get('name', '') for x in ['Mayor', 'Business', 'Building'])]
            for permit in lgu_permits:
                doc.add_paragraph(f"{permit.get('name', '')}: {permit.get('number', '')} (Issued: {permit.get('issued', '')}, Expiry: {permit.get('expiry', '')})")
            
            doc.add_heading('Permits from DENR/EMB', level=2)
            denr_permits = [p for p in detail.get('permits', []) if not any(x in p.get('name', '') for x in ['Mayor', 'Business', 'Building'])]
            for permit in denr_permits:
                doc.add_paragraph(f"{permit.get('name', '')}: {permit.get('number', '')} (Issued: {permit.get('issued', '')})")
            
            doc.add_heading('Remarks', level=2)
            doc.add_paragraph(detail.get('remarks', ''))
            
            doc.add_heading('Signatures', level=2)
            doc.add_paragraph(f"Enumerator: {detail.get('enumerator_name', '')} (Date: {detail.get('enumerator_signature_date', '')})")
            doc.add_paragraph(f"Informant: {detail.get('informant_name', '')} (Date: {detail.get('informant_signature_date', '')})")
            
            doc.add_heading('Attestation', level=2)
            doc.add_paragraph(f"Attested by: {detail.get('attested_by_name', '')} - {detail.get('attested_by_position', '')}")
            doc.add_paragraph(f"Noted by: {detail.get('noted_by_name', '')} - {detail.get('noted_by_position', '')}")
            
            doc.add_heading('Geo-Tagged Images', level=2)
            images = detail.get('images', [])
            if not images:
                doc.add_paragraph('No images available')
            for img in images:
                try:
                    import requests  # type: ignore
                    from io import BytesIO as ImgBytesIO
                    img_url = img.get('image', '') or img.get('image_url', '') or img.get('image_path', '')
                    logger.info(f"Processing image: {img_url}")
                    if img_url:
                        if not img_url.startswith('http'):
                            supabase_url = os.getenv('SUPABASE_URL', '')
                            bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
                            img_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{img_url.lstrip('/')}"
                        logger.info(f"Fetching image from: {img_url}")
                        response = requests.get(img_url, timeout=15)
                        logger.info(f"Image response status: {response.status_code}")
                        if response.status_code == 200:
                            doc.add_picture(ImgBytesIO(response.content), width=Inches(4))
                            doc.add_paragraph(f"Location: {img.get('location', '') or img.get('location_name', '')}")
                            doc.add_paragraph(f"Captured: {img.get('captured_at', '')}")
                        else:
                            doc.add_paragraph(f"Image URL: {img_url} (HTTP {response.status_code})")
                            doc.add_paragraph(f"Location: {img.get('location', '')}")
                except Exception as e:
                    logger.exception(f"Error embedding image: {e}")
                    doc.add_paragraph(f"Image: {img.get('image', '')} (Error: {str(e)})")
                    doc.add_paragraph(f"Location: {img.get('location', '')}")
            
            doc.add_page_break()
        
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = 'attachment; filename="detailed_reports.docx"'
        return response
    
    else:  # PDF
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
            from reportlab.lib.units import inch
        except ImportError:
            return JsonResponse({'error': 'PDF export requires reportlab. Install with: pip install reportlab'}, status=500)
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        styles = getSampleStyleSheet()
        
        for detail in detailed_reports:
            elements.append(Paragraph(f"<b>ENUMERATOR REPORT #{detail.get('id', '')}</b>", styles['Title']))
            elements.append(Spacer(1, 0.15*inch))
            
            elements.append(Paragraph(f"<b>Protected Area:</b> {detail.get('pa_name', '')}", styles['Normal']))
            elements.append(Paragraph(f"<b>Report Date:</b> {detail.get('report_date', '')} | <b>Created:</b> {detail.get('created_at', '')}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            elements.append(Paragraph("<b>Basic Information</b>", styles['Heading2']))
            elements.append(Paragraph(f"Establishment: {detail.get('establishment_name', '')}", styles['Normal']))
            elements.append(Paragraph(f"Proponent/Owner: {detail.get('proponent_name', '')}", styles['Normal']))
            elements.append(Paragraph(f"Contact: {detail.get('contact_number', '')}", styles['Normal']))
            elements.append(Paragraph(f"Location: {detail.get('location', '')}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            elements.append(Paragraph("<b>Property Details</b>", styles['Heading2']))
            elements.append(Paragraph(f"Lot Status: {detail.get('lot_status', '')} | Land Class: {detail.get('land_classification', '')}", styles['Normal']))
            elements.append(Paragraph(f"Title No: {detail.get('title_no', '')} | Lot No: {detail.get('lot_no', '')}", styles['Normal']))
            elements.append(Paragraph(f"Lot Owner: {detail.get('lot_owner', '')}", styles['Normal']))
            elements.append(Paragraph(f"Tax Declaration No: {detail.get('tax_declaration_no', '')}", styles['Normal']))
            elements.append(Paragraph(f"Coordinates: {detail.get('latitude', '')}, {detail.get('longitude', '')}", styles['Normal']))
            elements.append(Paragraph(f"Area: {detail.get('area_covered', '')} sq.m | PA Zone: {detail.get('pa_zone', '')} | Easement: {'Yes' if detail.get('within_easement') else 'No'}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            elements.append(Paragraph("<b>Establishment</b>", styles['Heading2']))
            elements.append(Paragraph(f"Type: {detail.get('establishment_type', '')} | Status: {detail.get('establishment_status', '')}", styles['Normal']))
            elements.append(Paragraph(f"Description: {detail.get('description', '')}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            lgu_permits = [p for p in detail.get('permits', []) if any(x in p.get('name', '') for x in ['Mayor', 'Business', 'Building'])]
            if lgu_permits:
                elements.append(Paragraph("<b>LGU Permits</b>", styles['Heading2']))
                permit_data = [['Permit', 'Number', 'Issued', 'Expiry']]
                for permit in lgu_permits:
                    permit_data.append([permit.get('name', '')[:25], permit.get('number', ''), permit.get('issued', ''), permit.get('expiry', '')])
                permit_table = Table(permit_data, colWidths=[2.2*inch, 1.3*inch, 1*inch, 1*inch])
                permit_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 1, colors.black), ('FONTSIZE', (0, 0), (-1, -1), 8)]))
                elements.append(permit_table)
                elements.append(Spacer(1, 0.1*inch))
            
            denr_permits = [p for p in detail.get('permits', []) if not any(x in p.get('name', '') for x in ['Mayor', 'Business', 'Building'])]
            if denr_permits:
                elements.append(Paragraph("<b>DENR/EMB Permits</b>", styles['Heading2']))
                permit_data = [['Permit', 'Number', 'Issued']]
                for permit in denr_permits:
                    permit_data.append([permit.get('name', '')[:30], permit.get('number', ''), permit.get('issued', '')])
                permit_table = Table(permit_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
                permit_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 1, colors.black), ('FONTSIZE', (0, 0), (-1, -1), 8)]))
                elements.append(permit_table)
                elements.append(Spacer(1, 0.1*inch))
            
            elements.append(Paragraph(f"<b>Remarks:</b> {detail.get('remarks', '')}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            
            elements.append(Paragraph("<b>Signatures</b>", styles['Heading2']))
            elements.append(Paragraph(f"Enumerator: {detail.get('enumerator_name', '')} ({detail.get('enumerator_signature_date', '')})", styles['Normal']))
            elements.append(Paragraph(f"Informant: {detail.get('informant_name', '')} ({detail.get('informant_signature_date', '')})", styles['Normal']))
            elements.append(Paragraph(f"Attested by: {detail.get('attested_by_name', '')} - {detail.get('attested_by_position', '')}", styles['Normal']))
            elements.append(Paragraph(f"Noted by: {detail.get('noted_by_name', '')} - {detail.get('noted_by_position', '')}", styles['Normal']))
            
            images = detail.get('images', [])
            if images:
                elements.append(Spacer(1, 0.1*inch))
                elements.append(Paragraph("<b>Geo-Tagged Images</b>", styles['Heading2']))
                for img in images:
                    try:
                        import requests  # type: ignore
                        from reportlab.platypus import Image as RLImage
                        from io import BytesIO as ImgBytesIO
                        img_url = img.get('image', '') or img.get('image_url', '') or img.get('image_path', '')
                        logger.info(f"PDF: Processing image: {img_url}")
                        if img_url:
                            if not img_url.startswith('http'):
                                supabase_url = os.getenv('SUPABASE_URL', '')
                                bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
                                img_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{img_url.lstrip('/')}"
                            logger.info(f"PDF: Fetching from: {img_url}")
                            response = requests.get(img_url, timeout=15)
                            logger.info(f"PDF: Response status: {response.status_code}")
                            if response.status_code == 200:
                                img_buffer = ImgBytesIO(response.content)
                                rl_img = RLImage(img_buffer, width=4*inch, height=3*inch)
                                elements.append(rl_img)
                                elements.append(Paragraph(f"Location: {img.get('location', '') or img.get('location_name', '')}", styles['Normal']))
                                elements.append(Paragraph(f"Captured: {img.get('captured_at', '')}", styles['Normal']))
                                elements.append(Spacer(1, 0.1*inch))
                            else:
                                elements.append(Paragraph(f"Image URL: {img_url} (HTTP {response.status_code})", styles['Normal']))
                    except Exception as e:
                        logger.exception(f"PDF: Error embedding image: {e}")
                        elements.append(Paragraph(f"Image: {img.get('image', '')} (Error: {str(e)})", styles['Normal']))
                        elements.append(Paragraph(f"Location: {img.get('location', '')}", styles['Normal']))
            
            elements.append(PageBreak())
        
        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="detailed_reports.pdf"'
        return response


def get_dashboard_stats(role, cenro_id=None, penro_id=None, region_id=None):
    """Get dashboard statistics based on user role."""
    stats = {}
    
    try:
        with connection.cursor() as cur:
            if role == 'cenro':
                cur.execute("SELECT COUNT(*) FROM enumerators_report")
                stats['total_reports'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(DISTINCT establishment_id) FROM establishment_history")
                stats['total_establishments'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM protected_areas")
                stats['total_protected_areas'] = cur.fetchone()[0]
                
            elif role == 'penro':
                cur.execute("SELECT COUNT(*) FROM enumerators_report")
                stats['total_reports'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM users WHERE role = 'CENRO'")
                stats['total_cenro'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(DISTINCT establishment_id) FROM establishment_history")
                stats['total_establishments'] = cur.fetchone()[0]
                
            elif role == 'admin':
                cur.execute("SELECT COUNT(*) FROM enumerators_report")
                stats['total_reports'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM users WHERE role = 'CENRO'")
                stats['total_cenro'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM users WHERE role = 'PENRO'")
                stats['total_penro'] = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(DISTINCT establishment_id) FROM establishment_history")
                stats['total_establishments'] = cur.fetchone()[0]
                
    except Exception as e:
        logger.exception(f'Error fetching dashboard stats: {e}')
        
    return stats


def get_establishment_type_stats(role=None, cenro_id=None, penro_id=None, region_id=None):
    """Get establishment type statistics for charts."""
    stats = []
    
    try:
        with connection.cursor() as cur:
            query = """
                SELECT ep.establishment_type, COUNT(*) as count
                FROM establishment_profile ep
                WHERE ep.establishment_type IS NOT NULL
                GROUP BY ep.establishment_type
                ORDER BY count DESC
                LIMIT 10
            """
            cur.execute(query)
            
            for row in cur.fetchall():
                stats.append({'type': row[0], 'count': row[1]})
                
    except Exception as e:
        logger.exception(f'Error fetching establishment type stats: {e}')
        
    return stats


def get_protected_area_stats(role=None, cenro_id=None, penro_id=None, region_id=None):
    """Get protected area statistics for charts."""
    stats = []
    
    try:
        with connection.cursor() as cur:
            query = """
                SELECT pa.name, COUNT(er.id) as count
                FROM protected_areas pa
                LEFT JOIN enumerators_report er ON pa.id = er.pa_id
                GROUP BY pa.id, pa.name
                ORDER BY count DESC
                LIMIT 10
            """
            cur.execute(query)
            
            for row in cur.fetchall():
                stats.append({'name': row[0], 'count': row[1]})
                
    except Exception as e:
        logger.exception(f'Error fetching protected area stats: {e}')
        
    return stats


def get_superadmin_dashboard_stats():
    """Get statistics for Super Admin dashboard."""
    stats = {}
    
    try:
        with connection.cursor() as cur:
            # Count users by role
            cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) = 'admin'")
            stats['admin_count'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) = 'penro'")
            stats['penro_count'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) = 'cenro'")
            stats['cenro_count'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) = 'evaluator'")
            stats['evaluator_count'] = cur.fetchone()[0]
            
            # Active vs inactive (assuming all users are active for now)
            cur.execute("SELECT COUNT(*) FROM users WHERE LOWER(role) != 'super admin'")
            stats['active_users'] = cur.fetchone()[0]
            stats['inactive_users'] = 0
            
    except Exception as e:
        logger.exception(f'Error fetching superadmin dashboard stats: {e}')
        
    return stats


def get_all_users_superadmin():
    """Fetch all users for Super Admin."""
    try:
        with connection.cursor() as cur:
            query = """
                SELECT u.id, u.first_name, u.last_name, u.role, u.username, u.email,
                       COALESCE(r.name, p.name, c.name, 'N/A') as office,
                       r.name as region_name, p.name as penro_name, c.name as cenro_name
                FROM users u
                LEFT JOIN regions r ON u.region_id = r.id
                LEFT JOIN penros p ON u.penro_id = p.id
                LEFT JOIN cenros c ON u.cenro_id = c.id
                ORDER BY u.id DESC;
            """
            
            cur.execute(query)
            
            users = []
            for row in cur.fetchall():
                users.append({
                    'user_id': row[0],
                    'first_name': row[1],
                    'last_name': row[2],
                    'role': row[3],
                    'username': row[4],
                    'email': row[5],
                    'office': row[6],
                    'region_name': row[7] or '—',
                    'penro_name': row[8] or '—',
                    'cenro_name': row[9] or '—'
                })
            return users
    except Exception as e:
        logger.exception('Error fetching all users: %s', e)
        return []


def get_region_admins():
    """Fetch all region admins with their region info."""
    try:
        with connection.cursor() as cur:
            query = """
                SELECT u.id, u.first_name, u.last_name, u.username, u.email,
                       r.id as region_id, r.name as region_name
                FROM users u
                LEFT JOIN regions r ON u.region_id = r.id
                WHERE LOWER(u.role) = 'admin'
                ORDER BY r.name, u.last_name;
            """
            
            cur.execute(query)
            
            admins = []
            for row in cur.fetchall():
                admins.append({
                    'user_id': row[0],
                    'first_name': row[1],
                    'last_name': row[2],
                    'username': row[3],
                    'email': row[4],
                    'region_id': row[5],
                    'region_name': row[6] or 'Unassigned'
                })
            return admins
    except Exception as e:
        logger.exception('Error fetching region admins: %s', e)
        return []


def get_all_regions():
    """Fetch all regions."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT id, name FROM regions ORDER BY name;")
            return [{'id': r[0], 'name': r[1]} for r in cur.fetchall()]
    except Exception as e:
        logger.exception('Error fetching regions: %s', e)
        return []

def convert_shapefile_to_geojson(file_path):
    """Convert shapefile to GeoJSON."""
    import tempfile
    import zipfile
    try:
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        with tempfile.TemporaryDirectory() as tmpdir:
            file_data = supabase.storage.from_(bucket).download(file_path)
            zip_path = os.path.join(tmpdir, 'shapefile.zip')
            with open(zip_path, 'wb') as f:
                f.write(file_data)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            shp_file = next((f for f in os.listdir(tmpdir) if f.endswith('.shp')), None)
            if not shp_file:
                return None, 'No .shp file found'
            shp_path = os.path.join(tmpdir, shp_file)
            import fiona
            features = []
            with fiona.open(shp_path) as src:
                for feature in src:
                    features.append({
                        'type': 'Feature',
                        'properties': dict(feature['properties']),
                        'geometry': dict(feature['geometry'])
                    })
            return {'type': 'FeatureCollection', 'features': features}, None
    except Exception as e:
        logger.exception('Error converting shapefile: %s', e)
        return None, str(e)
