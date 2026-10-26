from django.core.exceptions import ValidationError
from django.db import transaction

from payments.models import PaymentTransaction
from .models import Video, VideoPurchase


@transaction.atomic
def create_video_purchase_payment(*, user, video):
    if not user or not user.is_authenticated:
        raise ValidationError("Log in before purchasing a video.")

    video = Video.objects.select_for_update().get(pk=video.pk)

    if not video.is_premium:
        raise ValidationError("This video is free.")

    if video.creator_id == user.pk:
        raise ValidationError("You cannot purchase your own video.")

    if video.status != "published":
        raise ValidationError("This video is not available for purchase.")

    if VideoPurchase.objects.filter(
        buyer=user,
        video=video,
    ).exists():
        raise ValidationError("You already own this video.")

    if video.price is None or video.price <= 0:
        raise ValidationError("This video has an invalid purchase price.")

    # Reuse an existing pending transaction to avoid creating duplicates
    # every time the user refreshes the checkout page.
    existing = PaymentTransaction.objects.filter(
        user=user,
        video=video,
        purpose=PaymentTransaction.Purpose.VIDEO_PURCHASE,
        status=PaymentTransaction.Status.PENDING,
        currency="KES",
        amount=video.price,
    ).order_by("-created_at").first()

    if existing:
        return existing, False

    payment = PaymentTransaction.objects.create(
        user=user,
        video=video,
        purpose=PaymentTransaction.Purpose.VIDEO_PURCHASE,
        amount=video.price,
        currency="KES",
        provider="manual",
        status=PaymentTransaction.Status.PENDING,
        description=f"Premium video: {video.title}",
    )

    return payment, True