
from datetime import timedelta

from asgiref.sync import async_to_sync
from django.conf import settings

from livekit import api


def livekit_configured():
    return all([
        getattr(settings, "LIVEKIT_URL", ""),
        getattr(settings, "LIVEKIT_API_KEY", ""),
        getattr(settings, "LIVEKIT_API_SECRET", ""),
    ])


def generate_livekit_token(
    stream,
    identity,
    name,
    can_publish=False,
):
    """
    Generate a LiveKit JWT for a stream participant.

    The stream owner receives publishing permissions.
    Viewers receive subscription permissions only.
    """

    if not livekit_configured():
        raise RuntimeError(
            "LiveKit credentials are not configured."
        )

    access_token = (
        api.AccessToken(
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        )
        .with_identity(str(identity))
        .with_name(str(name))
        .with_ttl(timedelta(hours=2))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=stream.room_key,
                can_publish=can_publish,
                can_subscribe=True,
                can_publish_data=can_publish,
            )
        )
    )

    return access_token.to_jwt()


async def _create_rtmp_ingress(stream, username):
    livekit_api = api.LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )

    try:
        ingress = await livekit_api.ingress.create_ingress(
            api.CreateIngressRequest(
                input_type=api.IngressInput.RTMP_INPUT,
                name=f"StreamSphere - {stream.title[:80]}",
                room_name=stream.room_key,
                participant_identity=f"obs_{stream.pk}",
                participant_name=str(username),
                enable_transcoding=True,
            )
        )

        return {
            "ingress_id": ingress.ingress_id,
            "url": ingress.url,
            "stream_key": ingress.stream_key,
        }

    finally:
        await livekit_api.aclose()


def create_rtmp_ingress(stream, username):
    """
    Create an RTMP ingress for OBS broadcasting.
    """

    if not livekit_configured():
        raise RuntimeError(
            "LiveKit credentials are not configured."
        )

    return async_to_sync(_create_rtmp_ingress)(
        stream,
        username,
    )


async def _delete_rtmp_ingress(ingress_id):
    livekit_api = api.LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )

    try:
        await livekit_api.ingress.delete_ingress(
            api.DeleteIngressRequest(
                ingress_id=ingress_id,
            )
        )

    finally:
        await livekit_api.aclose()


def delete_rtmp_ingress(ingress_id):
    """
    Delete an existing LiveKit RTMP ingress.
    """

    if not ingress_id or not livekit_configured():
        return

    return async_to_sync(_delete_rtmp_ingress)(
        ingress_id,
    )
