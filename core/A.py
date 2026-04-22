# core/A.py
import logging

logger = logging.getLogger(__name__)

class YouTubeEngine:
    async def search(self, query: str):
        logger.info(f"Search called with: {query}")
        return [
            {"title": "Test Video 1", "url": "https://youtu.be/test1"},
            {"title": "Test Video 2", "url": "https://youtu.be/test2"},
        ]

    async def download(self, url: str):
        logger.info(f"Download called with: {url}")
        # در عمل باید فایل واقعی بسازی، برای تست فقط مسیر رو برمی‌گردونه
        return ("/tmp/test.mp4", "Test Video Title")
