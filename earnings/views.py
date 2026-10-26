
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import WithdrawalRequestForm, WithdrawalReviewForm
from .models import (
    CreatorBalance,
    EarningTransaction,
    WithdrawalRequest,
)
from .services import process_withdrawal, request_withdrawal


@login_required
def dashboard(request):
    balance, _ = CreatorBalance.objects.get_or_create(
        creator=request.user
    )

    transactions = EarningTransaction.objects.filter(
        creator=request.user
    )
    withdrawals = WithdrawalRequest.objects.filter(
        creator=request.user
    )

    completed_earnings = transactions.filter(
        status=EarningTransaction.Status.COMPLETED
    ).aggregate(total=Sum("amount"))["total"]

    paginator = Paginator(transactions, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "earnings/dashboard.html",
        {
            "balance": balance,
            "transactions": page_obj,
            "page_obj": page_obj,
            "withdrawals": withdrawals[:10],
            "completed_earnings": completed_earnings or 0,
        },
    )


@login_required
def withdrawal_request(request):
    if request.method == "POST":
        form = WithdrawalRequestForm(request.POST)

        if form.is_valid():
            try:
                withdrawal = request_withdrawal(
                    creator=request.user,
                    amount=form.cleaned_data["amount"],
                    payout_method=form.cleaned_data["payout_method"],
                    payout_account=form.cleaned_data["payout_account"],
                )
            except ValueError as exc:
                form.add_error("amount", str(exc))
            else:
                messages.success(
                    request,
                    f"Withdrawal request {withdrawal.reference} submitted for review.",
                )
                return redirect("earnings:dashboard")
    else:
        form = WithdrawalRequestForm()

    balance, _ = CreatorBalance.objects.get_or_create(
        creator=request.user
    )

    return render(
        request,
        "earnings/withdrawal_form.html",
        {
            "form": form,
            "balance": balance,
        },
    )


@staff_member_required
def withdrawal_review_list(request):
    withdrawals = (
        WithdrawalRequest.objects
        .select_related("creator")
        .all()
    )

    paginator = Paginator(withdrawals, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "earnings/withdrawal_review_list.html",
        {"withdrawals": page_obj, "page_obj": page_obj},
    )


@staff_member_required
def withdrawal_review(request, pk):
    withdrawal = get_object_or_404(
        WithdrawalRequest.objects.select_related("creator"),
        pk=pk,
    )

    if request.method == "POST":
        form = WithdrawalReviewForm(request.POST)

        if form.is_valid():
            try:
                process_withdrawal(
                    withdrawal_id=withdrawal.pk,
                    new_status=form.cleaned_data["status"],
                    admin_note=form.cleaned_data["admin_note"],
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    "Withdrawal status updated.",
                )
                return redirect("earnings:withdrawal_review", pk=withdrawal.pk)
    else:
        form = WithdrawalReviewForm(
            initial={
                "status": withdrawal.status,
                "admin_note": withdrawal.admin_note,
            }
        )

    return render(
        request,
        "earnings/withdrawal_review.html",
        {
            "withdrawal": withdrawal,
            "form": form,
        },
    )


@staff_member_required
@require_POST
def complete_earning_transaction(request, pk):
    """
    Staff-only manual completion for a payment already verified externally.
    """
    from .services import complete_earning

    earning = get_object_or_404(EarningTransaction, pk=pk)

    try:
        complete_earning(earning.pk)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Earning transaction completed.")

    return redirect("admin:earnings_earningtransaction_changelist")
