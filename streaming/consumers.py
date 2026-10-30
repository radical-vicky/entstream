import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Stream, StreamChatMessage


class StreamChatConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):

        self.stream_id = self.scope["url_route"]["kwargs"]["stream_id"]

        self.group_name = f"stream_chat_{self.stream_id}"

        self.user = self.scope["user"]

        stream_exists = await self.stream_exists()

        if not stream_exists:
            await self.close(code=4404)
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send_json({
            "type": "connection",
            "message": "Connected to stream chat."
        })

    async def disconnect(self, close_code):

        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive_json(self, content, **kwargs):

        if not self.user.is_authenticated:
            await self.send_json({
                "type": "error",
                "message": "Login is required to send messages."
            })
            return

        message = str(
            content.get("message", "")
        ).strip()

        if not message:
            return

        if len(message) > 500:
            await self.send_json({
                "type": "error",
                "message": "Message is too long."
            })
            return

        saved = await self.save_message(message)

        if not saved:
            await self.send_json({
                "type": "error",
                "message": "This stream is not accepting messages."
            })
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "username": self.user.get_username(),
                "message": message,
                "created_at": saved,
            }
        )

    async def chat_message(self, event):

        await self.send_json({
            "type": "chat_message",
            "username": event["username"],
            "message": event["message"],
            "created_at": event["created_at"],
        })

    @database_sync_to_async
    def stream_exists(self):

        return Stream.objects.filter(
            pk=self.stream_id,
            is_public=True
        ).exists()

    @database_sync_to_async
    def save_message(self, message):

        try:
            stream = Stream.objects.get(
                pk=self.stream_id,
                status=Stream.Status.LIVE,
                is_public=True,
            )

            saved = StreamChatMessage.objects.create(
                stream=stream,
                user=self.user,
                message=message,
            )

            return saved.created_at.isoformat()

        except Stream.DoesNotExist:
            return None