from django import forms

from .models import Video


class VideoUploadForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = [
            "title",
            "description",
            "video_file",
            "is_premium",
            "price",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Give your video a title",
                "class": "ss-input",
                "maxlength": 200,
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Tell viewers what your video is about",
                "class": "ss-input",
                "rows": 5,
            }),
            "video_file": forms.ClearableFileInput(attrs={
                "class": "ss-file-input",
                "accept": "video/*",
            }),
            "is_premium": forms.CheckboxInput(attrs={
                "class": "ss-checkbox",
            }),
            "price": forms.NumberInput(attrs={
                "class": "ss-input",
                "placeholder": "0.00",
                "min": "0",
                "step": "0.01",
            }),
        }

    def clean_title(self):
        title = self.cleaned_data.get("title", "").strip()

        if not title:
            raise forms.ValidationError("Enter a title for your video.")

        return title

    def clean_description(self):
        return self.cleaned_data.get("description", "").strip()

    def clean_video_file(self):
        video = self.cleaned_data.get("video_file")

        if not video:
            raise forms.ValidationError("Choose a video to upload.")

        max_size = 500 * 1024 * 1024

        if video.size > max_size:
            raise forms.ValidationError(
                "The video must be 500 MB or smaller."
            )

        content_type = getattr(video, "content_type", "")

        if content_type and not content_type.startswith("video/"):
            raise forms.ValidationError(
                "Please upload a valid video file."
            )

        return video

    def clean(self):
        cleaned_data = super().clean()

        is_premium = cleaned_data.get("is_premium")
        price = cleaned_data.get("price")

        if is_premium and (price is None or price <= 0):
            self.add_error(
                "price",
                "Enter a price greater than zero for premium videos.",
            )

        if not is_premium:
            cleaned_data["price"] = 0

        return cleaned_data
