
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.models import Notification
from creators.models import Follow

from .access import can_user_watch_video
from .forms import VideoUploadForm
from .models import Video, VideoLike, VideoComment
from .purchase_services import create_video_purchase_payment


def home(request):
    published_videos = (
        Video.objects.filter(status=Video.Status.PUBLISHED)
        .select_related("creator", "creator__profile")
    )

    trending_videos = published_videos.order_by(
        "-views",
        "-created_at",
    )[:12]

    recent_videos = published_videos.order_by(
        "-created_at",
    )[:12]

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
        Video.objects.select_related(
            "creator",
            "creator__profile",
        ),
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    if (
        not request.user.is_authenticated
        or request.user.pk != video.creator_id
    ):
        Video.objects.filter(pk=video.pk).update(
            views=F("views") + 1
        )
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
        .select_related(
            "user",
            "user__profile",
        )
        .order_by("-created_at")
    )

    like_count = video.likes.count()
    comment_count = comments.count()
    follower_count = Follow.objects.filter(
        following=video.creator,
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
        else:
            VideoLike.objects.create(
                video=video,
                user=request.user,
            )

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
        Video,
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    text = request.POST.get("text", "").strip()

    if not text:
        messages.error(
            request,
            "Write a comment before submitting.",
        )
    elif len(text) > 2000:
        messages.error(
            request,
            "Comments must be 2,000 characters or fewer.",
        )
    else:
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
        messages.error(
            request,
            "You cannot delete this comment.",
        )
        return redirect("videos:detail", pk=video_id)

    comment.delete()

    messages.success(request, "Comment deleted.")

    return redirect("videos:detail", pk=video_id)



import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


@login_required
def upload_video(request):
    if request.method == "POST":
        form = VideoUploadForm(
            request.POST,
            request.FILES,
        )

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

        logger.warning("Video upload validation errors: %s", form.errors)
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
            messages.error(
                request,
                " ".join(exc.messages),
            )
            return redirect(
                "videos:detail",
                pk=video.pk,
            )

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
            messages.info(
                request,
                "Log in to access this video.",
            )
            return redirect("account_login")

        messages.info(
            request,
            "Purchase this premium video to watch it.",
        )

        return redirect(
            "videos:purchase",
            pk=video.pk,
        )

    media_url = getattr(
        video.video_file,
        "url",
        None,
    )

    if not media_url:
        messages.error(
            request,
            "The video file is unavailable.",
        )
        return redirect(
            "videos:detail",
            pk=video.pk,
        )

    return redirect(media_url)



from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Video


@login_required
def my_videos(request):
    videos = Video.objects.filter(
        uploader=request.user
    ).order_by("-id")

    return render(
        request,
        "videos/video_list.html",
        {"videos": videos},
    )
