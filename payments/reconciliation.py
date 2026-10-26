from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PaymentTransaction
from .mpesa import query_stk_push


@transaction.atomic
def reconcile_mpesa_payment(*, payment_reference, user=None):
    payment = (
        PaymentTransaction.objects
        .select_for_update()
        .filter(reference=payment_reference)
        .first()
    )

    if payment is None:
        raise ValidationError("Payment transaction was not found.")

    if user is not None and payment.user_id != user.pk:
        raise ValidationError("You cannot access this payment.")

    if payment.provider != "mpesa":
        raise ValidationError("This payment is not an M-Pesa transaction.")

    if payment.status not in {
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.PROCESSING,
    }:
        return payment, None

    checkout_id = payment.provider_reference
    if not checkout_id:
        raise ValidationError("No M-Pesa checkout ID is recorded.")

    result = query_stk_push(
        checkout_request_id=checkout_id,
    )

    # Save the latest query response for audit/review. A query response
    # alone is not enough to verify the amount or M-Pesa receipt.
    payload = payment.provider_payload or {}
    payload["last_stk_query"] = {
        "ResponseCode": result.get("ResponseCode"),
        "ResponseDescription": result.get("ResponseDescription"),
        "ResultCode": result.get("ResultCode"),
        "ResultDesc": result.get("ResultDesc"),
    }

    payment.provider_payload = payload
    payment.save(update_fields=["provider_payload", "updated_at"])

    return payment, result