from django.urls import path

from . import views

app_name = "streaming"

urlpatterns = [
    path("", views.stream_list, name="stream_list"),

    path("create/", views.create_stream, name="create_stream"),

    path(
        "<uuid:stream_id>/edit/",
        views.edit_stream,
        name="edit_stream",
    ),

    path(
        "<uuid:stream_id>/studio/",
        views.studio,
        name="studio",
    ),

    path(
        "<uuid:stream_id>/watch/",
        views.watch_stream,
        name="watch_stream",
    ),

    path(
        "<uuid:stream_id>/start/",
        views.start_stream,
        name="start_stream",
    ),

    path(
        "<uuid:stream_id>/end/",
        views.end_stream,
        name="end_stream",
    ),

    path(
        "<uuid:stream_id>/obs/ingress/",
        views.create_obs_ingress,
        name="create_obs_ingress",
    ),

    path(
        "<uuid:stream_id>/token/",
        views.stream_token,
        name="stream_token",
    ),
]