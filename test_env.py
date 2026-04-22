import os
import sys

print("=" * 40)
print("🔧 تست محیط اجرا")
print("=" * 40)

# 1. نسخه پایتون
print(f"Python version: {sys.version}")

# 2. مسیر فعلی
print(f"Current directory: {os.getcwd()}")

# 3. وضعیت توکن
token_exists = "BALE_TOKEN" in os.environ
print(f"BALE_TOKEN is set: {token_exists}")
if token_exists:
    token = os.environ["BALE_TOKEN"]
    print(f"Token starts with: {token[:5]}... (length: {len(token)})")

# 4. تست import کتابخانه‌ها
try:
    import telegram
    print(f"python-telegram-bot version: {telegram.__version__}")
except ImportError as e:
    print(f"❌ Error importing telegram: {e}")

try:
    import yt_dlp
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
except ImportError as e:
    print(f"⚠️ yt-dlp not installed: {e}")

# 5. تست import ماژول‌های پروژه
sys.path.append(os.getcwd())
try:
    from core.A import YouTubeEngine
    print("✅ core.A imported successfully")
except Exception as e:
    print(f"❌ Error importing core.A: {e}")

try:
    from bot.bale_bot import BaleBot
    print("✅ BaleBot imported successfully")
except Exception as e:
    print(f"❌ Error importing BaleBot: {e}")

print("=" * 40)
print("🏁 تست پایان یافت")
