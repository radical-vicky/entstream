
from decimal import Decimal

from django import forms

from .models import WithdrawalRequest


class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal("1.00"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": "ss-input",
                "min": "1.00",
                "step": "0.01",
                "placeholder": "Enter amount",
            }
        ),
    )

    payout_method = forms.ChoiceField(
        choices=[
            ("mpesa", "M-Pesa"),
            ("bank", "Bank transfer"),
        ],
        widget=forms.Select(attrs={"class": "ss-input"}),
    )

    payout_account = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "ss-input",
                "placeholder": "M-Pesa number or bank account details",
                "autocomplete": "off",
            }
        ),
    )

    def clean_payout_account(self):
        value = self.cleaned_data["payout_account"].strip()

        if len(value) < 5:
            raise forms.ValidationError(
                "Enter valid payout details."
            )

        return value


class WithdrawalReviewForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            (
                WithdrawalRequest.Status.APPROVED,
                "Approve",
            ),
            (
                WithdrawalRequest.Status.PROCESSING,
                "Mark processing",
            ),
            (
                WithdrawalRequest.Status.PAID,
                "Mark paid",
            ),
            (
                WithdrawalRequest.Status.REJECTED,
                "Reject and return funds",
            ),
        ],
        widget=forms.Select(attrs={"class": "ss-input"}),
    )

    admin_note = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "ss-input",
                "rows": 3,
                "placeholder": "Internal review note",
            }
        ),
    )
