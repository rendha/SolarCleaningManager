from django.urls import path
from django.contrib.auth import views as auth_views
 
from . import views
 
 
urlpatterns = [
 
    # =========================================================
    # LOGIN / LOGOUT / HOME
    # =========================================================
 
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='login.html',
            redirect_authenticated_user=True,
        ),
        name='login'
    ),
 
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),
 
    # "/" now decides where to go:
    # owner -> dashboard, employee -> My Jobs
    path(
        '',
        views.home_view,
        name='home'
    ),
 
    path(
        'sw.js',
        views.service_worker,
        name='service_worker'
    ),
 
 
    # =========================================================
    # EMPLOYEE PAGES
    # =========================================================
 
    path(
        'my-jobs/',
        views.my_schedule_view,
        name='my_schedule'
    ),
 
    path(
        'my-jobs/record/',
        views.employee_add_job_view,
        name='employee_add_job'
    ),
 
 
    # =========================================================
    # DASHBOARD (owner only)
    # Moved from '' to 'dashboard/' because '' is now home_view.
    # {% url 'dashboard' %} links keep working.
    # =========================================================
 
    path(
        'dashboard/',
        views.dashboard_view,
        name='dashboard'
    ),
 
 
    # =========================================================
    # CUSTOMERS
    # =========================================================
 
    path(
        'customers/',
        views.customer_list_view,
        name='customer_list'
    ),
 
    path(
        'customers/<int:pk>/',
        views.customer_detail_view,
        name='customer_detail'
    ),
 
 
    # =========================================================
    # CLEANING JOBS
    # =========================================================
 
    path(
        'add/',
        views.add_job_view,
        name='add_job'
    ),
 
    path(
        'jobs/',
        views.job_list_view,
        name='job_list'
    ),
 
    path(
        'job/<int:pk>/edit/',
        views.edit_job_view,
        name='edit_job'
    ),
 
    path(
        'job/<int:pk>/payment-status/',
        views.update_payment_status_view,
        name='update_payment_status'
    ),
 
 
    # =========================================================
    # MONTHLY REPORTS
    # =========================================================
 
    path(
        'reports/',
        views.monthly_reports_view,
        name='monthly_reports'
    ),
 
    path(
        'reports/<str:month>/',
        views.monthly_report_detail_view,
        name='monthly_report_detail'
    ),
 
 
    # =========================================================
    # SCHEDULING
    # =========================================================
 
    path(
        'schedule/',
        views.schedule_view,
        name='schedule'
    ),
 
    path(
        'schedule/add/',
        views.add_schedule_view,
        name='add_schedule'
    ),
 
    path(
        'schedule/<int:pk>/edit/',
        views.edit_schedule_view,
        name='edit_schedule'
    ),
 
    path(
        'schedule/<int:pk>/delete/',
        views.delete_schedule_view,
        name='delete_schedule'
    ),
 
    path(
        'schedule/<int:pk>/status/',
        views.update_schedule_status_view,
        name='update_schedule_status'
    ),
 
    path(
        'schedule/<int:pk>/reschedule/',
        views.reschedule_api,
        name='reschedule_api'
    ),
 
 
    # =========================================================
    # APIs
    # =========================================================
 
    path(
        'api/schedule/events/',
        views.schedule_events_api,
        name='schedule_events_api'
    ),
 
    path(
        'api/customer/<int:customer_id>/sites/',
        views.customer_sites_api,
        name='customer_sites_api'
    ),
 
 
    # =========================================================
    # CANVASSING / LOCATION SEARCH
    # =========================================================
 
    path(
        'canvassing/',
        views.canvassing_view,
        name='canvassing'
    ),
 
]