
from django.urls import path

from . import views

app_name = "creators"

urlpatterns = [
    path("<str:username>/", views.creator_profile, name="profile"),
    path(
        "<str:username>/follow/",
        views.toggle_follow,
        name="toggle_follow",
    ),
]
