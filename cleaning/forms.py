from django import forms
from django.forms import inlineformset_factory
from .models import CleaningJob, JobExpense, Customer, Site,CleaningSchedule


class CleaningJobForm(forms.ModelForm):

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
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'site': forms.Select(attrs={'class': 'form-control'}),
            'cleaning_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
            'manual_rate_override': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Optional'
                }
            ),
            'is_free': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['customer'].queryset = (
            Customer.objects.all().order_by('name')
        )

        self.fields['site'].queryset = (
            Site.objects
            .all()
            .select_related('customer')
            .order_by('customer__name', 'location')
        )

        self.fields['site'].label_from_instance = (
            lambda site:
            f"{site.customer.name} - "
            f"{site.location} - "
            f"{site.solar_kw} kW"
        )


JobExpenseFormSet = inlineformset_factory(
    CleaningJob,
    JobExpense,
    fields=['expense_name', 'cost'],
    extra=1,
    can_delete=True
)

class CleaningScheduleForm(forms.ModelForm):

    class Meta:

        model = CleaningSchedule

        fields = [
            'customer',
            'customer_name',
            'phone',
            'site',
            'location',
            'address',
            'scheduled_date',
            'scheduled_time',
            'status',
            'notes',
        ]

        widgets = {

            'customer': forms.Select(
                attrs={
                    'class': 'form-control',
                    'id': 'id_customer',
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