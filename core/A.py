# core/A.py
import asyncio
import logging
import os
import tempfile
import math
from typing import List, Dict, Any, Tuple, Optional

# کتابخونه‌های اصلی برای عملیات
import scrapetube
import yt_dlp
# tubescrape رو به عنوان یه گزینه احتمالی وارد می‌کنیم
# اگه نصب نیست، برنامه نباید کلاً از کار بیفته
try:
    import tubescrape
    TUBESCRAPE_AVAILABLE = True
except ImportError:
    TUBESCRAPE_AVAILABLE = False
    logging.warning("tubescrape نصب نیست، این ابزار از زنجیره fallback حذف میشه.")

logger = logging.getLogger(__name__)

class YouTubeEngine:
    """
    موتور پردازشی یوتیوب با قابلیت استفاده از چند ابزار پشت سر هم (fallback).
    همه‌ی عملیات جستجو و دانلود از طریق این کلاس انجام میشه.
    """

    def __init__(self):
        # تنظیمات پایه برای yt-dlp
        self.ydl_base_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',  # برای جستجوها عالیه
            'proxy': self._get_proxy(),      # اگه پروکسی در دسترس باشه، اینجا ست میشه
            'socket_timeout': 30,
        }

    def _get_proxy(self) -> Optional[str]:
        """
        اینجا میتونیم پروکسی رو از یه منبع خارجی (مثلاً متغیر محیطی یا یه API) بگیریم.
        برای شروع، خالی برمی‌گردونه. بعداً میتونیم توسعه‌اش بدیم.
        """
        # مثلاً: return os.environ.get('YT_PROXY')
        return None

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        جستجوی یوتیوب با استفاده از چندین ابزار به ترتیب اولویت.
        اگه یکی شکست خورد، میره سراغ بعدی.
        """
        logger.info(f"🔍 شروع جستجوی چندمنظوره برای: '{query}'")

        # ۱. ابزار اول: scrapetube (سریع و ساده)
        try:
            results = await self._search_with_scrapetube(query)
            if results:
                logger.info(f"✅ جستجو با scrapetube موفقیت‌آمیز بود. {len(results)} نتیجه پیدا شد.")
                return results
        except Exception as e:
            logger.warning(f"⚠️ scrapetube شکست خورد: {e}")

        # ۲. ابزار دوم: tubescrape (اگه نصب باشه)
        if TUBESCRAPE_AVAILABLE:
            try:
                results = await self._search_with_tubescrape(query)
                if results:
                    logger.info(f"✅ جستجو با tubescrape موفقیت‌آمیز بود. {len(results)} نتیجه پیدا شد.")
                    return results
            except Exception as e:
                logger.warning(f"⚠️ tubescrape شکست خورد: {e}")

        # ۳. ابزار سوم: yt-dlp (قدرتمند اما ممکنه با پروکسی و ... کندتر باشه)
        try:
            results = await self._search_with_ytdlp(query)
            if results:
                logger.info(f"✅ جستجو با yt-dlp موفقیت‌آمیز بود. {len(results)} نتیجه پیدا شد.")
                return results
        except Exception as e:
            logger.warning(f"⚠️ yt-dlp هم شکست خورد: {e}")

        logger.error(f"❌ همه ابزارهای جستجو برای '{query}' شکست خوردن.")
        return []

    async def download(self, url: str) -> Tuple[str, str]:
        """
        دانلود ویدیو و برگردوندن مسیر فایل و عنوان.
        از yt-dlp با تنظیمات مخصوص دانلود استفاده می‌کنه.
        در صورت بروز خطاهای مربوط به تحریم، استراتژی‌های مختلف رو امتحان می‌کنه.
        """
        logger.info(f"📥 شروع دانلود: {url}")
        
        # استراتژی‌های دانلود از ملایم تا سخت‌گیرانه
        strategies = [
            {},  # ۱. بدون تنظیمات خاص
            {'cookiefile': self._get_cookie_file()}, # ۲. با کوکی (اگه موجود باشه)
            {'proxy': self._get_proxy()}, # ۳. با پروکسی
        ]

        last_error = None
        for i, extra_opts in enumerate(strategies):
            try:
                logger.info(f"🔄 تلاش #{i+1} برای دانلود...")
                video_path, title = await self._download_with_ytdlp(url, extra_opts)
                if video_path and os.path.exists(video_path):
                    logger.info(f"✅ دانلود موفقیت‌آمیز بود: {title}")
                    return video_path, title
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ تلاش #{i+1} شکست خورد: {e}")

        raise Exception(f"دانلود پس از {len(strategies)} بار تلاش ناموفق بود. آخرین خطا: {last_error}")

    # ----------------------------------------------------------------------
    # توابع کمکی خصوصی برای پیاده‌سازی ابزارها
    # ----------------------------------------------------------------------
    async def _search_with_scrapetube(self, query: str) -> List[Dict[str, Any]]:
        """جستجو با کتابخونه scrapetube"""
        videos = scrapetube.get_search(query)
        results = []
        # فقط ۱۰ نتیجه اول رو برمی‌داریم که پاسخ زیاد شلوغ نشه
        for i, video in enumerate(videos):
            if i >= 10:
                break
            results.append({
                'title': video.get('title', {}).get('runs', [{}])[0].get('text', 'بدون عنوان'),
                'url': f"https://youtu.be/{video['videoId']}",
                'id': video['videoId']
            })
        return results

    async def _search_with_tubescrape(self, query: str) -> List[Dict[str, Any]]:
        """جستجو با کتابخونه tubescrape"""
        # چون tubescrape ممکنه synchronous باشه، برای یکپارچگی از run_in_executor استفاده می‌کنیم
        loop = asyncio.get_event_loop()
        results_data = await loop.run_in_executor(None, tubescrape.search, query)
        
        results = []
        for video in results_data[:10]:  # فقط ۱۰ نتیجه
            results.append({
                'title': video.get('title', 'بدون عنوان'),
                'url': video.get('url', ''),
                'id': video.get('id', '')
            })
        return results

    async def _search_with_ytdlp(self, query: str) -> List[Dict[str, Any]]:
        """جستجو با yt-dlp (قدرتمندترین ابزار)"""
        ydl_opts = self.ydl_base_opts.copy()
        ydl_opts['extract_flat'] = True
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # استفاده از قابلیت جستجوی داخلی yt-dlp
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            
        results = []
        if 'entries' in info:
            for entry in info['entries']:
                if entry:
                    results.append({
                        'title': entry.get('title', 'بدون عنوان'),
                        'url': entry.get('webpage_url', f"https://youtu.be/{entry.get('id', '')}"),
                        'id': entry.get('id', '')
                    })
        return results

    async def _download_with_ytdlp(self, url: str, extra_opts: dict) -> Tuple[str, str]:
        """هسته اصلی دانلود با yt-dlp"""
        # یه دایرکتوری موقت برای دانلود فایل
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = self.ydl_base_opts.copy()
            ydl_opts.update(extra_opts)
            ydl_opts.update({
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # اول یه استخراج اطلاعات برای گرفتن عنوان
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'video')
                filename = ydl.prepare_filename(info)
                
                # حالا دانلود واقعی
                ydl.download([url])
                
                # اگه فایل با اسم دیگه‌ای ذخیره شده بود، پیداش می‌کنیم
                for f in os.listdir(tmpdir):
                    if f.endswith('.mp4') or f.endswith('.mkv') or f.endswith('.webm'):
                        video_path = os.path.join(tmpdir, f)
                        return video_path, title
                        
        raise Exception("فایل دانلود شده پیدا نشد.")

    def _get_cookie_file(self) -> Optional[str]:
        """
        اگه فایل کوکی در مسیر مشخصی وجود داشته باشه، مسیرش رو برمی‌گردونه.
        میتونی فایل cookie.txt رو توی مخزن بذاری و ازش استفاده کنی.
        """
        cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookie_path):
            return cookie_path
        return None
