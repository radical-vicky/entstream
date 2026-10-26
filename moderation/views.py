from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ReportForm, ReportReviewForm, ModerationActionForm
from .models import ModerationAction, Report
from .services import apply_moderation_action, get_report_target


@login_required
def create_report(request, target_type, target_id):
    allowed_types = {
        Report.TargetType.VIDEO,
        Report.TargetType.COMMENT,
        Report.TargetType.ACCOUNT,
    }

    if target_type not in allowed_types:
        messages.error(request, "That report type is not supported.")
        return redirect("videos:list")

    report_stub = Report(
        reporter=request.user,
        target_type=target_type,
        target_id=target_id,
        reason=Report.Reason.OTHER,
    )
    target = get_report_target(report_stub)

    if target is None:
        messages.error(request, "The item you tried to report no longer exists.")
        return redirect("videos:list")

    if (
        target_type == Report.TargetType.ACCOUNT
        and target.pk == request.user.pk
    ):
        messages.error(request, "You cannot report your own account.")
        return redirect("videos:list")

    if request.method == "POST":
        form = ReportForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    report = form.save(commit=False)
                    report.reporter = request.user
                    report.target_type = target_type
                    report.target_id = target_id
                    report.save()
            except IntegrityError:
                messages.info(
                    request,
                    "You already have an open report for this item.",
                )
                return redirect("videos:list")

            messages.success(
                request,
                "Your report has been submitted for review.",
            )
            return redirect("videos:list")
    else:
        form = ReportForm()

    return render(
        request,
        "moderation/report_form.html",
        {
            "form": form,
            "target": target,
            "target_type": target_type,
        },
    )


@staff_member_required
def report_queue(request):
    status = request.GET.get("status", "")
    reports = Report.objects.select_related(
        "reporter",
        "reviewer",
    )

    valid_statuses = {choice[0] for choice in Report.Status.choices}
    if status in valid_statuses:
        reports = reports.filter(status=status)

    paginator = Paginator(reports, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "moderation/report_queue.html",
        {
            "reports": page_obj,
            "page_obj": page_obj,
            "current_status": status,
            "statuses": Report.Status.choices,
        },
    )


@staff_member_required
def report_detail(request, pk):
    report = get_object_or_404(
        Report.objects.select_related("reporter", "reviewer"),
        pk=pk,
    )
    target = get_report_target(report)

    if request.method == "POST":
        form = ReportReviewForm(request.POST)

        if form.is_valid():
            new_status = form.cleaned_data["status"]
            note = form.cleaned_data["resolution_note"].strip()

            report.status = new_status
            report.reviewer = request.user
            report.resolution_note = note

            if new_status in {
                Report.Status.ACTIONED,
                Report.Status.DISMISSED,
            }:
                report.reviewed_at = timezone.now()
            else:
                report.reviewed_at = None

            report.save(
                update_fields=[
                    "status",
                    "reviewer",
                    "resolution_note",
                    "reviewed_at",
                    "updated_at",
                ]
            )

            messages.success(request, "Report review saved.")
            return redirect("moderation:report_detail", pk=report.pk)
    else:
        form = ReportReviewForm(
            initial={
                "status": report.status,
                "resolution_note": report.resolution_note,
            }
        )

    action_form = ModerationActionForm()
    actions = report.actions.select_related("moderator")

    return render(
        request,
        "moderation/report_detail.html",
        {
            "report": report,
            "target": target,
            "form": form,
            "action_form": action_form,
            "actions": actions,
        },
    )


@staff_member_required
@require_POST
def take_action(request, pk):
    report = get_object_or_404(Report, pk=pk)
    form = ModerationActionForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Please select a valid moderation action.")
        return redirect("moderation:report_detail", pk=pk)

    target = get_report_target(report)
    if target is None:
        messages.error(
            request,
            "The reported item no longer exists. Review the report without applying an action.",
        )
        return redirect("moderation:report_detail", pk=pk)

    try:
        apply_moderation_action(
            moderator=request.user,
            action_type=form.cleaned_data["action_type"],
            target_type=report.target_type,
            target_id=report.target_id,
            note=form.cleaned_data["note"].strip(),
            report=report,
        )
    except (ValidationError, PermissionError) as exc:
        messages.error(request, str(exc))
        return redirect("moderation:report_detail", pk=pk)

    messages.success(request, "Moderation action recorded.")
    return redirect("moderation:report_detail", pk=pk)


@staff_member_required
def action_history(request):
    actions = ModerationAction.objects.select_related(
        "moderator",
        "report",
    )

    paginator = Paginator(actions, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "moderation/action_history.html",
        {"actions": page_obj, "page_obj": page_obj},
    )