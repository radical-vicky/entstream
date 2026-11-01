
import hashlib
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

from asgiref.sync import async_to_sync
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 60 * 10
MAX_RESULTS = 8

ALLOWED_VIDEO_HOSTS = {
    "xvideos.com",
    "www.xvideos.com",
}


class IframeParser(HTMLParser):
    """Extract the iframe src returned by the provider."""

    def __init__(self):
        super().__init__()
        self.src = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "iframe":
            return

        attributes = dict(attrs)
        self.src = attributes.get("src", "").strip()


def _clean_value(value):
    if value is None:
        return ""

    value_text = str(value).strip()

    if not value_text or "UNLOADED" in value_text.upper():
        return ""

    return value_text


def _valid_video_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and parsed.hostname in ALLOWED_VIDEO_HOSTS
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and bool(
                re.fullmatch(
                    r"/video\.[A-Za-z0-9]+/[^/]+/?",
                    parsed.path,
                )
            )
            and not parsed.query
            and not parsed.fragment
        )

    except (ValueError, TypeError):
        return False


def _valid_thumbnail_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )

    except (ValueError, TypeError):
        return False


def _extract_embed_url(embed_value):
    """
    Accept either an iframe HTML string or a direct embed URL.
    Return only a verified provider embed URL.
    """

    embed_value = _clean_value(embed_value)

    if not embed_value:
        return ""

    if "<iframe" in embed_value.lower():
        parser = IframeParser()

        try:
            parser.feed(embed_value)
            embed_value = parser.src
        except Exception:
            return ""

    if not _valid_embed_url(embed_value):
        return ""

    return embed_value


def _valid_embed_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and parsed.hostname in ALLOWED_VIDEO_HOSTS
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and bool(
                re.fullmatch(
                    r"/embedframe/[A-Za-z0-9]+/?",
                    parsed.path,
                )
            )
            and not parsed.query
            and not parsed.fragment
        )

    except (ValueError, TypeError):
        return False


async def _search_xvideos_async(query, max_results):
    # Import lazily: a broken optional dependency must not
    # prevent Django from starting.
    try:
        from xvideos_api import Client
    except ImportError:
        logger.exception(
            "XVideos API dependency is unavailable. "
            "XVideos search has been disabled."
        )
        return []

    results = []

    try:
        client = Client()

        search_generator = client.search(
            query=query,
            pages=1,
        )

        async for result in search_generator:
            if not result.succeeded:
                continue

            video = result.item

            if video is None:
                continue

            video_url = _clean_value(
                getattr(video, "url", "")
            )

            title = _clean_value(
                getattr(video, "title", "")
            )

            thumbnail = _clean_value(
                getattr(video, "thumbnail_url", "")
            )

            video_id = _clean_value(
                getattr(video, "video_id", "")
            )

            creator_url = _clean_value(
                getattr(video, "author_link", "")
            )

            duration = _clean_value(
                getattr(video, "length", "")
            )

            views = _clean_value(
                getattr(video, "views", "")
            )

            embed_value = getattr(
                video,
                "embed_url",
                "",
            )

            embed_url = _extract_embed_url(embed_value)

            if not video_url or not title:
                continue

            if not _valid_video_url(video_url):
                continue

            if thumbnail and not _valid_thumbnail_url(thumbnail):
                thumbnail = ""

            if creator_url and not _valid_video_url(creator_url):
                creator_url = ""

            results.append({
                "video_id": video_id,
                "title": title,
                "url": video_url,
                "thumbnail": thumbnail,
                "creator": "",
                "creator_url": creator_url,
                "duration": duration,
                "views": views,
                "platform": "XVideos",
                "age_restricted": True,
                "embedding_allowed": bool(embed_url),
                "embed_url": embed_url,
            })

            if len(results) >= max_results:
                break

    except Exception:
        logger.exception("XVideos search failed")

    return results


def search_xvideos(query, max_results=MAX_RESULTS):
    query = (query or "").strip()

    if len(query) < 3:
        return []

    try:
        max_results = max(1, min(int(max_results), 20))
    except (TypeError, ValueError):
        max_results = MAX_RESULTS

    cache_key = (
        "streamsphere_xvideos_search_v3_"
        + hashlib.sha256(
            query.lower().encode("utf-8")
        ).hexdigest()
        + f"_{max_results}"
    )

    cached_results = cache.get(cache_key)

    if cached_results is not None:
        return cached_results

    try:
        results = async_to_sync(
            _search_xvideos_async
        )(query, max_results)

    except Exception:
        logger.exception(
            "Unable to initialize XVideos search"
        )
        return []

    cache.set(cache_key, results, CACHE_TIMEOUT)

    return results
