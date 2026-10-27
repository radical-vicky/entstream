
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from videos import views as video_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", video_views.home, name="home"),

    path("videos/", include("videos.urls")),
    path("creators/", include("creators.urls")),

    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),

    path("chat/", include("chat.urls")),
    path("streams/", include("streaming.urls")),

    path("subscriptions/", include("subscriptions.urls")),
    path("earnings/", include("earnings.urls")),
    path("moderation/", include("moderation.urls")),
    path("payments/", include("payments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)