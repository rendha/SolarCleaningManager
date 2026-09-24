from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from datetime import datetime
from .models import Customer,Site,CleaningJob, JobExpense,CanvassingLocation,CleaningSchedule
from .forms import CleaningJobForm, JobExpenseFormSet,CleaningScheduleForm
from django.http import JsonResponse
import re
import math
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST

def health_check(request):
    return JsonResponse({"status": "ok"})

def dashboard_view(request):
    selected_month = request.GET.get('month')
    
    jobs = CleaningJob.objects.all()
    if selected_month:
        jobs = jobs.filter(date__startswith=selected_month)

    total_cleanings = jobs.count()
    paid_count = jobs.filter(is_free=False, payment_status='Paid').count()
    unpaid_count = jobs.filter(is_free=False, payment_status='Unpaid').count()
    free_count = jobs.filter(is_free=True).count()
    
    total_revenue = float(jobs.aggregate(Sum('revenue'))['revenue__sum'] or 0.00)
    total_expenses = float(jobs.aggregate(Sum('total_expenses'))['total_expenses__sum'] or 0.00)
    total_profit = total_revenue - total_expenses
    
    outstanding_amount = float(jobs.filter(is_free=False, payment_status='Unpaid').aggregate(Sum('revenue'))['revenue__sum'] or 0.00)
    
    outstanding_amount = jobs.filter(is_free=False, payment_status='Unpaid').aggregate(Sum('revenue'))['revenue__sum'] or 0.00

    context = {
        'total_cleanings': total_cleanings,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'free_count': free_count,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,
        'outstanding_amount': outstanding_amount,
        'selected_month': selected_month,
    }
    return render(request, 'dashboard.html', context)


def add_job_view(request):

    if request.method == 'POST':

        print("\n==============================")
        print("ADD CLEANING POST RECEIVED")
        print("==============================")
        print("POST DATA:", request.POST)

        form = CleaningJobForm(request.POST)

        if form.is_valid():

            print("MAIN FORM: VALID")

            job = form.save(commit=False)

            print("Customer:", job.customer)
            print("Site:", job.site)
            print("Date:", job.date)
            print("Cleaning number:", job.cleaning_number)

            formset = JobExpenseFormSet(
                request.POST,
                instance=job
            )

            if formset.is_valid():

                print("EXPENSE FORMSET: VALID")

                try:

                    with transaction.atomic():

                        # Save cleaning job
                        job.save()

                        print("CLEANING JOB SAVED!")
                        print("JOB ID:", job.id)

                        # Save expenses
                        expenses = formset.save(commit=False)

                        total_exp = 0

                        for exp in expenses:

                            exp.job = job
                            exp.save()

                            print(
                                "EXPENSE SAVED:",
                                exp.expense_name,
                                exp.cost
                            )

                            total_exp += float(exp.cost or 0)

                        # Handle deleted expenses
                        for exp in formset.deleted_objects:
                            exp.delete()

                        job.total_expenses = total_exp

                        job.net_profit = (
                            float(job.revenue or 0)
                            - total_exp
                        )

                        job.save()

                        print("FINAL JOB SAVED!")
                        print("Revenue:", job.revenue)
                        print("Expenses:", job.total_expenses)
                        print("Profit:", job.net_profit)

                    messages.success(
                        request,
                        f"Cleaning saved successfully! Job #{job.id}"
                    )

                    return redirect('job_list')

                except Exception as e:

                    print("\n!!!!!!!!!!!!!!!!!!!!!!!!")
                    print("SAVE ERROR")
                    print("!!!!!!!!!!!!!!!!!!!!!!!!")
                    print(repr(e))

                    messages.error(
                        request,
                        f"Could not save cleaning: {str(e)}"
                    )

            else:

                print("EXPENSE FORMSET: INVALID")
                print("FORMSET ERRORS:", formset.errors)

                messages.error(
                    request,
                    "Please fix the expense errors."
                )

        else:

            print("MAIN FORM: INVALID")
            print("FORM ERRORS:", form.errors)

            messages.error(
                request,
                "Please fix the errors in the cleaning form."
            )

    else:

        form = CleaningJobForm(
            initial={
                'date': datetime.now().date()
            }
        )

        formset = JobExpenseFormSet()

    return render(
        request,
        'add_job.html',
        {
            'form': form,
            'formset': formset
        }
    )
def job_list_view(request):

    query = request.GET.get('q', '').strip()

    jobs = CleaningJob.objects.select_related(
        'customer',
        'site'
    ).prefetch_related(
        'expenses'
    ).all().order_by('-date')

    if query:
        jobs = jobs.filter(
            Q(customer__name__icontains=query) |
            Q(customer__contact_person__icontains=query) |
            Q(customer__phone__icontains=query) |
            Q(site__location__icontains=query) |
            Q(site__address__icontains=query) |
            Q(site__solar_kw__icontains=query) |
            Q(cleaning_number__icontains=query)
        )

    return render(
        request,
        'job_list.html',
        {
            'jobs': jobs,
            'query': query,
        }
    )

def edit_job_view(request, pk):
    job = get_object_or_404(CleaningJob, pk=pk)
    if request.method == 'POST':
        form = CleaningJobForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save(commit=False)
            formset = JobExpenseFormSet(request.POST, instance=job)
            if formset.is_valid():
                job.save()
                
                # Re-calculate expenses
                expenses = formset.save(commit=False)
                total_exp = 0.00
                for exp in expenses:
                    exp.job = job
                    exp.save()
                    total_exp += float(exp.cost)
                
                job.total_expenses = total_exp
                job.net_profit = float(job.revenue) - job.total_expenses
                job.save()
                
                return redirect('job_list')
    else:
        form = CleaningJobForm(instance=job)
        formset = JobExpenseFormSet(instance=job)

    return render(request, 'add_job.html', {'form': form, 'formset': formset})    


def schedule_view(request):
    upcoming_jobs = CleaningJob.objects.filter(job_status='Scheduled').order_by('date')
    return render(request,'schedule.html',{'upcomming_jobs': upcoming_jobs})   


def monthly_reports_view(request):
    jobs = CleaningJob.objects.select_related(
        'customer',
        'site'
    ).prefetch_related(
        'expenses'
    ).order_by('-date')

    # --------------------------------------------------
    # ALL-TIME TOTALS
    # --------------------------------------------------

    all_time_revenue = jobs.aggregate(
        total=Sum('revenue')
    )['total'] or 0

    all_time_expenses = jobs.aggregate(
        total=Sum('total_expenses')
    )['total'] or 0

    all_time_profit = all_time_revenue - all_time_expenses

    all_time_cleanings = jobs.count()

    all_time_paid = jobs.filter(
        is_free=False,
        payment_status='Paid'
    ).count()

    all_time_unpaid = jobs.filter(
        is_free=False,
        payment_status='Unpaid'
    ).count()

    all_time_free = jobs.filter(
        is_free=True
    ).count()

    all_time_outstanding = jobs.filter(
        is_free=False,
        payment_status='Unpaid'
    ).aggregate(
        total=Sum('revenue')
    )['total'] or 0


    # --------------------------------------------------
    # MONTHLY REPORTS
    # --------------------------------------------------

    reports = {}

    for job in jobs:

        if not job.date:
            continue

        month_key = job.date.strftime('%Y-%m')

        month_name = job.date.strftime('%B %Y')

        if month_key not in reports:

            reports[month_key] = {
                'month': month_key,
                'month_name': month_name,

                'revenue': 0,
                'expenses': 0,
                'profit': 0,

                'cleanings': 0,
                'paid_count': 0,
                'unpaid_count': 0,
                'free_count': 0,

                'outstanding': 0,

                'jobs': [],
            }


        report = reports[month_key]

        # Financials
        report['revenue'] += float(job.revenue or 0)
        report['expenses'] += float(job.total_expenses or 0)
        report['profit'] += float(job.net_profit or 0)

        # Counts
        report['cleanings'] += 1

        if job.is_free:

            report['free_count'] += 1

        elif job.payment_status == 'Paid':

            report['paid_count'] += 1

        else:

            report['unpaid_count'] += 1

            report['outstanding'] += float(
                job.revenue or 0
            )


        # Add job to month
        report['jobs'].append(job)


    # Convert dictionary to list
    reports = list(reports.values())


    # Sort newest month first
    reports.sort(
        key=lambda x: x['month'],
        reverse=True
    )


    context = {

        # Monthly reports
        'reports': reports,

        # All-time
        'all_time_revenue': all_time_revenue,
        'all_time_expenses': all_time_expenses,
        'all_time_profit': all_time_profit,
        'all_time_cleanings': all_time_cleanings,

        'all_time_paid': all_time_paid,
        'all_time_unpaid': all_time_unpaid,
        'all_time_free': all_time_free,

        'all_time_outstanding': all_time_outstanding,
    }

    return render(
        request,
        'monthly_reports.html',
        context
    )


def monthly_report_detail_view(request, month):
    """
    Shows all cleaning jobs and expenses for one month.
    Example:
    /monthly-reports/2026-09/
    """

    try:
        year, month_number = month.split('-')

        year = int(year)
        month_number = int(month_number)

    except (ValueError, AttributeError):

        return redirect('monthly_reports')


    jobs = CleaningJob.objects.filter(
        date__year=year,
        date__month=month_number
    ).select_related(
        'customer',
        'site'
    ).prefetch_related(
        'expenses'
    ).order_by('-date')


    # --------------------------------------------------
    # MONTH TOTALS
    # --------------------------------------------------

    total_cleanings = jobs.count()

    total_revenue = jobs.aggregate(
        total=Sum('revenue')
    )['total'] or 0

    total_expenses = jobs.aggregate(
        total=Sum('total_expenses')
    )['total'] or 0

    total_profit = total_revenue - total_expenses


    paid_count = jobs.filter(
        is_free=False,
        payment_status='Paid'
    ).count()


    unpaid_count = jobs.filter(
        is_free=False,
        payment_status='Unpaid'
    ).count()


    free_count = jobs.filter(
        is_free=True
    ).count()


    outstanding = jobs.filter(
        is_free=False,
        payment_status='Unpaid'
    ).aggregate(
        total=Sum('revenue')
    )['total'] or 0


    # --------------------------------------------------
    # EXPENSE BREAKDOWN
    # --------------------------------------------------

    expense_items = []

    total_manual_expenses = 0

    for job in jobs:

        for expense in job.expenses.all():

            cost = float(expense.cost or 0)

            total_manual_expenses += cost

            expense_items.append({
                'date': job.date,
                'customer': job.customer,
                'site': job.site,
                'job': job,
                'expense': expense,
            })


    month_name = jobs.first().date.strftime(
        '%B %Y'
    ) if jobs.exists() else f'{year}-{month_number:02d}'


    context = {

        'month': month,
        'month_name': month_name,

        'jobs': jobs,

        'total_cleanings': total_cleanings,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,

        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'free_count': free_count,

        'outstanding': outstanding,

        'expense_items': expense_items,
        'total_manual_expenses': total_manual_expenses,
    }


    return render(
        request,
        'monthly_report_detail.html',
        context
    )    

def customer_list_view(request):
    customers = Customer.objects.prefetch_related('sites').all().order_by('name')

    query = request.GET.get('q', '').strip()

    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(contact_person__icontains=query) |
            Q(phone__icontains=query)
        )

    return render(
        request,
        'customer_list.html',
        {
            'customers': customers,
            'query': query,
        }
    )


def customer_detail_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    sites = customer.sites.all().order_by('location')

    jobs = customer.cleaning_jobs.all().order_by('-date')

    total_revenue = jobs.aggregate(
        total=Sum('revenue')
    )['total'] or 0

    total_expenses = jobs.aggregate(
        total=Sum('total_expenses')
    )['total'] or 0

    total_profit = total_revenue - total_expenses

    paid_jobs = jobs.filter(
        is_free=False,
        payment_status='Paid'
    ).count()

    unpaid_jobs = jobs.filter(
        is_free=False,
        payment_status='Unpaid'
    ).count()

    free_jobs = jobs.filter(
        is_free=True
    ).count()

    outstanding = jobs.filter(
        is_free=False,
        payment_status='Unpaid'
    ).aggregate(
        total=Sum('revenue')
    )['total'] or 0

    context = {
        'customer': customer,
        'sites': sites,
        'jobs': jobs,

        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'total_profit': total_profit,

        'paid_jobs': paid_jobs,
        'unpaid_jobs': unpaid_jobs,
        'free_jobs': free_jobs,

        'outstanding': outstanding,
    }

    return render(
        request,
        'customer_detail.html',
        context
    )



def customer_sites_api(request, customer_id):

    sites = (
        Site.objects
        .filter(
            customer_id=customer_id
        )
        .order_by('location')
    )

    data = []

    for site in sites:

        data.append({
            'id': site.id,
            'location': site.location,
            'address': site.address,
            'solar_kw': site.solar_kw,
            'google_map_link': site.google_map_link,
        })

    return JsonResponse({
        'sites': data
    })


def canvassing_view(request):

    query = request.GET.get('q', '').strip()

    matching_customers = Customer.objects.none()
    matching_sites = Site.objects.none()
    nearby_sites = Site.objects.none()

    nearest_sites = []

    if query:

        # =================================================
        # 1. FIND CUSTOMERS MATCHING SEARCH
        # =================================================

        matching_customers = Customer.objects.filter(
            Q(name__icontains=query) |
            Q(contact_person__icontains=query) |
            Q(phone__icontains=query)
        ).prefetch_related('sites').distinct()


        # =================================================
        # 2. FIND SITES MATCHING SEARCH
        # =================================================

        matching_sites = Site.objects.filter(
            Q(location__icontains=query) |
            Q(address__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(customer__contact_person__icontains=query) |
            Q(customer__phone__icontains=query)
        ).select_related('customer').distinct()


        # =================================================
        # 3. SOURCE SITES
        # =================================================

        source_sites = Site.objects.filter(
            Q(location__icontains=query) |
            Q(address__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(customer__contact_person__icontains=query) |
            Q(customer__phone__icontains=query)
        ).select_related('customer').distinct()


        # =================================================
        # 4. LOCATION WORD MATCHING
        # =================================================

        location_words = set()

        ignored_words = {
            'PO',
            'P',
            'H',
            'HOUSE',
            'ROAD',
            'RD',
            'STREET',
            'ST',
            'POST',
            'DIST',
            'DISTRICT',
            'KERALA',
            'KOZHIKODE',
            'CALICUT',
            'PIN',
            'NEAR',
            'OPP',
            'OPPOSITE'
        }

        for site in source_sites:

            text = f"{site.location} {site.address}".upper()

            words = re.findall(
                r'[A-Z0-9]+',
                text
            )

            for word in words:

                if (
                    len(word) >= 4
                    and word not in ignored_words
                ):
                    location_words.add(word)


        # =================================================
        # 5. FIND CUSTOMERS IN SAME AREA
        # =================================================

        all_sites = Site.objects.select_related(
            'customer'
        ).all()

        nearby_ids = []

        source_customer_ids = set(
            source_sites.values_list(
                'customer_id',
                flat=True
            )
        )

        for site in all_sites:

            # Don't show searched customer
            if site.customer_id in source_customer_ids:
                continue

            site_text = (
                f"{site.location} "
                f"{site.address}"
            ).upper()

            site_words = set(
                re.findall(
                    r'[A-Z0-9]+',
                    site_text
                )
            )

            if location_words.intersection(site_words):

                nearby_ids.append(site.id)


        nearby_sites = Site.objects.filter(
            id__in=nearby_ids
        ).select_related(
            'customer'
        ).order_by(
            'location',
            'customer__name'
        )


        # =================================================
        # 6. HAVERSINE DISTANCE CALCULATION
        # =================================================

        EARTH_RADIUS_KM = 6371.0

        def calculate_distance(
            lat1,
            lon1,
            lat2,
            lon2
        ):

            lat1 = math.radians(lat1)
            lon1 = math.radians(lon1)

            lat2 = math.radians(lat2)
            lon2 = math.radians(lon2)

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = (
                math.sin(dlat / 2) ** 2
                +
                math.cos(lat1)
                * math.cos(lat2)
                * math.sin(dlon / 2) ** 2
            )

            c = 2 * math.atan2(
                math.sqrt(a),
                math.sqrt(1 - a)
            )

            return EARTH_RADIUS_KM * c


        # =================================================
        # 7. FIND REFERENCE SITE
        # =================================================

        reference_site = None

        for site in source_sites:

            if (
                site.latitude is not None
                and site.longitude is not None
            ):
                reference_site = site
                break


        # =================================================
        # 8. FIND 10 NEAREST CUSTOMERS
        # =================================================

        if reference_site:

            sites_with_coordinates = (
                Site.objects
                .filter(
                    latitude__isnull=False,
                    longitude__isnull=False
                )
                .exclude(
                    customer_id__in=source_customer_ids
                )
                .select_related('customer')
            )


            # Keep only the nearest site for each customer

            nearest_by_customer = {}


            for site in sites_with_coordinates:

                distance = calculate_distance(
                    reference_site.latitude,
                    reference_site.longitude,
                    site.latitude,
                    site.longitude
                )

                customer_id = site.customer_id


                if (
                    customer_id not in nearest_by_customer
                    or
                    distance <
                    nearest_by_customer[customer_id]['distance']
                ):

                    nearest_by_customer[customer_id] = {
                        'site': site,
                        'distance': distance
                    }


            # Convert to list

            calculated_sites = list(
                nearest_by_customer.values()
            )


            # Sort nearest → farthest

            calculated_sites.sort(
                key=lambda x: x['distance']
            )


            # Round distance for display

            nearest_sites = []

            for item in calculated_sites[:10]:

                nearest_sites.append({
                    'site': item['site'],
                    'distance': round(
                        item['distance'],
                        2
                    )
                })


    # =================================================
    # CONTEXT
    # =================================================

    context = {

        'query': query,

        'matching_customers':
            matching_customers,

        'matching_sites':
            matching_sites,

        'nearby_sites':
            nearby_sites,

        'nearest_sites':
            nearest_sites,
    }


    return render(
        request,
        'canvassing.html',
        context
    )



def add_schedule_view(request):

    if request.method == 'POST':

        form = CleaningScheduleForm(request.POST)

        if form.is_valid():

            schedule = form.save()

           

            return redirect('schedule')

       

    else:

        form = CleaningScheduleForm(
            initial={
                'scheduled_date': datetime.now().date(),
                'status': 'Scheduled',
            }
        )

    return render(
        request,
        'schedule_form.html',
        {
            'form': form,
            'title': 'Add Cleaning Schedule',
            'button_text': 'Save Schedule',
        }
    )

def edit_schedule_view(request, pk):

    schedule = get_object_or_404(
        CleaningSchedule,
        pk=pk
    )

    if request.method == 'POST':

        form = CleaningScheduleForm(
            request.POST,
            instance=schedule
        )

        if form.is_valid():

            schedule = form.save()

           

            return redirect('schedule')



    else:

        form = CleaningScheduleForm(
            instance=schedule
        )

    return render(
        request,
        'schedule_form.html',
        {
            'form': form,
            'title': 'Edit Cleaning Schedule',
            'button_text': 'Update Schedule',
            'schedule': schedule,
        }
    )

@require_POST
def delete_schedule_view(request, pk):

    schedule = get_object_or_404(
        CleaningSchedule,
        pk=pk
    )

    customer_name = schedule.get_customer_name()

    schedule.delete()

    messages.success(
        request,
        f"Schedule for {customer_name} deleted."
    )

    return redirect('schedule')    


@require_POST
def update_schedule_status_view(request, pk):

    schedule = get_object_or_404(
        CleaningSchedule,
        pk=pk
    )

    new_status = request.POST.get('status')

    valid_statuses = dict(
        CleaningSchedule.STATUS_CHOICES
    )

    if new_status not in valid_statuses:

        return JsonResponse(
            {
                'success': False,
                'error': 'Invalid status.'
            },
            status=400
        )

    schedule.status = new_status
    schedule.save(update_fields=[
        'status',
        'updated_at',
    ])

    return JsonResponse({
        'success': True,
        'status': schedule.status,
    })    



def schedule_events_api(request):

    schedules = (
        CleaningSchedule.objects
        .select_related(
            'customer',
            'site'
        )
        .all()
    )

    events = []

    status_colors = {
        'Scheduled': '#3B73B9',
        'Completed': '#28a745',
        'Rescheduled': '#f0ad4e',
        'Cancelled': '#dc3545',
    }

    for schedule in schedules:

        customer_name = schedule.get_customer_name()

        location = schedule.get_location()

        if schedule.scheduled_time:

            start = (
                f"{schedule.scheduled_date.isoformat()}"
                f"T{schedule.scheduled_time.strftime('%H:%M:%S')}"
            )

        else:

            start = schedule.scheduled_date.isoformat()

        events.append({

            'id': str(schedule.id),

            'title': customer_name,

            'start': start,

            'allDay': (
                schedule.scheduled_time is None
            ),

            'backgroundColor': (
                status_colors.get(
                    schedule.status,
                    '#3B73B9'
                )
            ),

            'borderColor': (
                status_colors.get(
                    schedule.status,
                    '#3B73B9'
                )
            ),

            'extendedProps': {

                'customer_name':
                    customer_name,

                'phone':
                    schedule.phone
                    or (
                        schedule.customer.phone
                        if schedule.customer
                        else ''
                    ),

                'location':
                    location or '',

                'address':
                    (
                        schedule.site.address
                        if schedule.site
                        else schedule.address
                    ) or '',

                'status':
                    schedule.status,

                'notes':
                    schedule.notes or '',

                'edit_url':
                    f"/schedule/{schedule.id}/edit/",

                'delete_url':
                    f"/schedule/{schedule.id}/delete/",
            }
        })

    return JsonResponse(
        events,
        safe=False
    )


@require_POST
def reschedule_api(request, pk):

    schedule = get_object_or_404(
        CleaningSchedule,
        pk=pk
    )

    new_date = request.POST.get('date')
    new_time = request.POST.get('time')

    if not new_date:

        return JsonResponse(
            {
                'success': False,
                'error': 'Date is required.'
            },
            status=400
        )

    try:

        schedule.scheduled_date = datetime.strptime(
            new_date,
            '%Y-%m-%d'
        ).date()

        if new_time:

            schedule.scheduled_time = datetime.strptime(
                new_time,
                '%H:%M'
            ).time()

        schedule.status = 'Rescheduled'

        schedule.save()

        return JsonResponse({
            'success': True,
            'date': schedule.scheduled_date.isoformat(),
            'time': (
                schedule.scheduled_time.strftime('%H:%M')
                if schedule.scheduled_time
                else None
            ),
            'status': schedule.status,
        })

    except ValueError:

        return JsonResponse(
            {
                'success': False,
                'error': 'Invalid date or time.'
            },
            status=400
        )

def service_worker(request):

    sw_content = """
const CACHE_NAME = "solarclean-manager-v1";

const APP_SHELL = [
    "/",
    "/static/manifest.json",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png"
];

self.addEventListener("install", event => {

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(APP_SHELL))
    );

    self.skipWaiting();
});


self.addEventListener("activate", event => {

    event.waitUntil(

        caches.keys().then(cacheNames => {

            return Promise.all(

                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))

            );

        })

    );

    self.clients.claim();
});


self.addEventListener("fetch", event => {

    event.respondWith(

        fetch(event.request)
            .catch(() => caches.match(event.request))

    );

});
"""

    return HttpResponse(
        sw_content,
        content_type="application/javascript"
    )
