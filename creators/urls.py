
from django.urls import path
from . import views

app_name = "creators"

urlpatterns = [
    path("<str:username>/follow/", views.toggle_follow, name="toggle_follow"),
]
