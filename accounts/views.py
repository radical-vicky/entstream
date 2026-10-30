from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Profile, Notification
from .forms import ProfileForm
from videos.models import Video


@login_required
def profile_view(request, username=None):
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = request.user

    profile, _ = Profile.objects.get_or_create(user=profile_user)
    active_tab = request.GET.get("tab", "videos")

    videos_qs = (
        Video.objects
        .filter(creator=profile_user)
        .order_by("-created_at")
    )
    
    followers_qs = profile.followers.all()
    following_qs = profile.following.all()

    context = {
        "profile": profile,
        "profile_user": profile_user,
        "viewed_user": profile_user,
        "is_owner": request.user == profile_user,
        "active_tab": active_tab,
        "video_count": videos_qs.count(),
        "total_views": sum(video.views or 0 for video in videos_qs),
        
        # Only pass the active tab's data
        "videos": videos_qs if active_tab == "videos" else [],
        "followers": followers_qs if active_tab == "followers" else [],
        "following": following_qs if active_tab == "following" else [],
    }

    return render(request, "accounts/profile.html", context)


@login_required
def my_profile(request):
    return profile_view(request)


@login_required
@require_POST
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)
    
    if target_user == request.user:
        messages.error(request, "You cannot follow yourself.")
        return redirect("accounts:profile_detail", username=username)
        
    target_profile = get_object_or_404(Profile, user=target_user)
    my_profile = get_object_or_404(Profile, user=request.user)
    
    if target_profile in my_profile.following.all():
        my_profile.following.remove(target_profile)
        messages.success(request, f"You unfollowed @{target_user.username}.")
    else:
        my_profile.following.add(target_profile)
        messages.success(request, f"You are now following @{target_user.username}.")
        
    return redirect("accounts:profile_detail", username=username)




@login_required
def my_profile(request):
    return profile_view(request)


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from .models import Profile
from .forms import ProfileForm

@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    UserModel = request.user.__class__

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        
        # Get User fields from the form submission
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()

        username_ok = bool(username) and not (
            UserModel.objects.filter(username=username)
            .exclude(pk=request.user.pk).exists()
        )

        if not username:
            messages.error(request, "Username is required.")
        elif not username_ok:
            messages.error(request, "That username is already taken.")

        if form.is_valid() and username_ok:
            # 1. Update User fields
            request.user.username = username
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save(
                update_fields=["username", "first_name", "last_name", "email"]
            )

            # 2. Update Profile fields
            profile_instance = form.save(commit=False)

            # Handle the custom avatar upload field
            upload = form.cleaned_data.get("avatar_upload")
            if upload:
                profile_instance.avatar_image = upload

            profile_instance.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field}: {err}")
    else:
        form = ProfileForm(instance=profile)

    return render(
        request,
        "accounts/profile_edit.html",
        {
            "form": form,
            "profile": profile,
            "account_user": request.user,
        },
    )


@login_required
@require_POST
def profile_delete(request):
    user = request.user
    logout(request)
    user.delete()
    messages.success(request, "Your account has been deleted.")
    return redirect("home")


@login_required
def notification_list(request):
    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("actor", "video", "comment")
        .order_by("-created_at")
    )

    unread_count = notifications.filter(is_read=False).count()

    paginator = Paginator(notifications, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications": page_obj,
            "page_obj": page_obj,
            "unread_count": unread_count,
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

    next_url = request.POST.get("next", "").strip()

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
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