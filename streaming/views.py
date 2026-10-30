
import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import StreamForm
from .models import Stream, StreamChatMessage
from .services import (
    create_rtmp_ingress,
    delete_rtmp_ingress,
    generate_livekit_token,
    livekit_configured,
)


logger = logging.getLogger(__name__)


def stream_list(request):
    streams = Stream.objects.filter(
        status=Stream.Status.LIVE,
        is_public=True,
    ).select_related("creator")

    return render(
        request,
        "streaming/index.html",
        {
            "streams": streams,
        },
    )


@login_required
def creator_dashboard(request):
    streams = Stream.objects.filter(
        creator=request.user,
    )

    return render(
        request,
        "streaming/index.html",
        {
            "streams": streams,
            "creator_dashboard": True,
        },
    )


@login_required
def create_stream(request):
    if request.method == "POST":
        form = StreamForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            stream = form.save(commit=False)
            stream.creator = request.user
            stream.save()

            messages.success(
                request,
                "Your livestream has been created.",
            )

            return redirect(
                "streaming:studio",
                stream_id=stream.pk,
            )

    else:
        form = StreamForm()

    return render(
        request,
        "streaming/create_stream.html",
        {
            "form": form,
        },
    )


@login_required
def edit_stream(request, stream_id):
    stream = get_object_or_404(
        Stream,
        pk=stream_id,
        creator=request.user,
    )

    if stream.status == Stream.Status.LIVE:
        messages.error(
            request,
            "End your livestream before editing it.",
        )

        return redirect(
            "streaming:studio",
            stream_id=stream.pk,
        )

    if request.method == "POST":
        form = StreamForm(
            request.POST,
            request.FILES,
            instance=stream,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Stream updated successfully.",
            )

            return redirect(
                "streaming:studio",
                stream_id=stream.pk,
            )

    else:
        form = StreamForm(instance=stream)

    return render(
        request,
        "streaming/create_stream.html",
        {
            "form": form,
            "stream": stream,
        },
    )


@login_required
def studio(request, stream_id):
    stream = get_object_or_404(
        Stream,
        pk=stream_id,
        creator=request.user,
    )

    return render(
        request,
        "streaming/studio.html",
        {
            "stream": stream,
            "livekit_url": getattr(
                settings,
                "LIVEKIT_URL",
                "",
            ),
        },
    )


def _notify_stream(stream, event_type):
    channel_layer = get_channel_layer()

    if channel_layer is None:
        logger.warning(
            "No channel layer configured for stream %s.",
            stream.pk,
        )
        return

    async_to_sync(channel_layer.group_send)(
        f"stream_chat_{stream.pk}",
        {
            "type": "chat_message",
            "username": "StreamSphere",
            "message": (
                "The livestream has started."
                if event_type == "started"
                else "The livestream has ended."
            ),
            "created_at": timezone.now().isoformat(),
        },
    )


@login_required
@require_POST
def start_stream(request, stream_id):
    stream = get_object_or_404(
        Stream,
        pk=stream_id,
        creator=request.user,
    )

    if not livekit_configured():
        return JsonResponse(
            {
                "error": "LiveKit is not configured.",
            },
            status=503,
        )

    if stream.status == Stream.Status.LIVE:
        return JsonResponse(
            {
                "error": "This stream is already live.",
            },
            status=400,
        )

    if stream.broadcast_type != Stream.BroadcastType.BROWSER:
        return JsonResponse(
            {
                "error": "Use OBS setup to start this stream.",
            },
            status=400,
        )

    with transaction.atomic():
        stream = Stream.objects.select_for_update().get(
            pk=stream.pk,
            creator=request.user,
        )

        if stream.status == Stream.Status.LIVE:
            return JsonResponse(
                {
                    "error": "This stream is already live.",
                },
                status=400,
            )

        stream.status = Stream.Status.LIVE
        stream.started_at = timezone.now()
        stream.ended_at = None
        stream.save(
            update_fields=[
                "status",
                "started_at",
                "ended_at",
                "updated_at",
            ]
        )

    _notify_stream(stream, "started")

    return JsonResponse(
        {
            "success": True,
            "message": "Your stream is now live.",
            "watch_url": stream.slug,
        }
    )


@login_required
@require_POST
def create_obs_ingress(request, stream_id):
    stream = get_object_or_404(
        Stream,
        pk=stream_id,
        creator=request.user,
    )

    if stream.broadcast_type != Stream.BroadcastType.OBS:
        return JsonResponse(
            {
                "error": "This stream is not configured for OBS.",
            },
            status=400,
        )

    if not livekit_configured():
        return JsonResponse(
            {
                "error": "LiveKit is not configured.",
            },
            status=503,
        )

    if stream.status == Stream.Status.LIVE:
        return JsonResponse(
            {
                "error": "This stream is already live.",
            },
            status=400,
        )

    if stream.ingress_id:
        return JsonResponse(
            {
                "error": (
                    "An OBS ingress already exists. "
                    "End the previous session first."
                ),
            },
            status=400,
        )

    try:
        ingress = create_rtmp_ingress(
            stream,
            request.user.get_username(),
        )

        stream.ingress_id = ingress["ingress_id"]
        stream.ingress_url = ingress["url"]
        stream.ingress_stream_key = ingress["stream_key"]

        # Preserve the existing application behaviour:
        # the stream becomes available after ingress creation.
        stream.status = Stream.Status.LIVE
        stream.started_at = timezone.now()
        stream.ended_at = None

        stream.save(
            update_fields=[
                "ingress_id",
                "ingress_url",
                "ingress_stream_key",
                "status",
                "started_at",
                "ended_at",
                "updated_at",
            ]
        )

        _notify_stream(stream, "started")

        return JsonResponse(
            {
                "success": True,
                "ingress_url": ingress["url"],
                "stream_key": ingress["stream_key"],
                "message": "OBS credentials created successfully.",
            }
        )

    except Exception:
        logger.exception(
            "Failed to create OBS ingress for stream %s",
            stream.pk,
        )

        return JsonResponse(
            {
                "error": (
                    "Could not create OBS ingress. "
                    "Check your LiveKit configuration and server logs."
                ),
            },
            status=502,
        )


@login_required
@require_POST
def end_stream(request, stream_id):
    stream = get_object_or_404(
        Stream,
        pk=stream_id,
        creator=request.user,
    )

    if stream.status != Stream.Status.LIVE:
        return JsonResponse(
            {
                "error": "This stream is not currently live.",
            },
            status=400,
        )

    ingress_id = stream.ingress_id

    stream.status = Stream.Status.ENDED
    stream.ended_at = timezone.now()
    stream.viewer_count = 0

    # Clear OBS credentials from the stream record.
    stream.ingress_id = ""
    stream.ingress_url = ""
    stream.ingress_stream_key = ""
    stream.ingress_username = ""
    stream.ingress_password = ""

    stream.save(
        update_fields=[
            "status",
            "ended_at",
            "viewer_count",
            "ingress_id",
            "ingress_url",
            "ingress_stream_key",
            "ingress_username",
            "ingress_password",
            "updated_at",
        ]
    )

    if ingress_id:
        try:
            delete_rtmp_ingress(ingress_id)

        except Exception:
            logger.exception(
                "Failed to delete LiveKit ingress %s",
                ingress_id,
            )

    _notify_stream(stream, "ended")

    return JsonResponse(
        {
            "success": True,
            "message": "Your livestream has ended.",
        }
    )


@require_GET
def stream_token(request, stream_id):
    """
    Generate a LiveKit access token.

    Stream owners:
        Can obtain a publishing token before starting their stream.

    Other authenticated users and guests:
        Can obtain a viewing token only when the stream is public and live.

    Unauthorized users:
        Cannot access private or inactive streams.
    """

    stream = get_object_or_404(
        Stream.objects.select_related("creator"),
        pk=stream_id,
    )

    is_owner = (
        request.user.is_authenticated
        and request.user.pk == stream.creator_id
    )

    if is_owner:
        if stream.broadcast_type != Stream.BroadcastType.BROWSER:
            return JsonResponse(
                {
                    "error": "This stream uses OBS broadcasting.",
                },
                status=400,
            )

        can_publish = True

    else:
        if (
            stream.status != Stream.Status.LIVE
            or not stream.is_public
        ):
            return JsonResponse(
                {
                    "error": "This livestream is not available.",
                },
                status=404,
            )

        can_publish = False

    if not livekit_configured():
        return JsonResponse(
            {
                "error": "Streaming service is unavailable.",
            },
            status=503,
        )

    identity = (
        f"user_{request.user.pk}"
        if request.user.is_authenticated
        else f"guest_{uuid.uuid4().hex}"
    )

    name = (
        request.user.get_username()
        if request.user.is_authenticated
        else "Guest"
    )

    try:
        token = generate_livekit_token(
            stream=stream,
            identity=identity,
            name=name,
            can_publish=can_publish,
        )

        return JsonResponse(
            {
                "token": token,
                "url": settings.LIVEKIT_URL,
                "room": stream.room_key,
                "can_publish": can_publish,
            }
        )

    except Exception:
        logger.exception(
            "LiveKit token generation failed for stream %s",
            stream.pk,
        )

        return JsonResponse(
            {
                "error": "Unable to generate streaming credentials.",
            },
            status=503,
        )


def watch_stream(request, stream_id):
    stream = get_object_or_404(
    Stream,
    pk=stream_id,
    is_public=True,
    status=Stream.Status.LIVE
)

    messages_list = (
        StreamChatMessage.objects
        .filter(stream=stream)
        .select_related("user")
        .order_by("-created_at")[:50]
    )

    if stream.status == Stream.Status.LIVE:
        Stream.objects.filter(
            pk=stream.pk,
        ).update(
            total_views=F("total_views") + 1,
        )

    return render(
        request,
        "streaming/watch.html",
        {
            "stream": stream,
            "chat_messages": reversed(messages_list),
        },
    )
