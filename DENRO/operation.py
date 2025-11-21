# operation.py
from django.contrib import messages
from django.db import connection, DatabaseError, transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.conf import settings
import logging
from supabase import create_client
import os

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
                                                SELECT create_user(
                                %s, %s, %s, %s,   -- first_name, last_name, gender, email
                                %s,               -- phone_number
                                %s,               -- role
                                %s, %s,           -- username, password
                                %s,               -- profile_pic
                                %s, %s, %s,       -- region_id, penro_id, cenro_id
                                %s                -- p_hash_password
                            );
                        """,
                        [
                            first_name, last_name, gender, email,
                            phone_number, role, username,
                            password, profile_pic,
                            r, p, c,
                            True,
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
# GET ENUMERATOR REPORTS for CENRO (WITH ALL FILTERS)
# =========================
def get_enumerator_reports(cenro_id=None, from_date=None, to_date=None, establishment_type=None, pa_id=None, establishment_status=None):
    """
    Fetch enumerator reports for a CENRO office with all filters.
    
    Args:
        cenro_id: Filter reports by CENRO office (None for all)
        from_date: Start date (datetime.date object or None)
        to_date: End date (datetime.date object or None)
        establishment_type: Filter by establishment type (None for all)
        pa_id: Filter by protected area ID (None for all)
        establishment_status: Filter by establishment status (None for all)
    
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
                    ep.establishment_status
                FROM enumerators_report er
                LEFT JOIN users u ON er.enumerator_id = u.id
                LEFT JOIN establishment_profile ep ON er.establishment_id = ep.id
                WHERE 1=1
            """
            
            params = []
            
            if cenro_id:
                query += " AND u.cenro_id = %s"
                params.append(cenro_id)
            
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
    Get list of protected areas for a specific CENRO.
    Gets PAs from reports by this CENRO's enumerators.
    
    Args:
        cenro_id: The CENRO office ID
    
    Returns:
        List of dictionaries with id and name
    """
    protected_areas = []
    
    try:
        with connection.cursor() as cur:
            query = """
                SELECT DISTINCT 
                    pa.id,
                    pa.name
                FROM enumerators_report er
                LEFT JOIN users u ON er.enumerator_id = u.id
                LEFT JOIN protected_areas pa ON er.pa_id = pa.id
                WHERE u.cenro_id = %s
                AND pa.id IS NOT NULL
                ORDER BY pa.name;
            """
            
            cur.execute(query, [cenro_id])
            
            for row in cur.fetchall():
                protected_areas.append({
                    'id': row[0],
                    'name': row[1]
                })
                
    except DatabaseError as e:
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
                    er.updated_at,
                    er.enumerator_signature,
                    er.enumerator_signature_date,
                    er.informant_signature,
                    er.informant_signature_date,
                    u.first_name || ' ' || u.last_name as enumerator_full_name,
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
                    gti.image as geo_image_url,
                    gti.latitude as geo_latitude,
                    gti.longitude as geo_longitude,
                    gti.location as geo_location,
                    gti.captured_at as geo_captured_at,
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
            
            # If cenro_id provided, verify access
            if cenro_id:
                query += " AND u.cenro_id = %s"
                params.append(cenro_id)
            
            cur.execute(query, params)
            row = cur.fetchone()
            
            if not row:
                return None
            

            
            # Build permits array
            permits = []
            
            # Mayor's Permit
            if row[28] or row[29] or row[30]:
                permits.append({
                    'name': "Mayor's Permit",
                    'number': row[28],
                    'issued': row[29].isoformat() if row[29] else None,
                    'expiry': row[30].isoformat() if row[30] else None
                })
            
            # Business Permit
            if row[31] or row[32] or row[33]:
                permits.append({
                    'name': 'Business Permit',
                    'number': row[31],
                    'issued': row[32].isoformat() if row[32] else None,
                    'expiry': row[33].isoformat() if row[33] else None
                })
            
            # Building Permit
            if row[34] or row[35] or row[36]:
                permits.append({
                    'name': 'Building Permit',
                    'number': row[34],
                    'issued': row[35].isoformat() if row[35] else None,
                    'expiry': row[36].isoformat() if row[36] else None
                })
            
            # PAMB Resolution
            if row[37] or row[38]:
                permits.append({
                    'name': 'PAMB Resolution',
                    'number': row[37],
                    'issued': row[38].isoformat() if row[38] else None,
                    'expiry': None
                })
            
            # SAPA
            if row[39] or row[40]:
                permits.append({
                    'name': 'SAPA',
                    'number': row[39],
                    'issued': row[40].isoformat() if row[40] else None,
                    'expiry': None
                })
            
            # PACBRMA
            if row[41] or row[42]:
                permits.append({
                    'name': 'PACBRMA',
                    'number': row[41],
                    'issued': row[42].isoformat() if row[42] else None,
                    'expiry': None
                })
            
            # ECC
            if row[43] or row[44]:
                permits.append({
                    'name': 'Environmental Compliance Certificate (ECC)',
                    'number': row[43],
                    'issued': row[44].isoformat() if row[44] else None,
                    'expiry': None
                })
            
            # Discharge Permit
            if row[45] or row[46]:
                permits.append({
                    'name': 'Discharge Permit',
                    'number': row[45],
                    'issued': row[46].isoformat() if row[46] else None,
                    'expiry': None
                })
            
            # PTO
            if row[47] or row[48]:
                permits.append({
                    'name': 'Permit to Operate (PTO)',
                    'number': row[47],
                    'issued': row[48].isoformat() if row[48] else None,
                    'expiry': None
                })
            
            # Build response dictionary
            report_details = {
                'id': row[0],
                'establishment_name': row[1],
                'proponent_name': row[2],
                'pa_name': row[3],
                'enumerator_name': row[4],
                'report_date': row[5].isoformat() if row[5] else None,
                'informant_name': row[6],
                'remarks': row[7],
                'created_at': row[8].isoformat() if row[8] else None,
                'updated_at': row[9].isoformat() if row[9] else None,
                'enumerator_signature': row[10],
                'enumerator_signature_date': row[11].isoformat() if row[11] else None,
                'informant_signature': row[12],
                'informant_signature_date': row[13].isoformat() if row[13] else None,
                'establishment_type': row[16],
                'establishment_status': row[17],
                'description': row[18],
                'lot_status': row[19],
                'land_classification': row[20],
                'title_no': row[21],
                'lot_no': row[22],
                'lot_owner': row[23],
                'area_covered': row[24],
                'pa_zone': row[25],
                'within_easement': row[26],
                'tax_declaration_no': row[27],
                'permits': permits,
                'other_emb': row[49],
                'geo_image_url': row[50],
                'latitude': row[51],
                'longitude': row[52],
                'location': row[53],
                'geo_captured_at': row[54].isoformat() if row[54] else None,
                'attested_by_name': row[55],
                'attested_by_position': row[56],
                'attested_by_signature': row[57],
                'noted_by_name': row[58],
                'noted_by_position': row[59],
                'noted_by_signature': row[60]
            }
            
            return report_details
                
    except DatabaseError as e:
        logger.error(f"Error fetching report details: {e}")
        return None
    



def get_activity_logs():
    conn = connect_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM get_activity_logs();")
        logs = cursor.fetchall()

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
        print("Error fetching logs:", e)
        return []
    finally:
        cursor.close()
        conn.close()
