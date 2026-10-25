
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
            "duration",
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
            "video_file": forms.FileInput(attrs={
                "accept": "video/*",
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

        # Creators can publish now or save a draft.
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

        if is_premium and (price is None or price <= 0):
            self.add_error(
                "price",
                "Enter a price greater than zero for a premium video.",
            )

        if not is_premium:
            cleaned_data["price"] = 0

        return cleaned_data
