
from django import forms

from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body", "attachment"]
        widgets = {
            "body": forms.Textarea(attrs={
                "placeholder": "Write a message...",
                "rows": 2,
                "maxlength": 5000,
                "autocomplete": "off",
            }),
            "attachment": forms.ClearableFileInput(attrs={
                "accept": "image/*,video/*,.pdf,.doc,.docx",
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        body = (cleaned_data.get("body") or "").strip()
        attachment = cleaned_data.get("attachment")

        if not body and not attachment:
            raise forms.ValidationError(
                "Write a message or attach a file."
            )

        if len(body) > 5000:
            self.add_error("body", "Messages cannot exceed 5,000 characters.")

        if attachment and attachment.size > 15 * 1024 * 1024:
            self.add_error(
                "attachment",
                "Attachments must be 15 MB or smaller.",
            )

        cleaned_data["body"] = body
        return cleaned_data
