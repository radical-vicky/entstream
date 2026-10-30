from django import forms

from .models import Stream


class StreamForm(forms.ModelForm):

    class Meta:
        model = Stream

        fields = [
            "title",
            "description",
            "category",
            "thumbnail",
            "broadcast_type",
            "is_public",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter your stream title",
                "maxlength": 200,
            }),

            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Tell viewers what your stream is about",
            }),

            "category": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Technology, Gaming, Education",
            }),

            "thumbnail": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": "image/*",
            }),

            "broadcast_type": forms.Select(attrs={
                "class": "form-control",
            }),

            "is_public": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

    def clean_thumbnail(self):

        image = self.cleaned_data.get("thumbnail")

        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "Thumbnail must not exceed 5MB."
            )

        if image:
            allowed_types = [
                "image/jpeg",
                "image/png",
                "image/webp",
            ]

            if getattr(image, "content_type", "") not in allowed_types:
                raise forms.ValidationError(
                    "Upload a JPG, PNG or WebP image."
                )

        return image