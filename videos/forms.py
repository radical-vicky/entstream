
from django import forms
from django.conf import settings

from .models import Video


class VideoUploadForm(forms.ModelForm):
    video_file_url = forms.URLField(
        widget=forms.HiddenInput(),
        required=False,
    )

    bunny_video_id = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    class Meta:
        model = Video
        fields = [
            "title",
            "description",
            "duration",
            "is_premium",
            "price",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Give your video a clear title",
                "maxlength": 200,
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Describe your video for viewers",
                "rows": 5,
            }),
            "price": forms.NumberInput(attrs={
                "min": "0",
                "step": "0.01",
            }),
            "duration": forms.TextInput(attrs={
                "placeholder": "e.g. 08:35",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["status"].choices = [
            (Video.Status.DRAFT, "Save as draft"),
            (Video.Status.PUBLISHED, "Publish video"),
        ]

        self.fields["price"].required = False
        self.fields["price"].initial = 0

    def clean(self):
        cleaned_data = super().clean()

        is_premium = cleaned_data.get("is_premium")
        price = cleaned_data.get("price")
        video_url = cleaned_data.get("video_file_url")
        bunny_video_id = cleaned_data.get("bunny_video_id")

        if not video_url and not bunny_video_id:
            self.add_error(
                "video_file_url",
                "Please upload a video before submitting.",
            )

        if video_url and bunny_video_id:
            self.add_error(
                "video_file_url",
                "Select only one upload provider.",
            )

        if is_premium and (price is None or price <= 0):
            self.add_error(
                "price",
                "Enter a price greater than zero for a premium video.",
            )

        if not is_premium:
            cleaned_data["price"] = 0

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        bunny_video_id = self.cleaned_data.get("bunny_video_id")
        video_url = self.cleaned_data.get("video_file_url")

        if bunny_video_id:
            instance.source = Video.Source.BUNNY
            instance.bunny_video_id = bunny_video_id
            instance.bunny_library_id = str(
                settings.BUNNY_STREAM_LIBRARY_ID
            )
            instance.video_file = ""

        elif video_url:
            instance.source = Video.Source.CLOUDINARY
            instance.video_file = video_url
            instance.bunny_video_id = ""
            instance.bunny_library_id = ""

        if commit:
            instance.save()

        return instance


class VideoForm(forms.ModelForm):
    video_file_url = forms.URLField(
        widget=forms.HiddenInput(),
        required=False,
        label="Replace video file",
        help_text=(
            "Leave empty to keep the current video. "
            "Upload a new file to replace it."
        ),
    )

    class Meta:
        model = Video
        fields = [
            "title",
            "description",
            "duration",
            "is_premium",
            "price",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Give your video a clear title",
                "maxlength": 200,
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Describe your video for viewers",
                "rows": 5,
            }),
            "price": forms.NumberInput(attrs={
                "min": "0",
                "step": "0.01",
            }),
            "duration": forms.TextInput(attrs={
                "placeholder": "e.g. 08:35",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["status"].choices = [
            (Video.Status.DRAFT, "Save as draft"),
            (Video.Status.PUBLISHED, "Publish video"),
        ]

        self.fields["price"].required = False

        if self.instance and self.instance.pk:
            self.fields["price"].initial = self.instance.price or 0
        else:
            self.fields["price"].initial = 0

    def clean(self):
        cleaned_data = super().clean()

        is_premium = cleaned_data.get("is_premium")
        price = cleaned_data.get("price")

        if is_premium and (price is None or price <= 0):
            self.add_error(
                "price",
                "Enter a price greater than zero for a premium video.",
            )

        if not is_premium:
            cleaned_data["price"] = 0

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        new_url = (
            self.cleaned_data.get("video_file_url") or ""
        ).strip()

        if new_url:
            instance.source = Video.Source.CLOUDINARY
            instance.video_file = new_url
            instance.bunny_video_id = ""
            instance.bunny_library_id = ""

        if commit:
            instance.save()

        return instance
