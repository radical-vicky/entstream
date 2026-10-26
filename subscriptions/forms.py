from django import forms

from .models import SubscriptionPlan


class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "name",
            "description",
            "price",
            "duration_days",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "ss-input",
                    "placeholder": "e.g. Creator Plus",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "ss-input",
                    "rows": 4,
                    "placeholder": "Describe the benefits of this plan",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "class": "ss-input",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),
            "duration_days": forms.NumberInput(
                attrs={
                    "class": "ss-input",
                    "min": "1",
                }
            ),
            "is_active": forms.CheckboxInput(),
        }

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price <= 0:
            raise forms.ValidationError("The plan price must be greater than zero.")
        return price

    def clean_duration_days(self):
        days = self.cleaned_data["duration_days"]
        if days < 1:
            raise forms.ValidationError("The plan must last at least one day.")
        return days