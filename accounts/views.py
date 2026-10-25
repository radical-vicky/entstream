
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
import cloudinary.uploader

from .forms import ProfileForm
from .models import Profile
from videos.models import Video


@login_required
def my_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
        )

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

                messages.success(
                    request,
                    "Your profile has been updated successfully.",
                )
                return redirect("accounts:profile")

            except Exception:
                messages.error(
                    request,
                    "We couldn't upload your image. Check your Cloudinary "
                    "configuration and try again.",
                )
        else:
            messages.error(
                request,
                "Please correct the errors below and try again.",
            )
    else:
        form = ProfileForm(instance=profile)

    videos = Video.objects.filter(
        creator=request.user
    ).order_by("-created_at")

    published_videos = videos.filter(
        status=Video.Status.PUBLISHED
    )

    context = {
        "profile": profile,
        "profile_user": request.user,
        "form": form,
        "videos": videos,
        "published_videos": published_videos,
        "video_count": published_videos.count(),
        "total_views": sum(
            video.views for video in published_videos
        ),
    }

    return render(request, "accounts/profile.html", context)
