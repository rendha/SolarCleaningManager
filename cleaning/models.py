from django.db import models

class RateCard(models.Model):
    system_size_kw = models.CharField(max_length=20, unique=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.system_size_kw.upper()} - {self.rate}"


class Customer(models.Model):
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=150, blank=True) 
    phone = models.CharField(max_length=50,blank=True)

    def __str__(self):
        return self.name

class Site(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='sites'
    )

    location = models.CharField(
        max_length=250,
        blank=True
    )

    address = models.CharField(
        max_length=500,
        blank=True
    )

    solar_kw = models.CharField(
        max_length=20,
        blank=True
    )

    google_map_link = models.URLField(
        blank=True
    )

    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True,blank=True)

    first_cleaning_done = models.BooleanField(
        default=False
    )

    first_cleaning_date = models.DateField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.customer.name} - {self.location or self.address}"


class CleaningJob(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Unpaid', 'Unpaid'),
    ]

    JOB_STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('Completed', 'Completed'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='cleaning_jobs'
    )

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='cleaning_jobs'
    )

    cleaning_number = models.PositiveIntegerField(default=1)

    is_free = models.BooleanField(default=False)

    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='Unpaid'
    )

    job_status = models.CharField(
        max_length=20,
        choices=JOB_STATUS_CHOICES,
        default='Completed'
    )

    date = models.DateField()

    manual_rate_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    total_expenses = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    net_profit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    def save(self, *args, **kwargs):
        import re
        from decimal import Decimal

        # FREE CLEANING = ₹0
        if self.is_free:
            self.revenue = Decimal('0.00')

        # MANUAL OVERRIDE
        elif self.manual_rate_override is not None:
            self.revenue = self.manual_rate_override

        # AUTOMATIC RATE CARD
        else:
            site_kw = str(self.site.solar_kw).strip()

            site_match = re.search(
                r'(\d+(?:\.\d+)?)',
                site_kw
            )

            if site_match:
                site_size = Decimal(
                    site_match.group(1)
                )

                rate_found = None

                for rate in RateCard.objects.all():

                    rate_match = re.search(
                        r'(\d+(?:\.\d+)?)',
                        str(rate.system_size_kw)
                    )

                    if rate_match:
                        rate_size = Decimal(
                            rate_match.group(1)
                        )

                        if rate_size == site_size:
                            rate_found = rate
                            break

                if rate_found:
                    self.revenue = rate_found.rate
                else:
                    self.revenue = Decimal('0.00')

            else:
                self.revenue = Decimal('0.00')

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.customer.name} - "
            f"{self.site.location} - "
            f"{self.date}"
        )

class JobExpense(models.Model):
    # This ForeignKey is what the inlineformset_factory is looking for!
    job = models.ForeignKey(CleaningJob, related_name='expenses', on_delete=models.CASCADE)
    expense_name = models.CharField(max_length=100) 
    cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.expense_name}: {self.cost}"    

class CanvassingLocation(models.Model):

    STATUS_CHOICES = [
        ('Lead', 'Lead'),
        ('Customer', 'Customer'),
    ]

    customer_name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    location = models.CharField(max_length=250)

    solar_kw = models.CharField(max_length=20, blank=True)

    google_map_link = models.URLField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Lead'
    )

    def __str__(self):
        return f"{self.customer_name} - {self.location}"


class CleaningSchedule(models.Model):

    STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('Completed', 'Completed'),
        ('Rescheduled', 'Rescheduled'),
        ('Cancelled', 'Cancelled'),
    ]

    # Existing customer - optional because this can also be a
    # temporary/non-customer schedule.
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cleaning_schedules'
    )

    # Used when scheduling someone who is not yet in Customer list.
    customer_name = models.CharField(
        max_length=150,
        blank=True
    )

    phone = models.CharField(
        max_length=50,
        blank=True
    )

    # Existing customer site - optional for non-customer schedules.
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cleaning_schedules'
    )

    # These allow a schedule to exist even without a Site.
    location = models.CharField(
        max_length=250,
        blank=True
    )

    address = models.CharField(
        max_length=500,
        blank=True
    )

    scheduled_date = models.DateField()

    scheduled_time = models.TimeField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Scheduled'
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def get_customer_name(self):
        """
        Return the actual customer name if this schedule
        belongs to an existing customer.

        Otherwise return the manually entered name.
        """

        if self.customer:
            return self.customer.name

        return self.customer_name

    def get_location(self):
        """
        Return Site location when available.
        Otherwise use manually entered location/address.
        """

        if self.site:
            return (
                self.site.location
                or self.site.address
                or self.location
            )

        return self.location or self.address

    def __str__(self):

        customer_name = self.get_customer_name()

        return (
            f"{customer_name} - "
            f"{self.scheduled_date}"
        )