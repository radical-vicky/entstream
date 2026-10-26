import json
import logging

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import PaymentTransaction

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def mpesa_callback(request):
    """
    Receive a Safaricom STK Push callback.

    A callback is not, by itself, sufficient proof of payment.
    Record it for reconciliation; do not grant access here.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"})

    callback = (
        payload.get("Body", {})
        .get("stkCallback", {})
    )

    checkout_id = callback.get("CheckoutRequestID")
    merchant_id = callback.get("MerchantRequestID")
    result_code = callback.get("ResultCode")

    if not checkout_id or result_code is None:
        return JsonResponse(
            {"ResultCode": 1, "ResultDesc": "Missing callback identifiers"}
        )

    with transaction.atomic():
        payment = (
            PaymentTransaction.objects
            .select_for_update()
            .filter(
                provider="mpesa",
                provider_reference=checkout_id,
            )
            .first()
        )

        if payment is None:
            # Acknowledge receipt, but log the unmatched callback for review.
            logger.warning(
                "Unmatched M-Pesa callback: checkout_id=%s merchant_id=%s",
                checkout_id,
                merchant_id,
            )
            return JsonResponse(
                {"ResultCode": 0, "ResultDesc": "Callback received"}
            )

        # Preserve callback details for reconciliation. Do not overwrite
        # an already-successful payment or fulfill a purchase here.
        stored_payload = payment.provider_payload or {}
        stored_payload["callback_received"] = True
        stored_payload["callback_result_code"] = result_code
        stored_payload["callback_merchant_request_id"] = merchant_id
        stored_payload["callback_metadata"] = (
            callback.get("CallbackMetadata", {}).get("Item", [])
        )

        payment.provider_payload = stored_payload

        if payment.status not in {
            PaymentTransaction.Status.SUCCEEDED,
            PaymentTransaction.Status.REFUNDED,
        }:
            payment.status = PaymentTransaction.Status.PROCESSING

        payment.save(
            update_fields=[
                "provider_payload",
                "status",
                "updated_at",
            ]
        )

    return JsonResponse(
        {"ResultCode": 0, "ResultDesc": "Callback received"}
    )