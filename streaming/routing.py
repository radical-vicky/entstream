from django.urls import re_path

from .consumers import StreamChatConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/streams/(?P<stream_id>[0-9a-f-]+)/chat/$",
        StreamChatConsumer.as_asgi(),
    ),
]