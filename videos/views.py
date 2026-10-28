from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Video
from .forms import VideoForm

def home(request):
    published_videos = (
        Video.objects
        .filter(status=Video.Status.PUBLISHED)
        .select_related("creator")
    )

    latest_videos = published_videos.order_by("-created_at")[:10]
    popular_videos = published_videos.order_by("-views", "-created_at")[:5]

    return render(
        request,
        "home.html",
        {
            "latest_videos": latest_videos,
            "popular_videos": popular_videos,
            "total_videos": published_videos.count(),
        },
    )


def video_list(request):
    videos = (
        Video.objects
        .filter(status=Video.Status.PUBLISHED)
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

    context = {
        "videos": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "sort_by": sort_by,
        "total_videos": paginator.count,
    }

    return render(request, "videos/video_list.html", context)


def video_detail(request, pk):
    video = get_object_or_404(
        Video.objects.select_related("creator"),
        pk=pk,
        status=Video.Status.PUBLISHED,
    )

    # Do not count the creator viewing their own video.
    if not request.user.is_authenticated or request.user.pk != video.creator_id:
        Video.objects.filter(pk=video.pk).update(views=F("views") + 1)
        video.refresh_from_db(fields=["views"])

    related_videos = (
        Video.objects
        .filter(status=Video.Status.PUBLISHED)
        .exclude(pk=video.pk)
        .select_related("creator")
        .order_by("-created_at")[:8]
    )

    # Premium playback remains locked until verified payment
    can_watch = (
        not video.is_premium
        or (
            request.user.is_authenticated
            and request.user.pk == video.creator_id
        )
    )

    context = {
        "video": video,
        "related_videos": related_videos,
        "can_watch": can_watch,
    }

    return render(request, "videos/video_detail.html", context)


@login_required
def upload_video(request):
    if request.method == "POST":
        form = VideoForm(request.POST)
        if form.is_valid():
            # 1. Save the form but don't commit to DB yet
            video = form.save(commit=False)
            
            # 2. Assign the user and the Cloudinary URL
            video.creator = request.user
            video.video_file = form.cleaned_data["video_url"]
            
            # 3. Save to database
            video.save()
            
            messages.success(request, "Video uploaded successfully!")
            return redirect(video.get_absolute_url())
    else:
        form = VideoForm()

    return render(request, "videos/upload.html", {"form": form})
