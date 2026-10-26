
import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import PaymentSearchForm
from .models import PaymentTransaction


@login_required
@require_GET
def payment_history(request):
    payments = PaymentTransaction.objects.filter(
        user=request.user
    ).order_by("-created_at")

    paginator = Paginator(payments, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "payments/history.html", {
        "page_obj": page_obj,
        "payments": page_obj.object_list,
    })


@login_required
@require_GET
def payment_detail(request, reference):
    payment = get_object_or_404(
        PaymentTransaction,
        reference=reference,
        user=request.user,
    )
    return render(request, "payments/detail.html", {"payment": payment})


@staff_member_required
@require_GET
def payment_admin_list(request):
    form = PaymentSearchForm(request.GET or None)
    payments = PaymentTransaction.objects.select_related("user").all()

    if form.is_valid():
        reference = form.cleaned_data.get("reference")
        status = form.cleaned_data.get("status")
        purpose = form.cleaned_data.get("purpose")

        if reference:
            payments = payments.filter(reference__icontains=reference)
        if status:
            payments = payments.filter(status=status)
        if purpose:
            payments = payments.filter(purpose=purpose)

    page_obj = Paginator(payments.order_by("-created_at"), 50).get_page(
        request.GET.get("page")
    )

    return render(request, "payments/admin_list.html", {
        "form": form,
        "page_obj": page_obj,
        "payments": page_obj.object_list,
    })


@csrf_exempt
@require_POST
def payment_provider_callback(request):
    """
    Provider integration placeholder.

    Do not mark payments as paid from unverified request data.
    Implement the specific provider's signature verification, event validation,
    and server-to-server payment lookup before calling the fulfillment service.
    """
    return JsonResponse(
        {
            "error": "Payment provider verification is not configured.",
            "code": "provider_not_configured",
        },
        status=501,
    )



from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import PaymentTransaction
from .reconciliation import reconcile_mpesa_payment


@login_required
@require_POST
def check_mpesa_status(request, reference):
    payment = get_object_or_404(
        PaymentTransaction,
        reference=reference,
        user=request.user,
    )

    try:
        payment, result = reconcile_mpesa_payment(
            payment_reference=payment.reference,
            user=request.user,
        )

        if payment.status == PaymentTransaction.Status.SUCCEEDED:
            messages.success(request, "Your payment is confirmed.")
        elif result is None:
            messages.info(
                request,
                f"Payment status: {payment.get_status_display()}.",
            )
        else:
            messages.info(
                request,
                "Safaricom returned a query response. "
                "The payment still needs transaction verification.",
            )

    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    except Exception:
        # Log the exception server-side in production; don't expose
        # credentials or raw provider responses to the customer.
        messages.error(
            request,
            "We could not check the payment right now. Please try again.",
        )

    return redirect("payments:detail", reference=payment.reference)