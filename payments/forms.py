
from django import forms

from .models import PaymentTransaction


class PaymentSearchForm(forms.Form):
    reference = forms.CharField(
        required=False,
        max_length=80,
        label="Payment reference",
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(PaymentTransaction.Status.choices),
    )
    purpose = forms.ChoiceField(
        required=False,
        choices=[("", "All payment types")] + list(PaymentTransaction.Purpose.choices),
    )
