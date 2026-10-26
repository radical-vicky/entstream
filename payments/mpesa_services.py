from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PaymentTransaction
from .mpesa import initiate_stk_push


@transaction.atomic
def request_video_payment(*, payment_reference, phone_number, user):
    payment = (
        PaymentTransaction.objects
        .select_for_update()
        .select_related("video")
        .get(reference=payment_reference, user=user)
    )

    if payment.status != PaymentTransaction.Status.PENDING:
        raise ValidationError("This payment is no longer pending.")

    if payment.purpose != PaymentTransaction.Purpose.VIDEO_PURCHASE:
        raise ValidationError("This is not a video purchase.")

    if payment.video_id is None:
        raise ValidationError("No video is linked to this payment.")

    video = payment.video

    if not video.is_premium or video.status != "published":
        raise ValidationError("This video is not available for purchase.")

    if payment.currency != "KES":
        raise ValidationError("Only KES payments are supported.")

    if payment.amount != Decimal(str(video.price)):
        raise ValidationError("The payment amount no longer matches the price.")

    if payment.amount != payment.amount.to_integral_value():
        raise ValidationError(
            "M-Pesa STK Push requires an integer amount in KES."
        )

    # The provider request occurs only after validating the database record.
    result = initiate_stk_push(
        phone_number=phone_number,
        amount=payment.amount,
        payment_reference=payment.reference,
    )

    # Store the provider's request identifiers while leaving the payment
    # pending until a verified callback is processed.
    payment.provider = "mpesa"
    payment.provider_reference = result.get("CheckoutRequestID", "")
    payment.provider_payload = {
        "MerchantRequestID": result.get("MerchantRequestID"),
        "CheckoutRequestID": result.get("CheckoutRequestID"),
        "ResponseCode": result.get("ResponseCode"),
        "ResponseDescription": result.get("ResponseDescription"),
        "CustomerMessage": result.get("CustomerMessage"),
    }
    payment.save(
        update_fields=[
            "provider",
            "provider_reference",
            "provider_payload",
            "updated_at",
        ]
    )

    return payment, result