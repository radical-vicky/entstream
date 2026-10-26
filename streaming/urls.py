
from django.urls import path

from . import views

app_name = "streaming"

urlpatterns = [
    path("", views.stream_list, name="list"),
    path("mine/", views.my_streams, name="my_streams"),
    path("schedule/", views.schedule_stream, name="schedule"),
    path("<int:pk>/", views.stream_detail, name="detail"),
    path("<int:pk>/edit/", views.edit_stream, name="edit"),
    path("<int:pk>/start/", views.start_stream, name="start"),
    path("<int:pk>/end/", views.end_stream, name="end"),
    path("<int:pk>/cancel/", views.cancel_stream, name="cancel"),
]
