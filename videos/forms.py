from django import forms
from .models import Video


class VideoForm(forms.ModelForm):
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
            "status", 
            "is_premium", 
            "price"
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "placeholder": "Enter a compelling title for your video",
                "class": "sv-input",
            }),
            "description": forms.Textarea(attrs={
                "placeholder": "Tell viewers what your video is about...",
                "rows": 4,
                "class": "sv-textarea",
            }),
            "duration": forms.TextInput(attrs={
                "placeholder": "e.g., 05:24",
                "class": "sv-input",
            }),
            "price": forms.NumberInput(attrs={
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0",
                "class": "sv-input",
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_premium = cleaned_data.get("is_premium")
        price = cleaned_data.get("price")
        video_url = cleaned_data.get("video_file_url")

        # 1. Ensure a video was actually uploaded
        if not video_url:
            self.add_error("video_file_url", "You must upload a video file.")

        # 2. Validate pricing rules
        if is_premium and not price:
            self.add_error("price", "You must set a price for premium content.")
        elif is_premium and price and price <= 0:
            self.add_error("price", "Price must be greater than zero.")
        elif not is_premium:
            # Automatically clear the price if it's a free video
            cleaned_data["price"] = None

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Map the uploaded URL string to the model's video_file field
        instance.video_file = self.cleaned_data.get("video_file_url")
        
        if commit:
            instance.save()
        return instance
