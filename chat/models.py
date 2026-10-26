
from django.conf import settings
from django.db import models
from django.db.models import Q


class Conversation(models.Model):
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="chat_conversations",
        blank=True,
    )
    subject = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject or f"Conversation {self.pk}"

    def other_participant(self, user):
        return self.participants.exclude(pk=user.pk).first()

    def last_message(self):
        return self.messages.order_by("-created_at").first()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages_sent",
    )
    body = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="chat/attachments/%Y/%m/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["conversation", "is_read"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~Q(body="")
                    | Q(attachment__isnull=False)
                    | ~Q(attachment="")
                ),
                name="chat_message_has_body_or_attachment",
            ),
        ]

    def __str__(self):
        return f"Message {self.pk} in conversation {self.conversation_id}"
