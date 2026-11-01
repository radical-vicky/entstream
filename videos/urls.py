
from django.urls import path
from . import views

app_name = "videos"

urlpatterns = [
    path("", views.video_list, name="list"),

    # Uploads
    path("upload/", views.upload_video, name="upload"),
    path("cloudinary-signature/", views.get_cloudinary_signature, name="cloudinary_signature"),
    path("bunny/create-upload/", views.create_bunny_upload, name="create_bunny_upload"),

    # YouTube external videos
    path(
        "external/<str:video_id>/",
        views.external_video_detail,
        name="external_detail",
    ),

    # XVideos external integration
    path(
        "external/xvideos/import/",
        views.import_xvideos,
        name="import_xvideos",
    ),
    path(
        "external/xvideos/<str:video_id>/",
        views.external_xvideos_detail,
        name="external_xvideos_detail",
    ),
    path(
        "external/xvideos/<str:video_id>/open/",
        views.open_xvideos_source,
        name="open_xvideos_source",
    ),

    # Local videos
    path("<int:pk>/", views.video_detail, name="detail"),
    path("<int:pk>/like/", views.toggle_like, name="toggle_like"),
    path("<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("comment/<int:comment_id>/delete/", views.delete_comment, name="delete_comment"),
    path("<int:pk>/edit/", views.video_edit, name="edit"),
    path("<int:pk>/delete/", views.video_delete, name="delete"),
    path("<int:pk>/purchase/", views.purchase_video, name="purchase"),
    path("<int:pk>/watch/", views.watch_video, name="watch"),
    path("<int:pk>/download/", views.video_download, name="download"),
]
