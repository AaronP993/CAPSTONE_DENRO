# views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .operation import (
    login_user,
    create_account,
    get_enumerator_reports,
    get_establishment_types_for_cenro,
    get_protected_areas_for_cenro,
    get_report_details,
    get_report_images,
    get_activity_logs,
)
from .decorators import login_required, role_required, can_create_users
from datetime import datetime 
import os
from django.shortcuts import render
# moved get_activity_logs import into the grouped import above

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
    return render(request, 'SUPER_ADMIN/SA_dashboard.html')

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

    # Get report details (existing DB-backed function)
    report_data = get_report_details(report_id, cenro_id)

    if not report_data:
        return JsonResponse({'error': 'Report not found or access denied'}, status=404)

    # New: fetch images via Supabase
    images = get_report_images(report_id)
    report_data['images'] = images

    return JsonResponse(report_data)


@login_required
@role_required(['CENRO', 'PENRO'])
def cenro_attest_report(request, report_id):
    """Endpoint to save attestation (attested_by) and signature for a report.

    Expects POST JSON: { attested_by_name, attested_by_position, signature_dataurl }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

    attested_by_name = payload.get('attested_by_name') or f"{request.session.get('first_name','').strip()} {request.session.get('last_name','').strip()}".strip()
    attested_by_position = payload.get('attested_by_position') or ''
    signature_dataurl = payload.get('signature_dataurl')

    if not signature_dataurl:
        return JsonResponse({'error': 'Signature data is required'}, status=400)

    # Call operation helper to save attestation and signature
    result = None
    try:
        result = save_attest_result = get_attest_result = None
        from . import operation as op
        # pass current user id for auditing if needed
        current_user_id = request.session.get('user_id')
        ok, info = op.save_attestation(report_id,
                                       attested_by_name,
                                       attested_by_position,
                                       signature_dataurl,
                                       current_user_id)
        if not ok:
            return JsonResponse({'error': info or 'Failed to save attestation'}, status=500)

        # On success, return the updated attestation fields so frontend can render
        return JsonResponse({'success': True, 'attested_by_signature_url': info})

    except Exception as e:
        import logging
        logging.exception('Error in cenro_attest_report')
        return JsonResponse({'error': 'Internal server error'}, status=500)


def cenro_activity_logs(request):
    logs = get_activity_logs()

    return render(request, "cenro/activity_logs.html", {
        "activity_logs": logs
    })
