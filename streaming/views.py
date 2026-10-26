
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import LiveStreamForm
from .models import LiveStream


def stream_list(request):
    live_streams = LiveStream.objects.filter(
        status=LiveStream.Status.LIVE,
        is_public=True,
    ).select_related("creator")

    upcoming_streams = LiveStream.objects.filter(
        status=LiveStream.Status.SCHEDULED,
        is_public=True,
        scheduled_at__gte=timezone.now(),
    ).select_related("creator")

    query = request.GET.get("q", "").strip()
    if query:
        live_streams = live_streams.filter(
            Q(title__icontains=query)
            | Q(creator__username__icontains=query)
            | Q(category__icontains=query)
        )
        upcoming_streams = upcoming_streams.filter(
            Q(title__icontains=query)
            | Q(creator__username__icontains=query)
            | Q(category__icontains=query)
        )

    return render(request, "streaming/stream_list.html", {
        "live_streams": live_streams,
        "upcoming_streams": upcoming_streams,
        "query": query,
    })


def stream_detail(request, pk):
    stream = get_object_or_404(
        LiveStream.objects.select_related("creator"),
        pk=pk,
    )

    if not stream.is_public and (
        not request.user.is_authenticated
        or (request.user.pk != stream.creator_id and not request.user.is_staff)
    ):
        raise PermissionDenied

    return render(request, "streaming/stream_detail.html", {
        "stream": stream,
        "is_owner": (
            request.user.is_authenticated
            and request.user.pk == stream.creator_id
        ),
    })


@login_required
def my_streams(request):
    streams = LiveStream.objects.filter(
        creator=request.user
    ).order_by("-created_at")

    return render(request, "streaming/my_streams.html", {
        "streams": streams,
    })


@login_required
def schedule_stream(request):
    if request.method == "POST":
        form = LiveStreamForm(request.POST)
        if form.is_valid():
            stream = form.save(commit=False)
            stream.creator = request.user
            stream.status = LiveStream.Status.SCHEDULED
            stream.save()
            messages.success(request, "Your stream has been scheduled.")
            return redirect("streaming:my_streams")
    else:
        form = LiveStreamForm()

    return render(request, "streaming/stream_form.html", {
        "form": form,
        "page_title": "Schedule a stream",
    })


@login_required
def edit_stream(request, pk):
    stream = get_object_or_404(LiveStream, pk=pk, creator=request.user)

    if stream.status != LiveStream.Status.SCHEDULED:
        messages.error(request, "Only scheduled streams can be edited.")
        return redirect("streaming:my_streams")

    if request.method == "POST":
        form = LiveStreamForm(request.POST, instance=stream)
        if form.is_valid():
            form.save()
            messages.success(request, "Your stream details have been updated.")
            return redirect("streaming:my_streams")
    else:
        form = LiveStreamForm(instance=stream)

    return render(request, "streaming/stream_form.html", {
        "form": form,
        "page_title": "Edit stream",
        "stream": stream,
    })


@login_required
@require_POST
def start_stream(request, pk):
    stream = get_object_or_404(LiveStream, pk=pk, creator=request.user)

    if stream.start():
        messages.success(
            request,
            "Stream marked live. Start broadcasting through your configured provider."
        )
    else:
        messages.error(request, "This stream cannot be started in its current state.")

    return redirect("streaming:my_streams")


@login_required
@require_POST
def end_stream(request, pk):
    stream = get_object_or_404(LiveStream, pk=pk, creator=request.user)

    if stream.end():
        messages.success(request, "Your stream has been marked as ended.")
    else:
        messages.error(request, "This stream is not currently live.")

    return redirect("streaming:my_streams")


@login_required
@require_POST
def cancel_stream(request, pk):
    stream = get_object_or_404(LiveStream, pk=pk, creator=request.user)

    if stream.status != LiveStream.Status.SCHEDULED:
        messages.error(request, "Only scheduled streams can be cancelled.")
    else:
        stream.status = LiveStream.Status.CANCELLED
        stream.save(update_fields=["status", "updated_at"])
        messages.success(request, "Your scheduled stream has been cancelled.")

    return redirect("streaming:my_streams")
