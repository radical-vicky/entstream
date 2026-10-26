
from django import forms
from django.utils import timezone

from .models import LiveStream


class LiveStreamForm(forms.ModelForm):
    class Meta:
        model = LiveStream
        fields = [
            "title",
            "description",
            "category",
            "scheduled_at",
            "thumbnail_url",
            "is_public",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Give your stream a clear title",
                "maxlength": 160,
            }),
            "description": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "What will you be streaming?",
            }),
            "category": forms.TextInput(attrs={
                "placeholder": "Gaming, education, music...",
            }),
            "scheduled_at": forms.DateTimeInput(attrs={
                "type": "datetime-local",
            }),
            "thumbnail_url": forms.URLInput(attrs={
                "placeholder": "https://example.com/thumbnail.jpg",
            }),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError(
                "The stream title must contain at least 3 characters."
            )
        return title

    

def clean_scheduled_at(self):
    scheduled_at = self.cleaned_data["scheduled_at"]
    if scheduled_at < timezone.now():
        raise forms.ValidationError(
            "Choose a current or future date and time."
        )
    return scheduled_at