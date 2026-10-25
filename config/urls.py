
from django.contrib import admin
from django.urls import include, path

from videos import views as video_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", video_views.home, name="home"),
    path("videos/", include("videos.urls")),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),
]
