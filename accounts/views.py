
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
import cloudinary.uploader

from .forms import ProfileForm
from .models import Profile, Notification
from videos.models import Video


@login_required
def my_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            try:
                updated_profile = form.save(commit=False)
                image = form.cleaned_data.get("avatar_upload")

                if image:
                    result = cloudinary.uploader.upload(
                        image,
                        folder="streamsphere/avatars",
                        resource_type="image",
                    )
                    updated_profile.avatar = result["secure_url"]

                updated_profile.save()
                messages.success(request, "Your profile has been updated successfully.")
                return redirect("accounts:profile")
            except Exception:
                messages.error(
                    request,
                    "We couldn't upload your image. Check your Cloudinary configuration and try again.",
                )
        else:
            messages.error(request, "Please correct the errors below and try again.")
    else:
        form = ProfileForm(instance=profile)

    videos = Video.objects.filter(creator=request.user).order_by("-created_at")
    published_videos = videos.filter(status=Video.Status.PUBLISHED)

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
            "profile_user": request.user,
            "form": form,
            "videos": videos,
            "published_videos": published_videos,
            "video_count": published_videos.count(),
            "total_views": sum(video.views for video in published_videos),
        },
    )


@login_required
def notification_list(request):
    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("actor", "video", "comment")
    )
    page_obj = Paginator(notifications, 30).get_page(request.GET.get("page"))

    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "unread_count": notifications.filter(is_read=False).count(),
        },
    )


@login_required
@require_POST
def mark_notification_read(request, pk):
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )
    notification.is_read = True
    notification.save(update_fields=["is_read"])

    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    if notification.video_id:
        return redirect("videos:detail", pk=notification.video_id)

    return redirect("accounts:notifications")


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("accounts:notifications")
