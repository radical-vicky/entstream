import cloudinary
import cloudinary.utils
import hashlib
import json
import os
import re
import requests
import time

from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Notification
from creators.models import Follow
from .access import can_user_watch_video
from .forms import VideoForm, VideoUploadForm
from .models import Video, VideoLike, VideoComment
from .purchase_services import create_video_purchase_payment


YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


# ============================================================
# BUNNY STREAM CONFIGURATION
# ============================================================

BUNNY_API_URL = "https://video.bunnycdn.com"
BUNNY_TUS_URL = "https://video.bunnycdn.com/tusupload"

PIPED_INSTANCES = [
    "https://pipedapi.adminforge.de",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.nosebs.ru",
    "https://pipedapi-libre.kavin.rocks",
    "https://api.piped.private.coffee",
    "https://pipedapi.drgns.space",
]


def get_bunny_settings():
    library_id = str(getattr(settings, "BUNNY_STREAM_LIBRARY_ID", "")).strip()
    api_key = str(getattr(settings, "BUNNY_STREAM_API_KEY", "")).strip()
    return library_id, api_key


def is_bunny_video(video):
    return (
        getattr(video, "source", "") == "bunny"
        and bool(getattr(video, "bunny_video_id", ""))
        and bool(getattr(video, "bunny_library_id", ""))
    )


def get_bunny_embed_url(video):
    if not is_bunny_video(video):
        return ""
    return f"https://iframe.mediadelivery.net/embed/{video.bunny_library_id}/{video.bunny_video_id}"


# ============================================================
# BUNNY STREAM UPLOAD
# ============================================================

@login_required
@require_POST
def create_bunny_upload(request):
    library_id, api_key = get_bunny_settings()

    if not library_id or not api_key:
        return JsonResponse({"success": False, "error": "Bunny Stream is not configured."}, status=503)

    try:
        data = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "Invalid request data."}, status=400)

    title = str(data.get("title", "")).strip()

    if not title:
        return JsonResponse({"success": False, "error": "Please enter a video title."}, status=400)

    try:
        response = requests.post(
            f"{BUNNY_API_URL}/library/{library_id}/videos",
            headers={"AccessKey": api_key, "Accept": "application/json", "Content-Type": "application/json"},
            json={"title": title},
            timeout=20,
        )
        response.raise_for_status()
        bunny_data = response.json()
        bunny_video_id = bunny_data.get("guid")

        if not bunny_video_id:
            return JsonResponse({"success": False, "error": "Bunny did not return a video ID."}, status=502)

        expires = int(time.time()) + 3600
        signature_source = library_id + api_key + str(expires) + bunny_video_id
        signature = hashlib.sha256(signature_source.encode("utf-8")).hexdigest()

        return JsonResponse({
            "success": True,
            "video_id": bunny_video_id,
            "library_id": library_id,
            "upload_url": BUNNY_TUS_URL,
            "authorization_signature": signature,
            "authorization_expire": expires,
            "embed_url": f"https://iframe.mediadelivery.net/embed/{library_id}/{bunny_video_id}",
        })
    except requests.RequestException:
        return JsonResponse({"success": False, "error": "Unable to create the Bunny video."}, status=502)


# ============================================================
# YOUTUBE HELPERS (HYBRID FALLBACK)
# ============================================================

def get_youtube_thumbnail(thumbnails, video_id, prefer_high=False):
    thumbnails = thumbnails or {}
    if prefer_high:
        thumbnail = (
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
        )
    else:
        thumbnail = (
            thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
        )
    return thumbnail or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def parse_iso8601_duration(duration_str):
    """
    Parses YouTube's ISO 8601 duration string (e.g., 'PT1M30S')
    and returns the total duration in seconds.
    """
    if not duration_str:
        return 0
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _parse_piped_video_id(url_path):
    if not url_path or "/watch?v=" not in url_path:
        return ""
    return url_path.split("v=")[-1].split("&")[0]


def _search_via_youtube_api(query, max_results):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("YouTube API key is missing")

    response = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={"part": "snippet", "q": query, "type": "video", "maxResults": max_results, "key": api_key, "safeSearch": "moderate"},
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue

        thumbnail = get_youtube_thumbnail(snippet.get("thumbnails"), video_id)
        channel_title = snippet.get("channelTitle", "")

        results.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "channel": channel_title,
            "channel_title": channel_title,
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail": thumbnail,
            "thumbnail_url": thumbnail,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "platform": "YouTube",
        })
    return results


def _search_via_piped(query, max_results):
    last_error = None
    for base_url in PIPED_INSTANCES:
        try:
            response = requests.get(
                f"{base_url}/search",
                params={"q": query, "filter": "videos"},
                headers={"User-Agent": "StreamSphere/1.0"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()

            results = []
            for item in payload.get("items", [])[:max_results]:
                video_id = _parse_piped_video_id(item.get("url", ""))
                if not video_id:
                    continue

                channel_title = item.get("uploaderName", "")
                thumbnail = item.get("thumbnail", "") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                results.append({
                    "video_id": video_id,
                    "title": item.get("title", ""),
                    "description": item.get("shortDescription", ""),
                    "channel": channel_title,
                    "channel_title": channel_title,
                    "published_at": item.get("uploadedDate", ""),
                    "thumbnail": thumbnail,
                    "thumbnail_url": thumbnail,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "platform": "YouTube",
                })

            if results:
                return results
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return []


def search_youtube_videos(query, max_results=8):
    query = (query or "").strip()
    if len(query) < 3:
        return []

    cache_key = f"streamsphere_youtube_search_{hashlib.sha256(query.lower().encode()).hexdigest()}_{max_results}"
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return cached_results

    try:
        results = _search_via_youtube_api(query, max_results)
        if results:
            cache.set(cache_key, results, 60 * 30)
            return results
    except Exception:
        pass

    try:
        results = _search_via_piped(query, max_results)
        if results:
            cache.set(cache_key, results, 60 * 30)
            return results
    except Exception:
        pass

    cache.set(cache_key, [], 60)
    return []


def _youtube_api_video_details(video_id):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("YouTube API key is missing")

    response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,status", "id": video_id, "key": api_key},
        timeout=8,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        return None

    item = items[0]
    snippet = item.get("snippet", {})
    status = item.get("status", {})

    thumbnail = get_youtube_thumbnail(snippet.get("thumbnails"), video_id, prefer_high=True)
    channel_title = snippet.get("channelTitle", "StreamSphere Creator")

    embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&showinfo=0&modestbranding=1&iv_load_policy=3&enablejsapi=1"

    return {
        "video_id": video_id,
        "title": snippet.get("title", "Video"),
        "description": snippet.get("description", ""),
        "channel": channel_title,
        "channel_title": channel_title,
        "channel_id": snippet.get("channelId", ""),
        "channel_thumbnail": None,
        "published_at": snippet.get("publishedAt", ""),
        "thumbnail": thumbnail,
        "thumbnail_url": thumbnail,
        "embeddable": status.get("embeddable", True),
        "embed_url": embed_url,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "platform": "YouTube",
    }


def _piped_video_details(video_id):
    last_error = None
    for base_url in PIPED_INSTANCES:
        try:
            response = requests.get(f"{base_url}/streams/{video_id}", headers={"User-Agent": "StreamSphere/1.0"}, timeout=10)
            response.raise_for_status()
            payload = response.json()

            if not payload or payload.get("error"):
                continue

            channel_title = payload.get("uploader", "") or "StreamSphere Creator"
            thumbnail = payload.get("thumbnailUrl", "") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            
            embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&showinfo=0&modestbranding=1&iv_load_policy=3&enablejsapi=1"

            return {
                "video_id": video_id,
                "title": payload.get("title", "Video"),
                "description": payload.get("description", "") or "",
                "channel": channel_title,
                "channel_title": channel_title,
                "channel_id": payload.get("uploaderUrl", "").rstrip("/").split("/")[-1],
                "channel_thumbnail": payload.get("uploaderAvatar", None),
                "published_at": payload.get("uploadDate", ""),
                "thumbnail": thumbnail,
                "thumbnail_url": thumbnail,
                "embeddable": True,
                "embed_url": embed_url,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "platform": "YouTube",
            }
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return None


def get_youtube_video_details(video_id):
    if not YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_id or ""):
        return None

    cache_key = f"streamsphere_youtube_video_v5_{video_id}"
    cached_video = cache.get(cache_key)
    if cached_video is not None:
        return cached_video

    try:
        video = _youtube_api_video_details(video_id)
        if video is not None:
            cache.set(cache_key, video, 60 * 30)
            return video
    except Exception:
        pass

    try:
        video = _piped_video_details(video_id)
        if video is not None:
            cache.set(cache_key, video, 60 * 30)
            return video
    except Exception:
        pass

    cache.set(cache_key, None, 60)
    return None


def _youtube_api_recommendations(external_video, max_results):
    api_key = getattr(settings, "YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("YouTube API key is missing")

    video_id = external_video.get("video_id")
    if not video_id:
        return []

    endpoint = "https://www.googleapis.com/youtube/v3/search"
    recommendations = []
    seen_ids = {video_id}

    def add_results(items):
        # 1. Collect the video IDs
        video_ids = [item.get("id", {}).get("videoId") for item in items if item.get("id", {}).get("videoId") and item.get("id", {}).get("videoId") not in seen_ids]
        if not video_ids:
            return

        # 2. Fetch durations for all these videos in one API call
        try:
            details_response = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "contentDetails", "id": ",".join(video_ids), "key": api_key},
                timeout=8,
            )
            details_response.raise_for_status()
            durations_map = {
                d["id"]: parse_iso8601_duration(d.get("contentDetails", {}).get("duration"))
                for d in details_response.json().get("items", [])
            }
        except Exception:
            durations_map = {}

        # 3. Add the valid videos
        for item in items:
            result_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            
            if not result_id or result_id in seen_ids:
                continue
                
            title = snippet.get("title", "")
            title_lower = title.lower()
            if any(tag in title_lower for tag in ["#shorts", "#short", "#reel", "#fyp"]):
                continue

            # Block if duration is under 60 seconds
            duration = durations_map.get(result_id, 999)
            if duration < 60:
                continue

            channel_title = snippet.get("channelTitle", "")
            thumbnail = get_youtube_thumbnail(snippet.get("thumbnails"), result_id)

            recommendations.append({
                "video_id": result_id,
                "title": title,
                "description": snippet.get("description", ""),
                "channel": channel_title,
                "channel_title": channel_title,
                "published_at": snippet.get("publishedAt", ""),
                "thumbnail": thumbnail,
                "thumbnail_url": thumbnail,
                "watch_url": reverse("videos:external_detail", kwargs={"video_id": result_id}),
            })
            seen_ids.add(result_id)
            if len(recommendations) >= max_results:
                break

    channel_id = external_video.get("channel_id")
    if channel_id:
        response = requests.get(
            endpoint,
            params={"part": "snippet", "channelId": channel_id, "type": "video", "maxResults": max_results * 3, "order": "date", "key": api_key, "safeSearch": "moderate"},
            timeout=8,
        )
        response.raise_for_status()
        add_results(response.json().get("items", []))

    if len(recommendations) < max_results:
        related_query = external_video.get("title", "").strip()
        if related_query:
            response = requests.get(
                endpoint,
                params={"part": "snippet", "q": related_query[:100], "type": "video", "maxResults": max_results * 3, "key": api_key, "safeSearch": "moderate"},
                timeout=8,
            )
            response.raise_for_status()
            add_results(response.json().get("items", []))

    return recommendations[:max_results]


def _piped_recommendations(external_video, max_results):
    video_id = external_video.get("video_id")
    if not video_id:
        return []

    last_error = None
    for base_url in PIPED_INSTANCES:
        try:
            response = requests.get(f"{base_url}/streams/{video_id}/related", headers={"User-Agent": "StreamSphere/1.0"}, timeout=10)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("relatedStreams", [])
            if not items:
                continue

            recommendations = []
            seen_ids = {video_id}

            for item in items:
                result_id = _parse_piped_video_id(item.get("url", ""))
                if not result_id or result_id in seen_ids:
                    continue

                title = item.get("title", "Untitled video")
                title_lower = title.lower()
                if any(tag in title_lower for tag in ["#shorts", "#short", "#reel", "#fyp"]):
                    continue

                duration = item.get("duration", 0)
                if isinstance(duration, int) and 0 < duration < 60:
                    continue

                channel_title = item.get("uploaderName", "")
                thumbnail = item.get("thumbnail", "") or f"https://i.ytimg.com/vi/{result_id}/hqdefault.jpg"

                recommendations.append({
                    "video_id": result_id,
                    "title": title,
                    "description": item.get("shortDescription", ""),
                    "channel": channel_title,
                    "channel_title": channel_title,
                    "published_at": item.get("uploadedDate", ""),
                    "thumbnail": thumbnail,
                    "thumbnail_url": thumbnail,
                    "watch_url": reverse("videos:external_detail", kwargs={"video_id": result_id}),
                })
                seen_ids.add(result_id)
                if len(recommendations) >= max_results:
                    break

            return recommendations
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    return []


def get_youtube_recommendations(external_video, max_results=8):
    video_id = external_video.get("video_id")
    if not video_id:
        return []

    cache_key = f"streamsphere_youtube_recommendations_v5_{video_id}"
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return cached_results

    try:
        recommendations = _youtube_api_recommendations(external_video, max_results)
        if recommendations:
            cache.set(cache_key, recommendations, 60 * 30)
            return recommendations
    except Exception:
        pass

    try:
        recommendations = _piped_recommendations(external_video, max_results)
        if recommendations:
            cache.set(cache_key, recommendations, 60 * 30)
            return recommendations
    except Exception:
        pass

    cache.set(cache_key, [], 60 * 5)
    return []


# ============================================================
# VIEWS
# ============================================================

def home(request):
    published_videos = Video.objects.filter(status=Video.Status.PUBLISHED).select_related("creator", "creator__profile")
    trending_videos = published_videos.order_by("-views", "-created_at")[:12]
    recent_videos = published_videos.order_by("-created_at")[:12]

    return render(request, "home.html", {
        "trending_videos": trending_videos,
        "recent_videos": recent_videos,
        "latest_videos": recent_videos[:10],
        "popular_videos": trending_videos[:5],
        "total_videos": published_videos.count(),
    })


def video_list(request):
    videos = Video.objects.filter(status=Video.Status.PUBLISHED).select_related("creator", "creator__profile")
    search_query = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")

    if search_query:
        videos = videos.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query) | Q(creator__username__icontains=search_query))

    if sort_by == "popular":
        videos = videos.order_by("-views", "-created_at")
    else:
        sort_by = "newest"
        videos = videos.order_by("-created_at")

    paginator = Paginator(videos, 24)
    page_obj = paginator.get_page(request.GET.get("page"))
    youtube_videos = search_youtube_videos(search_query) if len(search_query) >= 3 else []

    context = {
        "videos": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "sort_by": sort_by,
        "total_videos": paginator.count,
        "youtube_videos": youtube_videos,
        "youtube_enabled": bool(getattr(settings, "YOUTUBE_API_KEY", "")),
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "grid_html": render_to_string("videos/partials/_video_grid.html", context, request=request),
            "pagination_html": render_to_string("videos/partials/_pagination.html", context, request=request),
            "external_html": render_to_string("videos/partials/_external_video_grid.html", context, request=request),
            "total_videos": paginator.count,
            "search_query": search_query,
            "sort_by": sort_by,
        })

    return render(request, "videos/video_list.html", context)


def video_detail(request, pk):
    video = get_object_or_404(Video.objects.select_related("creator", "creator__profile"), pk=pk, status=Video.Status.PUBLISHED)

    if not request.user.is_authenticated or request.user.pk != video.creator_id:
        Video.objects.filter(pk=video.pk).update(views=F("views") + 1)
        video.refresh_from_db(fields=["views"])

    related_videos = Video.objects.filter(status=Video.Status.PUBLISHED).exclude(pk=video.pk).select_related("creator", "creator__profile").order_by("-created_at")[:8]

    can_watch = can_user_watch_video(request.user, video)
    liked = False
    following_creator = False

    if request.user.is_authenticated:
        liked = VideoLike.objects.filter(video=video, user=request.user).exists()
        following_creator = Follow.objects.filter(follower=request.user, following=video.creator).exists()

    comments = VideoComment.objects.filter(video=video).select_related("user", "user__profile").order_by("-created_at")

    return render(request, "videos/video_detail.html", {
        "video": video,
        "related_videos": related_videos,
        "can_watch": can_watch,
        "liked": liked,
        "like_count": video.likes.count(),
        "comments": comments,
        "comment_count": comments.count(),
        "following_creator": following_creator,
        "follower_count": Follow.objects.filter(following=video.creator).count(),
        "bunny_embed_url": get_bunny_embed_url(video),
    })


def external_video_detail(request, video_id):
    if not YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_id or ""):
        raise Http404("Invalid video ID.")

    external_video = get_youtube_video_details(video_id)

    if not external_video:
        return render(request, "videos/external_video_detail.html", {
            "external_video": None,
            "video_error": "This video could not be loaded.",
            "recommended_videos": [],
        }, status=404)

    if not external_video.get("embeddable", True):
        return render(request, "videos/external_video_detail.html", {
            "external_video": None,
            "video_error": "This video cannot be played on StreamSphere.",
            "recommended_videos": [],
        }, status=403)

    origin = request.build_absolute_uri("/").rstrip("/")
    external_video["embed_url"] = f"{external_video['embed_url']}&origin={origin}"

    recommended_videos = get_youtube_recommendations(external_video)

    return render(request, "videos/external_video_detail.html", {
        "external_video": external_video,
        "video_error": None,
        "recommended_videos": recommended_videos,
    })


@login_required
@require_POST
def toggle_like(request, pk):
    video = get_object_or_404(Video, pk=pk, status=Video.Status.PUBLISHED)

    with transaction.atomic():
        existing = VideoLike.objects.filter(video=video, user=request.user)
        if existing.exists():
            existing.delete()
            liked = False
        else:
            VideoLike.objects.create(video=video, user=request.user)
            liked = True
            if video.creator_id != request.user.pk:
                Notification.objects.create(recipient=video.creator, actor=request.user, notification_type=Notification.Type.LIKE, video=video)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"liked": liked, "count": video.likes.count()})

    return redirect("videos:detail", pk=video.pk)


@login_required
@require_POST
def add_comment(request, pk):
    video = get_object_or_404(Video, pk=pk, status=Video.Status.PUBLISHED)
    text = request.POST.get("text", request.POST.get("content", "")).strip()

    if not text:
        return JsonResponse({"error": "Write a comment before submitting."}, status=400)
    if len(text) > 2000:
        return JsonResponse({"error": "Comments must be 2,000 characters or fewer."}, status=400)

    comment = VideoComment.objects.create(video=video, user=request.user, text=text)

    if video.creator_id != request.user.pk:
        Notification.objects.create(recipient=video.creator, actor=request.user, notification_type=Notification.Type.COMMENT, video=video, comment=comment)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        avatar_url = request.user.profile.avatar_image.url if hasattr(request.user, "profile") and request.user.profile.avatar_image else None
        return JsonResponse({
            "success": True,
            "comment_id": comment.pk,
            "text": comment.text,
            "username": request.user.username,
            "avatar": avatar_url,
            "created_at": comment.created_at.strftime("%b %d, %Y"),
            "comment_count": video.comments.count(),
        })

    return redirect("videos:detail", pk=video.pk)


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(VideoComment.objects.select_related("video"), pk=comment_id)
    video_id = comment.video_id

    if comment.user_id != request.user.pk and comment.video.creator_id != request.user.pk:
        messages.error(request, "You cannot delete this comment.")
        return redirect("videos:detail", pk=video_id)

    comment.delete()
    messages.success(request, "Comment deleted.")
    return redirect("videos:detail", pk=video_id)


@login_required
def get_cloudinary_signature(request):
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request"}, status=400)

    timestamp = int(timezone.now().timestamp())
    params = {"timestamp": timestamp, "folder": "streamsphere/videos"}
    signature = cloudinary.utils.api_sign_request(params, settings.CLOUDINARY_API_SECRET)

    return JsonResponse({
        "signature": signature,
        "timestamp": timestamp,
        "api_key": settings.CLOUDINARY_API_KEY,
        "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
        "folder": "streamsphere/videos",
    })


@login_required
def upload_video(request):
    if request.method == "POST":
        form = VideoUploadForm(request.POST)
        if form.is_valid():
            video = form.save(commit=False)
            video.creator = request.user
            upload_provider = request.POST.get("upload_provider", "cloudinary").strip().lower()

            if upload_provider == "bunny":
                bunny_video_id = request.POST.get("bunny_video_id", "").strip()
                library_id, api_key = get_bunny_settings()

                if not library_id or not api_key or not bunny_video_id:
                    messages.error(request, "Bunny Stream error. Please try again.")
                    return render(request, "videos/video_upload.html", {"form": form})

                video.source = "bunny"
                video.bunny_video_id = bunny_video_id
                video.bunny_library_id = library_id
                video.video_file = ""
            else:
                cloudinary_url = request.POST.get("video_file_url", "").strip()
                if not cloudinary_url:
                    messages.error(request, "Please upload your video before submitting.")
                    return render(request, "videos/video_upload.html", {"form": form})

                video.source = "cloudinary"
                video.video_file = cloudinary_url
                if hasattr(video, "bunny_video_id"): video.bunny_video_id = ""
                if hasattr(video, "bunny_library_id"): video.bunny_library_id = ""

            video.save()

            if video.status == Video.Status.PUBLISHED:
                messages.success(request, "Your video has been uploaded and published successfully.")
                return redirect("videos:detail", pk=video.pk)

            messages.success(request, "Your video has been saved as a draft.")
            return redirect("accounts:profile")

        messages.error(request, "The video could not be uploaded. Please correct the errors below.")
    else:
        form = VideoUploadForm()

    return render(request, "videos/video_upload.html", {"form": form})


@login_required
def purchase_video(request, pk):
    video = get_object_or_404(Video, pk=pk, is_premium=True, status=Video.Status.PUBLISHED)

    if request.method == "POST":
        try:
            payment, created = create_video_purchase_payment(user=request.user, video=video)
            return render(request, "videos/purchase_video.html", {"video": video, "payment": payment, "payment_created": created})
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("videos:detail", pk=video.pk)

    return render(request, "videos/purchase_video.html", {"video": video, "payment": None, "payment_created": False})


@require_GET
def watch_video(request, pk):
    video = get_object_or_404(Video, pk=pk, status=Video.Status.PUBLISHED)
    if not can_user_watch_video(request.user, video):
        if not request.user.is_authenticated:
            messages.info(request, "Log in to access this video.")
            return redirect("account_login")
        messages.info(request, "Purchase this premium video to watch it.")
        return redirect("videos:purchase", pk=video.pk)

    if is_bunny_video(video):
        return redirect("videos:detail", pk=video.pk)

    media_url = video.video_file
    if not media_url:
        messages.error(request, "The video file is unavailable.")
        return redirect("videos:detail", pk=video.pk)

    return redirect(media_url)


@login_required
def video_download(request, pk):
    video = get_object_or_404(Video, pk=pk, status=Video.Status.PUBLISHED)
    if not can_user_watch_video(request.user, video):
        messages.error(request, "You do not have permission to download this video.")
        return redirect("videos:detail", pk=video.pk)

    if is_bunny_video(video):
        messages.info(request, "Downloads are not enabled for this video.")
        return redirect("videos:detail", pk=video.pk)

    media_url = video.video_file
    if not media_url:
        messages.error(request, "The video file is unavailable.")
        return redirect("videos:detail", pk=video.pk)

    try:
        response = requests.get(media_url, stream=True, timeout=30)
        response.raise_for_status()
        filename = os.path.basename(urlparse(media_url).path) or f"{video.title}.mp4"
        return FileResponse(response.raw, as_attachment=True, filename=filename)
    except requests.RequestException:
        messages.error(request, "Could not download the video at this time.")
        return redirect("videos:detail", pk=video.pk)


@login_required
def my_videos(request):
    videos = Video.objects.filter(creator=request.user).order_by("-id")
    return render(request, "videos/video_list.html", {"videos": videos})


@login_required
def my_videos(request):
    videos = Video.objects.filter(creator=request.user).order_by("-id")
    return render(request, "videos/video_list.html", {"videos": videos})


@login_required
def video_edit(request, pk):
    video = get_object_or_404(Video, pk=pk)
    if video.creator != request.user:
        messages.error(request, "You can only edit your own videos.")
        return redirect("videos:detail", pk=video.pk)

    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, "Video updated.")
            return redirect("videos:detail", pk=video.pk)
    else:
        form = VideoForm(instance=video)

    return render(request, "videos/video_edit.html", {"form": form, "video": video})



@login_required
@require_POST
def video_delete(request, pk):
    video = get_object_or_404(Video, pk=pk)

    if video.creator != request.user:
        messages.error(
            request,
            "You can only delete your own videos.",
        )
        return redirect("videos:detail", pk=video.pk)

    video.delete()
    messages.success(request, "Video deleted.")

    return redirect("accounts:profile")