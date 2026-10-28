from django import forms
from .models import Video

class VideoForm(forms.ModelForm):
    # This hidden field will hold the Cloudinary URL
    video_url = forms.URLField(
        widget=forms.HiddenInput(),
        required=True,
        error_messages={'required': 'Please upload a video before submitting.'}
    )

    class Meta:
        model = Video
        # Exclude video_file because the widget handles it
        fields = ["title", "description", "is_premium", "price", "status"]
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Give your video a title'}),
            'description': forms.Textarea(attrs={'placeholder': 'Tell viewers about your video...', 'rows': 4}),
        }
