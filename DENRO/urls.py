# urls.py
from django.urls import path
from django.shortcuts import redirect
from . import views, operation

urlpatterns = [
    path('', lambda request: redirect('login')),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', operation.logout_user, name='logout'),

    # Registration
    path('register/', operation.create_account, name='account-create'),

    # Cascading select APIs
    path('api/penros/<int:region_id>/', operation.api_penros_by_region, name='api-penros-by-region'),
    path('api/cenros/<int:penro_id>/', operation.api_cenros_by_penro, name='api-cenros-by-penro'),

    # Dashboards
    path('sa/dashboard/',     views.superadmin_dashboard, name='SA-dashboard'),
    path('admin/dashboard/',  views.admin_dashboard,      name='Admin_dashboard'),

    path('penro/dashboard/',  views.penro_dashboard,      name='PENRO_dashboard'),
    # PENRO subpages
    path('penro/activity-logs/', views.penro_activity_logs, name='PENRO_activitylogs'),
    path('penro/inventory/', views.penro_inventory, name='PENRO_inventory'),
    path('penro/create-account/', views.create_account_view, name='PENRO_create_account'),
   
    path('cenro/dashboard/',  views.cenro_dashboard,      name='CENRO_dashboard'),
    # ✅ CENRO subpages (match the names used in your templates)
    path('cenro/activity-logs/', views.cenro_activitylogs, name='CENRO-activitylogs'),
    path('cenro/reports/',       views.cenro_reports,      name='CENRO-reports'),
    path('cenro/templates/',     views.cenro_templates,    name='CENRO-templates'),

    # Notification URL
    path('mark-notification-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
]

