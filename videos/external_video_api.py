
import re
from urllib.parse import urlparse

import requests


ALLOWED_HOSTS = {
    "xvideos.com",
    "www.xvideos.com",
}


def validate_xvideos_url(url):
    parsed = urlparse(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or not re.fullmatch(r"/video\.[a-zA-Z0-9]+/[^/]+/?", parsed.path)
    ):
        raise ValueError("Please provide a valid XVideos video URL.")

    return url


def fetch_video_metadata(url):
    url = validate_xvideos_url(url)

    response = requests.get(
        url,
        headers={"User-Agent": "StreamSphere/1.0"},
        timeout=15,
    )
    response.raise_for_status()

    # Do not scrape private player endpoints or extract
    # restricted video files.
    return {
        "source": "xvideos",
        "original_url": url,
        "status": "page_accessible",
    }
