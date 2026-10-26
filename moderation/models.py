
from django.conf import settings
from django.db import models
from django.db.models import Q


class Report(models.Model):
    class TargetType(models.TextChoices):
        VIDEO = "video", "Video"
        COMMENT = "comment", "Comment"
        ACCOUNT = "account", "Account"

    class Reason(models.TextChoices):
        SPAM = "spam", "Spam or misleading"
        HARASSMENT = "harassment", "Harassment or bullying"
        HATE = "hate", "Hateful content"
        VIOLENCE = "violence", "Violence or dangerous content"
        COPYRIGHT = "copyright", "Copyright concern"
        SEXUAL = "sexual", "Sexual content"
        SCAM = "scam", "Scam or fraud"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Under review"
        ACTIONED = "actioned", "Action taken"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="moderation_reports_submitted",
    )

    target_type = models.CharField(
        max_length=20,
        choices=TargetType.choices,
        db_index=True,
    )

    # Keep the reported target's ID even if the target is later deleted.
    target_id = models.PositiveBigIntegerField(db_index=True)

    reason = models.CharField(
        max_length=30,
        choices=Reason.choices,
    )
    details = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_reports_reviewed",
    )
    resolution_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "target_type", "target_id"],
                condition=Q(status__in=["open", "reviewing"]),
                name="one_open_report_per_user_target",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_target_type_display()} #{self.target_id} "
            f"reported by {self.reporter}"
        )


class ModerationAction(models.Model):
    class ActionType(models.TextChoices):
        WARNING = "warning", "Warning"
        HIDE_VIDEO = "hide_video", "Hide video"
        RESTORE_VIDEO = "restore_video", "Restore video"
        DELETE_COMMENT = "delete_comment", "Delete comment"
        ACCOUNT_NOTE = "account_note", "Account note"
        OTHER = "other", "Other action"

    report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="moderation_actions",
    )
    target_type = models.CharField(max_length=20)
    target_id = models.PositiveBigIntegerField()
    action_type = models.CharField(
        max_length=30,
        choices=ActionType.choices,
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["moderator", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.target_type} #{self.target_id}"
