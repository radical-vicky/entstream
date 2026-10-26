
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import PaymentTransaction


@transaction.atomic
def mark_payment_succeeded(
    *,
    reference,
    provider_reference,
    verified_amount,
    verified_currency,
    provider,
):
    """
    Call only after server-side provider verification.

    This records a verified payment. It deliberately does not activate
    subscriptions or credit creator balances; those require purpose-specific
    fulfillment services and their own idempotency protections.
    """
    payment = (
        PaymentTransaction.objects
        .select_for_update()
        .get(reference=reference)
    )

    amount = Decimal(str(verified_amount))

    if amount != payment.amount:
        raise ValidationError("Verified payment amount does not match.")

    if str(verified_currency).upper() != payment.currency.upper():
        raise ValidationError("Verified payment currency does not match.")

    if payment.provider != provider:
        raise ValidationError("Payment provider does not match.")

    if not provider_reference:
        raise ValidationError("A provider transaction reference is required.")

    if payment.status == PaymentTransaction.Status.SUCCEEDED:
        if payment.provider_reference == provider_reference:
            return payment, False
        raise ValidationError(
            "This payment was already completed with another reference."
        )

    if payment.status not in (
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.PROCESSING,
    ):
        raise ValidationError("This payment cannot be completed in its current state.")

    duplicate = PaymentTransaction.objects.filter(
        provider=provider,
        provider_reference=provider_reference,
        status=PaymentTransaction.Status.SUCCEEDED,
    ).exclude(pk=payment.pk).exists()

    if duplicate:
        raise ValidationError("This provider transaction was already recorded.")

    payment.status = PaymentTransaction.Status.SUCCEEDED
    payment.provider_reference = provider_reference
    payment.verified_at = timezone.now()
    payment.failure_reason = ""
    payment.save(update_fields=[
        "status",
        "provider_reference",
        "verified_at",
        "failure_reason",
        "updated_at",
    ])

    return payment, True


from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import PaymentTransaction


@transaction.atomic
def mark_payment_succeeded(
    *,
    reference,
    provider_reference,
    verified_amount,
    verified_currency,
    provider,
    provider_receipt=None,
):
    """
    Complete a payment after a trusted server-side provider verification.

    For M-Pesa:
      provider_reference = the original CheckoutRequestID
      provider_receipt = the verified M-Pesa receipt number

    Never pass unverified callback data as verified values.
    """
    payment = (
        PaymentTransaction.objects
        .select_for_update()
        .get(reference=reference)
    )

    amount = Decimal(str(verified_amount))
    currency = (verified_currency or "").upper()
    provider = (provider or "").lower()

    if payment.provider.lower() != provider:
        raise ValidationError("Payment provider does not match.")

    if amount != payment.amount:
        raise ValidationError("Verified amount does not match.")

    if currency != payment.currency.upper():
        raise ValidationError("Verified currency does not match.")

    # For M-Pesa, preserve the checkout identifier.
    if provider == "mpesa":
        if not provider_reference:
            raise ValidationError("Checkout request ID is required.")

        if payment.provider_reference != provider_reference:
            raise ValidationError("Checkout request ID does not match.")

        receipt = (provider_receipt or "").strip()
        if not receipt:
            raise ValidationError("A verified M-Pesa receipt is required.")

        duplicate_receipt = PaymentTransaction.objects.filter(
            provider="mpesa",
            provider_receipt=receipt,
        ).exclude(pk=payment.pk).exists()

        if duplicate_receipt:
            raise ValidationError(
                "This M-Pesa receipt is already linked to another payment."
            )

        if payment.provider_receipt and payment.provider_receipt != receipt:
            raise ValidationError("A different receipt is already recorded.")

    else:
        # For other providers, retain the existing reference-based behavior.
        if not provider_reference:
            raise ValidationError("Provider transaction reference is required.")

        duplicate_reference = PaymentTransaction.objects.filter(
            provider=provider,
            provider_reference=provider_reference,
        ).exclude(pk=payment.pk).exists()

        if duplicate_reference:
            raise ValidationError(
                "This provider transaction reference is already in use."
            )

    if payment.status == PaymentTransaction.Status.SUCCEEDED:
        if provider == "mpesa" and payment.provider_receipt != receipt:
            raise ValidationError(
                "The successful payment has a different receipt."
            )

        return payment, False

    if payment.status not in {
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.PROCESSING,
    }:
        raise ValidationError(
            "This payment is not in a completable state."
        )

    if provider == "mpesa":
        payment.provider_receipt = receipt
    else:
        payment.provider_reference = provider_reference

    payment.status = PaymentTransaction.Status.SUCCEEDED
    payment.verified_at = timezone.now()
    payment.failure_reason = ""

    payment.save(
        update_fields=[
            "provider_receipt",
            "provider_reference",
            "status",
            "verified_at",
            "failure_reason",
            "updated_at",
        ]
    )

    return payment, True