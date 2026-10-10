from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta
from .models import Customer,Site,CleaningJob, JobExpense,CanvassingLocation,CleaningSchedule
from .forms import CleaningJobForm, JobExpenseFormSet,CleaningScheduleForm,EmployeeJobForm
from django.http import JsonResponse
import re
import math
import time
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, login_not_required
from .permissions import owner_required
from .geo import coords_from_text, geocode_place, place_names_near, distance_km, looks_like_link, text_matches


@owner_required
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


@owner_required
def add_job_view(request):

    if request.method == 'POST':

        form = CleaningJobForm(request.POST)
        formset = JobExpenseFormSet(request.POST)

        if form.is_valid() and formset.is_valid():

            try:
                with transaction.atomic():

                    job = form.save(commit=False)
                    data = form.cleaned_data

                    # ----- Create customer + site for a non-customer -----
                    if data.get('new_customer'):

                        customer = Customer.objects.create(
                            name=data['new_customer_name'],
                            phone=data.get('new_phone', ''),
                        )

                        site = Site.objects.create(
                            customer=customer,
                            location=data.get('new_location', ''),
                            address=data.get('new_address', ''),
                            solar_kw=data.get('new_solar_kw', ''),
                            google_map_link=data.get('new_map_link', ''),
                            first_cleaning_done=True,
                            first_cleaning_date=job.date,
                        )

                        job.customer = customer
                        job.site = site

                    job.save()   # revenue calculated in model.save()

                    # ----- Expenses -----
                    formset.instance = job
                    expenses = formset.save()

                    job.total_expenses = sum(float(e.cost or 0) for e in expenses)
                    job.net_profit = float(job.revenue or 0) - job.total_expenses
                    job.save()

                messages.success(request, f"Cleaning saved successfully! Job #{job.id}")
                return redirect('job_list')

            except Exception as e:
                messages.error(request, f"Could not save cleaning: {e}")

        else:
            messages.error(request, "Please fix the errors in the form.")

    else:
        form = CleaningJobForm(initial={'date': datetime.now().date()})
        formset = JobExpenseFormSet()

    return render(request, 'add_job.html', {'form': form, 'formset': formset})


@owner_required
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


@require_POST
@owner_required
def update_payment_status_view(request, pk):

    job = get_object_or_404(
        CleaningJob,
        pk=pk
    )

    new_status = request.POST.get('payment_status')

    if new_status not in ['Paid', 'Unpaid']:

        return JsonResponse({
            'success': False,
            'error': 'Invalid payment status.'
        }, status=400)

    job.payment_status = new_status
    job.save(update_fields=['payment_status'])

    return JsonResponse({
        'success': True,
        'payment_status': job.payment_status
    })  


@owner_required
def edit_job_view(request, pk):
    job = get_object_or_404(CleaningJob, pk=pk)
    if request.method == 'POST':
        form = CleaningJobForm(request.POST, instance=job)
        formset = JobExpenseFormSet(request.POST, instance=job)
        if form.is_valid() and formset.is_valid():
            job = form.save(commit=False)
            job.save()
            
            # Re-calculate expenses
            expenses = formset.save(commit=False)
            for exp in expenses:
                exp.job = job
                exp.save()
            for exp in formset.deleted_objects:
                exp.delete()

            total_exp = sum(float(e.cost or 0) for e in job.expenses.all())
            
            job.total_expenses = total_exp
            job.net_profit = float(job.revenue or 0) - total_exp
            job.save()
            
            return redirect('job_list')
    else:
        form = CleaningJobForm(instance=job)
        formset = JobExpenseFormSet(instance=job)

    return render(request, 'add_job.html', {'form': form, 'formset': formset})    


@owner_required
def schedule_view(request):
    upcoming_jobs = CleaningJob.objects.filter(job_status='Scheduled').order_by('date')
    return render(request,'schedule.html',{'upcomming_jobs': upcoming_jobs})   


@owner_required
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


@owner_required
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


@owner_required
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


@owner_required
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


@owner_required
def canvassing_view(request):
    """
    Find existing installations near a new client.

    The search box accepts:
      - a Google Maps link (long or short maps.app.goo.gl link)
      - coordinates like "11.2588, 75.7804"
      - a place name, e.g. "Vellimadukunnu" (any capitalisation)
      - an existing customer's name or phone
    """

    query = ' '.join(request.GET.get('q', '').split())   # tidy spaces

    try:
        radius_km = float(request.GET.get('radius', 5))
    except ValueError:
        radius_km = 5
    radius_km = min(max(radius_km, 0.5), 50)

    matching_customers = Customer.objects.none()
    matching_sites = Site.objects.none()

    center = None            # (lat, lng) we measure distances from
    center_label = ''        # what the centre is, shown on the page
    center_source = ''       # 'link', 'site', 'place'
    center_site = None       # existing site used as the centre
    exclude_customer_ids = set()

    within_radius = []       # installations inside radius_km
    nearest_outside = []     # shown when nothing is inside the radius
    area_matches = []        # sites without coordinates, matched by area name
    area_words = []

    if query:

        is_link = looks_like_link(query)

        # ---------------------------------------------
        # 1. Coordinates straight from a map link / "lat, lng"
        # ---------------------------------------------

        center = coords_from_text(query)

        if center:
            center_source = 'link'
            center_label = 'Google Maps location' if is_link else query

        elif is_link:
            messages.warning(
                request,
                "Couldn't read a location from that link. In Google Maps, "
                "open the place, tap Share, copy the link and paste it here."
            )

        # ---------------------------------------------
        # 2. Text search (icontains = not case-sensitive)
        # ---------------------------------------------

        if not is_link and not center:

            matching_customers = Customer.objects.filter(
                Q(name__icontains=query) |
                Q(contact_person__icontains=query) |
                Q(phone__icontains=query)
            ).prefetch_related('sites').distinct()

            matching_sites = Site.objects.filter(
                Q(location__icontains=query) |
                Q(address__icontains=query) |
                Q(customer__name__icontains=query) |
                Q(customer__contact_person__icontains=query) |
                Q(customer__phone__icontains=query)
            ).select_related('customer').distinct()

            # Spelling-tolerant matches: "velimadkunnu" finds "VELLIMADUKUNNU"
            fuzzy_site_ids = [
                site.id
                for site in Site.objects.select_related('customer')
                if text_matches(query, f"{site.location} {site.address}")
            ]

            fuzzy_customer_ids = [
                customer.id
                for customer in Customer.objects.all()
                if text_matches(query, f"{customer.name} {customer.contact_person}")
            ]

            if fuzzy_customer_ids:
                matching_customers = (
                    Customer.objects
                    .filter(Q(id__in=matching_customers.values('id')) | Q(id__in=fuzzy_customer_ids))
                    .prefetch_related('sites')
                    .distinct()
                )

            if fuzzy_site_ids or fuzzy_customer_ids:
                matching_sites = (
                    Site.objects
                    .filter(
                        Q(id__in=matching_sites.values('id')) |
                        Q(id__in=fuzzy_site_ids) |
                        Q(customer_id__in=fuzzy_customer_ids)
                    )
                    .select_related('customer')
                    .distinct()
                )

            # Use a matching site that has coordinates as the centre
            for site in matching_sites:
                if site.latitude is not None and site.longitude is not None:
                    center = (site.latitude, site.longitude)
                    center_source = 'site'
                    center_site = site
                    center_label = f"{site.customer.name} – {site.location or site.address}"
                    break

            # Searched by a customer's name/phone: don't list them as "nearby"
            customer_hit = matching_customers.exists()
            if customer_hit:
                exclude_customer_ids = set(
                    matching_customers.values_list('id', flat=True)
                )

            # ---------------------------------------------
            # 3. Not in our records: look the place name up
            # ---------------------------------------------

            if center is None and not customer_hit:
                center = geocode_place(query)
                if center:
                    center_source = 'place'
                    center_label = query.title()

            # Found the customer, but their site has no coordinates:
            # estimate from the site's address instead
            if center is None:
                for site in matching_sites:
                    text = ' '.join(filter(None, [site.location, site.address]))
                    center = geocode_place(text)
                    if center:
                        center_source = 'site'
                        center_site = site
                        center_label = (
                            f"{site.customer.name} – {site.location or site.address} "
                            "(approximate, from address)"
                        )
                        break

        # ---------------------------------------------
        # 4. Distances to every installation with coordinates
        # ---------------------------------------------

        if center:

            nearest_by_customer = {}

            sites_with_coords = (
                Site.objects
                .filter(latitude__isnull=False, longitude__isnull=False)
                .exclude(customer_id__in=exclude_customer_ids)
                .select_related('customer')
            )

            for site in sites_with_coords:

                distance = distance_km(
                    center[0], center[1],
                    site.latitude, site.longitude
                )

                current = nearest_by_customer.get(site.customer_id)

                if current is None or distance < current['distance']:
                    nearest_by_customer[site.customer_id] = {
                        'site': site,
                        'distance': round(distance, 2),
                        # No map link = position estimated from the address
                        'approx': not site.google_map_link,
                    }

            ranked = sorted(
                nearest_by_customer.values(),
                key=lambda item: item['distance']
            )

            within_radius = [i for i in ranked if i['distance'] <= radius_km]

            if not within_radius:
                nearest_outside = ranked[:10]

            # ---------------------------------------------
            # 5. Sites with NO coordinates: match by area name
            # ---------------------------------------------

            words = set(place_names_near(center[0], center[1]))

            # Also use the typed place name itself
            if center_source == 'place':
                words |= {
                    w.upper() for w in re.findall(r'[A-Za-z]{4,}', query)
                }

            # ...or the matched site's own location text
            if center_site is not None:
                words |= {
                    w.upper() for w in re.findall(
                        r'[A-Za-z]{4,}',
                        f"{center_site.location} {center_site.address}"
                    )
                }

            ignored = {
                'HOUSE', 'ROAD', 'STREET', 'POST', 'DIST', 'DISTRICT',
                'KERALA', 'KOZHIKODE', 'CALICUT', 'NEAR', 'OPPOSITE', 'INDIA',
            }
            words -= ignored
            area_words = sorted(words)

            if words:

                listed_customers = {i['site'].customer_id for i in ranked}

                candidates = (
                    Site.objects
                    .filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
                    .exclude(customer_id__in=exclude_customer_ids | listed_customers)
                    .select_related('customer')
                    .order_by('location', 'customer__name')
                )

                area_matches = [
                    site for site in candidates
                    if any(
                        text_matches(word, f"{site.location} {site.address}")
                        for word in words
                    )
                ][:30]

    missing_coordinates = Site.objects.filter(
        Q(latitude__isnull=True) | Q(longitude__isnull=True)
    ).count()

    context = {
        'query': query,
        'radius_km': radius_km,
        'radius_choices': [1, 2, 5, 10, 20],

        'center': center,
        'center_label': center_label,
        'center_source': center_source,

        'within_radius': within_radius,
        'nearest_outside': nearest_outside,
        'area_matches': area_matches,
        'area_words': area_words,

        'matching_customers': matching_customers,
        'matching_sites': matching_sites,

        'missing_coordinates': missing_coordinates,
    }

    return render(
        request,
        'canvassing.html',
        context
    )


@require_POST
@owner_required
def fill_site_coordinates_view(request):
    """
    Finds coordinates for sites that don't have them yet, a batch at a time:
      1. from the site's Google Maps link (exact)
      2. otherwise from its location/address text (approximate)
    OpenStreetMap allows about 1 lookup per second, so each click
    handles up to 15 sites.
    """

    BATCH = 15

    tried_before = set(request.session.get('geo_failed_site_ids', []))

    sites = (
        Site.objects
        .filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
        .exclude(id__in=tried_before)
        .order_by('id')[:BATCH]
    )

    found_exact = 0
    found_approx = 0
    failed = []

    for site in sites:

        coords = None
        approx = False

        if site.google_map_link:
            coords = coords_from_text(site.google_map_link)

        if not coords:
            text = ' '.join(filter(None, [site.location, site.address]))
            if text:
                coords = geocode_place(text)
                approx = True
                time.sleep(1.1)   # OpenStreetMap usage limit

        if coords:
            site.latitude, site.longitude = coords
            site.save(update_fields=['latitude', 'longitude'])
            if approx:
                found_approx += 1
            else:
                found_exact += 1
        else:
            failed.append(site.id)

    request.session['geo_failed_site_ids'] = list(tried_before | set(failed))

    remaining = (
        Site.objects
        .filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
        .exclude(id__in=request.session['geo_failed_site_ids'])
        .count()
    )

    messages.success(
        request,
        f"Located {found_exact} site(s) from map links and "
        f"{found_approx} from their address (approximate). "
        f"{len(failed)} couldn't be found. {remaining} still to check."
    )

    return redirect('canvassing')


@owner_required
def add_schedule_view(request):

    if request.method == 'POST':

        form = CleaningScheduleForm(request.POST)

        if form.is_valid():

            form.save()

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


@owner_required
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

            form.save()

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
@owner_required
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

    # Employees can only update their own schedules
    if (
        not request.user.is_staff
        and schedule.assigned_to_id != request.user.id
    ):
        return JsonResponse(
            {'success': False, 'error': 'Not allowed.'},
            status=403
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


STATUS_COLORS = {
    'Scheduled': '#3B73B9',
    'Completed': '#28a745',
    'Rescheduled': '#f0ad4e',
    'Cancelled': '#dc3545',
}


def _schedule_events(schedules, for_owner):
    """Turns schedules into FullCalendar events."""

    events = []

    for schedule in schedules:

        customer_name = schedule.get_customer_name()

        if schedule.scheduled_time:
            start = (
                f"{schedule.scheduled_date.isoformat()}"
                f"T{schedule.scheduled_time.strftime('%H:%M:%S')}"
            )
        else:
            start = schedule.scheduled_date.isoformat()

        color = STATUS_COLORS.get(schedule.status, '#3B73B9')

        assigned = ''
        if schedule.assigned_to:
            assigned = (
                schedule.assigned_to.get_full_name()
                or schedule.assigned_to.username
            )

        props = {
            'customer_name': customer_name,
            'phone': schedule.phone or (
                schedule.customer.phone if schedule.customer else ''
            ),
            'location': schedule.get_location() or '',
            'address': (
                schedule.site.address if schedule.site else schedule.address
            ) or '',
            'map_link': (
                schedule.site.google_map_link if schedule.site else ''
            ) or '',
            'solar_kw': (
                schedule.site.solar_kw if schedule.site else schedule.solar_kw
            ) or '',
            'status': schedule.status,
            'notes': schedule.notes or '',
            'assigned_to': assigned,
        }

        if for_owner:
            props['edit_url'] = f"/schedule/{schedule.id}/edit/"
            props['delete_url'] = f"/schedule/{schedule.id}/delete/"
        else:
            props['record_url'] = (
                f"/my-jobs/record/?schedule={schedule.id}"
                if schedule.site else ''
            )

        events.append({
            'id': str(schedule.id),
            'title': customer_name,
            'start': start,
            'allDay': schedule.scheduled_time is None,
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': props,
        })

    return events


@owner_required
def schedule_events_api(request):

    schedules = (
        CleaningSchedule.objects
        .select_related('customer', 'site', 'assigned_to')
        .all()
    )

    return JsonResponse(
        _schedule_events(schedules, for_owner=True),
        safe=False
    )


def my_schedule_events_api(request):
    """Calendar data for the logged-in employee: only his own jobs."""

    schedules = (
        CleaningSchedule.objects
        .filter(assigned_to=request.user)
        .exclude(status='Cancelled')
        .select_related('customer', 'site', 'assigned_to')
    )

    return JsonResponse(
        _schedule_events(schedules, for_owner=False),
        safe=False
    )


@require_POST
@owner_required
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


# =========================================================
# HEALTH CHECK (Render pings this - must work without login)
# =========================================================

@login_not_required
def health_check(request):
    return HttpResponse("OK")


@login_not_required
def service_worker(request):

    sw_content = """
const CACHE_NAME = "solarclean-manager-v2";

// Only public static files - NO pages like "/" (they contain private data)
const APP_SHELL = [
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


// Delete old caches (including v1, which had the dashboard cached)
self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(cacheNames =>
            Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            )
        )
    );
    self.clients.claim();
});


self.addEventListener("fetch", event => {

    const request = event.request;

    // Only handle GET requests; POSTs (status updates, login) go straight to network
    if (request.method !== "GET") {
        return;
    }

    const url = new URL(request.url);

    // Static files: serve from cache if available, otherwise fetch
    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(request).then(cached => cached || fetch(request))
        );
        return;
    }

    // Pages and APIs: always from network, never cached.
    // If offline, show a simple message instead of old private data.
    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(() =>
                new Response(
                    "<h2 style='font-family:sans-serif;text-align:center;margin-top:40px'>" +
                    "You are offline. Please check your internet connection.</h2>",
                    { headers: { "Content-Type": "text/html" } }
                )
            )
        );
    }
});
"""

    response = HttpResponse(
        sw_content,
        content_type="application/javascript"
    )

    # Stop the browser from caching the service worker file itself,
    # so future changes reach phones quickly
    response["Cache-Control"] = "no-cache"

    return response


# =========================================================
# EMPLOYEE PAGES
# =========================================================

def home_view(request):

    # Owner -> dashboard, employee -> his jobs
    if request.user.is_staff:
        return redirect('dashboard')

    return redirect('my_schedule')


def my_schedule_view(request):

    today = datetime.now().date()

    pending = (
        CleaningSchedule.objects
        .filter(
            assigned_to=request.user,
            status__in=['Scheduled', 'Rescheduled'],
        )
        .select_related('customer', 'site')
        .order_by('scheduled_date', 'scheduled_time')
    )

    overdue = [s for s in pending if s.scheduled_date < today]
    today_jobs = [s for s in pending if s.scheduled_date == today]
    upcoming = [s for s in pending if s.scheduled_date > today]

    done_today = CleaningSchedule.objects.filter(
        assigned_to=request.user,
        status='Completed',
        scheduled_date=today,
    ).count()

    return render(
        request,
        'my_schedule.html',
        {
            'today': today,
            'tomorrow': today + timedelta(days=1),
            'overdue': overdue,
            'today_jobs': today_jobs,
            'upcoming': upcoming,
            'done_today': done_today,
            'pending_count': len(overdue) + len(today_jobs) + len(upcoming),
        }
    )


def employee_add_job_view(request):

    # Optional: opened from a schedule card (?schedule=12)
    schedule = None

    schedule_id = (
        request.GET.get('schedule')
        or request.POST.get('schedule')
    )

    if schedule_id:

        schedule = get_object_or_404(
            CleaningSchedule,
            pk=schedule_id,
            assigned_to=request.user,   # can't open other people's schedules
        )

    if request.method == 'POST':

        form = EmployeeJobForm(
            request.POST,
            user=request.user
        )

        formset = JobExpenseFormSet(request.POST)

        if form.is_valid() and formset.is_valid():

            with transaction.atomic():

                job = form.save(commit=False)

                job.done_by = request.user
                job.payment_status = 'Unpaid'    # owner marks Paid later
                job.job_status = 'Completed'

                job.save()   # revenue auto-filled from RateCard in model.save()

                formset.instance = job

                expenses = formset.save()

                job.total_expenses = sum(
                    float(exp.cost or 0)
                    for exp in expenses
                )

                job.net_profit = (
                    float(job.revenue or 0)
                    - job.total_expenses
                )

                job.save()

                # Close the schedule this cleaning came from
                if schedule:

                    schedule.status = 'Completed'

                    schedule.save(update_fields=[
                        'status',
                        'updated_at',
                    ])

            messages.success(
                request,
                "Cleaning recorded. Thank you!"
            )

            return redirect('my_schedule')

        messages.error(
            request,
            "Please fix the errors below."
        )

    else:

        initial = {
            'date': datetime.now().date()
        }

        if schedule:

            initial['customer'] = schedule.customer_id
            initial['site'] = schedule.site_id

        form = EmployeeJobForm(
            initial=initial,
            user=request.user
        )

        formset = JobExpenseFormSet()

    return render(
        request,
        'employee_add_job.html',
        {
            'form': form,
            'formset': formset,
            'schedule': schedule,
        }
    )