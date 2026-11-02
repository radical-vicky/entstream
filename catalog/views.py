
import hashlib
import json
import logging
import time
from urllib.parse import urlencode

import requests

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from subscriptions.models import UserSubscription

from .models import (
    CatalogTitle,
    Episode,
    MovieStream,
    VideoAsset,
    WatchProgress,
)

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
BUNNY_PLAYER_URL = "https://player.mediadelivery.net/embed"


# =========================================================
# TMDB
# =========================================================

def tmdb_request(endpoint, params=None):
    """Make a cached request to TMDB."""
    token = getattr(settings, "TMDB_ACCESS_TOKEN", "")

    if not token:
        logger.error("TMDB_ACCESS_TOKEN is not configured.")
        return {}

    cache_key = f"tmdb_v3_{endpoint}_{str(params or {})}"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
    }

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/{endpoint.lstrip('/')}",
            headers=headers,
            params=params or {},
            timeout=12,
        )
        response.raise_for_status()

        data = response.json()
        cache.set(cache_key, data, 60 * 15)

        return data

    except requests.RequestException:
        logger.exception("TMDB request failed: %s", endpoint)
        return {}


def prepare_titles(items, media_type):
    """Prepare TMDB results for catalog templates."""
    prepared = []

    for original_item in items or []:
        if not original_item.get("id"):
            continue

        item = dict(original_item)
        item["media_type"] = media_type

        item["display_title"] = (
            item.get("title")
            or item.get("name")
            or "Untitled"
        )

        item["display_date"] = (
            item.get("release_date")
            or item.get("first_air_date")
            or ""
        )

        item["poster_url"] = (
            f"{IMAGE_BASE_URL}/w500{item['poster_path']}"
            if item.get("poster_path")
            else ""
        )

        item["backdrop_url"] = (
            f"{IMAGE_BASE_URL}/w1280{item['backdrop_path']}"
            if item.get("backdrop_path")
            else ""
        )

        prepared.append(item)

    return prepared


# =========================================================
# SUBSCRIPTION ACCESS
# =========================================================

def user_has_premium_access(user):
    """Return True when the user has an active, unexpired plan."""
    if not user.is_authenticated:
        return False

    return UserSubscription.objects.filter(
        user=user,
        status=UserSubscription.Status.ACTIVE,
        expires_at__gt=timezone.now(),
    ).exists()


def can_watch_title(user, title):
    """Check whether the user is allowed to watch a title."""
    if not title.is_premium:
        return True

    return user_has_premium_access(user)


def access_required_response(request, title):
    """Render the login or subscription-required page."""
    if not request.user.is_authenticated:
        return render(
            request,
            "catalog/access_required.html",
            {
                "title": title,
                "requires_login": True,
            },
            status=403,
        )

    return render(
        request,
        "catalog/access_required.html",
        {
            "title": title,
            "requires_login": False,
        },
        status=403,
    )


# =========================================================
# VIDEO READINESS
# =========================================================

def is_video_ready(video):
    """Check whether an asset is active and ready to play."""
    return bool(
        video
        and video.is_active
        and video.status == VideoAsset.READY
    )


# =========================================================
# BUNNY STREAM PLAYBACK
# =========================================================

def bunny_embed_url(video_id):
    """
    Generate a Bunny Stream embed URL.

    When Embed View Token Authentication is enabled,
    BUNNY_STREAM_TOKEN_KEY must contain the library's
    Token Authentication Key.

    Never expose this key to browser-side JavaScript.
    """
    library_id = getattr(
        settings,
        "BUNNY_STREAM_LIBRARY_ID",
        "",
    )

    token_key = getattr(
        settings,
        "BUNNY_STREAM_TOKEN_KEY",
        "",
    )

    if not library_id:
        raise ValueError("Bunny Stream library ID is missing.")

    if not video_id:
        raise ValueError("Bunny video ID is missing.")

    base_url = (
        f"{BUNNY_PLAYER_URL}/{library_id}/{video_id}"
    )

    if not token_key:
        logger.warning(
            "BUNNY_STREAM_TOKEN_KEY is not configured. "
            "Returning an unsigned Bunny embed URL."
        )
        return base_url

    expires = int(time.time()) + 3600

    token = hashlib.sha256(
        f"{token_key}{video_id}{expires}".encode("utf-8")
    ).hexdigest()

    query = urlencode({
        "token": token,
        "expires": expires,
    })

    return f"{base_url}?{query}"


def get_video_playback_url(video):
    """Resolve a ready Bunny or authorized external video."""
    if not is_video_ready(video):
        return ""

    if video.provider == VideoAsset.BUNNY:
        try:
            return bunny_embed_url(video.provider_video_id)
        except ValueError:
            logger.exception(
                "Unable to generate Bunny playback URL."
            )
            return ""

    if video.provider == VideoAsset.EXTERNAL:
        return video.external_embed_url or ""

    return ""


# =========================================================
# CATALOG DISCOVERY
# =========================================================

@require_GET
def catalog_home(request):
    query = request.GET.get("q", "").strip()[:100]
    category = request.GET.get("type", "movie")

    if category not in ("movie", "tv"):
        category = "movie"

    if query:
        endpoint = (
            "search/movie"
            if category == "movie"
            else "search/tv"
        )

        results = tmdb_request(
            endpoint,
            {
                "query": query,
                "include_adult": "false",
                "page": 1,
            },
        )

        return render(
            request,
            "catalog/index.html",
            {
                "query": query,
                "category": category,
                "titles": prepare_titles(
                    results.get("results", []),
                    category,
                ),
                "searching": True,
            },
        )

    if category == "movie":
        sections = [
            ("Trending Movies", "trending/movie/week"),
            ("Popular Movies", "movie/popular"),
            ("Upcoming Movies", "movie/upcoming"),
            ("Top Rated Movies", "movie/top_rated"),
        ]
    else:
        sections = [
            ("Trending TV Series", "trending/tv/week"),
            ("Popular TV Series", "tv/popular"),
            ("Top Rated TV Series", "tv/top_rated"),
        ]

    collections = []

    for section_title, endpoint in sections:
        data = tmdb_request(endpoint)

        collections.append({
            "title": section_title,
            "items": prepare_titles(
                data.get("results", []),
                category,
            ),
        })

    return render(
        request,
        "catalog/index.html",
        {
            "category": category,
            "collections": collections,
            "searching": False,
        },
    )


# =========================================================
# MOVIE AND SERIES DETAILS
# =========================================================

@require_GET
def catalog_detail(request, media_type, movie_id):
    if media_type not in ("movie", "tv"):
        raise Http404("Invalid catalog category.")

    data = tmdb_request(
        f"{media_type}/{movie_id}",
        {
            "append_to_response": (
                "credits,recommendations,videos"
            ),
        },
    )

    if not data or not data.get("id"):
        raise Http404("Title not found.")

    title_name = (
        data.get("title")
        or data.get("name")
        or "Untitled"
    )

    local_title = CatalogTitle.objects.filter(
        media_type=media_type,
        tmdb_id=movie_id,
        is_published=True,
    ).first()

    movie_stream = None
    movie_playback_available = False
    seasons = []

    if local_title and media_type == "movie":
        movie_stream = (
            MovieStream.objects
            .select_related("video")
            .filter(title=local_title)
            .first()
        )

        if movie_stream:
            movie_playback_available = is_video_ready(
                movie_stream.video
            )

    elif local_title and media_type == "tv":
        seasons = list(
            local_title.seasons
            .prefetch_related("episodes__video")
            .all()
        )

        for season in seasons:
            for episode in season.episodes.all():
                episode.playback_available = (
                    episode.is_published
                    and is_video_ready(episode.video)
                )

    cast = data.get("credits", {}).get("cast", [])[:12]

    recommendations = prepare_titles(
        data.get("recommendations", {}).get("results", []),
        media_type,
    )

    # Select an official YouTube trailer when available.
    videos = data.get("videos", {}).get("results", [])

    trailer = next(
        (
            video
            for video in videos
            if (
                video.get("site") == "YouTube"
                and video.get("type") == "Trailer"
                and video.get("key")
                and video.get("official", False)
            )
        ),
        None,
    )

    # Fall back to another YouTube trailer if TMDB has
    # not marked any trailer as official.
    if not trailer:
        trailer = next(
            (
                video
                for video in videos
                if (
                    video.get("site") == "YouTube"
                    and video.get("type") == "Trailer"
                    and video.get("key")
                )
            ),
            None,
        )

    trailer_url = (
        f"https://www.youtube.com/embed/{trailer['key']}"
        if trailer
        else ""
    )

    context = {
        "item": data,
        "title": title_name,
        "media_type": media_type,
        "poster_url": (
            f"{IMAGE_BASE_URL}/w500{data['poster_path']}"
            if data.get("poster_path")
            else ""
        ),
        "backdrop_url": (
            f"{IMAGE_BASE_URL}/w1280{data['backdrop_path']}"
            if data.get("backdrop_path")
            else ""
        ),
        "trailer_url": trailer_url,
        "cast": cast,
        "recommendations": recommendations,
        "local_title": local_title,
        "movie_stream": movie_stream,
        "movie_playback_available": movie_playback_available,
        "seasons": seasons,
        "has_premium_access": user_has_premium_access(
            request.user
        ),
    }

    return render(
        request,
        "catalog/detail.html",
        context,
    )


# =========================================================
# MOVIE PLAYER
# =========================================================

@require_GET
def movie_player(request, title_id):
    title = get_object_or_404(
        CatalogTitle,
        pk=title_id,
        media_type=CatalogTitle.MOVIE,
        is_published=True,
    )

    if not can_watch_title(request.user, title):
        return access_required_response(request, title)

    movie_stream = get_object_or_404(
        MovieStream.objects.select_related("video"),
        title=title,
    )

    video = movie_stream.video
    embed_url = get_video_playback_url(video)

    if not embed_url:
        return render(
            request,
            "catalog/unavailable.html",
            {"title": title},
            status=503,
        )

    progress = None

    if request.user.is_authenticated:
        progress = WatchProgress.objects.filter(
            user=request.user,
            video=video,
        ).first()

    return render(
        request,
        "catalog/movie_player.html",
        {
            "title": title,
            "video": video,
            "embed_url": embed_url,
            "progress": progress,
            "is_movie": True,
        },
    )


# =========================================================
# EPISODE PLAYER
# =========================================================

@require_GET
def episode_player(request, episode_id):
    episode = get_object_or_404(
        Episode.objects.select_related(
            "season__series",
            "video",
        ),
        pk=episode_id,
        is_published=True,
        season__series__is_published=True,
    )

    title = episode.season.series

    if not can_watch_title(request.user, title):
        return access_required_response(request, title)

    video = episode.video
    embed_url = get_video_playback_url(video)

    if not embed_url:
        return render(
            request,
            "catalog/unavailable.html",
            {"title": episode.title},
            status=503,
        )

    # Find the next episode using season and episode
    # numbers rather than database primary keys.
    next_episode = (
        Episode.objects
        .filter(
            season__series=title,
            is_published=True,
        )
        .filter(
            Q(
                season__season_number__gt=(
                    episode.season.season_number
                )
            )
            |
            Q(
                season__season_number=(
                    episode.season.season_number
                ),
                episode_number__gt=episode.episode_number,
            )
        )
        .order_by(
            "season__season_number",
            "episode_number",
        )
        .first()
    )

    previous_episode = (
        Episode.objects
        .filter(
            season__series=title,
            is_published=True,
        )
        .filter(
            Q(
                season__season_number__lt=(
                    episode.season.season_number
                )
            )
            |
            Q(
                season__season_number=(
                    episode.season.season_number
                ),
                episode_number__lt=episode.episode_number,
            )
        )
        .order_by(
            "-season__season_number",
            "-episode_number",
        )
        .first()
    )

    progress = None

    if request.user.is_authenticated:
        progress = WatchProgress.objects.filter(
            user=request.user,
            video=video,
        ).first()

    return render(
        request,
        "catalog/episode_player.html",
        {
            "title": title,
            "episode": episode,
            "video": video,
            "embed_url": embed_url,
            "next_episode": next_episode,
            "previous_episode": previous_episode,
            "progress": progress,
        },
    )


# =========================================================
# WATCH PROGRESS
# =========================================================

@require_POST
def save_watch_progress(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )

        video_id = int(payload.get("video_id"))
        position = int(payload.get("position_seconds", 0))

    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return JsonResponse(
            {"error": "Invalid progress information."},
            status=400,
        )

    if position < 0:
        return JsonResponse(
            {"error": "Invalid playback position."},
            status=400,
        )

    video = get_object_or_404(
        VideoAsset,
        pk=video_id,
        is_active=True,
        status=VideoAsset.READY,
    )

    # Verify that this video is attached to a published
    # movie or a published episode.
    movie_stream = (
        MovieStream.objects
        .select_related("title")
        .filter(
            video=video,
            title__is_published=True,
        )
        .first()
    )

    episode = (
        Episode.objects
        .select_related("season__series")
        .filter(
            video=video,
            is_published=True,
            season__series__is_published=True,
        )
        .first()
    )

    if not movie_stream and not episode:
        return JsonResponse(
            {"error": "This video is not available."},
            status=404,
        )

    # Check the entitlement for the title containing
    # this video before accepting a progress update.
    if movie_stream:
        if not can_watch_title(request.user, movie_stream.title):
            return JsonResponse(
                {"error": "You are not allowed to watch this video."},
                status=403,
            )

    if episode:
        if not can_watch_title(
            request.user,
            episode.season.series,
        ):
            return JsonResponse(
                {"error": "You are not allowed to watch this video."},
                status=403,
            )

    # Prevent impossible progress values.
    if video.duration_seconds:
        position = min(position, video.duration_seconds)

    completed = (
        video.duration_seconds > 0
        and position >= video.duration_seconds * 0.9
    )

    progress, _ = WatchProgress.objects.update_or_create(
        user=request.user,
        video=video,
        defaults={
            "position_seconds": position,
            "completed": completed,
        },
    )

    return JsonResponse({
        "success": True,
        "position_seconds": progress.position_seconds,
        "completed": progress.completed,
    })
