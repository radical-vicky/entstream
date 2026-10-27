
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.my_profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),

    path("notifications/", views.notification_list, name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        views.mark_notification_read,
        name="notification_read",
    ),
    path(
        "notifications/read-all/",
        views.mark_all_notifications_read,
        name="notifications_read_all",
    ),
]
