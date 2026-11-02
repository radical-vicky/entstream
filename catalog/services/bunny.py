
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BUNNY_API_URL = "https://video.bunnycdn.com"


class BunnyStreamError(Exception):
    pass


def get_bunny_config():
    library_id = getattr(settings, "BUNNY_STREAM_LIBRARY_ID", "")
    api_key = getattr(settings, "BUNNY_STREAM_API_KEY", "")

    if not library_id or not api_key:
        raise BunnyStreamError(
            "Bunny Stream library ID or API key is missing."
        )

    return str(library_id), api_key


def bunny_request(method, endpoint, **kwargs):
    library_id, api_key = get_bunny_config()

    headers = kwargs.pop("headers", {})
    headers["AccessKey"] = api_key
    headers["Accept"] = "application/json"

    url = f"{BUNNY_API_URL}/library/{library_id}/{endpoint.lstrip('/')}"

    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()

        if response.content:
            return response.json()

        return {}

    except requests.RequestException as exc:
        logger.exception("Bunny Stream API request failed.")
        raise BunnyStreamError(
            "Unable to communicate with Bunny Stream."
        ) from exc


def create_video(title):
    """Create an empty video record in the Bunny library."""
    return bunny_request(
        "POST",
        "videos",
        json={"title": title},
        headers={"Content-Type": "application/json"},
    )


def get_video(video_id):
    """Retrieve video processing information."""
    return bunny_request("GET", f"videos/{video_id}")


def delete_video(video_id):
    """Delete a video from Bunny Stream."""
    return bunny_request("DELETE", f"videos/{video_id}")


def get_embed_url(video_id):
    """Return the Bunny Stream iframe player URL."""
    library_id, _ = get_bunny_config()
    hostname = getattr(
        settings,
        "BUNNY_STREAM_CDN_HOST",
        "",
    )

    if not hostname:
        raise BunnyStreamError("Bunny CDN hostname is missing.")

    return (
        f"https://iframe.mediadelivery.net/embed/"
        f"{library_id}/{video_id}"
    )


def get_video_status(video_id):
    data = get_video(video_id)

    # Bunny's API status 4 indicates the video is finished processing.
    status = data.get("status")

    return {
        "status": status,
        "length_seconds": data.get("length", 0),
        "available_resolutions": data.get(
            "availableResolutions", ""
        ),
        "thumbnail_file_name": data.get(
            "thumbnailFileName", ""
        ),
    }
