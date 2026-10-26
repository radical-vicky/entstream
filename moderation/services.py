from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from videos.models import Video, VideoComment

from .models import ModerationAction, Report


User = get_user_model()


def get_report_target(report):
    if report.target_type == Report.TargetType.VIDEO:
        return Video.objects.filter(pk=report.target_id).first()

    if report.target_type == Report.TargetType.COMMENT:
        return VideoComment.objects.filter(pk=report.target_id).first()

    if report.target_type == Report.TargetType.ACCOUNT:
        return User.objects.filter(pk=report.target_id).first()

    return None


@transaction.atomic
def apply_moderation_action(
    *,
    moderator,
    action_type,
    target_type,
    target_id,
    note="",
    report=None,
):
    if not moderator.is_authenticated or not moderator.is_staff:
        raise PermissionError("Only staff members can moderate content.")

    target = None

    if target_type == Report.TargetType.VIDEO:
        target = Video.objects.select_for_update().filter(
            pk=target_id
        ).first()
        if target is None:
            raise ValidationError("The reported video no longer exists.")

    elif target_type == Report.TargetType.COMMENT:
        target = VideoComment.objects.select_for_update().filter(
            pk=target_id
        ).first()
        if target is None:
            raise ValidationError("The reported comment no longer exists.")

    elif target_type == Report.TargetType.ACCOUNT:
        target = User.objects.select_for_update().filter(
            pk=target_id
        ).first()
        if target is None:
            raise ValidationError("The reported account no longer exists.")

    else:
        raise ValidationError("Unknown moderation target type.")

    if action_type == ModerationAction.ActionType.HIDE_VIDEO:
        if target_type != Report.TargetType.VIDEO:
            raise ValidationError("Hide video applies only to videos.")
        target.status = "archived"
        target.save(update_fields=["status", "updated_at"])

    elif action_type == ModerationAction.ActionType.RESTORE_VIDEO:
        if target_type != Report.TargetType.VIDEO:
            raise ValidationError("Restore video applies only to videos.")
        target.status = "published"
        target.save(update_fields=["status", "updated_at"])

    elif action_type == ModerationAction.ActionType.DELETE_COMMENT:
        if target_type != Report.TargetType.COMMENT:
            raise ValidationError("Delete comment applies only to comments.")
        target.delete()

    elif action_type == ModerationAction.ActionType.ACCOUNT_NOTE:
        if target_type != Report.TargetType.ACCOUNT:
            raise ValidationError("Account note applies only to accounts.")

    elif action_type == ModerationAction.ActionType.WARNING:
        # This records a warning action; it does not send a user notification.
        pass

    elif action_type == ModerationAction.ActionType.OTHER:
        pass

    else:
        raise ValidationError("Unsupported moderation action.")

    return ModerationAction.objects.create(
        report=report,
        moderator=moderator,
        target_type=target_type,
        target_id=target_id,
        action_type=action_type,
        note=note,
    )