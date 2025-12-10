# views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .operation import login_user, create_account, get_enumerator_reports, get_establishment_types_for_cenro, get_protected_areas_for_cenro, get_report_details
from .decorators import login_required, role_required, can_create_users
from datetime import datetime 
import os


def login_view(request):
    if request.method == "POST":
        return login_user(request)  # DB-backed login
    return render(request, "LogIn.html")

# Add the decorator to create_account view
@can_create_users
def create_account_view(request):
    return create_account(request)

@login_required
@role_required(['Super Admin'])
def superadmin_dashboard(request):
    from django.db import connection
    
    # Get user counts by role
    with connection.cursor() as cur:
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE role = 'Admin') as admin_count,
                COUNT(*) FILTER (WHERE role = 'PENRO') as penro_count,
                COUNT(*) FILTER (WHERE role = 'CENRO') as cenro_count,
                COUNT(*) FILTER (WHERE role = 'Evaluator') as evaluator_count,
                COUNT(*) as total_users
            FROM users
            WHERE role != 'Super Admin';
        """)
        row = cur.fetchone()
    
    total = row[4] if row else 0
    # Assume all users are active for now (since is_active column doesn't exist)
    active = total
    inactive = 0
        
    context = {
        'admin_count': row[0] if row else 0,
        'penro_count': row[1] if row else 0,
        'cenro_count': row[2] if row else 0,
        'evaluator_count': row[3] if row else 0,
        'total_users': total,
        'active_users': active,
        'inactive_users': inactive,
    }
    
    return render(request, 'SUPER_ADMIN/SA_dashboard.html', context)

@login_required  
@role_required(['Admin'])
def admin_dashboard(request):
    return render(request, 'ADMIN/ADMIN_dashboard.html')

@login_required
@role_required(['PENRO'])
def penro_dashboard(request):
    return render(request, 'PENRO/PENRO_dashboard.html')

@login_required
@role_required(['CENRO'])
def cenro_dashboard(request):
    return render(request, 'CENRO/CENRO_dashboard.html')

@login_required
@role_required(['CENRO'])
def cenro_activitylogs(request):
    return render(request, 'CENRO/CENRO_activitylogs.html')

@login_required
@role_required(['CENRO'])
def cenro_reports(request):
    # Get current user's CENRO ID from session
    cenro_id = request.session.get('cenro_id')
    
    # Get filter parameters from query string
    from_date_str = request.GET.get('from_date', None)
    to_date_str = request.GET.get('to_date', None)
    establishment_type = request.GET.get('establishment_type', None)
    pa_id_str = request.GET.get('pa_id', None)
    establishment_status = request.GET.get('establishment_status', None)
    
    # Convert date strings to date objects
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
    
    # Convert pa_id to int if present
    pa_id = None
    if pa_id_str:
        try:
            pa_id = int(pa_id_str)
        except (ValueError, TypeError):
            pa_id = None
    
    # Fetch reports for this CENRO
    reports = get_enumerator_reports(
        cenro_id=cenro_id, 
        from_date=from_date,
        to_date=to_date,
        establishment_type=establishment_type,
        pa_id=pa_id,
        establishment_status=establishment_status
    )
    
    # Get list of establishment types and protected areas for dropdowns
    establishment_types = get_establishment_types_for_cenro(cenro_id) if cenro_id else []
    protected_areas = get_protected_areas_for_cenro(cenro_id) if cenro_id else []
    
    # Pass reports and filter options to template
    context = {
        'reports': reports,
        'from_date': from_date,
        'to_date': to_date,
        'establishment_type': establishment_type,
        'establishment_types': establishment_types,
        'pa_id': pa_id,
        'protected_areas': protected_areas,
        'establishment_status': establishment_status,
        # 🆕 ADD THESE TWO LINES FOR SUPABASE SUPPORT
        'supabase_url': os.getenv('SUPABASE_URL'),
        'supabase_bucket': os.getenv('SUPABASE_BUCKET', 'images'),
    }
    
    return render(request, 'CENRO/CENRO_reports.html', context)

@login_required
@role_required(['CENRO'])
def cenro_templates(request):
    return render(request, 'CENRO/CENRO_templates.html')

@login_required
@role_required(['CENRO'])
def cenro_report_details(request, report_id):
    """
    API endpoint to get detailed report information for the modal
    """
    cenro_id = request.session.get('cenro_id')
    
    # Get report details
    report_data = get_report_details(report_id, cenro_id)
    
    if not report_data:
        return JsonResponse({'error': 'Report not found or access denied'}, status=404)
    
    return JsonResponse(report_data)


















from django.shortcuts import render
from .operation import get_activity_logs

def cenro_activity_logs(request):
    logs = get_activity_logs()

    return render(request, "cenro/activity_logs.html", {
        "activity_logs": logs
    })









@login_required
@role_required(['PENRO'])
def penro_activitylogs(request):
    logs = get_activity_logs()  # your ORM query
    return render(request, 'PENRO/PENRO_activitylogs.html', {'logs': logs})

@login_required
@role_required(['PENRO'])
def penro_reports(request):
    penro_id = request.session.get('penro_id')
    # Get all reports for CENROs under this PENRO
    reports = []
    return render(request, 'PENRO/PENRO_reports.html', {'reports': reports})

@login_required
@role_required(['PENRO'])
def penro_usermanagement(request):
    return render(request, 'PENRO/PENRO_usermanagement.html')

@login_required
@role_required(['PENRO'])
def penro_profile(request):
    return render(request, 'PENRO/PENRO_profile.html')


@login_required
@role_required(['PENRO'])
def penro_profile(request):
    return render(request, 'PENRO/PENRO_profile.html')




# @login_required
# @role_required(['PENRO'])
# def penro_activitylogs(request):
#     # Replace with real data
#     logs = get_activity_logs()  # or your ORM query
#     return render(request, 'PENRO/PENRO_activitylogs.html', {'logs': logs})

# @login_required
# @role_required(['PENRO'])
# def penro_reports(request):
#     # Replace with real data
#     reports = get_penro_reports()  # your reports function
#     return render(request, 'PENRO/PENRO_reports.html', {'reports': reports})
