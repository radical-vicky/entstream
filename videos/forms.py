from django import forms
from .models import Video


class VideoUploadForm(forms.ModelForm):
    # Hidden field to receive the Cloudinary URL from the frontend JS widget
    video_file_url = forms.URLField(
        widget=forms.HiddenInput(),
        required=True,
        error_messages={
            "required": "Please upload a video file before submitting."
        }
    )

    class Meta:
        model = Video
        # We exclude 'video_file' because the URL is handled via 'video_file_url'
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
        video_url = cleaned_data.get("video_file_url")

        # 1. Ensure a video was actually uploaded
        if not video_url:
            self.add_error("video_file_url", "You must upload a video file.")

        # 2. Validate pricing rules
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
        
        # Map the uploaded URL string to the model's video_file field
        instance.video_file = self.cleaned_data.get("video_file_url")
        
        if commit:
            instance.save()
        return instance
