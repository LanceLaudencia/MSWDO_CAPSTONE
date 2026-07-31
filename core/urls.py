from django.urls import path
from . import views
from .views import test_api
from .views import dashboard_data


from .import views

urlpatterns = [
    path('', views.landing, name='landing'),

    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('verify/', views.verify, name='verify'),

    path('admin_account/', views.admin_account, name='admin_account'),
    path('update_staff/<int:staff_id>/', views.update_staff, name='update_staff'),
    path('select_account/', views.select_account, name='select_account'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('add-client/', views.add_client, name='add_client'),

    # API endpoints
    path('api/program-counts/', views.api_program_counts, name='api_program_counts'),
    path('api/status-counts/', views.api_status_counts, name='api_status_counts'),

    # Assistance Program
    path('assistance/', views.assistance_program, name='assistance_program'),
    path('assistance/<str:program>/', views.assistance_program, name='assistance_program_program'),

    # Applications
    path('application/<int:pk>/', views.application_detail, name='application_detail'),
    path('application/<int:pk>/delete/', views.application_delete, name='application_delete'),

    # documents
    path('document/<int:doc_id>/download/', views.document_download, name='document_download'),
    
  path("staff_account/", views.staff_account, name="staff_account"),
  
  path("predict/", views.ml_predict_view, name="predict"),
  
  path("pending/", views.pending_applications, name="pending_applications"),

  path('client/<int:pk>/', views.client_detail, name='client_view'),
  path('client/<int:pk>/delete/', views.client_delete, name='client_delete'),
  path("toggle_staff/<int:staff_id>/", views.toggle_staff_status, name="toggle_staff"),


   
  path("api/dashboard/", dashboard_data, name="dashboard_data"),

  path('api/test/', test_api, name='test_api'),

    # Application actions
  path('application/<int:pk>/approve/', views.application_approve, name='application_approve'),
  path('application/<int:pk>/reject/', views.application_reject, name='application_reject'),
  path('application/<int:pk>/edit/', views.application_edit, name='application_edit'),
path("assistance/", views.assistance_program, name="assistance_program"),

  path('application/<int:pk>/approve/', views.approve_application, name='approve_application'),
path('application/<int:pk>/reject/', views.reject_application, name='reject_application'),
path('application/<int:pk>/release/', views.release_application, name='release_application'),
path('staff/<int:staff_id>/reset_password/', views.reset_staff_password, name='reset_staff_password'),
path('staff/<int:staff_id>/edit_role/', views.edit_staff_role, name='edit_staff_role'),
 path('staff/<int:staff_id>/activity_logs/', views.staff_activity_logs, name='staff_activity_logs'),

#client
path('client-login/', views.client_login, name='client_login'),
path('client-dashboard/', views.client_dashboard, name='client_dashboard'),
path("client/register/", views.client_register, name="client_register"),
path('client/profile/edit/', views.client_edit_profile, name='client_edit_profile'),
    path('client/applications/', views.client_applications, name='client_applications'),
    path('client/apply/', views.client_apply_program, name='client_apply_program'),
path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),

 path('access/', views.access_code_view, name='access_code'),

 path('notifications/json/', views.get_notifications_json, name='notifications_json'),
path('application/<int:pk>/advance/', views.application_advance, name='application_advance'),

 # Staff
path('reports/submit/',           views.report_submit,     name='report_submit'),
path('reports/my/',               views.my_reports,        name='my_reports'),
path('reports/my/<int:pk>/',      views.my_report_detail,  name='my_report_detail'),

# Admin
path('reports/',                  views.reports_dashboard, name='reports_dashboard'),
path('reports/<int:pk>/',         views.report_detail,     name='report_detail'),
path('reports/<int:pk>/approve/', views.report_approve,    name='report_approve'),
path('reports/<int:pk>/decline/', views.report_decline,    name='report_decline'),

path('reports/generate/', views.generate_report, name='generate_report'),

path('reports/generate/', views.generate_report, name='generate_report'),
    path('program-prediction/', views.program_rate_prediction, name='program_rate_prediction'),
    
    path('analytics/barangay/', views.barangay_analytics, name='barangay_analytics'),
    
    
    path('client/verify/', views.client_verify, name='client_verify'),
path('client/resend-verification/', views.resend_client_verification, name='resend_client_verification'),

path('account/update-profile/', views.admin_update_profile, name='admin_update_profile'),
path('account/change-password/', views.admin_change_password, name='admin_change_password'),

path('staff/<int:staff_id>/change-password/', views.change_staff_password, name='change_staff_password'),
]



