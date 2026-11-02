
from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    # Movie and series discovery
    path("", views.catalog_home, name="home"),

    # Movie and series information
    path(
        "<str:media_type>/<int:movie_id>/",
        views.catalog_detail,
        name="detail",
    ),

    # Full movie playback
    path(
        "watch/movie/<int:title_id>/",
        views.movie_player,
        name="movie_player",
    ),

    # Full TV episode playback
    path(
        "watch/episode/<int:episode_id>/",
        views.episode_player,
        name="episode_player",
    ),

    # Save the user's playback position
    path(
        "watch/progress/",
        views.save_watch_progress,
        name="save_watch_progress",
    ),
]
