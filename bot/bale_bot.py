#!/usr/bin/env python3
"""
Bale Bot Frontend - مسئول تعامل با کاربر و مدیریت دستورات.
از کتابخانه python-telegram-bot برای ارتباط با API بله استفاده می‌کند.
مغز پردازشی (core.A) را برای عملیات جستجو و دانلود فراخوانی می‌کند.
دارای حلقه حیات ۵:۵۵ دقیقه اجرا / ۵ دقیقه خواب برای دور زدن محدودیت ۶ ساعته گیت‌هاب.
"""

import os
import sys
import time
import logging
import asyncio
import tempfile
import math
from pathlib import Path
from typing import List, Tuple, Optional

# کتابخانه اصلی ربات (سازگار با API بله)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# مغز پردازشی (در گام بعدی ساخته می‌شود)
# فرض می‌کنیم core/A.py کلاسی به نام YouTubeEngine با متدهای search و download دارد.
sys.path.append(str(Path(__file__).parent.parent))  # افزودن ریشه پروژه به مسیر پایتون
try:
    from core.A import YouTubeEngine
except ImportError:
    # در صورتی که هنوز core/A.py وجود نداشته باشد، یک نمونه موقت قرار می‌دهیم.
    class YouTubeEngine:
        async def search(self, query: str) -> List[dict]:
            return [{"title": "نمونه ویدیو", "url": "https://youtu.be/dQw4w9WgXcQ"}]
        async def download(self, url: str) -> Tuple[str, str]:
            return ("/tmp/sample.mp4", "Sample Video.mp4")
    logging.warning("core.A یافت نشد، از نمونه موقت استفاده می‌شود.")

# تنظیمات لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات از متغیر محیطی (در گیت‌هاب از Secrets می‌آید)
BALE_TOKEN = os.environ.get("BALE_TOKEN")
if not BALE_TOKEN:
    logger.error("BALE_TOKEN تنظیم نشده است!")
    sys.exit(1)

# آدرس API بله
BASE_URL = "https://tapi.bale.ai/bot"

# محدودیت حجم فایل در بله (۲۰ مگابایت)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

# مدت زمان اجرا و خواب (برای دور زدن محدودیت ۶ ساعته)
RUN_DURATION = 5 * 60 * 60 + 55 * 60  # 5 ساعت و 55 دقیقه (به ثانیه)
SLEEP_DURATION = 5 * 60               # 5 دقیقه (به ثانیه)


class BaleBot:
    """کلاس مدیریت ربات بله"""
    
    def __init__(self):
        self.engine = YouTubeEngine()
        self.start_time = time.time()
        self.app = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """دستور /start"""
        user = update.effective_user
        await update.message.reply_text(
            f"سلام {user.first_name}! 👋\n"
            "من ربات جستجو و دانلود یوتیوب هستم.\n\n"
            "🔍 برای جستجو از دستور /search استفاده کن.\n"
            "📥 برای دانلود لینک رو مستقیم بفرست.\n"
            "ℹ️ راهنما: /help"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """نمایش راهنما"""
        help_text = (
            "📌 **راهنمای ربات یوتیوب**\n\n"
            "• `/search عبارت جستجو` : جستجوی ویدیو در یوتیوب (از چند ابزار fallback استفاده می‌کند)\n"
            "• `ارسال لینک یوتیوب` : دانلود ویدیو و ارسال به صورت تکه‌های ۲۰ مگابایتی\n\n"
            "⚠️ توجه: دانلود ممکن است چند دقیقه طول بکشد.\n"
            "🛡️ ربات از سیستم چندلایه برای دور زدن محدودیت‌ها استفاده می‌کند."
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """جستجوی یوتیوب"""
        query = " ".join(context.args)
        if not query:
            await update.message.reply_text("❌ لطفاً عبارت جستجو را وارد کنید. مثال: `/search آموزش پایتون`")
            return
        
        status_msg = await update.message.reply_text("🔍 در حال جستجو...")
        
        try:
            # فراخوانی مغز برای جستجو (اجرای غیرهمزمان)
            results = await self.engine.search(query)
            
            if not results:
                await status_msg.edit_text("😕 هیچ نتیجه‌ای یافت نشد.")
                return
            
            # ساخت دکمه‌های انتخاب
            keyboard = []
            for i, video in enumerate(results[:5]):  # حداکثر ۵ نتیجه
                title = video.get('title', 'بدون عنوان')[:50]
                url = video.get('url', '')
                if url:
                    keyboard.append([InlineKeyboardButton(
                        f"{i+1}. {title}",
                        callback_data=f"dl_{url}"  # ذخیره لینک برای دانلود
                    )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await status_msg.edit_text(
                "✅ نتایج جستجو:\n\nیک گزینه را برای دانلود انتخاب کنید:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.exception("خطا در جستجو")
            await status_msg.edit_text(f"❌ خطا در جستجو: {str(e)[:200]}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """پردازش پیام‌های متنی (برای لینک یوتیوب)"""
        text = update.message.text.strip()
        
        # بررسی لینک یوتیوب
        if "youtube.com/watch" in text or "youtu.be/" in text:
            await self._process_download(update, context, text)
        else:
            await update.message.reply_text(
                "❓ لینک یوتیوب معتبر ارسال کنید یا از دستور /search استفاده کنید."
            )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """پردازش کلیک روی دکمه‌های inline"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data.startswith("dl_"):
            url = data[3:]  # حذف پیشوند dl_
            await query.edit_message_text("📥 در حال آماده‌سازی دانلود...")
            # شبیه‌سازی دریافت پیام متنی برای شروع دانلود
            fake_update = update
            fake_update.message = query.message
            await self._process_download(fake_update, context, url)
    
    async def _process_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
        """پردازش دانلود و ارسال تکه‌ای فایل"""
        status_msg = await update.message.reply_text("⏳ در حال دریافت اطلاعات ویدیو...")
        
        try:
            # مرحله ۱: دانلود با استفاده از مغز
            video_path, title = await self.engine.download(url)
            
            if not video_path or not os.path.exists(video_path):
                await status_msg.edit_text("❌ دانلود فایل با شکست مواجه شد.")
                return
            
            file_size = os.path.getsize(video_path)
            await status_msg.edit_text(f"📦 دانلود کامل شد. حجم: {file_size / (1024*1024):.1f} MB\n🔄 در حال ارسال تکه‌ای...")
            
            # مرحله ۲: تقسیم و ارسال فایل
            await self._send_file_in_chunks(update, context, video_path, title, file_size)
            
            # پاکسازی فایل موقت
            os.unlink(video_path)
            await status_msg.edit_text("✅ ارسال با موفقیت انجام شد.")
            
        except Exception as e:
            logger.exception("خطا در دانلود/ارسال")
            await status_msg.edit_text(f"❌ خطا: {str(e)[:200]}")
    
    async def _send_file_in_chunks(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   file_path: str, title: str, total_size: int) -> None:
        """
        ارسال فایل به صورت تکه‌های ۲۰ مگابایتی.
        به دلیل محدودیت API بله، فایل را به قسمت‌های مجزا تقسیم می‌کند.
        """
        chunk_size = MAX_FILE_SIZE
        total_chunks = math.ceil(total_size / chunk_size)
        
        with open(file_path, 'rb') as f:
            for chunk_idx in range(total_chunks):
                chunk_data = f.read(chunk_size)
                
                # ذخیره تکه در فایل موقت (API بله نیاز به فایل دارد)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                    tmp.write(chunk_data)
                    tmp_path = tmp.name
                
                caption = f"🎬 {title}\n📦 تکه {chunk_idx+1} از {total_chunks}"
                
                try:
                    # ارسال فایل ویدیویی
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=open(tmp_path, 'rb'),
                        caption=caption,
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال تکه {chunk_idx+1}: {e}")
                    await update.message.reply_text(f"⚠️ خطا در ارسال تکه {chunk_idx+1}")
                finally:
                    os.unlink(tmp_path)
                
                # کمی مکث برای جلوگیری از محدودیت نرخ
                await asyncio.sleep(1)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """مدیریت خطاهای ربات"""
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
        if update and hasattr(update, 'effective_message'):
            await update.effective_message.reply_text("⚠️ متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.")
    
    def build_app(self) -> Application:
        """ساخت و پیکربندی Application"""
        app = Application.builder() \
            .token(BALE_TOKEN) \
            .base_url(BASE_URL) \
            .base_file_url(BASE_URL) \
            .read_timeout(30) \
            .write_timeout(30) \
            .connect_timeout(30) \
            .pool_timeout(30) \
            .build()
        
        # هندلرها
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("search", self.search_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.button_callback))
        app.add_error_handler(self.error_handler)
        
        return app
    
    async def run_with_lifecycle(self):
        """اجرای ربات با چرخه ۵:۵۵ / ۵ دقیقه"""
        while True:
            self.start_time = time.time()
            logger.info(f"🚀 ربات شروع به کار کرد (تا {RUN_DURATION/3600:.2f} ساعت دیگر)")
            
            self.app = self.build_app()
            async with self.app:
                await self.app.start()
                await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                
                # حلقه اصلی اجرا تا زمان تعیین شده
                while time.time() - self.start_time < RUN_DURATION:
                    await asyncio.sleep(10)
                
                # توقف منظم
                logger.info("⏸️ زمان استراحت فرا رسید. ربات متوقف می‌شود.")
                await self.app.updater.stop()
                await self.app.stop()
            
            # خواب ۵ دقیقه
            logger.info(f"💤 خواب {SLEEP_DURATION/60} دقیقه...")
            await asyncio.sleep(SLEEP_DURATION)


async def main():
    """تابع اصلی اجرا"""
    bot = BaleBot()
    await bot.run_with_lifecycle()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ربات به صورت دستی متوقف شد.")
    except Exception as e:
        logger.critical(f"خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
      
