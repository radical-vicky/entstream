from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PaymentTransaction
from .services import mark_payment_succeeded


@transaction.atomic
def fulfill_verified_mpesa_payment(
    *,
    payment_reference,
    checkout_request_id,
    receipt_number,
    verified_amount,
    verified_currency,
):
    """
    Complete a payment only after a trusted server-side verification
    process has confirmed the transaction details.

    Do not call this directly with unverified callback data.
    """
    payment = (
        PaymentTransaction.objects
        .select_for_update()
        .get(reference=payment_reference)
    )

    if payment.provider != "mpesa":
        raise ValidationError("This is not an M-Pesa payment.")

    if payment.provider_reference != checkout_request_id:
        raise ValidationError("The checkout request does not match.")

    receipt_number = (receipt_number or "").strip()
    if not receipt_number:
        raise ValidationError("A verified M-Pesa receipt is required.")

    if payment.provider_receipt and payment.provider_receipt != receipt_number:
        raise ValidationError("The payment has a different receipt recorded.")

    if PaymentTransaction.objects.filter(
        provider="mpesa",
        provider_receipt=receipt_number,
    ).exclude(pk=payment.pk).exists():
        raise ValidationError("This M-Pesa receipt has already been used.")

    if Decimal(str(verified_amount)) != payment.amount:
        raise ValidationError("The verified amount does not match.")

    if (verified_currency or "").upper() != payment.currency.upper():
        raise ValidationError("The verified currency does not match.")

    if payment.status == PaymentTransaction.Status.SUCCEEDED:
        if payment.provider_receipt != receipt_number:
            raise ValidationError("The successful payment receipt does not match.")
        return payment, False

    if payment.status not in {
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.PROCESSING,
    }:
        raise ValidationError("This payment cannot be completed.")

    payment.provider_receipt = receipt_number
    payment.save(update_fields=["provider_receipt", "updated_at"])

    completed_payment, changed = mark_payment_succeeded(
        reference=payment.reference,
        provider_reference=receipt_number,
        verified_amount=verified_amount,
        verified_currency=verified_currency,
        provider="mpesa",
    )

    if completed_payment.purpose == PaymentTransaction.Purpose.VIDEO_PURCHASE:
        from videos.services import fulfill_video_purchase

        fulfill_video_purchase(
            payment_reference=completed_payment.reference,
        )

    return completed_payment, changed

    
