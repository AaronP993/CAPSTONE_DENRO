# views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import connection
from .operation import (
    login_user,
    create_account,
    get_enumerator_reports,
    get_establishment_types_for_cenro,
    get_protected_areas_for_cenro,
    get_report_details,
    get_report_images,
    get_activity_logs,
    export_reports,
)
from django.contrib import messages
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
    from .operation import get_superadmin_dashboard_stats
    stats = get_superadmin_dashboard_stats()
    return render(request, 'SUPER_ADMIN/SA_dashboard.html', stats)

@login_required
@role_required(['Super Admin'])
def sa_region_admin_management(request):
    from .operation import get_region_admins, get_all_regions
    admins = get_region_admins()
    regions = get_all_regions()
    return render(request, 'SUPER_ADMIN/region_admin_management.html', {'admins': admins, 'regions': regions})

@login_required
@role_required(['Super Admin'])
def sa_pending_registration(request):
    return render(request, 'SUPER_ADMIN/pending_registration.html')

@login_required
@role_required(['Super Admin'])
def sa_authentication_logs(request):
    return render(request, 'SUPER_ADMIN/authentication_logs.html')

@login_required
@role_required(['Super Admin'])
def sa_activity_logs(request):
    return render(request, 'SUPER_ADMIN/activity_logs.html')

@login_required
@role_required(['Super Admin'])
def sa_all_users(request):
    from .operation import get_all_users_superadmin
    users = get_all_users_superadmin()
    return render(request, 'SUPER_ADMIN/all_users.html', {'users': users})

@login_required
@role_required(['Super Admin'])
def sa_profile(request):
    return render(request, 'SUPER_ADMIN/profile.html')

@login_required  
@role_required(['Admin'])
def admin_dashboard(request):
    from .operation import get_dashboard_stats, get_establishment_type_stats, get_protected_area_stats
    region_id = request.session.get('region_id')
    stats = get_dashboard_stats('admin', region_id=region_id)
    stats['establishment_types'] = get_establishment_type_stats('admin', region_id=region_id)
    stats['protected_areas'] = get_protected_area_stats('admin', region_id=region_id)
    return render(request, 'ADMIN/ADMIN_dashboard.html', stats)

@login_required
@role_required(['PENRO'])
def penro_dashboard(request):
    from .operation import get_dashboard_stats, get_establishment_type_stats, get_protected_area_stats
    penro_id = request.session.get('penro_id')
    stats = get_dashboard_stats('penro', penro_id=penro_id)
    stats['establishment_types'] = get_establishment_type_stats('penro', penro_id=penro_id)
    stats['protected_areas'] = get_protected_area_stats('penro', penro_id=penro_id)
    return render(request, 'PENRO/PENRO_dashboard.html', stats)

@login_required
@role_required(['PENRO'])
def penro_activitylogs(request):
    return render(request, 'PENRO/PENRO_activitylogs.html')

@login_required
@role_required(['PENRO'])
def penro_reports(request):
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
    
    # Fetch reports submitted by PENRO role only
    reports = get_enumerator_reports(
        submitter_role='PENRO',
        from_date=from_date,
        to_date=to_date,
        establishment_type=establishment_type,
        pa_id=pa_id,
        establishment_status=establishment_status
    )
    
    # Get list of establishment types and protected areas for dropdowns
    penro_id = request.session.get('penro_id')
    establishment_types = get_establishment_types_for_cenro(penro_id) if penro_id else []
    protected_areas = get_protected_areas_for_cenro(penro_id) if penro_id else []
    
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
        'supabase_url': os.getenv('SUPABASE_URL'),
        'supabase_bucket': os.getenv('SUPABASE_BUCKET', 'images'),
    }
    
    return render(request, 'PENRO/PENRO_reports.html', context)

@login_required
@role_required(['PENRO'])
def penro_usermanagement(request):
    from .operation import get_all_users
    current_role = request.session.get('role', '').lower()
    penro_id = request.session.get('penro_id')
    users = get_all_users(current_role, penro_id=penro_id)
    return render(request, 'PENRO/PENRO_usermanagement.html', {'users': users})

@login_required
@role_required(['PENRO'])
def penro_profile(request):
    return render(request, 'PENRO/PENRO_profile.html')

@login_required
@role_required(['CENRO'])
def cenro_dashboard(request):
    from .operation import get_dashboard_stats, get_establishment_type_stats, get_protected_area_stats
    cenro_id = request.session.get('cenro_id')
    stats = get_dashboard_stats('cenro', cenro_id=cenro_id)
    stats['establishment_types'] = get_establishment_type_stats('cenro', cenro_id=cenro_id)
    stats['protected_areas'] = get_protected_area_stats('cenro', cenro_id=cenro_id)
    return render(request, 'CENRO/CENRO_dashboard.html', stats)

@login_required
@role_required(['CENRO'])
def cenro_activitylogs(request):
    return render(request, 'CENRO/CENRO_activitylogs.html')

@login_required
@role_required(['CENRO'])
def cenro_reports(request):
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
    
    # Fetch reports submitted by CENRO role only
    reports = get_enumerator_reports(
        submitter_role='CENRO',
        from_date=from_date,
        to_date=to_date,
        establishment_type=establishment_type,
        pa_id=pa_id,
        establishment_status=establishment_status
    )
    
    # Get list of establishment types and protected areas for dropdowns
    cenro_id = request.session.get('cenro_id')
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
def cenro_export_reports(request):
    """Export filtered reports as PDF, Word, or Excel"""
    cenro_id = request.session.get('cenro_id')
    format_type = request.GET.get('format', 'pdf')
    
    from_date_str = request.GET.get('from_date')
    to_date_str = request.GET.get('to_date')
    establishment_type = request.GET.get('establishment_type')
    pa_id_str = request.GET.get('pa_id')
    establishment_status = request.GET.get('establishment_status')
    
    from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else None
    to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else None
    pa_id = int(pa_id_str) if pa_id_str else None
    
    reports = get_enumerator_reports(
        submitter_role='CENRO',
        from_date=from_date,
        to_date=to_date,
        establishment_type=establishment_type,
        pa_id=pa_id,
        establishment_status=establishment_status,
        cenro_id=cenro_id
    )
    return export_reports(reports, format_type)

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
@role_required(['Admin'])
def admin_report_details(request, report_id):
    report_data = get_report_details(report_id)
    if not report_data:
        return JsonResponse({'error': 'Report not found'}, status=404)
    images = get_report_images(report_id)
    report_data['images'] = images
    return JsonResponse(report_data)

@login_required
@role_required(['PENRO'])
def penro_export_reports(request):
    from . import operation as op
    format_type = request.GET.get('format', 'pdf')
    context = op.get_reports_context(request, 'PENRO')
    return op.export_reports(context['reports'], format_type)

@login_required
@role_required(['Admin'])
def admin_export_reports(request):
    from . import operation as op
    format_type = request.GET.get('format', 'pdf')
    context = op.get_reports_context(request, 'Admin')
    return op.export_reports(context['reports'], format_type)


@login_required
@role_required(['CENRO', 'PENRO'])
def cenro_note_report(request, report_id):
    """Endpoint to save notation (noted_by) and signature for a report."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        import json
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

    noted_by_name = payload.get('noted_by_name') or f"{request.session.get('first_name','').strip()} {request.session.get('last_name','').strip()}".strip()
    noted_by_position = payload.get('noted_by_position') or ''
    signature_dataurl = payload.get('signature_dataurl')

    if not signature_dataurl:
        return JsonResponse({'error': 'Signature data is required'}, status=400)

    try:
        from . import operation as op
        current_user_id = request.session.get('user_id')
        ok, info = op.save_notation(report_id, noted_by_name, noted_by_position, signature_dataurl, current_user_id)
        if not ok:
            return JsonResponse({'error': info or 'Failed to save notation'}, status=500)
        return JsonResponse({'success': True, 'noted_by_signature_url': info, 'signature_url': info})
    except Exception as e:
        import logging
        logging.exception('Error in cenro_note_report')
        return JsonResponse({'error': 'Internal server error'}, status=500)


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





# Admin

@login_required
@role_required(['Admin'])
def admin_reports(request):
    from . import operation as op
    context = op.get_reports_context(request, 'Admin')
    return render(request, 'ADMIN/ADMIN_reports.html', context)

@login_required
@role_required(['Admin'])
def protected_areas(request):
    from . import operation as op
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'delete':
            pa_id = request.POST.get('pa_id')
            if pa_id:
                success, message = op.delete_protected_area(int(pa_id))
                if success:
                    messages.success(request, message)
                else:
                    messages.error(request, message)
        else:
            # Add new protected area
            name = request.POST.get('name', '').strip()
            file_obj = request.FILES.get('file')
            jurisdiction_level = request.POST.get('jurisdiction_level', '').strip()
            region_id = request.POST.get('region_id')
            penro_id = request.POST.get('penro_id')
            cenro_id = request.POST.get('cenro_id')
            
            if not name:
                messages.error(request, 'Protected area name is required.')
            elif not file_obj:
                messages.error(request, 'File upload is required.')
            else:
                success, message = op.add_protected_area(name, file_obj, jurisdiction_level, region_id, penro_id, cenro_id)
                if success:
                    messages.success(request, message)
                else:
                    messages.error(request, message)
        
        return redirect('protected-areas')
    
    # GET request - display protected areas
    protected_areas_list = op.get_protected_areas()
    
    # Get user's office info for jurisdiction assignment
    user_region_id = request.session.get('region_id')
    user_region_name = None
    if user_region_id:
        with connection.cursor() as cur:
            cur.execute("SELECT name FROM regions WHERE id = %s;", [user_region_id])
            row = cur.fetchone()
            if row:
                user_region_name = row[0]
    
    # Get available offices
    penros = []
    cenros = []
    with connection.cursor() as cur:
        if user_region_id:
            cur.execute("SELECT id, name FROM penros WHERE region_id = %s ORDER BY name;", [user_region_id])
            penros = [{'id': r[0], 'name': r[1]} for r in cur.fetchall()]
            cur.execute("SELECT id, name FROM cenros WHERE penro_id IN (SELECT id FROM penros WHERE region_id = %s) ORDER BY name;", [user_region_id])
            cenros = [{'id': r[0], 'name': r[1]} for r in cur.fetchall()]
    
    return render(request, 'ADMIN/ProtectedArea.html', {
        'protected_areas': protected_areas_list,
        'supabase_url': os.getenv('SUPABASE_URL'),
        'supabase_bucket': os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos'),
        'user_region_id': user_region_id,
        'user_region_name': user_region_name,
        'penros': penros,
        'cenros': cenros,
    })

@login_required
def list_enumerated_pa(request):
    from . import operation as op
    import json
    
    protected_areas_list = op.get_protected_areas()
    
    # Get enumerated establishments grouped by PA
    enumerated_by_pa = {}
    with connection.cursor() as cur:
        cur.execute("""
            SELECT er.pa_id, er.id, er.establishment_name, ep.establishment_type, 
                   ep.establishment_status, gti.latitude, gti.longitude, pa.name as pa_name
            FROM enumerators_report er
            JOIN protected_areas pa ON er.pa_id = pa.id
            LEFT JOIN establishment_profile ep ON er.establishment_id = ep.id
            LEFT JOIN geo_tagged_images gti ON er.geo_tagged_image_id = gti.id
            WHERE gti.latitude IS NOT NULL AND gti.longitude IS NOT NULL
            ORDER BY pa.name, er.establishment_name
        """)
        for row in cur.fetchall():
            pa_id = row[0]
            if pa_id not in enumerated_by_pa:
                enumerated_by_pa[pa_id] = []
            enumerated_by_pa[pa_id].append({
                'id': row[1],
                'establishment_name': row[2],
                'establishment_type': row[3],
                'establishment_status': row[4],
                'latitude': float(row[5]) if row[5] else None,
                'longitude': float(row[6]) if row[6] else None,
                'pa_name': row[7]
            })
    
    # Add enumerated count to each PA
    for pa in protected_areas_list:
        pa['enumerated_count'] = len(enumerated_by_pa.get(pa['id'], []))
    
    return render(request, 'List_enumerated_pa.html', {
        'protected_areas': protected_areas_list,
        'enumerated_data': json.dumps(enumerated_by_pa),
        'supabase_url': os.getenv('SUPABASE_URL'),
        'supabase_bucket': os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos'),
    })


@login_required
def convert_shapefile_to_geojson(request, file_path):
    from . import operation as op
    geojson, error = op.convert_shapefile_to_geojson(file_path)
    if error:
        return JsonResponse({'error': error}, status=500)
    return JsonResponse(geojson)


@login_required
@role_required(['CENRO'])
def cenro_usermanagement(request):
    from .operation import get_all_users
    current_role = request.session.get('role', '').lower()
    users = get_all_users(current_role)
    return render(request, 'CENRO/CENRO_usermanagement.html', {'users': users})

@login_required
@role_required(['CENRO'])
def cenro_profile(request):
    return render(request, 'CENRO/CENRO_profile.html')

@login_required
@role_required(['CENRO'])
def cenro_establishment_history(request):
    search = request.GET.get('search', '').strip()
    cenro_id = request.session.get('cenro_id')
    if not cenro_id:
        return render(request, 'CENRO/CENRO_establishment_history.html', {'establishments': [], 'search': search})
    with connection.cursor() as cur:
        query = """WITH latest_versions AS (SELECT establishment_id, MAX(version) as max_version FROM establishment_history GROUP BY establishment_id) SELECT eh.id, eh.establishment_id, eh.establishment_name, eh.establishment_type, eh.establishment_status, eh.change_reason, eh.updated_at, eh.version, eh.attestation_id, an.attested_by_name, an.attested_by_position, an.attested_by_signature, an.noted_by_name, an.noted_by_position, an.noted_by_signature, (SELECT COUNT(*) FROM establishment_history WHERE establishment_id = eh.establishment_id) as total_versions FROM establishment_history eh INNER JOIN latest_versions lv ON eh.establishment_id = lv.establishment_id AND eh.version = lv.max_version LEFT JOIN attestation_notations an ON eh.attestation_id = an.id WHERE 1=1"""
        params = []
        if search:
            query += " AND (eh.establishment_name ILIKE %s OR CAST(eh.establishment_id AS TEXT) LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        query += " ORDER BY eh.updated_at DESC;"
        cur.execute(query, params)
        rows = cur.fetchall()
        supabase_url = os.getenv('SUPABASE_URL')
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        establishments = []
        for row in rows:
            pa_name = '—'
            if row[5] and 'Report ' in row[5]:
                try:
                    import re
                    match = re.search(r'Report (\d+)', row[5])
                    if match:
                        cur.execute("SELECT pa.name FROM enumerators_report er JOIN protected_areas pa ON er.pa_id = pa.id WHERE er.id = %s", [int(match.group(1))])
                        pa_row = cur.fetchone()
                        if pa_row:
                            pa_name = pa_row[0]
                except:
                    pass
            establishments.append({'id': row[0], 'establishment_id': row[1], 'establishment_name': row[2], 'establishment_type': row[3], 'establishment_status': row[4], 'change_reason': row[5], 'date_recorded': row[6], 'version': row[7], 'total_versions': row[15], 'attestation_id': row[8], 'attested_by_name': row[9], 'attested_by_position': row[10], 'attested_by_signature': row[11] if row[11] and row[11].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{row[11]}" if row[11] else None, 'noted_by_name': row[12], 'noted_by_position': row[13], 'noted_by_signature': row[14] if row[14] and row[14].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{row[14]}" if row[14] else None, 'pa_name': pa_name})
    return render(request, 'CENRO/CENRO_establishment_history.html', {'establishments': establishments, 'search': search})

@login_required
@role_required(['CENRO'])
def cenro_establishment_versions(request, establishment_id):
    with connection.cursor() as cur:
        cur.execute("SELECT eh.id, eh.version, eh.establishment_name, eh.establishment_type, eh.establishment_status, eh.change_reason, eh.updated_at, eh.attestation_id, an.attested_by_name, an.attested_by_position, an.attested_by_signature, an.noted_by_name, an.noted_by_position, an.noted_by_signature, eh.pa_name FROM establishment_history eh LEFT JOIN attestation_notations an ON eh.attestation_id = an.id WHERE eh.establishment_id = %s ORDER BY eh.version DESC;", [establishment_id])
        supabase_url = os.getenv('SUPABASE_URL')
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        versions = [{'id': r[0], 'version': r[1], 'establishment_name': r[2], 'establishment_type': r[3], 'establishment_status': r[4], 'change_reason': r[5], 'pa_name': r[14] or '', 'updated_at': r[6].isoformat() if r[6] else None, 'attestation_id': r[7], 'attested_by_name': r[8], 'attested_by_position': r[9], 'attested_by_signature': (r[10] if r[10] and r[10].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{r[10]}") if r[10] else None, 'noted_by_name': r[11], 'noted_by_position': r[12], 'noted_by_signature': (r[13] if r[13] and r[13].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{r[13]}") if r[13] else None} for r in cur.fetchall()]
    return JsonResponse(versions, safe=False)

@login_required
@role_required(['PENRO'])
def penro_establishment_history(request):
    search = request.GET.get('search', '').strip()
    penro_id = request.session.get('penro_id')
    if not penro_id:
        return render(request, 'PENRO/PENRO_establishment_history.html', {'establishments': [], 'search': search})
    with connection.cursor() as cur:
        query = """WITH latest_versions AS (SELECT establishment_id, MAX(version) as max_version FROM establishment_history GROUP BY establishment_id) SELECT eh.id, eh.establishment_id, eh.establishment_name, eh.establishment_type, eh.establishment_status, eh.change_reason, eh.updated_at, eh.version, eh.attestation_id, an.attested_by_name, an.attested_by_position, an.attested_by_signature, an.noted_by_name, an.noted_by_position, an.noted_by_signature, (SELECT COUNT(*) FROM establishment_history WHERE establishment_id = eh.establishment_id) as total_versions FROM establishment_history eh INNER JOIN latest_versions lv ON eh.establishment_id = lv.establishment_id AND eh.version = lv.max_version LEFT JOIN attestation_notations an ON eh.attestation_id = an.id WHERE 1=1"""
        params = []
        if search:
            query += " AND (eh.establishment_name ILIKE %s OR CAST(eh.establishment_id AS TEXT) LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        query += " ORDER BY eh.updated_at DESC;"
        cur.execute(query, params)
        rows = cur.fetchall()
        supabase_url = os.getenv('SUPABASE_URL')
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        establishments = []
        for row in rows:
            pa_name = '—'
            if row[5] and 'Report ' in row[5]:
                try:
                    import re
                    match = re.search(r'Report (\d+)', row[5])
                    if match:
                        cur.execute("SELECT pa.name FROM enumerators_report er JOIN protected_areas pa ON er.pa_id = pa.id WHERE er.id = %s", [int(match.group(1))])
                        pa_row = cur.fetchone()
                        if pa_row:
                            pa_name = pa_row[0]
                except:
                    pass
            establishments.append({'id': row[0], 'establishment_id': row[1], 'establishment_name': row[2], 'establishment_type': row[3], 'establishment_status': row[4], 'change_reason': row[5], 'date_recorded': row[6], 'version': row[7], 'total_versions': row[15], 'attestation_id': row[8], 'attested_by_name': row[9], 'attested_by_position': row[10], 'attested_by_signature': row[11] if row[11] and row[11].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{row[11]}" if row[11] else None, 'noted_by_name': row[12], 'noted_by_position': row[13], 'noted_by_signature': row[14] if row[14] and row[14].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{row[14]}" if row[14] else None, 'pa_name': pa_name})
    return render(request, 'PENRO/PENRO_establishment_history.html', {'establishments': establishments, 'search': search})

@login_required
@role_required(['PENRO'])
def penro_establishment_versions(request, establishment_id):
    with connection.cursor() as cur:
        cur.execute("SELECT eh.id, eh.version, eh.establishment_name, eh.establishment_type, eh.establishment_status, eh.change_reason, eh.updated_at, eh.attestation_id, an.attested_by_name, an.attested_by_position, an.attested_by_signature, an.noted_by_name, an.noted_by_position, an.noted_by_signature, eh.pa_name FROM establishment_history eh LEFT JOIN attestation_notations an ON eh.attestation_id = an.id WHERE eh.establishment_id = %s ORDER BY eh.version DESC;", [establishment_id])
        supabase_url = os.getenv('SUPABASE_URL')
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        versions = [{'id': r[0], 'version': r[1], 'establishment_name': r[2], 'establishment_type': r[3], 'establishment_status': r[4], 'change_reason': r[5], 'pa_name': r[14] or '', 'updated_at': r[6].isoformat() if r[6] else None, 'attestation_id': r[7], 'attested_by_name': r[8], 'attested_by_position': r[9], 'attested_by_signature': (r[10] if r[10] and r[10].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{r[10]}") if r[10] else None, 'noted_by_name': r[11], 'noted_by_position': r[12], 'noted_by_signature': (r[13] if r[13] and r[13].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{r[13]}") if r[13] else None} for r in cur.fetchall()]
    return JsonResponse(versions, safe=False)

@login_required
@role_required(['Admin'])
def admin_usermanagement(request):
    from .operation import get_all_users
    current_role = request.session.get('role', '').lower()
    users = get_all_users(current_role)
    return render(request, 'ADMIN/ADMIN_usermanagement.html', {'users': users})

@login_required
@role_required(['Admin'])
def admin_user_update(request):
    if request.method == 'POST':
        from .operation import update_user_profile
        user_id = request.POST.get('user_id')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        role = request.POST.get('role')
        success, message = update_user_profile(user_id, first_name, last_name, username, email, role)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
    return redirect('admin-usermanagement')

@login_required
@role_required(['Admin'])
def admin_user_delete(request):
    if request.method == 'POST':
        from .operation import delete_user
        user_id = request.POST.get('user_id')
        success, message = delete_user(user_id)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
    return redirect('admin-usermanagement')

@login_required
@role_required(['Admin'])
def admin_profile(request):
    return render(request, 'ADMIN/ADMIN_profile.html')

@login_required
@role_required(['Admin'])
def admin_establishment_history(request):
    search = request.GET.get('search', '').strip()
    region_id = request.session.get('region_id')
    if not region_id:
        return render(request, 'ADMIN/ADMIN_establishment_history.html', {'establishments': [], 'search': search})
    with connection.cursor() as cur:
        query = """WITH latest_versions AS (SELECT establishment_id, MAX(version) as max_version FROM establishment_history GROUP BY establishment_id) SELECT eh.id, eh.establishment_id, eh.establishment_name, eh.establishment_type, eh.establishment_status, eh.change_reason, eh.updated_at, eh.version, eh.attestation_id, an.attested_by_name, an.attested_by_position, an.attested_by_signature, an.noted_by_name, an.noted_by_position, an.noted_by_signature, (SELECT COUNT(*) FROM establishment_history WHERE establishment_id = eh.establishment_id) as total_versions FROM establishment_history eh INNER JOIN latest_versions lv ON eh.establishment_id = lv.establishment_id AND eh.version = lv.max_version LEFT JOIN attestation_notations an ON eh.attestation_id = an.id WHERE 1=1"""
        params = []
        if search:
            query += " AND (eh.establishment_name ILIKE %s OR CAST(eh.establishment_id AS TEXT) LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        query += " ORDER BY eh.updated_at DESC;"
        cur.execute(query, params)
        rows = cur.fetchall()
        supabase_url = os.getenv('SUPABASE_URL')
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        establishments = []
        for row in rows:
            pa_name = '—'
            if row[5] and 'Report ' in row[5]:
                try:
                    import re
                    match = re.search(r'Report (\d+)', row[5])
                    if match:
                        cur.execute("SELECT pa.name FROM enumerators_report er JOIN protected_areas pa ON er.pa_id = pa.id WHERE er.id = %s", [int(match.group(1))])
                        pa_row = cur.fetchone()
                        if pa_row:
                            pa_name = pa_row[0]
                except:
                    pass
            establishments.append({'id': row[0], 'establishment_id': row[1], 'establishment_name': row[2], 'establishment_type': row[3], 'establishment_status': row[4], 'change_reason': row[5], 'date_recorded': row[6], 'version': row[7], 'total_versions': row[15], 'attestation_id': row[8], 'attested_by_name': row[9], 'attested_by_position': row[10], 'attested_by_signature': row[11] if row[11] and row[11].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{row[11]}" if row[11] else None, 'noted_by_name': row[12], 'noted_by_position': row[13], 'noted_by_signature': row[14] if row[14] and row[14].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{row[14]}" if row[14] else None, 'pa_name': pa_name})
    return render(request, 'ADMIN/ADMIN_establishment_history.html', {'establishments': establishments, 'search': search})

@login_required
@role_required(['Admin'])
def admin_establishment_versions(request, establishment_id):
    with connection.cursor() as cur:
        cur.execute("SELECT eh.id, eh.version, eh.establishment_name, eh.establishment_type, eh.establishment_status, eh.change_reason, eh.updated_at, eh.attestation_id, an.attested_by_name, an.attested_by_position, an.attested_by_signature, an.noted_by_name, an.noted_by_position, an.noted_by_signature, eh.pa_name FROM establishment_history eh LEFT JOIN attestation_notations an ON eh.attestation_id = an.id WHERE eh.establishment_id = %s ORDER BY eh.version DESC;", [establishment_id])
        supabase_url = os.getenv('SUPABASE_URL')
        bucket = os.getenv('SUPABASE_BUCKET', 'geo-tagged-photos')
        versions = [{'id': r[0], 'version': r[1], 'establishment_name': r[2], 'establishment_type': r[3], 'establishment_status': r[4], 'change_reason': r[5], 'pa_name': r[14] or '', 'updated_at': r[6].isoformat() if r[6] else None, 'attestation_id': r[7], 'attested_by_name': r[8], 'attested_by_position': r[9], 'attested_by_signature': (r[10] if r[10] and r[10].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{r[10]}") if r[10] else None, 'noted_by_name': r[11], 'noted_by_position': r[12], 'noted_by_signature': (r[13] if r[13] and r[13].startswith('http') else f"{supabase_url}/storage/v1/object/public/{bucket}/{r[13]}") if r[13] else None} for r in cur.fetchall()]
    return JsonResponse(versions, safe=False)


