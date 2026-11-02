
import logging

import requests

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

TMDB_HEADERS = {
    "Authorization": f"Bearer {getattr(settings, 'TMDB_ACCESS_TOKEN', '')}",
    "accept": "application/json",
}


def tmdb_request(endpoint, params=None):
    """Make a cached request to TMDB."""
    token = getattr(settings, "TMDB_ACCESS_TOKEN", "")

    if not token:
        logger.error("TMDB_ACCESS_TOKEN is not configured.")
        return {}

    cache_key = f"tmdb_v1_{endpoint}_{str(params or {})}"
    cached = cache.get(cache_key)

    if cached is not None:
        return cached

    try:
        response = requests.get(
            f"{TMDB_BASE_URL}/{endpoint.lstrip('/')}",
            headers=TMDB_HEADERS,
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
    """Add display-friendly poster and detail information."""
    prepared = []

    for item in items or []:
        if not item.get("id"):
            continue

        item = dict(item)
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


@require_GET
def catalog_home(request):
    query = request.GET.get("q", "").strip()[:100]
    category = request.GET.get("type", "movie")

    if category not in ("movie", "tv"):
        category = "movie"

    if query:
        endpoint = "search/movie" if category == "movie" else "search/tv"
        results = tmdb_request(
            endpoint,
            {
                "query": query,
                "include_adult": "false",
                "page": 1,
            },
        )

        titles = prepare_titles(
            results.get("results", []),
            category,
        )

        context = {
            "query": query,
            "category": category,
            "titles": titles,
            "searching": True,
        }

        return render(request, "catalog/index.html", context)

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

    for title, endpoint in sections:
        data = tmdb_request(endpoint)
        collections.append({
            "title": title,
            "items": prepare_titles(
                data.get("results", []),
                category,
            ),
        })

    context = {
        "category": category,
        "collections": collections,
        "searching": False,
    }

    return render(request, "catalog/index.html", context)


@require_GET
def catalog_detail(request, media_type, movie_id):
    if media_type not in ("movie", "tv"):
        return render(
            request,
            "404.html",
            status=404,
        )

    data = tmdb_request(
        f"{media_type}/{movie_id}",
        {
            "append_to_response": "videos,credits,recommendations",
        },
    )

    if not data or not data.get("id"):
        return render(
            request,
            "404.html",
            status=404,
        )

    title = data.get("title") or data.get("name") or "Untitled"

    videos = data.get("videos", {}).get("results", [])
    trailer = next(
        (
            video for video in videos
            if video.get("site") == "YouTube"
            and video.get("type") == "Trailer"
            and video.get("key")
        ),
        None,
    )

    cast = data.get("credits", {}).get("cast", [])[:12]

    recommendations = prepare_titles(
        data.get("recommendations", {}).get("results", []),
        media_type,
    )

    context = {
        "item": data,
        "title": title,
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
        "trailer_url": (
            f"https://www.youtube.com/embed/{trailer['key']}"
            if trailer
            else ""
        ),
        "cast": cast,
        "recommendations": recommendations,
    }

    return render(request, "catalog/detail.html", context)
