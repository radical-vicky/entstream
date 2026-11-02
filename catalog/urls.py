
from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog_home, name="home"),
    path(
        "<str:media_type>/<int:movie_id>/",
        views.catalog_detail,
        name="detail",
    ),
]
