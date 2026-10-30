from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Stream, StreamChatMessage


User = get_user_model()


class StreamingModelTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="streamer",
            password="test-password-123"
        )

    def test_stream_creation(self):

        stream = Stream.objects.create(
            creator=self.user,
            title="My First Stream"
        )

        self.assertEqual(
            stream.status,
            Stream.Status.DRAFT
        )

        self.assertTrue(stream.slug)
        self.assertTrue(stream.stream_key)
        self.assertTrue(stream.livekit_room)

    def test_unique_slug(self):

        first = Stream.objects.create(
            creator=self.user,
            title="Gaming Live"
        )

        second = Stream.objects.create(
            creator=self.user,
            title="Gaming Live"
        )

        self.assertNotEqual(
            first.slug,
            second.slug
        )


class StreamingViewTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="streamer",
            password="test-password-123"
        )

        self.stream = Stream.objects.create(
            creator=self.user,
            title="Test Stream"
        )

    def test_public_stream_list(self):

        response = self.client.get(
            reverse("streaming:index")
        )

        self.assertEqual(response.status_code, 200)

    def test_create_stream_requires_login(self):

        response = self.client.get(
            reverse("streaming:create")
        )

        self.assertEqual(response.status_code, 302)

    def test_creator_can_open_studio(self):

        self.client.login(
            username="streamer",
            password="test-password-123"
        )

        response = self.client.get(
            reverse(
                "streaming:studio",
                kwargs={"stream_id": self.stream.pk}
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_open_studio(self):

        other = User.objects.create_user(
            username="other",
            password="test-password-123"
        )

        self.client.login(
            username="other",
            password="test-password-123"
        )

        response = self.client.get(
            reverse(
                "streaming:studio",
                kwargs={"stream_id": self.stream.pk}
            )
        )

        self.assertEqual(response.status_code, 404)