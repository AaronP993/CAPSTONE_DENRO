from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from .operation import login_user, create_account  # uses Postgres functions under the hood
from .decorators import login_required, role_required, can_create_users


def login_view(request):
    if request.method == "POST":
        return login_user(request)  # DB-backed login
    return render(request, "LogIn.html")


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
    return render(request, 'PENRO/PENRO_dashboard.html', {
        "side_nav_template": "includes/sidenav/sidenav_penro.html",
        "top_nav_template": "includes/topnav/topnav_penro.html",
    })


# ----------------- PENRO Create Account -----------------
@login_required
@role_required(['PENRO'])
def create_account_view(request):
    return render(request, 'PENRO/PENROI_create_account.html', {
        "side_nav_template": "includes/sidenav/sidenav_penro.html",
        "top_nav_template": "includes/topnav/topnav_penro.html",
    })


@login_required
@role_required(['PENRO'])
def penro_activity_logs(request):
    return render(request, 'PENRO/PENRO_activitylogs.html', {
        "side_nav_template": "includes/sidenav/sidenav_penro.html",
        "top_nav_template": "includes/topnav/topnav_penro.html",
    })


@login_required
@role_required(['PENRO'])
def penro_inventory(request):
    # Dummy data for notifications
    notifications = [
        {'id': 1, 'message': 'New report submitted', 'created_at': timezone.now()},
        {'id': 2, 'message': 'Account created successfully', 'created_at': timezone.now()},
    ]
    unread_count = len(notifications)

    # Dummy data for protected areas
    protected_areas = [
        {'id': 1, 'name': 'Protected Area 1'},
        {'id': 2, 'name': 'Protected Area 2'},
    ]

    # Dummy data for CCPL reports
    ccpl_reports = [
        {'enumerator': {'get_full_name': lambda: 'John Doe'}, 'profile': {'proponent_name': 'Proponent 1', 'report_date': timezone.now()}},
        {'enumerator': {'get_full_name': lambda: 'Jane Smith'}, 'profile': {'proponent_name': 'Proponent 2', 'report_date': timezone.now()}},
    ]

    return render(request, 'PENRO/PENRO_inventory.html', {
        'notifications': notifications,
        'unread_count': unread_count,
        'protected_areas': protected_areas,
        'ccpl_reports': ccpl_reports,
        "side_nav_template": "includes/sidenav/sidenav_penro.html",
        "top_nav_template": "includes/topnav/topnav_penro.html",
    })


@login_required
def mark_notification_read(request, notification_id):
    messages.success(request, f'Notification {notification_id} marked as read.')
    return redirect(request.META.get('HTTP_REFERER', 'PENRO_inventory'))


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
    return render(request, 'CENRO/CENRO_reports.html')

@login_required
@role_required(['CENRO'])
def cenro_templates(request):
    return render(request, 'CENRO/CENRO_templates.html')
