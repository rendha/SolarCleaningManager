
from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
 
from .models import CleaningJob, JobExpense, Customer, Site, CleaningSchedule
 
 
class CleaningJobForm(forms.ModelForm):

    # ---------- New / one-time customer fields (not saved on the job itself) ----------

    new_customer = forms.BooleanField(
        required=False,
        label='Not an existing customer',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_new_customer',
            'role': 'switch',
        })
    )

    new_customer_name = forms.CharField(
        required=False, max_length=150, label='Customer name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer name'})
    )

    new_phone = forms.CharField(
        required=False, max_length=50, label='Phone',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'})
    )

    new_location = forms.CharField(
        required=False, max_length=250, label='Location',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Kakkanad'})
    )

    new_address = forms.CharField(
        required=False, max_length=500, label='Address',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full address (optional)'})
    )

    new_solar_kw = forms.CharField(
        required=False, max_length=20, label='System size (kW)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3, 5, 10'})
    )

    new_map_link = forms.URLField(
        required=False, label='Google Maps link',
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Optional'})
    )

    class Meta:
        model = CleaningJob

        fields = [
            'customer',
            'site',
            'cleaning_number',
            'is_free',
            'payment_status',
            'date',
            'manual_rate_override',
        ]

        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control', 'data-customer-search': 'true'}),
            'site': forms.Select(attrs={'class': 'form-control'}),
            'cleaning_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'manual_rate_override': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'is_free': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Not required here - clean() decides based on the switch
        self.fields['customer'].required = False
        self.fields['site'].required = False

        self.fields['customer'].queryset = Customer.objects.all().order_by('name')

        self.fields['site'].queryset = (
            Site.objects.all()
            .select_related('customer')
            .order_by('customer__name', 'location')
        )

        self.fields['site'].label_from_instance = (
            lambda site: f"{site.customer.name} - {site.location} - {site.solar_kw} kW"
        )

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get('new_customer'):

            if not cleaned_data.get('new_customer_name'):
                self.add_error('new_customer_name', 'Please enter the customer name.')

            if not cleaned_data.get('new_location') and not cleaned_data.get('new_address'):
                self.add_error('new_location', 'Please enter a location or address.')

            # Need kW (for rate card) unless it's free or the rate is typed manually
            if (
                not cleaned_data.get('new_solar_kw')
                and cleaned_data.get('manual_rate_override') is None
                and not cleaned_data.get('is_free')
            ):
                self.add_error('new_solar_kw', 'Enter the kW, or fill in Manual Rate Override.')

        else:
            customer = cleaned_data.get('customer')
            site = cleaned_data.get('site')

            if not customer:
                self.add_error(None, 'Please select a customer, or switch on "Not an existing customer".')
            elif not site:
                self.add_error(None, 'Please select a site.')
            elif site.customer_id != customer.id:
                self.add_error(None, 'The selected site does not belong to this customer.')

        return cleaned_data
 
JobExpenseFormSet = inlineformset_factory(
    CleaningJob,
    JobExpense,
    fields=['expense_name', 'cost'],
    extra=1,
    can_delete=True,
    widgets={
        'expense_name': forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Fuel, Water',
            }
        ),
        'cost': forms.NumberInput(
            attrs={
                'class': 'form-control',
                'placeholder': '₹',
                'step': '0.01',
            }
        ),
    },
)
 
 
class CleaningScheduleForm(forms.ModelForm):
 
    class Meta:
 
        model = CleaningSchedule
 
        fields = [
            'customer',
            'customer_name',
            'phone',
            'site',
            'solar_kw',
            'location',
            'address',
            'scheduled_date',
            'scheduled_time',
            'assigned_to',
            'status',
            'notes',
        ]
 
        widgets = {
 
            'customer': forms.Select(
                attrs={
                    'class': 'form-control',
                    'id': 'id_customer',
                    'data-customer-search': 'true,'
                }
            ),
 
            'customer_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Customer name',
                    'id': 'id_customer_name',
                }
            ),
 
            'phone': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Phone number',
                }
            ),
 
            'solar_kw': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'e.g. 3, 5, 7.2, 10',
                }
            ),
 
            'site': forms.Select(
                attrs={
                    'class': 'form-control',
                    'id': 'id_site',
                }
            ),
 
            'location': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Location',
                }
            ),
 
            'address': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Full address',
                }
            ),
 
            'scheduled_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),
 
            'scheduled_time': forms.TimeInput(
                attrs={
                    'class': 'form-control',
                    'type': 'time',
                }
            ),
 
            'assigned_to': forms.Select(
                attrs={
                    'class': 'form-control',
                }
            ),
 
            'status': forms.Select(
                attrs={
                    'class': 'form-control',
                }
            ),
 
            'notes': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Notes...',
                }
            ),
        }
 
    def __init__(self, *args, **kwargs):
 
        super().__init__(*args, **kwargs)
 
        self.fields['customer'].required = False
        self.fields['site'].required = False
        self.fields['customer_name'].required = False
        self.fields['phone'].required = False
        self.fields['location'].required = False
        self.fields['address'].required = False
        self.fields['scheduled_time'].required = False
        self.fields['notes'].required = False
 
        # Employee dropdown: only active, non-owner users
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].label = 'Assign to employee'
        self.fields['assigned_to'].queryset = (
            get_user_model().objects
            .filter(is_active=True, is_staff=False)
            .order_by('first_name', 'username')
        )
        self.fields['assigned_to'].label_from_instance = (
            lambda user: user.get_full_name() or user.username
        )
 
        # Initially show all sites.
        self.fields['site'].queryset = (
            self.fields['site']
            .queryset
            .select_related('customer')
            .order_by(
                'customer__name',
                'location'
            )
        )
 
    def clean(self):
 
        cleaned_data = super().clean()
 
        customer = cleaned_data.get('customer')
        customer_name = cleaned_data.get('customer_name')
        site = cleaned_data.get('site')
 
        # Existing customer
        if customer:
 
            # If no site selected, allow manual location.
            if not site:
 
                location = cleaned_data.get('location')
                address = cleaned_data.get('address')
 
                if not location and not address:
 
                    raise forms.ValidationError(
                        'Please select a site or enter a location/address.'
                    )
 
        # New/non-customer
        else:
 
            if not customer_name:
 
                raise forms.ValidationError(
                    'Please enter the customer name.'
                )
 
            location = cleaned_data.get('location')
            address = cleaned_data.get('address')
 
            if not location and not address:
 
                raise forms.ValidationError(
                    'Please enter a location or address.'
                )
 
        return cleaned_data
 
 
class EmployeeJobForm(forms.ModelForm):
    """
    Cleaning form for employees.
    No price, free/paid or payment status fields.
    Customer and site dropdowns only show customers
    from schedules assigned to this employee.
    """
 
    class Meta:
        model = CleaningJob
 
        fields = [
            'customer',
            'site',
            'date',
            'cleaning_number',
        ]
 
        widgets = {
            'customer': forms.Select(
                attrs={'class': 'form-control'}
            ),
 
            'site': forms.Select(
                attrs={'class': 'form-control'}
            ),
 
            'date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
 
            'cleaning_number': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),
        }
 
    def __init__(self, *args, user=None, **kwargs):
 
        super().__init__(*args, **kwargs)
 
        self.fields['customer'].queryset = (
            Customer.objects
            .filter(cleaning_schedules__assigned_to=user)
            .distinct()
            .order_by('name')
        )
 
        self.fields['site'].queryset = (
            Site.objects
            .filter(cleaning_schedules__assigned_to=user)
            .select_related('customer')
            .distinct()
            .order_by('customer__name', 'location')
        )
 
        self.fields['site'].label_from_instance = (
            lambda site:
            f"{site.customer.name} - "
            f"{site.location} - "
            f"{site.solar_kw} kW"
        )
 
    def clean(self):
 
        cleaned_data = super().clean()
 
        customer = cleaned_data.get('customer')
        site = cleaned_data.get('site')
 
        if customer and site and site.customer_id != customer.id:
 
            raise forms.ValidationError(
                'The selected site does not belong to this customer.'
            )
 
        return cleaned_data
