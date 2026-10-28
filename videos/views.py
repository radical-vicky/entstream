import cloudinary
import cloudinary.utils
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import VideoUploadForm
from .models import Video
from .access import can_user_watch_video
# ... (keep your other imports)


@login_required
def get_cloudinary_signature(request):
    """Generates a secure signature so the frontend can upload directly to Cloudinary."""
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request"}, status=400)

    timestamp = int(timezone.now().timestamp())
    params = {
        "timestamp": timestamp,
        "folder": "streamsphere/videos", # Matches the folder in your model
    }
    
    signature = cloudinary.utils.api_sign_request(
        params, settings.CLOUDINARY_API_SECRET
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
        form = VideoUploadForm(request.POST) # No request.FILES needed!

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
