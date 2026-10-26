from django import forms

from .models import ModerationAction, Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {
            "reason": forms.Select(attrs={"class": "ss-input"}),
            "details": forms.Textarea(
                attrs={
                    "class": "ss-input",
                    "rows": 4,
                    "maxlength": 3000,
                    "placeholder": "Provide any relevant details (optional).",
                }
            ),
        }

    def clean_details(self):
        return self.cleaned_data.get("details", "").strip()


class ReportReviewForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            (Report.Status.REVIEWING, "Under review"),
            (Report.Status.ACTIONED, "Action taken"),
            (Report.Status.DISMISSED, "Dismiss report"),
        ],
        widget=forms.Select(attrs={"class": "ss-input"}),
    )
    resolution_note = forms.CharField(
        required=False,
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "class": "ss-input",
                "rows": 4,
                "placeholder": "Record the reason for your decision.",
            }
        ),
    )


class ModerationActionForm(forms.Form):
    action_type = forms.ChoiceField(
        choices=ModerationAction.ActionType.choices,
        widget=forms.Select(attrs={"class": "ss-input"}),
    )
    note = forms.CharField(
        required=False,
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "class": "ss-input",
                "rows": 3,
                "placeholder": "Internal moderation note.",
            }
        ),
    )