
import cloudinary
import cloudinary.utils
import hashlib
import os
import re
import requests

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


def get_youtube_thumbnail(thumbnails, video_id, prefer_high=False):
    """
    Return the best available YouTube thumbnail.

    Falls back to YouTube's standard hqdefault image URL
    when the API does not provide a thumbnail.
    """
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


def search_youtube_videos(query, max_results=8):
    """
    Search YouTube using the official YouTube Data API v3.

    Results are cached for 15 minutes.
    """
    query = (query or "").strip()

    if len(query) < 3:
        return []

    api_key = getattr(settings, "YOUTUBE_API_KEY", "")

    if not api_key:
        return []

    cache_key = "streamsphere_youtube_search_{}".format(
        hashlib.sha256(query.lower().encode("utf-8")).hexdigest()
    )

    cached_results = cache.get(cache_key)

    if cached_results is not None:
        return cached_results

    endpoint = "https://www.googleapis.com/youtube/v3/search"

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": api_key,
        "safeSearch": "moderate",
    }

    try:
        response = requests.get(endpoint, params=params, timeout=8)
        response.raise_for_status()

        payload = response.json()
        results = []

        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})

            if not video_id:
                continue

            thumbnail = get_youtube_thumbnail(
                snippet.get("thumbnails"),
                video_id,
            )

            results.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "thumbnail": thumbnail,
                "thumbnail_url": thumbnail,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "platform": "YouTube",
            })

        cache.set(cache_key, results, 60 * 15)
        return results

    except (requests.RequestException, ValueError):
        cache.set(cache_key, [], 60)
        return []


def get_youtube_video_details(video_id):
    """
    Retrieve metadata and embedding permission for one YouTube video.
    """
    if not YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_id or ""):
        return None

    api_key = getattr(settings, "YOUTUBE_API_KEY", "")

    if not api_key:
        return None

    cache_key = f"streamsphere_youtube_video_v3_{video_id}"
    cached_video = cache.get(cache_key)

    if cached_video is not None:
        return cached_video

    endpoint = "https://www.googleapis.com/youtube/v3/videos"

    params = {
        "part": "snippet,status",
        "id": video_id,
        "key": api_key,
    }

    try:
        response = requests.get(endpoint, params=params, timeout=8)
        response.raise_for_status()

        payload = response.json()
        items = payload.get("items", [])

        if not items:
            return None

        item = items[0]
        snippet = item.get("snippet", {})
        status = item.get("status", {})

        thumbnail = get_youtube_thumbnail(
            snippet.get("thumbnails"),
            video_id,
            prefer_high=True,
        )

        channel_title = snippet.get("channelTitle", "YouTube creator")

        video = {
            "video_id": video_id,
            "title": snippet.get("title", "YouTube video"),
            "description": snippet.get("description", ""),
            "channel": channel_title,
            "channel_title": channel_title,
            "channel_id": snippet.get("channelId", ""),
            "channel_thumbnail": None,
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail": thumbnail,
            "thumbnail_url": thumbnail,
            "embeddable": status.get("embeddable", True),
            "embed_url": (
                f"https://www.youtube-nocookie.com/embed/{video_id}"
                "?rel=0&playsinline=1"
            ),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "platform": "YouTube",
        }

        cache.set(cache_key, video, 60 * 30)
        return video

    except (requests.RequestException, ValueError):
        return None


def get_youtube_recommendations(external_video, max_results=8):
    """
    Get recommendations for an external YouTube video.

    Videos from the same creator are prioritised.
    Related videos fill any remaining spaces.

    Every recommendation contains both the original field names
    and the field names expected by the external video template.
    """
    video_id = external_video.get("video_id")

    if not video_id:
        return []

    # v2 prevents reuse of old cached recommendation dictionaries
    # that did not contain thumbnail_url and channel_title.
    cache_key = f"streamsphere_youtube_recommendations_v2_{video_id}"
    cached_results = cache.get(cache_key)

    if cached_results is not None:
        return cached_results

    api_key = getattr(settings, "YOUTUBE_API_KEY", "")

    if not api_key:
        return []

    endpoint = "https://www.googleapis.com/youtube/v3/search"

    recommendations = []
    seen_ids = {video_id}

    def add_results(items, category):
        for item in items:
            result_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})

            if not result_id or result_id in seen_ids:
                continue

            if not YOUTUBE_VIDEO_ID_PATTERN.fullmatch(result_id):
                continue

            channel_title = snippet.get("channelTitle", "")

            thumbnail = get_youtube_thumbnail(
                snippet.get("thumbnails"),
                result_id,
            )

            recommendations.append({
                "video_id": result_id,
                "title": snippet.get("title", "Untitled video"),
                "description": snippet.get("description", ""),
                "channel": channel_title,
                "channel_title": channel_title,
                "published_at": snippet.get("publishedAt", ""),
                "thumbnail": thumbnail,
                "thumbnail_url": thumbnail,
                "category": category,
                "watch_url": reverse(
                    "videos:external_detail",
                    kwargs={"video_id": result_id},
                ),
            })

            seen_ids.add(result_id)

            if len(recommendations) >= max_results:
                break

    try:
        # First: videos from the same creator.
        channel_id = external_video.get("channel_id")

        if channel_id:
            same_creator_params = {
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "maxResults": max_results,
                "order": "date",
                "key": api_key,
                "safeSearch": "moderate",
            }

            response = requests.get(
                endpoint,
                params=same_creator_params,
                timeout=8,
            )
            response.raise_for_status()

            add_results(
                response.json().get("items", []),
                "More from this creator",
            )

        # Second: related videos.
        if len(recommendations) < max_results:
            related_query = external_video.get("title", "").strip()

            if related_query:
                related_params = {
                    "part": "snippet",
                    "q": related_query[:100],
                    "type": "video",
                    "maxResults": max_results,
                    "key": api_key,
                    "safeSearch": "moderate",
                }

                response = requests.get(
                    endpoint,
                    params=related_params,
                    timeout=8,
                )
                response.raise_for_status()

                add_results(
                    response.json().get("items", []),
                    "Related videos",
                )

        recommendations = recommendations[:max_results]

        cache.set(cache_key, recommendations, 60 * 30)

        return recommendations

    except (requests.RequestException, ValueError):
        cache.set(cache_key, recommendations, 60 * 5)
        return recommendations


def home(request):
    published_videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .select_related("creator", "creator__profile")
    )

    trending_videos = published_videos.order_by("-views", "-created_at")[:12]
    recent_videos = published_videos.order_by("-created_at")[:12]

    return render(
        request,
        "home.html",
        {
            "trending_videos": trending_videos,
            "recent_videos": recent_videos,
            "latest_videos": recent_videos[:10],
            "popular_videos": trending_videos[:5],
            "total_videos": published_videos.count(),
        },
    )


def video_list(request):
    videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .select_related("creator", "creator__profile")
    )

    search_query = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "newest")

    if search_query:
        videos = videos.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(creator__username__icontains=search_query)
        )

    if sort_by == "popular":
        videos = videos.order_by("-views", "-created_at")
    else:
        sort_by = "newest"
        videos = videos.order_by("-created_at")

    paginator = Paginator(videos, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    youtube_videos = (
        search_youtube_videos(search_query)
        if len(search_query) >= 3
        else []
    )

    context = {
        "videos": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "sort_by": sort_by,
        "total_videos": paginator.count,
        "youtube_videos": youtube_videos,
        "youtube_enabled": bool(
            getattr(settings, "YOUTUBE_API_KEY", "")
        ),
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        grid_html = render_to_string(
            "videos/partials/_video_grid.html",
            context,
            request=request,
        )

        pagination_html = render_to_string(
            "videos/partials/_pagination.html",
            context,
            request=request,
        )

        external_html = render_to_string(
            "videos/partials/_external_video_grid.html",
            context,
            request=request,
        )

        return JsonResponse({
            "grid_html": grid_html,
            "pagination_html": pagination_html,
            "external_html": external_html,
            "total_videos": paginator.count,
            "search_query": search_query,
            "sort_by": sort_by,
        })

    return render(request, "videos/video_list.html", context)


def video_detail(request, pk):
    video = get_object_or_404(
        Video.objects.select_related("creator", "creator__profile"),
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    if not request.user.is_authenticated or request.user.pk != video.creator_id:
        Video.objects.filter(pk=video.pk).update(views=F("views") + 1)
        video.refresh_from_db(fields=["views"])

    related_videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .exclude(pk=video.pk)
        .select_related("creator", "creator__profile")
        .order_by("-created_at")[:8]
    )

    can_watch = can_user_watch_video(request.user, video)
    liked = False
    following_creator = False

    if request.user.is_authenticated:
        liked = VideoLike.objects.filter(
            video=video,
            user=request.user,
        ).exists()

        following_creator = Follow.objects.filter(
            follower=request.user,
            following=video.creator,
        ).exists()

    comments = (
        VideoComment.objects.filter(video=video)
        .select_related("user", "user__profile")
        .order_by("-created_at")
    )

    like_count = video.likes.count()
    comment_count = comments.count()
    follower_count = Follow.objects.filter(
        following=video.creator
    ).count()

    return render(
        request,
        "videos/video_detail.html",
        {
            "video": video,
            "related_videos": related_videos,
            "can_watch": can_watch,
            "liked": liked,
            "like_count": like_count,
            "comments": comments,
            "comment_count": comment_count,
            "following_creator": following_creator,
            "follower_count": follower_count,
        },
    )


def external_video_detail(request, video_id):
    """
    Display an external YouTube video inside StreamSphere,
    together with recommendations.
    """
    if not YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_id or ""):
        raise Http404("Invalid video ID.")

    external_video = get_youtube_video_details(video_id)

    if not external_video:
        return render(
            request,
            "videos/external_video_detail.html",
            {
                "external_video": None,
                "video_error": (
                    "This video could not be loaded. It may have been "
                    "removed, restricted, or YouTube search may not "
                    "be configured."
                ),
                "recommended_videos": [],
            },
            status=404,
        )

    origin = request.build_absolute_uri("/").rstrip("/")

    external_video["embed_url"] = (
        f"{external_video['embed_url']}"
        f"&enablejsapi=1&origin={origin}"
    )

    recommended_videos = get_youtube_recommendations(external_video)

    return render(
        request,
        "videos/external_video_detail.html",
        {
            "external_video": external_video,
            "video_error": None,
            "recommended_videos": recommended_videos,
        },
    )


@login_required
@require_POST
def toggle_like(request, pk):
    video = get_object_or_404(
        Video,
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    with transaction.atomic():
        existing = VideoLike.objects.filter(
            video=video,
            user=request.user,
        )

        if existing.exists():
            existing.delete()
            liked = False
        else:
            VideoLike.objects.create(
                video=video,
                user=request.user,
            )
            liked = True

            if video.creator_id != request.user.pk:
                Notification.objects.create(
                    recipient=video.creator,
                    actor=request.user,
                    notification_type=Notification.Type.LIKE,
                    video=video,
                )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "liked": liked,
            "count": video.likes.count(),
        })

    return redirect("videos:detail", pk=video.pk)


@login_required
@require_POST
def add_comment(request, pk):
    video = get_object_or_404(
        Video,
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    text = request.POST.get(
        "text",
        request.POST.get("content", ""),
    ).strip()

    if not text:
        return JsonResponse(
            {"error": "Write a comment before submitting."},
            status=400,
        )

    if len(text) > 2000:
        return JsonResponse(
            {"error": "Comments must be 2,000 characters or fewer."},
            status=400,
        )

    comment = VideoComment.objects.create(
        video=video,
        user=request.user,
        text=text,
    )

    if video.creator_id != request.user.pk:
        Notification.objects.create(
            recipient=video.creator,
            actor=request.user,
            notification_type=Notification.Type.COMMENT,
            video=video,
            comment=comment,
        )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        avatar_url = (
            request.user.profile.avatar_image.url
            if hasattr(request.user, "profile")
            and request.user.profile.avatar_image
            else None
        )

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
    comment = get_object_or_404(
        VideoComment.objects.select_related("video"),
        pk=comment_id,
    )

    video_id = comment.video_id

    if (
        comment.user_id != request.user.pk
        and comment.video.creator_id != request.user.pk
    ):
        messages.error(request, "You cannot delete this comment.")
        return redirect("videos:detail", pk=video_id)

    comment.delete()
    messages.success(request, "Comment deleted.")

    return redirect("videos:detail", pk=video_id)


@login_required
def get_cloudinary_signature(request):
    if request.method != "GET":
        return JsonResponse(
            {"error": "Invalid request"},
            status=400,
        )

    timestamp = int(timezone.now().timestamp())

    params = {
        "timestamp": timestamp,
        "folder": "streamsphere/videos",
    }

    signature = cloudinary.utils.api_sign_request(
        params,
        settings.CLOUDINARY_API_SECRET,
    )

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
            video.save()

            if video.status == Video.Status.PUBLISHED:
                messages.success(
                    request,
                    "Your video has been uploaded and published successfully.",
                )
                return redirect("videos:detail", pk=video.pk)

            messages.success(
                request,
                "Your video has been saved as a draft.",
            )
            return redirect("accounts:profile")

        messages.error(
            request,
            "The video could not be uploaded. Please correct the errors below.",
        )
    else:
        form = VideoUploadForm()

    return render(
        request,
        "videos/video_upload.html",
        {"form": form},
    )


@login_required
def purchase_video(request, pk):
    video = get_object_or_404(
        Video,
        pk=pk,
        is_premium=True,
        status=Video.Status.PUBLISHED,
    )

    if request.method == "POST":
        try:
            payment, created = create_video_purchase_payment(
                user=request.user,
                video=video,
            )

            return render(
                request,
                "videos/purchase_video.html",
                {
                    "video": video,
                    "payment": payment,
                    "payment_created": created,
                },
            )

        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("videos:detail", pk=video.pk)

    return render(
        request,
        "videos/purchase_video.html",
        {
            "video": video,
            "payment": None,
            "payment_created": False,
        },
    )


@require_GET
def watch_video(request, pk):
    video = get_object_or_404(
        Video,
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    if not can_user_watch_video(request.user, video):
        if not request.user.is_authenticated:
            messages.info(request, "Log in to access this video.")
            return redirect("account_login")

        messages.info(
            request,
            "Purchase this premium video to watch it.",
        )
        return redirect("videos:purchase", pk=video.pk)

    media_url = video.video_file

    if not media_url:
        messages.error(request, "The video file is unavailable.")
        return redirect("videos:detail", pk=video.pk)

    return redirect(media_url)


@login_required
def video_download(request, pk):
    video = get_object_or_404(
        Video,
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    if not can_user_watch_video(request.user, video):
        messages.error(
            request,
            "You do not have permission to download this video.",
        )
        return redirect("videos:detail", pk=video.pk)

    media_url = video.video_file

    if not media_url:
        messages.error(request, "The video file is unavailable.")
        return redirect("videos:detail", pk=video.pk)

    try:
        response = requests.get(
            media_url,
            stream=True,
            timeout=30,
        )
        response.raise_for_status()

        filename = (
            os.path.basename(urlparse(media_url).path)
            or f"{video.title}.mp4"
        )

        return FileResponse(
            response.raw,
            as_attachment=True,
            filename=filename,
        )

    except requests.RequestException:
        messages.error(
            request,
            "Could not download the video at this time.",
        )
        return redirect("videos:detail", pk=video.pk)


@login_required
def my_videos(request):
    videos = Video.objects.filter(
        creator=request.user,
    ).order_by("-id")

    return render(
        request,
        "videos/video_list.html",
        {"videos": videos},
    )


@login_required
def video_edit(request, pk):
    video = get_object_or_404(Video, pk=pk)

    if video.creator != request.user:
        messages.error(
            request,
            "You can only edit your own videos.",
        )
        return redirect("videos:detail", pk=video.pk)

    if request.method == "POST":
        form = VideoForm(
            request.POST,
            request.FILES,
            instance=video,
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Video updated.")
            return redirect("videos:detail", pk=video.pk)

    else:
        form = VideoForm(instance=video)

    return render(
        request,
        "videos/video_edit.html",
        {
            "form": form,
            "video": video,
        },
    )


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
