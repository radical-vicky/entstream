
from django.urls import path
from . import views

app_name = "videos"

urlpatterns = [
    path("", views.video_list, name="list"),
    path("upload/", views.upload_video, name="upload"),
    path("<int:pk>/", views.video_detail, name="detail"),
]
