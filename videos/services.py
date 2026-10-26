
from django.core.exceptions import ValidationError
from django.db import transaction

from payments.models import PaymentTransaction
from .models import VideoPurchase


@transaction.atomic
def fulfill_video_purchase(*, payment_reference):
    payment = (
        PaymentTransaction.objects
        .select_for_update()
        .select_related("user", "video")
        .get(reference=payment_reference)
    )

    if payment.status != PaymentTransaction.Status.SUCCEEDED:
        raise ValidationError("The payment has not been verified successfully.")

    if payment.purpose != PaymentTransaction.Purpose.VIDEO_PURCHASE:
        raise ValidationError("This payment is not for a video purchase.")

    video = payment.video
    if video is None:
        raise ValidationError("This payment is not linked to a video.")

    if not video.is_premium:
        raise ValidationError("This video does not require a purchase.")

    if payment.amount != video.price:
        raise ValidationError("The payment amount does not match the video price.")

    if payment.currency.upper() != "KES":
        raise ValidationError("Unsupported currency for this video purchase.")

    purchase, created = VideoPurchase.objects.get_or_create(
        buyer=payment.user,
        video=video,
        defaults={
            "payment_reference": payment.reference,
            "amount_paid": payment.amount,
            "currency": payment.currency,
        },
    )

    return purchase, created


def user_can_watch_video(*, user, video):
    if not video.is_premium:
        return True

    if not user or not user.is_authenticated:
        return False

    if user.pk == video.creator_id or user.is_staff:
        return True

    return VideoPurchase.objects.filter(
        buyer=user,
        video=video,
    ).exists()
