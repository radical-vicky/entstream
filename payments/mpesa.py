import base64
import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone


TIMEOUT = (5, 25)


def _configuration():
    environment = settings.MPESA_ENVIRONMENT.lower()

    if environment not in {"sandbox", "production"}:
        raise ImproperlyConfigured(
            "MPESA_ENVIRONMENT must be sandbox or production."
        )

    required = {
        "MPESA_CONSUMER_KEY": settings.MPESA_CONSUMER_KEY,
        "MPESA_CONSUMER_SECRET": settings.MPESA_CONSUMER_SECRET,
        "MPESA_SHORTCODE": settings.MPESA_SHORTCODE,
        "MPESA_PASSKEY": settings.MPESA_PASSKEY,
        "MPESA_CALLBACK_URL": settings.MPESA_CALLBACK_URL,
    }

    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "Missing M-Pesa settings: " + ", ".join(missing)
        )

    if not settings.MPESA_CALLBACK_URL.startswith("https://"):
        raise ImproperlyConfigured(
            "The M-Pesa callback URL must use HTTPS."
        )

    base_url = (
        "https://sandbox.safaricom.co.ke"
        if environment == "sandbox"
        else "https://api.safaricom.co.ke"
    )

    return base_url


def get_access_token():
    base_url = _configuration()

    response = requests.get(
        f"{base_url}/oauth/v1/generate",
        params={"grant_type": "client_credentials"},
        auth=(
            settings.MPESA_CONSUMER_KEY,
            settings.MPESA_CONSUMER_SECRET,
        ),
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    token = response.json().get("access_token")
    if not token:
        raise ValidationError("M-Pesa did not return an access token.")

    return token


def initiate_stk_push(*, phone_number, amount, payment_reference):
    """
    Initiate an STK Push for an existing pending PaymentTransaction.

    Never use this function's response as proof of payment.
    Verify the eventual transaction using trusted provider data.
    """
    base_url = _configuration()

    phone = re.sub(r"[\s+-]", "", phone_number or "")

    if phone.startswith("0") and len(phone) == 10:
        phone = "254" + phone[1:]
    elif phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone
    elif phone.startswith("1") and len(phone) == 9:
        phone = "254" + phone

    if not re.fullmatch(r"254[17]\d{8}", phone):
        raise ValidationError(
            "Enter a valid Kenyan mobile number, such as 0712345678."
        )

    amount = int(amount)
    if amount < 1:
        raise ValidationError("The M-Pesa amount must be at least KES 1.")

    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        (
            settings.MPESA_SHORTCODE
            + settings.MPESA_PASSKEY
            + timestamp
        ).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": str(payment_reference)[:12],
        "TransactionDesc": settings.MPESA_TRANSACTION_DESCRIPTION,
    }

    response = requests.post(
        f"{base_url}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("ResponseCode") != "0":
        raise ValidationError(
            data.get("ResponseDescription")
            or data.get("errorMessage")
            or "M-Pesa did not accept the STK Push request."
        )

    return data



def query_stk_push(*, checkout_request_id):
    """
    Ask Safaricom for the status of an existing STK Push request.

    A successful HTTP response only means the query was accepted.
    Inspect ResultCode and reconcile transaction details separately.
    """
    if not checkout_request_id:
        raise ValidationError("Checkout request ID is required.")

    base_url = _configuration()
    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")

    password = base64.b64encode(
        (
            settings.MPESA_SHORTCODE
            + settings.MPESA_PASSKEY
            + timestamp
        ).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    response = requests.post(
        f"{base_url}/mpesa/stkpushquery/v1/query",
        json=payload,
        headers={
            "Authorization": f"Bearer {get_access_token()}",
            "Content-Type": "application/json",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    data = response.json()

    # ResponseCode=0 means the query request was accepted, not
    # necessarily that the customer paid.
    if data.get("ResponseCode") != "0":
        raise ValidationError(
            data.get("errorMessage")
            or data.get("ResponseDescription")
            or "Safaricom did not accept the STK Query."
        )

    return data