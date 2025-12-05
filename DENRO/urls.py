# urls.py
from django.urls import path
from django.shortcuts import redirect
from . import views, operation

urlpatterns = [
    path('', lambda request: redirect('login')),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', operation.logout_user, name='logout'),

    # Registration - Updated to use the decorated view
    path('register/', views.create_account_view, name='account-create'),

    # Cascading select APIs
    path('api/penros/<int:region_id>/', operation.api_penros_by_region, name='api-penros-by-region'),
    path('api/cenros/<int:penro_id>/', operation.api_cenros_by_penro, name='api-cenros-by-penro'),

    # Dashboards
    path('sa/dashboard/',     views.superadmin_dashboard, name='SA-dashboard'),
    path('sa/region-admin-management/', views.region_admin_management_view, name='sa-region-admin-management'),
    path('sa/pending-registration/', views.pending_registration_view, name='sa-pending-registration'),
    path('sa/authentication-logs/', views.authentication_logs_view, name='sa-authentication-logs'),
    path('sa/activity-logs/', views.activity_logs_view, name='sa-activity-logs'),
    path('sa/all-users/', views.all_users_view, name='sa-all-users'),
    path('sa/profile/', views.profile_view, name='sa-profile'),
    path('admin/dashboard/',  views.admin_dashboard,      name='Admin-dashboard'),
    path('penro/dashboard/',  views.penro_dashboard,      name='PENRO-dashboard'),
    path('cenro/dashboard/',  views.cenro_dashboard,      name='CENRO-dashboard'),

    # CENRO subpages 
    path('cenro/activity-logs/', views.cenro_activitylogs, name='CENRO-activitylogs'),
    path('cenro/reports/',       views.cenro_reports,      name='CENRO-reports'),
    path('cenro/reports/<int:report_id>/details/', views.cenro_report_details, name='CENRO-report-details'),
    path('cenro/templates/',     views.cenro_templates,    name='CENRO-templates'),



    path("cenro/activity-logs/", views.cenro_activitylogs, name="cenro_activity_logs"),
    path('penro/activity-logs/', views.penro_activitylogs, name='PENRO-activitylogs'),


# SUPER ADMIN ROUTES
path('sa/dashboard/', views.superadmin_dashboard, name='SA-dashboard'),
path('sa/region-admin-management/', views.region_admin_management_view, name='sa-region-admin-management'),
path('sa/pending-registration/', views.pending_registration_view, name='sa-pending-registration'),
path('sa/authentication-logs/', views.authentication_logs_view, name='sa-authentication-logs'),
path('sa/activity-logs/', views.activity_logs_view, name='sa-activity-logs'),
path('sa/all-users/', views.all_users_view, name='sa-all-users'),
path('sa/profile/', views.profile_view, name='sa-profile'),

]