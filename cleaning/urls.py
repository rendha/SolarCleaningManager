from django.urls import path
from . import views


urlpatterns = [

    path(
        'sw.js',
        views.service_worker,
        name='service_worker'
    ),

    # =========================================================
    # DASHBOARD
    # =========================================================

    path(
        '',
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

    # IMPORTANT:
    # This fixes the NoReverseMatch error from the monthly report.
    #
    # Your customer detail view must exist in views.py.
    #
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
    # SCHEDULE API
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