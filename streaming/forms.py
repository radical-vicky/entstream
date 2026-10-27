
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
                "autocomplete": "off",
            }),
            "description": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "What will you be streaming?",
            }),
            "category": forms.TextInput(attrs={
                "placeholder": "Gaming, education, music...",
                "maxlength": 80,
            }),
            "scheduled_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "type": "datetime-local",
                },
            ),
            "thumbnail_url": forms.URLInput(attrs={
                "placeholder": "https://example.com/thumbnail.jpg",
                "autocomplete": "url",
            }),
            "is_public": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure datetime-local inputs display existing scheduled dates.
        self.fields["scheduled_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ]

        # Add consistent CSS hooks for the StreamSphere form template.
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "stream-input")

        self.fields["title"].help_text = (
            "Use a clear title so viewers know what to expect."
        )
        self.fields["description"].help_text = (
            "Explain what your stream is about."
        )
        self.fields["category"].help_text = (
            "Optional. For example, gaming, education, or music."
        )
        self.fields["scheduled_at"].help_text = (
            "Choose the date and time you plan to stream."
        )
        self.fields["thumbnail_url"].help_text = (
            "Optional. Enter a publicly accessible thumbnail image URL."
        )
        self.fields["is_public"].help_text = (
            "Public streams can appear in the stream discovery page."
        )

    def clean_title(self):
        title = self.cleaned_data["title"].strip()

        if len(title) < 3:
            raise forms.ValidationError(
                "The stream title must contain at least 3 characters."
            )

        return title

    def clean_category(self):
        return self.cleaned_data["category"].strip()

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data["scheduled_at"]

        if scheduled_at < timezone.now():
            raise forms.ValidationError(
                "Choose a current or future date and time."
            )

        return scheduled_at
