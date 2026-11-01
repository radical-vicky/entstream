
import asyncio
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from xvideos_api import Client


async def inspect_xvideos():
    client = Client()

    async for result in client.search(query="test", pages=1):
        if not result.succeeded:
            continue

        video = result.item

        print("\n========== VIDEO DATA ==========")
        print(video.to_dict())

        print("\n========== EMBED URL ==========")
        print(repr(getattr(video, "embed_url", None)))

        print("\n========== VIDEO ID ==========")
        print(repr(getattr(video, "video_id", None)))

        print("\n========== VIDEO URL ==========")
        print(repr(getattr(video, "url", None)))

        break


if __name__ == "__main__":
    asyncio.run(inspect_xvideos())
