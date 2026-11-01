
import hashlib
import time

import requests

from django.conf import settings


BUNNY_API_BASE = "https://video.bunnycdn.com"


def create_bunny_video(title):
    library_id = settings.BUNNY_STREAM_LIBRARY_ID
    api_key = settings.BUNNY_STREAM_API_KEY

    if not library_id or not api_key:
        raise ValueError("Bunny Stream credentials are missing.")

    response = requests.post(
        f"{BUNNY_API_BASE}/library/{library_id}/videos",
        headers={
            "AccessKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={"title": title},
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    video_id = data.get("guid")

    if not video_id:
        raise ValueError("Bunny did not return a video ID.")

    expiration = int(time.time()) + 3600

    signature = hashlib.sha256(
        (
            str(library_id)
            + str(api_key)
            + str(expiration)
            + str(video_id)
        ).encode("utf-8")
    ).hexdigest()

    return {
        "video_id": video_id,
        "library_id": str(library_id),
        "expiration": expiration,
        "signature": signature,
    }


def get_bunny_embed_url(video):
    if not video.bunny_video_id or not video.bunny_library_id:
        return ""

    return (
        "https://iframe.mediadelivery.net/embed/"
        f"{video.bunny_library_id}/{video.bunny_video_id}"
    )
