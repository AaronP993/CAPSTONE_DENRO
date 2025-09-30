# views.py
from django.shortcuts import render, redirect
from .operation import login_user, create_account  # uses Postgres functions under the hood
from .decorators import login_required, role_required, can_create_users

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
    return render(request, 'CENRO/CENRO_reports.html')

@login_required
@role_required(['CENRO'])
def cenro_templates(request):
    return render(request, 'CENRO/CENRO_templates.html')