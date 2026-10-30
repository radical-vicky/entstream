from django import forms
from .models import Profile

from django import forms
from .models import Profile


class ProfileForm(forms.ModelForm):
    avatar_upload = forms.FileField(
        required=False,
        label="Choose profile picture",
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp,image/gif",
                "class": "ep-file-input",
                "id": "id_avatar_upload",
            }
        ),
    )

    class Meta:
        model = Profile
        # CHANGED: Added cover_image to the fields
        fields = ["bio", "location", "website", "cover_image"]
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Tell people about yourself",
                    "class": "ep-input",
                }
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Your location", "class": "ep-input"}
            ),
            "website": forms.URLInput(
                attrs={"placeholder": "https://example.com", "class": "ep-input"}
            ),
            "cover_image": forms.ClearableFileInput(
                attrs={"class": "ep-file-input"}
            ),
        }

    def clean_avatar_upload(self):
        image = self.cleaned_data.get("avatar_upload")

        if image:
            if image.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    "The image must be 5 MB or smaller."
                )

            allowed_types = {
                "image/jpeg",
                "image/png",
                "image/webp",
                "image/gif",
            }

            if image.content_type not in allowed_types:
                raise forms.ValidationError(
                    "Choose a JPEG, PNG, WEBP or GIF image."
                )

        return image