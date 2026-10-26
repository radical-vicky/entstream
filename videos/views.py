
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import Notification
from creators.models import Follow
from .forms import VideoUploadForm
from .models import Video, VideoLike, VideoComment


def home(request):
    published_videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .select_related("creator")
    )
    return render(
        request,
        "home.html",
        {
            "latest_videos": published_videos.order_by("-created_at")[:10],
            "popular_videos": published_videos.order_by("-views", "-created_at")[:5],
            "total_videos": published_videos.count(),
        },
    )


def video_list(request):
    videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .select_related("creator")
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

    return render(
        request,
        "videos/video_list.html",
        {
            "videos": page_obj.object_list,
            "page_obj": page_obj,
            "search_query": search_query,
            "sort_by": sort_by,
            "total_videos": paginator.count,
        },
    )


def video_detail(request, pk):
    video = get_object_or_404(
        Video.objects.select_related("creator"),
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    if not request.user.is_authenticated or request.user.pk != video.creator_id:
        Video.objects.filter(pk=video.pk).update(views=F("views") + 1)
        video.refresh_from_db(fields=["views"])

    related_videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .exclude(pk=video.pk)
        .select_related("creator")
        .order_by("-created_at")[:8]
    )

    can_watch = (
        not video.is_premium
        or (
            request.user.is_authenticated
            and request.user.pk == video.creator_id
        )
    )

    liked = False
    following_creator = False

    if request.user.is_authenticated:
        liked = VideoLike.objects.filter(
            video=video, user=request.user
        ).exists()
        following_creator = Follow.objects.filter(
            follower=request.user, following=video.creator
        ).exists()

    comments = (
        VideoComment.objects.filter(video=video)
        .select_related("user", "user__profile")
    )

    return render(
        request,
        "videos/video_detail.html",
        {
            "video": video,
            "related_videos": related_videos,
            "can_watch": can_watch,
            "liked": liked,
            "like_count": video.likes.count(),
            "comments": comments,
            "comment_count": comments.count(),
            "following_creator": following_creator,
            "follower_count": Follow.objects.filter(
                following=video.creator
            ).count(),
        },
    )


@login_required
@require_POST
def toggle_like(request, pk):
    video = get_object_or_404(
        Video, pk=pk, status=Video.Status.PUBLISHED
    )

    with transaction.atomic():
        existing = VideoLike.objects.filter(
            video=video, user=request.user
        )
        if existing.exists():
            existing.delete()
        else:
            VideoLike.objects.create(video=video, user=request.user)
            if video.creator_id != request.user.pk:
                Notification.objects.create(
                    recipient=video.creator,
                    actor=request.user,
                    notification_type=Notification.Type.LIKE,
                    video=video,
                )

    return redirect("videos:detail", pk=video.pk)


@login_required
@require_POST
def add_comment(request, pk):
    video = get_object_or_404(
        Video, pk=pk, status=Video.Status.PUBLISHED
    )
    text = request.POST.get("text", "").strip()

    if not text:
        messages.error(request, "Write a comment before submitting.")
    elif len(text) > 2000:
        messages.error(request, "Comments must be 2,000 characters or fewer.")
    else:
        comment = VideoComment.objects.create(
            video=video, user=request.user, text=text
        )
        if video.creator_id != request.user.pk:
            Notification.objects.create(
                recipient=video.creator,
                actor=request.user,
                notification_type=Notification.Type.COMMENT,
                video=video,
                comment=comment,
            )

    return redirect("videos:detail", pk=video.pk)


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(
        VideoComment.objects.select_related("video"),
        pk=comment_id,
    )
    video_id = comment.video_id

    if comment.user_id != request.user.pk and comment.video.creator_id != request.user.pk:
        messages.error(request, "You cannot delete this comment.")
        return redirect("videos:detail", pk=video_id)

    comment.delete()
    messages.success(request, "Comment deleted.")
    return redirect("videos:detail", pk=video_id)


@login_required
def upload_video(request):
    if request.method == "POST":
        form = VideoUploadForm(request.POST, request.FILES)
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

            messages.success(request, "Your video has been saved as a draft.")
            return redirect("accounts:profile")
    else:
        form = VideoUploadForm()

    return render(request, "videos/video_upload.html", {"form": form})
