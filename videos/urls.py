
from django.urls import path
from . import views

app_name = "videos"

urlpatterns = [
    path("", views.video_list, name="list"),
    path("upload/", views.upload_video, name="upload"),
    path("api/signature/", views.get_cloudinary_signature, name="cloudinary_signature"),
    path("<int:pk>/like/", views.toggle_like, name="like"),
    path("<int:pk>/comment/", views.add_comment, name="comment"),
    path("comments/<int:comment_id>/delete/", views.delete_comment, name="delete_comment"),
    path("<int:pk>/purchase/", views.purchase_video, name="purchase"),
    path("<int:pk>/watch/", views.watch_video, name="watch"),
    path("<int:pk>/", views.video_detail, name="detail"),
    path("my-videos/", views.my_videos, name="my_videos"),
    path("<int:pk>/edit/", views.video_edit, name="edit"),      # CHANGED
    path("<int:pk>/delete/", views.video_delete, name="delete"),
]
