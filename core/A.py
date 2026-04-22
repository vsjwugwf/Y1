# core/A.py
import asyncio
import logging
import os
import tempfile
from typing import List, Dict, Any, Tuple, Optional

import yt_dlp

logger = logging.getLogger(__name__)

class YouTubeEngine:
    """
    موتور یوتیوب با استفاده انحصاری از yt-dlp.
    هم جستجو و هم دانلود را پوشش می‌دهد.
    """

    def __init__(self):
        # تنظیمات پایه yt-dlp
        self.ydl_base_opts = {
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            # استفاده از کلاینت اندروید برای کاهش احتمال تحریم
            'extractor_args': {'youtube': {'client': ['android']}},
        }

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        جستجوی یوتیوب با استفاده از قابلیت جستجوی داخلی yt-dlp.
        """
        logger.info(f"🔍 جستجو با yt-dlp برای: '{query}'")
        try:
            # اجرای synchronous yt-dlp در thread جدا
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(self.ydl_base_opts).extract_info(
                    f"ytsearch10:{query}", download=False
                )
            )
            results = []
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        title = entry.get('title', 'بدون عنوان')
                        video_id = entry.get('id')
                        url = entry.get('webpage_url') or f"https://youtu.be/{video_id}"
                        results.append({
                            'title': title,
                            'url': url,
                            'id': video_id
                        })
            logger.info(f"✅ {len(results)} نتیجه یافت شد.")
            return results
        except Exception as e:
            logger.error(f"❌ خطا در جستجو با yt-dlp: {e}")
            return []

    async def download(self, url: str) -> Tuple[str, str]:
        """
        دانلود ویدیو با yt-dlp.
        فایل در یک دایرکتوری موقت ذخیره می‌شود.
        """
        logger.info(f"📥 دانلود با yt-dlp: {url}")
        
        # استراتژی‌های مختلف در صورت شکست
        strategies = [
            {},  # پیش‌فرض
            {'extractor_args': {'youtube': {'client': ['web']}}},
            {'cookiefile': self._get_cookie_file()},
        ]

        last_error = None
        for i, extra_opts in enumerate(strategies):
            try:
                logger.info(f"🔄 تلاش #{i+1} برای دانلود...")
                video_path, title = await self._do_download(url, extra_opts)
                if video_path and os.path.exists(video_path):
                    logger.info(f"✅ دانلود موفق: {title}")
                    return video_path, title
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ تلاش #{i+1} شکست خورد: {e}")

        raise Exception(f"دانلود ناموفق. آخرین خطا: {last_error}")

    async def _do_download(self, url: str, extra_opts: dict) -> Tuple[str, str]:
        """عملیات اصلی دانلود (اجرا در thread جدا)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = self.ydl_base_opts.copy()
            ydl_opts.update(extra_opts)
            ydl_opts.update({
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            })

            loop = asyncio.get_event_loop()
            # مرحله ۱: استخراج اطلاعات (بدون دانلود)
            info = await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)
            )
            title = info.get('title', 'video')
            
            # مرحله ۲: دانلود
            await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(ydl_opts).download([url])
            )

            # پیدا کردن فایل دانلود شده
            for f in os.listdir(tmpdir):
                file_path = os.path.join(tmpdir, f)
                if os.path.isfile(file_path) and f.endswith(('.mp4', '.mkv', '.webm')):
                    return file_path, title

        raise Exception("فایل دانلود شده یافت نشد.")

    def _get_cookie_file(self) -> Optional[str]:
        """اگر فایل cookies.txt در کنار این ماژول باشد، مسیر آن را برمی‌گرداند."""
        cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookie_path):
            logger.info("🍪 استفاده از فایل کوکی برای احراز هویت.")
            return cookie_path
        return None
