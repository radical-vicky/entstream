
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import CreatorBalance, EarningTransaction, WithdrawalRequest


@transaction.atomic
def complete_earning(earning_id, external_reference=""):
    """
    Complete one verified earning and credit the creator exactly once.

    Call only after the underlying payment has been verified.
    """
    earning = EarningTransaction.objects.select_for_update().get(
        pk=earning_id
    )

    if earning.status == EarningTransaction.Status.COMPLETED:
        return earning

    if earning.status != EarningTransaction.Status.PENDING:
        raise ValueError("Only pending earnings can be completed.")

    balance, _ = CreatorBalance.objects.get_or_create(
        creator=earning.creator
    )
    balance = CreatorBalance.objects.select_for_update().get(
        pk=balance.pk
    )

    earning.status = EarningTransaction.Status.COMPLETED
    earning.completed_at = timezone.now()

    if external_reference:
        earning.external_reference = external_reference

    earning.save(
        update_fields=[
            "status",
            "completed_at",
            "external_reference",
        ]
    )

    balance.available_balance += earning.amount
    balance.total_earned += earning.amount
    balance.save(
        update_fields=[
            "available_balance",
            "total_earned",
            "updated_at",
        ]
    )

    return earning


@transaction.atomic
def request_withdrawal(
    *,
    creator,
    amount,
    payout_method,
    payout_account,
):
    amount = Decimal(str(amount))

    if amount <= Decimal("0.00"):
        raise ValueError("Withdrawal amount must be greater than zero.")

    balance, _ = CreatorBalance.objects.get_or_create(creator=creator)
    balance = CreatorBalance.objects.select_for_update().get(
        pk=balance.pk
    )

    if balance.available_balance < amount:
        raise ValueError("Your available balance is insufficient.")

    withdrawal = WithdrawalRequest.objects.create(
        creator=creator,
        amount=amount,
        payout_method=payout_method,
        payout_account=payout_account,
    )

    # Reserve the amount so it cannot be requested twice.
    balance.available_balance -= amount
    balance.pending_balance += amount
    balance.save(
        update_fields=[
            "available_balance",
            "pending_balance",
            "updated_at",
        ]
    )

    return withdrawal


@transaction.atomic
def process_withdrawal(withdrawal_id, new_status, admin_note=""):
    """
    Apply a staff-approved status transition to a withdrawal.

    A PAID transition must only be used after the actual payout is verified.
    """
    allowed_statuses = {
        WithdrawalRequest.Status.APPROVED,
        WithdrawalRequest.Status.PROCESSING,
        WithdrawalRequest.Status.PAID,
        WithdrawalRequest.Status.REJECTED,
    }

    if new_status not in allowed_statuses:
        raise ValueError("Invalid withdrawal status.")

    withdrawal = WithdrawalRequest.objects.select_for_update().get(
        pk=withdrawal_id
    )

    if withdrawal.status in {
        WithdrawalRequest.Status.PAID,
        WithdrawalRequest.Status.REJECTED,
    }:
        if withdrawal.status == new_status:
            return withdrawal
        raise ValueError("This withdrawal has already been finalized.")

    if new_status == WithdrawalRequest.Status.PROCESSING:
        if withdrawal.status != WithdrawalRequest.Status.APPROVED:
            raise ValueError("Approve the withdrawal before processing it.")

    if new_status == WithdrawalRequest.Status.PAID:
        if withdrawal.status not in {
            WithdrawalRequest.Status.APPROVED,
            WithdrawalRequest.Status.PROCESSING,
        }:
            raise ValueError("Approve the withdrawal before marking it paid.")

    balance = CreatorBalance.objects.select_for_update().get(
        creator=withdrawal.creator
    )

    if new_status == WithdrawalRequest.Status.REJECTED:
        balance.pending_balance -= withdrawal.amount
        balance.available_balance += withdrawal.amount
    elif new_status == WithdrawalRequest.Status.PAID:
        balance.pending_balance -= withdrawal.amount
        balance.total_paid_out += withdrawal.amount
        withdrawal.paid_at = timezone.now()

    if new_status in {
        WithdrawalRequest.Status.REJECTED,
        WithdrawalRequest.Status.PAID,
    }:
        balance.save(
            update_fields=[
                "available_balance",
                "pending_balance",
                "total_paid_out",
                "updated_at",
            ]
        )

    withdrawal.status = new_status
    withdrawal.admin_note = admin_note
    withdrawal.save(
        update_fields=[
            "status",
            "admin_note",
            "paid_at",
            "updated_at",
        ]
    )

    return withdrawal
