from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.my_profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/delete/", views.profile_delete, name="profile_delete"),
    
    # Dynamic routes must go after static ones
    path("profile/<str:username>/", views.profile_view, name="profile_detail"),
    path("profile/<str:username>/follow/", views.toggle_follow, name="toggle_follow"),

    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/<int:pk>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/read-all/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
]