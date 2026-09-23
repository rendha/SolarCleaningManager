from django.contrib import admin
from .models import Customer, Site, RateCard, CleaningJob, JobExpense,CanvassingLocation


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'contact_person', 'phone')
    search_fields = ('name', 'contact_person', 'phone')


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'location',
        'solar_kw',
        'google_map_link',
        'first_cleaning_done',
        'first_cleaning_date',
    )

    search_fields = (
        'customer__name',
        'customer__phone',
        'location',
        'address',
    )

    list_filter = (
        'first_cleaning_done',
    )

admin.site.register(RateCard)
admin.site.register(CleaningJob)
admin.site.register(JobExpense)  

@admin.register(CanvassingLocation)
class CanvassingLocationAdmin(admin.ModelAdmin):

    list_display = (
        'customer_name',
        'contact_person',
        'phone',
        'location',
        'solar_kw',
        'status',
        'google_map_link',
    )

    search_fields = (
        'customer_name',
        'contact_person',
        'phone',
        'location',
    )

    list_filter = (
        'status',
    )
