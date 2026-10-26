from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import SubscriptionPlan, UserSubscription


def plan_list(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)

    active_subscription = None
    if request.user.is_authenticated:
        active_subscription = (
            UserSubscription.objects.filter(
                user=request.user,
                status=UserSubscription.Status.ACTIVE,
                expires_at__gt=timezone.now(),
            )
            .select_related("plan")
            .first()
        )

    return render(
        request,
        "subscriptions/plans.html",
        {
            "plans": plans,
            "active_subscription": active_subscription,
        },
    )


@login_required
def my_subscriptions(request):
    subscriptions = (
        UserSubscription.objects.filter(user=request.user)
        .select_related("plan")
    )

    return render(
        request,
        "subscriptions/my_subscriptions.html",
        {"subscriptions": subscriptions},
    )


@login_required
@require_POST
def subscribe(request, plan_id):
    plan = get_object_or_404(
        SubscriptionPlan,
        pk=plan_id,
        is_active=True,
    )

    with transaction.atomic():
        existing = (
            UserSubscription.objects.select_for_update()
            .filter(
                user=request.user,
                plan=plan,
                status=UserSubscription.Status.PENDING,
            )
            .first()
        )

        if existing:
            subscription = existing
        else:
            subscription = UserSubscription.objects.create(
                user=request.user,
                plan=plan,
                status=UserSubscription.Status.PENDING,
            )

    # Payment processing belongs in the payment integration.
    # Do not activate the subscription from this request.
    messages.info(
        request,
        "Your subscription request is ready. Complete payment through the configured payment process to activate it.",
    )

    return redirect("subscriptions:my_subscriptions")


@login_required
@require_POST
def cancel_subscription(request, subscription_id):
    subscription = get_object_or_404(
        UserSubscription,
        pk=subscription_id,
        user=request.user,
    )

    if subscription.status == UserSubscription.Status.ACTIVE:
        subscription.cancel()
        messages.success(
            request,
            "Your subscription has been cancelled.",
        )
    elif subscription.status == UserSubscription.Status.PENDING:
        subscription.status = UserSubscription.Status.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.save(
            update_fields=[
                "status",
                "cancelled_at",
                "updated_at",
            ]
        )
        messages.success(
            request,
            "Your pending subscription request has been cancelled.",
        )
    else:
        messages.info(
            request,
            "This subscription is not active or pending.",
        )

    return redirect("subscriptions:my_subscriptions")