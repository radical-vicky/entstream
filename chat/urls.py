
from django.urls import path

from . import views

app_name = "chat"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("start/<str:username>/", views.start_conversation, name="start"),
    path("<int:pk>/", views.conversation_detail, name="conversation"),
    path("messages/<int:pk>/delete/", views.delete_message, name="delete_message"),
]
