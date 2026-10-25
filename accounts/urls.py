
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/", views.my_profile, name="profile"),
]
