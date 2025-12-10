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
    path('admin/dashboard/',  views.admin_dashboard,      name='Admin-dashboard'),
    path('penro/dashboard/',  views.penro_dashboard,      name='PENRO-dashboard'),
    path('cenro/dashboard/',  views.cenro_dashboard,      name='CENRO-dashboard'),

    # Super Admin subpages
    path('sa/region-admin-management/', views.sa_region_admin_management, name='sa-region-admin-management'),
    path('sa/pending-registration/', views.sa_pending_registration, name='sa-pending-registration'),
    path('sa/authentication-logs/', views.sa_authentication_logs, name='sa-authentication-logs'),
    path('sa/activity-logs/', views.sa_activity_logs, name='sa-activity-logs'),
    path('sa/all-users/', views.sa_all_users, name='sa-all-users'),
    path('sa/profile/', views.sa_profile, name='sa-profile'),

    # CENRO subpages 
    path('cenro/activity-logs/', views.cenro_activitylogs, name='CENRO-activitylogs'),
    path('cenro/reports/',       views.cenro_reports,      name='CENRO-reports'),
    
    # PENRO subpages
    path('penro/activity-logs/', views.penro_activitylogs, name='PENRO-activitylogs'),
    path('penro/reports/', views.penro_reports, name='PENRO-reports'),
    path('penro/user-management/', views.penro_usermanagement, name='PENRO-usermanagement'),
    path('penro/profile/', views.penro_profile, name='PENRO-profile'),
    path('cenro/reports/export/', views.cenro_export_reports, name='CENRO-reports-export'),
    path('cenro/reports/<int:report_id>/details/', views.cenro_report_details, name='CENRO-report-details'),
    path('cenro/reports/<int:report_id>/attest/', views.cenro_attest_report, name='CENRO-report-attest'),
    path('cenro/reports/<int:report_id>/note/', views.cenro_note_report, name='CENRO-report-note'),
    path('cenro/templates/',     views.cenro_templates,    name='CENRO-templates'),
    path("cenro/activity-logs/", views.cenro_activitylogs, name="cenro_activity_logs"),

    #Admin Subpages
    path('admin/protected-areas/', views.protected_areas, name='protected-areas'),
    path('admin/protected-areas/convert/<path:file_path>/', views.convert_shapefile_to_geojson, name='convert-shapefile'),

]