import cloudinary
import cloudinary.utils
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from .forms import VideoForm

@login_required
def get_cloudinary_signature(request):
    """Generates a secure signature so the frontend can upload directly to Cloudinary."""
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request"}, status=400)

    timestamp = int(timezone.now().timestamp())
    params = {
        "timestamp": timestamp,
        "folder": "videos/uploads",
    }
    
    signature = cloudinary.utils.api_sign_request(
        params, settings.CLOUDINARY_API_SECRET
    )

    return JsonResponse({
        "signature": signature,
        "timestamp": timestamp,
        "api_key": settings.CLOUDINARY_API_KEY,
        "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
        "folder": "videos/uploads",
    })

@login_required
def upload_video(request):
    if request.method == "POST":
        form = VideoForm(request.POST) # Note: No request.FILES needed anymore!
        if form.is_valid():
            video = form.save(commit=False)
            video.creator = request.user
            
            # The frontend JS will inject the Cloudinary URL into a hidden input called video_file_url
            video_file_url = request.POST.get("video_file_url")
            if video_file_url:
                # We save the Cloudinary URL string to the database
                video.video_file = video_file_url 
                
            video.save()
            messages.success(request, "Video uploaded successfully.")
            return redirect("videos:detail", pk=video.pk) # Adjust redirect as needed
    else:
        form = VideoForm()

    return render(request, "videos/upload_video.html", {"form": form})
