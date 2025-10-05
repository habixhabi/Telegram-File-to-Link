import os
from dataclasses import dataclass
from pyrogram.types import Message
import asyncio

api_id = os.environ.get("API_ID")
api_hash = os.environ.get("API_HASH")
bot_token = os.environ.get("BOT_TOKEN")

# متغیرهای کنترل وضعیت برنامه
running = True
background_tasks = set()

# تعریف یکبار دستورات برای BotFather
BOT_COMMANDS = [
    ('start', 'شروع کار با ربات 🚀'),
    ('help', 'راهنمای استفاده از ربات 📖'),
    ('status', 'نمایش وضعیت سیستم و فایل‌ها 📊'),
    ('config', 'نمایش تنظیمات فعلی ⚙️'),
    ('proxy', 'نمایش وضعیت پروکسی 🌐'),
    ('cleanup', 'پاکسازی فایل‌های قدیمی 🧹'),
]

@dataclass
class DownloadState:
    """
    کلاس نگهداری وضعیت دانلود
    """
    message_id: int
    chat_id: int
    start_time: float
    file_path: str = None
    file_name: str = None
    cancelled: bool = False
    status_msg: Message = None
    task: asyncio.Task = None
    progress: float = 0.0
    last_update: float = time.time()

class MemoryManager:
    """
    کلاس مدیریت حافظه و منابع
    """
    def __init__(self, memory_threshold: float = 90.0):
        self.memory_threshold = memory_threshold
        self.process = psutil.Process()
        
    def get_memory_usage(self) -> Dict[str, float]:
        """
        دریافت آمار استفاده از حافظه
        """
        memory = psutil.virtual_memory()
        process_memory = self.process.memory_info()
        
        return {
            'system_total': memory.total / (1024 ** 2),  # MB
            'system_used': memory.used / (1024 ** 2),    # MB
            'system_percent': memory.percent,
            'process_rss': process_memory.rss / (1024 ** 2),  # MB
            'process_vms': process_memory.vms / (1024 ** 2)   # MB
        }
    
    def cleanup_memory(self) -> None:
        """
        پاکسازی حافظه و اجرای garbage collector
        """
        # فراخوانی garbage collector
        collected = gc.collect()
        print(f"🧹 تعداد {collected} شیء از حافظه پاکسازی شد")
        
    def should_cleanup(self) -> bool:
        """
        بررسی نیاز به پاکسازی حافظه
        """
        memory_usage = self.get_memory_usage()
        return memory_usage['system_percent'] > self.memory_threshold
    
    def log_memory_stats(self) -> None:
        """
        ثبت وضعیت حافظه در لاگ
        """
        stats = self.get_memory_usage()
        if stats['system_percent'] > 90:
            print(f"⚠️ هشدار: استفاده از حافظه بالاست ({stats['system_percent']:.1f}%)")
    
    async def monitor_memory(self, interval: int = 300) -> None:
        """
        نظارت مستمر بر وضعیت حافظه
        interval: فاصله زمانی بررسی به ثانیه (پیش‌فرض: 5 دقیقه)
        """
        while True:
            try:
                if self.should_cleanup():
                    print("⚠️ مصرف حافظه بالاست، در حال پاکسازی...")
                    self.cleanup_memory()
                
                self.log_memory_stats()
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"❌ خطا در نظارت بر حافظه: {e}")
                await asyncio.sleep(60)  # انتظار 1 دقیقه در صورت خطا

# ایجاد نمونه مدیر حافظه
memory_manager = MemoryManager()

# تابع پاکسازی خودکار فایل‌های قدیمی در صورت نیاز
def cleanup_old_files():
    """
    پاکسازی خودکار فایل‌های قدیمی در صورت پر شدن حافظه
    پاکسازی براساس قدمت فایل‌ها انجام می‌شود
    """
    try:
        # بررسی وضعیت فعلی
        stats = get_file_stats()
        if not stats['files']:
            return

        # بررسی فضای دیسک در لینوکس
        st = os.statvfs(DOWNLOAD_PATH)
        total_space = st.f_blocks * st.f_frsize
        free_space = st.f_bavail * st.f_frsize
        used_percent = ((total_space - free_space) / total_space) * 100 if total_space > 0 else 0

        # اگر فضای استفاده شده بیشتر از 90% است
        if used_percent > 90:
            # مرتب‌سازی و حذف فایل‌های قدیمی
            for file_info in sorted(stats['files'], key=lambda x: -x['age_hours']):
                if used_percent <= 75:
                    break
                
                file_path = os.path.join(DOWNLOAD_PATH, file_info['name'])
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"🧹 حذف فایل قدیمی: {os.path.basename(file_path)}")

                        # بروزرسانی درصد استفاده
                        st = os.statvfs(DOWNLOAD_PATH)
                        total_space = st.f_blocks * st.f_frsize
                        free_space = st.f_bavail * st.f_frsize
                        used_percent = ((total_space - free_space) / total_space) * 100 if total_space > 0 else 0

                        # پس از حذف موفق، بروزرسانی config.json
                        try:
                            update_config_file_list()
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"❌ خطا در حذف {os.path.basename(file_path)}: {e}")

    except Exception as e:
        print(f"❌ خطا در پاکسازی: {e}")

# تعریف مسیر پایه برای ذخیره فایل‌ها
BASE_STORAGE_PATH = "/var/www/html"

# خواندن تنظیمات از config.json
def load_config():
    """
    خواندن تنظیمات از فایل config.json
    """
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # اضافه کردن مسیر پایه به مسیر دانلود اگر مسیر نسبی باشد
            if config.get('download_path', '').startswith('/'):
                if not config['download_path'].startswith(BASE_STORAGE_PATH):
                    config['download_path'] = os.path.join(BASE_STORAGE_PATH.rstrip('/'), config['download_path'].lstrip('/'))
            
            return config
            
    except FileNotFoundError:
        print("❌ فایل config.json یافت نشد!")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ خطا در خواندن فایل config.json: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در خواندن config: {e}")
        exit(1)

# بارگذاری تنظیمات
config = load_config()

# استخراج تنظیمات از config
API_ID = str(config.get('api_id', ''))
API_HASH = config.get('api_hash', '')
BOT_TOKEN = config.get('bot_token', '')
FILE_MAX_AGE_HOURS = config.get('file_max_age_hours', 24)
YOUR_DOMAIN = config.get('your_domain', '')
DOWNLOAD_PATH = config.get('download_path', 'dl')
ALLOWED_CHAT_IDS = config.get('allowed_chat_ids', [])
PROXY_CONFIG = config.get('proxy', {})

# تبدیل مسیر نسبی به مطلق
if not os.path.isabs(DOWNLOAD_PATH):
    DOWNLOAD_PATH = os.path.join(os.path.dirname(__file__), DOWNLOAD_PATH)

# ایجاد پوشه در صورت عدم وجود
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# مدیریت دانلودهای فعال
class DownloadManager:
    """
    کلاس مدیریت دانلودهای فعال
    """
    def __init__(self):
        self.active_downloads: Dict[str, DownloadState] = {}
        self.cleanup_interval = 3600  # پاکسازی هر 1 ساعت
        self._last_cleanup = time.time()
    
    def add_download(self, message: Message) -> str:
        """
        اضافه کردن دانلود جدید
        """
        download_id = f"{message.chat.id}_{message.id}"
        self.active_downloads[download_id] = DownloadState(
            message_id=message.id,
            chat_id=message.chat.id,
            start_time=time.time()
        )
        return download_id
    
    def update_download(self, download_id: str, **kwargs) -> None:
        """
        بروزرسانی وضعیت دانلود
        """
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            for key, value in kwargs.items():
                setattr(download, key, value)
            download.last_update = time.time()
    
    def remove_download(self, download_id: str) -> None:
        """
        حذف دانلود از لیست فعال
        """
        if download_id in self.active_downloads:
            download = self.active_downloads[download_id]
            # پاکسازی فایل‌های موقت در صورت لغو
            if download.cancelled and download.file_path:
                try:
                    if os.path.exists(download.file_path):
                        os.remove(download.file_path)
                        print(f"🗑️ فایل نیمه‌کاره حذف شد: {download.file_path}")
                        try:
                            update_config_file_list()
                        except Exception:
                            pass
                except Exception as e:
                    print(f"❌ خطا در حذف فایل نیمه‌کاره: {e}")
            
            del self.active_downloads[download_id]
    
    def get_download(self, download_id: str) -> DownloadState:
        """
        دریافت وضعیت دانلود
        """
        return self.active_downloads.get(download_id)
    
    def cleanup_stale_downloads(self) -> None:
        """
        پاکسازی دانلودهای قدیمی و متوقف شده
        """
        now = time.time()
        # پاکسازی دانلودهای قدیمی‌تر از 1 ساعت
        stale_downloads = [
            download_id for download_id, download in self.active_downloads.items()
            if now - download.last_update > 3600  # 1 ساعت
        ]
        
        for download_id in stale_downloads:
            print(f"🧹 پاکسازی دانلود قدیمی: {download_id}")
            self.remove_download(download_id)
    
    async def monitor_downloads(self) -> None:
        """
        نظارت مستمر بر وضعیت دانلودها
        """
        while True:
            try:
                now = time.time()
                if now - self._last_cleanup >= self.cleanup_interval:
                    self.cleanup_stale_downloads()
                    self._last_cleanup = now
                
                # نمایش آمار دانلودهای فعال
                active_count = len(self.active_downloads)
                if active_count > 0:
                    print(f"📥 دانلودهای فعال: {active_count}")
                
                await asyncio.sleep(300)  # بررسی هر 5 دقیقه
                
            except Exception as e:
                print(f"❌ خطا در نظارت بر دانلودها: {e}")
                await asyncio.sleep(60)

# ایجاد نمونه مدیر دانلود
download_manager = DownloadManager()

# تابع برنامه‌ریز برای اجرای دوره‌ای پاکسازی
async def cleanup_scheduler():
    """
    برنامه‌ریز برای اجرای دوره‌ای پاکسازی هر 2 ساعت
    """
    while True:
        try:
            # اجرای پاکسازی
            cleanup_old_files()
            # انتظار 2 ساعت
            await asyncio.sleep(2 * 60 * 60)  # تبدیل 2 ساعت به ثانیه
        except Exception as e:
            print(f"❌ خطا در برنامه‌ریز پاکسازی: {e}")
            # در صورت خطا، 5 دقیقه صبر می‌کنیم و دوباره تلاش می‌کنیم
            await asyncio.sleep(5 * 60)

# بررسی و تنظیم پروکسی
def get_proxy_config():
    """
    بررسی تنظیمات پروکسی و برگرداندن کانفیگ مناسب
    """
    if PROXY_CONFIG and PROXY_CONFIG.get("server") and PROXY_CONFIG.get("port"):
        proxy = {
            "scheme": PROXY_CONFIG.get("scheme", "socks5"),
            "hostname": PROXY_CONFIG["server"],
            "port": PROXY_CONFIG["port"]
        }
        # اضافه کردن احراز هویت در صورت وجود
        if PROXY_CONFIG.get("user") and PROXY_CONFIG.get("pass"):
            proxy["username"] = PROXY_CONFIG["user"]
            proxy["password"] = PROXY_CONFIG["pass"]
        return proxy
    return None

# تابع کنترل دسترسی
def is_allowed_chat(chat_id):
    """
    بررسی اینکه کاربر اجازه استفاده دارد یا خیر
    در صورت خالی بودن لیست، همه کاربران مجاز هستند
    """
    try:
        if chat_id is None:
            return False
        # اگر لیست خالی باشد، همه مجاز هستند
        if not ALLOWED_CHAT_IDS:
            return True
        return int(chat_id) in ALLOWED_CHAT_IDS
    except Exception:
        return False

# تابع تولید لینک عمومی
def build_public_url(file_name):
    """
    تولید لینک عمومی برای فایل و حذف مسیر پایه از آن
    """
    if YOUR_DOMAIN.startswith('http://') or YOUR_DOMAIN.startswith('https://'):
        base = YOUR_DOMAIN.rstrip('/')
    else:
        base = f"https://{YOUR_DOMAIN}".rstrip('/')
    
    # استفاده از مسیر نسبی برای URL
    relative_path = config.get('download_path', 'dl').replace(BASE_STORAGE_PATH, '').lstrip('/')
    return f"{base}/{relative_path}/{file_name}"

# تابع محاسبه آمار فایل‌ها
def get_file_stats():
    """
    محاسبه آمار فایل‌های موجود
    """
    try:
        if not os.path.exists(DOWNLOAD_PATH):
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'files': []
            }
        
        files = []
        total_size = 0
        
        for filename in os.listdir(DOWNLOAD_PATH):
            file_path = os.path.join(DOWNLOAD_PATH, filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_age = time.time() - os.path.getmtime(file_path)
                files.append({
                    'name': filename,
                    'size': file_size,
                    'age_hours': file_age / 3600
                })
                total_size += file_size
        
        return {
            'total_files': len(files),
            'total_size_mb': total_size / (1024 * 1024),
            'files': files
        }
    except Exception as e:
        print(f"❌ خطا در محاسبه آمار: {e}")
        return {
            'total_files': 0,
            'total_size_mb': 0,
            'files': []
        }


def update_config_file_list():
    """
    نوشتن آرایه فایل‌ها در فایل `files.json` کنار اسکریپت.
    هر آیتم شامل: name, size_bytes, public_url
    """
    try:
        files = []
        for filename in os.listdir(DOWNLOAD_PATH):
            file_path = os.path.join(DOWNLOAD_PATH, filename)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                public_url = build_public_url(filename)
                mtime = os.path.getmtime(file_path)
                files.append({
                    'name': filename,
                    'size_bytes': size,
                    'public_url': public_url,
                    'mtime': mtime
                })

        # Write files.json into the webroot (BASE_STORAGE_PATH) so the web server can serve it
        web_files_path = os.path.join(BASE_STORAGE_PATH, 'files.json')
        try:
            os.makedirs(BASE_STORAGE_PATH, exist_ok=True)
        except Exception:
            pass

        # sort by mtime descending (newest first)
        files.sort(key=lambda x: x.get('mtime', 0), reverse=True)

        # remove mtime from output
        out_files = [{k: v for k, v in f.items() if k != 'mtime'} for f in files]
        with open(web_files_path, 'w', encoding='utf-8') as f:
            json.dump(out_files, f, ensure_ascii=False, indent=4)

        print(f"✅ {web_files_path} updated with {len(files)} files")
    except Exception as e:
        print(f"❌ خطا در بروزرسانی files.json: {e}")

# ایجاد کلاینت ربات با پشتیبانی پروکسی
proxy_config = get_proxy_config()
if proxy_config:
    print(f"🌐 اتصال از طریق پروکسی: {proxy_config['hostname']}:{proxy_config['port']}")
    bot = Client(
        "file_saver_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        proxy=proxy_config
    )
else:
    print("⚠️ بدون پروکسی ادامه می‌دهیم")
    bot = Client(
        "file_saver_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

@bot.on_message(filters.document | filters.photo | filters.video | filters.audio | filters.voice)
async def handle_file(client: Client, message: Message):
    """
    دریافت و ذخیره فایل‌های فوروارد شده به ربات
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return
    
    # ایجاد وضعیت دانلود جدید
    download_id = download_manager.add_download(message)
    
    # شروع زمان‌سنج
    start_time = time.time()
    
    try:
        # بررسی وضعیت حافظه قبل از شروع دانلود
        if memory_manager.should_cleanup():
            print("⚠️ حافظه در وضعیت بحرانی است، پاکسازی خودکار...")
            memory_manager.cleanup_memory()
        
        # ایجاد دکمه لغو دانلود
        cancel_button = InlineKeyboardButton("❌ لغو دانلود", callback_data=f"cancel_{download_id}")
        keyboard = InlineKeyboardMarkup([[cancel_button]])
        
        # نمایش پیام در حال دانلود با دکمه لغو
        status_message = await message.reply_text(
            "⏳ در حال دانلود فایل...\n"
            "📊 وضعیت: شروع دانلود\n"
            "⏱️ زمان: محاسبه...",
            reply_markup=keyboard,
            reply_to_message_id=message.id
        )
        
        # بروزرسانی وضعیت دانلود
        download_manager.update_download(
            download_id,
            cancelled=False,
            status_msg=status_message
        )
        
        # تعیین نوع فایل و دانلود آن
        file_path = None
        file_name = None
        
        # تابع دانلود که در Task جداگانه اجرا می‌شود
        async def do_download():
            nonlocal file_path, file_name
            try:
                if message.document:
                    file_name = message.document.file_name
                    file_path = await message.download(
                        file_name=os.path.join(DOWNLOAD_PATH, file_name)
                    )
                elif message.photo:
                    file_name = f"photo_{message.photo.file_unique_id}.jpg"
                    file_path = await message.download(
                        file_name=os.path.join(DOWNLOAD_PATH, file_name)
                    )
                elif message.video:
                    file_name = message.video.file_name or f"video_{message.video.file_unique_id}.mp4"
                    file_path = await message.download(
                        file_name=os.path.join(DOWNLOAD_PATH, file_name)
                    )
                elif message.audio:
                    file_name = message.audio.file_name or f"audio_{message.audio.file_unique_id}.mp3"
                    file_path = await message.download(
                        file_name=os.path.join(DOWNLOAD_PATH, file_name)
                    )
                elif message.voice:
                    file_name = f"voice_{message.voice.file_unique_id}.ogg"
                    file_path = await message.download(
                        file_name=os.path.join(DOWNLOAD_PATH, file_name)
                    )
                
                return file_path, file_name
            except asyncio.CancelledError:
                raise
            except Exception as e:
                raise e
        
        # اجرای دانلود در Task جداگانه
        download_task = asyncio.create_task(do_download())
        download_manager.update_download(download_id, task=download_task)
        
        try:
            # منتظر تکمیل دانلود یا لغو آن
            file_path, file_name = await download_task
            download_manager.update_download(download_id, file_path=file_path, file_name=file_name)
            
        except asyncio.CancelledError:
            # دانلود لغو شد - پاکسازی فایل نیمه‌کاره
            if file_path and os.path.exists(file_path):
                try:
                    # بررسی اینکه آیا فایل در حال نوشتن است
                    if os.access(file_path, os.W_OK):
                        os.remove(file_path)
                        print(f"🗑️ فایل نیمه‌کاره حذف شد: {file_path}")
                    else:
                        print(f"⚠️ امکان حذف فایل نیمه‌کاره وجود ندارد: {file_path}")
                except PermissionError:
                    print(f"⚠️ خطای دسترسی در حذف فایل نیمه‌کاره: {file_path}")
                except Exception as e:
                    print(f"❌ خطا در حذف فایل نیمه‌کاره: {e}")
            
            # پاکسازی فایل‌های موقت مرتبط
            temp_pattern = f"{file_path}.*" if file_path else os.path.join(DOWNLOAD_PATH, f"*{message.id}*")
            for temp_file in glob.glob(temp_pattern):
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"🗑️ فایل موقت حذف شد: {temp_file}")
                        try:
                            update_config_file_list()
                        except Exception:
                            pass
                except Exception as e:
                    print(f"❌ خطا در حذف فایل موقت: {e}")
            
            download_manager.remove_download(download_id)
            return
        
        # بررسی اینکه آیا در حین دانلود لغو شده
        download_state = download_manager.get_download(download_id)
        if download_state and download_state.cancelled:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    try:
                        update_config_file_list()
                    except Exception:
                        pass
                except Exception:
                    pass
            
            # حذف پیام وضعیت در صورت وجود
            if download_state.status_msg:
                try:
                    await download_state.status_msg.delete()
                except Exception as e:
                    print(f"⚠️ خطا در حذف پیام وضعیت: {e}")

            await message.reply_text(
                "🚫 دانلود لغو شد",
                reply_to_message_id=message.id
            )
            
            download_manager.remove_download(download_id)
            return
        
        # محاسبه مدت زمان دانلود
        end_time = time.time()
        download_duration = end_time - start_time
        
        # فرمت کردن مدت زمان
        if download_duration < 60:
            duration_str = f"{download_duration:.1f} ثانیه"
        elif download_duration < 3600:
            minutes = int(download_duration // 60)
            seconds = int(download_duration % 60)
            duration_str = f"{minutes} دقیقه و {seconds} ثانیه"
        else:
            hours = int(download_duration // 3600)
            minutes = int((download_duration % 3600) // 60)
            duration_str = f"{hours} ساعت و {minutes} دقیقه"
        
        # محاسبه حجم فایل و سرعت دانلود
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # تبدیل به مگابایت
        speed_mbps = (file_size / download_duration) if download_duration > 0 else 0
        
        # تولید لینک عمومی
        public_url = build_public_url(file_name)
        
        # نمایش پیام موفقیت با جزئیات و حذف پیام وضعیت قبلی
        try:
            # حذف پیام وضعیت قبلی
            if download_state and download_state.status_msg:
                await download_state.status_msg.delete()
        except Exception as e:
            print(f"⚠️ خطا در حذف پیام وضعیت: {e}")

        await message.reply_text(
            f"✅ فایل با موفقیت ذخیره شد!\n\n"
            f"📁 نام فایل: `{file_name}`\n"
            f"📊 حجم: {file_size:.2f} MB\n"
            f"⏱️ مدت زمان: {duration_str}\n"
            f"⚡ سرعت: {speed_mbps:.2f} MB/s\n\n"
            f"🌐 لینک: {public_url}\n\n"
            f"🔗 کپی لینک: `{public_url}`\n\n"
            f"📂 مسیر: `{file_path}`",
            reply_to_message_id=message.id
        )
        
        # پاک کردن از لیست دانلودهای فعال
        download_manager.remove_download(download_id)
            
        # بررسی و پاکسازی خودکار در صورت نیاز
        cleanup_old_files()
        # بروزرسانی لیست فایل‌ها در config.json پس از دانلود و احتمالی حذف
        try:
            update_config_file_list()
        except Exception as e:
            print(f"⚠️ خطا در بروزرسانی لیست فایل‌ها پس از دانلود: {e}")
        
    except Exception as e:
        # حذف فایل نیمه‌کاره در صورت خطا
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                try:
                    update_config_file_list()
                except Exception:
                    pass
            except Exception:
                pass
        
        # حذف پیام وضعیت در صورت وجود
        if download_id in download_manager.active_downloads:
            download_state = download_manager.get_download(download_id)
            if download_state and download_state.status_msg:
                try:
                    await download_state.status_msg.delete()
                except Exception as e:
                    print(f"⚠️ خطا در حذف پیام وضعیت: {e}")
        
        await message.reply_text(
            f"❌ خطا در ذخیره فایل: {str(e)}",
            reply_to_message_id=message.id
        )
        
        # پاک کردن از لیست دانلودهای فعال در صورت خطا
        download_manager.remove_download(download_id)

@bot.on_callback_query()
async def handle_callback_query(client: Client, callback_query: CallbackQuery):
    """
    هندلر دکمه‌های تعاملی (لغو دانلود)
    """
    try:
        # کنترل دسترسی
        if not is_allowed_chat(callback_query.message.chat.id):
            return
        
        # استخراج download_id از callback data
        if callback_query.data.startswith("cancel_"):
            download_id = callback_query.data.replace("cancel_", "")
            
            download_state = download_manager.get_download(download_id)
            if download_state:
                # علامت‌گذاری به عنوان لغو شده
                download_manager.update_download(download_id, cancelled=True)
                
                # لغو Task دانلود
                if download_state.task and not download_state.task.done():
                    download_state.task.cancel()
                
                # حذف پیام وضعیت دانلود
                try:
                    await callback_query.message.delete()
                except Exception as e:
                    print(f"⚠️ خطا در حذف پیام وضعیت: {e}")

                # اعلان به کاربر
                await callback_query.answer("⏹️ دانلود لغو شد", show_alert=False)
                
                # ارسال پیام لغو به عنوان reply به پیام اصلی
                await client.send_message(
                    chat_id=callback_query.message.chat.id,
                    text="🚫 دانلود لغو شد",
                    reply_to_message_id=download_state.message_id
                )
                
            else:
                await callback_query.answer("⚠️ این دانلود قبلاً تکمیل یا لغو شده است", show_alert=True)
        
        elif callback_query.data == "help_info":
            # نمایش راهنمای کامل
            help_text = """
📖 **راهنمای کامل ربات:**

1️⃣ **ارسال فایل:** هر فایلی را به این ربات فوروارد کنید
2️⃣ **دانلود خودکار:** ربات فایل را دانلود و ذخیره می‌کند
3️⃣ **لغو دانلود:** در حین دانلود می‌توانید با دکمه لغو، دانلود را متوقف کنید
4️⃣ **لینک عمومی:** پس از دانلود، لینک مستقیم دریافت می‌کنید

📋 **دستورات موجود:**
• /start - شروع و معرفی ربات
• /help - راهنمای استفاده
• /proxy - نمایش وضعیت پروکسی
• /status - نمایش وضعیت سیستم
• /config - نمایش تنظیمات فعلی

🔧 **ویژگی‌های پیشرفته:**
• کنترل دسترسی کامل
• پشتیبانی از پروکسی SOCKS5
• آمار و اطلاعات سیستم
• تولید لینک عمومی
• لغو دانلود در حین انجام
            """
            await callback_query.edit_message_text(help_text)
            await callback_query.answer("📖 راهنمای کامل نمایش داده شد")
            
        elif callback_query.data == "status_info":
            # نمایش وضعیت سیستم
            try:
                stats = get_file_stats()
                old_files = sum(1 for f in stats['files'] if f['age_hours'] > FILE_MAX_AGE_HOURS)
                
                status_text = f"""
📊 **وضعیت سیستم:**

📁 **تعداد فایل:** {stats['total_files']}
💾 **حجم کل:** {stats['total_size_mb']:.2f} MB
⏰ **فایل‌های قدیمی:** {old_files} (بیش از {FILE_MAX_AGE_HOURS} ساعت)

🌐 **دامنه:** `{YOUR_DOMAIN}`
📂 **مسیر:** `{DOWNLOAD_PATH}`

🔒 **کاربران مجاز:** {len(ALLOWED_CHAT_IDS)} نفر
🌐 **پروکسی:** {'فعال' if get_proxy_config() else 'غیرفعال'}
                """
                await callback_query.edit_message_text(status_text)
                await callback_query.answer("📊 وضعیت سیستم نمایش داده شد")
            except Exception as e:
                await callback_query.answer(f"❌ خطا در دریافت وضعیت: {str(e)}", show_alert=True)
                
    except Exception as e:
        print(f"❌ خطا در هندلر callback: {e}")
        try:
            await callback_query.answer("❌ خطا در لغو دانلود", show_alert=True)
        except Exception:
            pass

@bot.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """
    پاسخ به دستور /start
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return
    
    # ایجاد دکمه‌های تعاملی
    help_button = InlineKeyboardButton("📖 راهنما", callback_data="help_info")
    status_button = InlineKeyboardButton("📊 وضعیت", callback_data="status_info")
    keyboard = InlineKeyboardMarkup([
        [help_button, status_button]
    ])
    
    # ایجاد متن دستورات
    commands_text = "\n".join([f"/{cmd} - {desc}" for cmd, desc in BOT_COMMANDS])
    
    await message.reply_text(
        "👋 سلام! به ربات ذخیره‌ساز فایل خوش آمدید.\n\n"
        "📤 هر فایلی که به این ربات فوروارد کنید، "
        f"در مسیر `{DOWNLOAD_PATH}` ذخیره می‌شود.\n\n"
        "✅ انواع فایل پشتیبانی شده:\n"
        "• اسناد (Documents)\n"
        "• عکس‌ها (Photos)\n"
        "• ویدیوها (Videos)\n"
        "• فایل‌های صوتی (Audio)\n"
        "• پیام‌های صوتی (Voice)\n\n"
        "🚫 **قابلیت لغو دانلود:** در حین دانلود می‌توانید با دکمه لغو، دانلود را متوقف کنید\n\n"
        "📋 **دستورات موجود:**\n"
        f"{commands_text}\n\n"
        "⚠️ توجه: فایل‌ها فقط زمانی ذخیره می‌شوند که به این ربات فوروارد شوند.",
        reply_markup=keyboard
    )

@bot.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """
    راهنمای استفاده از ربات
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return
    
    # ایجاد متن دستورات
    commands_text = "\n".join([f"• /{cmd} - {desc}" for cmd, desc in BOT_COMMANDS])
    
    await message.reply_text(
        "📖 راهنمای استفاده:\n\n"
        "1️⃣ هر فایلی را که می‌خواهید ذخیره کنید، به این ربات فوروارد کنید\n"
        "2️⃣ ربات فایل را دانلود کرده و در سرور ذخیره می‌کند\n"
        "3️⃣ پیام تأیید همراه با مشخصات فایل دریافت می‌کنید\n\n"
        f"📂 مسیر ذخیره‌سازی: `{DOWNLOAD_PATH}`\n\n"
        "⚠️ مهم: فقط فایل‌هایی که به این ربات فوروارد می‌شوند ذخیره می‌شوند.\n"
        "اگر فایل را به جای دیگری فوروارد کنید، ذخیره نمی‌شود.\n\n"
        "📋 دستورات موجود:\n"
        f"{commands_text}\n\n"
        "🚫 **قابلیت لغو دانلود:** در حین دانلود می‌توانید با دکمه لغو، دانلود را متوقف کنید"
    )

@bot.on_message(filters.command("proxy"))
async def proxy_command(client: Client, message: Message):
    """
    نمایش وضعیت پروکسی
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return
    
    proxy_status = get_proxy_config()
    if proxy_status:
        proxy_info = f"""
🌐 **وضعیت پروکسی:**

✅ **فعال**
🖥️ **سرور:** `{proxy_status['hostname']}`
🔌 **پورت:** `{proxy_status['port']}`
🔧 **نوع:** `{proxy_status['scheme'].upper()}`
👤 **کاربر:** `{proxy_status.get('username', 'تنظیم نشده')}`
🔑 **رمز:** `{'تنظیم شده' if proxy_status.get('password') else 'تنظیم نشده'}`

💡 **نحوه تنظیم:** مقادیر proxy را در فایل config.json ویرایش کنید
        """
    else:
        proxy_info = f"""
🌐 **وضعیت پروکسی:**

❌ **غیرفعال**

💡 **راهنما:** برای فعال‌سازی پروکسی، بخش proxy را در فایل config.json تنظیم کنید:
```json
"proxy": {{
    "scheme": "socks5",
    "server": "your_proxy_server",
    "port": 1080,
    "user": "your_username",
    "pass": "your_password"
}}
```
        """
    
    await message.reply_text(proxy_info)

@bot.on_message(filters.command("status"))
async def status_command(client: Client, message: Message):
    """
    نمایش وضعیت فایل‌ها و سیستم
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return
    
    try:
        # دریافت آمار فایل‌ها
        stats = get_file_stats()
        
        # شمارش فایل‌های قدیمی
        old_files = sum(1 for f in stats['files'] if f['age_hours'] > FILE_MAX_AGE_HOURS)
        
        # نمایش وضعیت سیستم
        status_msg = f"""
📊 **وضعیت سیستم:**

📁 **تعداد فایل:** {stats['total_files']}
💾 **حجم کل:** {stats['total_size_mb']:.2f} MB
⏰ **فایل‌های قدیمی:** {old_files} (بیش از {FILE_MAX_AGE_HOURS} ساعت)

🌐 **دامنه:** `{YOUR_DOMAIN}`
📂 **مسیر:** `{DOWNLOAD_PATH}`

🔒 **کاربران مجاز:** {len(ALLOWED_CHAT_IDS)} نفر
🌐 **پروکسی:** {'فعال' if get_proxy_config() else 'غیرفعال'}

📋 **دستورات موجود:**
• /start - شروع و معرفی ربات
• /help - راهنمای استفاده  
• /proxy - نمایش وضعیت پروکسی
• /status - نمایش وضعیت سیستم
• /config - نمایش تنظیمات فعلی

🚫 **قابلیت لغو دانلود:** در حین دانلود می‌توانید با دکمه لغو، دانلود را متوقف کنید
        """
        
        await message.reply_text(status_msg)
        
    except Exception as e:
        await message.reply_text(f"❌ خطا در دریافت وضعیت: {str(e)}")

@bot.on_message(filters.command("config"))
async def config_command(client: Client, message: Message):
    """
    نمایش تنظیمات فعلی ربات
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return
    
    try:
        proxy_status = "فعال" if get_proxy_config() else "غیرفعال"
        
        config_text = f"""
⚙️ **تنظیمات فعلی ربات:**

🤖 **اطلاعات ربات:**
• API ID: `{API_ID}`
• Bot Token: `{BOT_TOKEN[:20]}...`

🌐 **دامنه و مسیر:**
• دامنه: `{YOUR_DOMAIN}`
• مسیر دانلود: `{DOWNLOAD_PATH}`

⏰ **حداکثر سن فایل:**
• {FILE_MAX_AGE_HOURS} ساعت

🔒 **کاربران مجاز:**
• تعداد: {len(ALLOWED_CHAT_IDS)} نفر
• IDs: `{', '.join(map(str, ALLOWED_CHAT_IDS))}`

🌐 **پروکسی:**
• وضعیت: {proxy_status}
{f'• سرور: `{PROXY_CONFIG.get("server")}`' if proxy_status == 'فعال' else ''}
{f'• پورت: `{PROXY_CONFIG.get("port")}`' if proxy_status == 'فعال' else ''}
{f'• نوع: `{PROXY_CONFIG.get("scheme", "socks5").upper()}`' if proxy_status == 'فعال' else ''}

💡 **راهنما:**
تمام تنظیمات از فایل `config.json` خوانده می‌شوند.
برای تغییر تنظیمات، فایل config.json را ویرایش کنید و ربات را مجدداً راه‌اندازی کنید.
        """
        
        await message.reply_text(config_text)
        
    except Exception as e:
        await message.reply_text(f"❌ خطا در نمایش تنظیمات: {str(e)}")

@bot.on_message(filters.command([cmd for cmd, _ in BOT_COMMANDS]))
async def handle_commands(client: Client, message: Message):
    """
    هندلر برای تمام دستورات
    """
    # کنترل دسترسی
    if not is_allowed_chat(message.chat.id):
        return

    command = message.command[0] if message.command else ""

    # اجرای دستور cleanup
    if command == "cleanup":
        try:
            stats_before = get_file_stats()
            if stats_before['total_files'] == 0:
                await message.reply_text("📂 پوشه خالی است - نیازی به پاکسازی نیست")
                return
                
            status_msg = await message.reply_text(
                f"🔍 بررسی {stats_before['total_files']} فایل...",
                reply_to_message_id=message.id
            )
            
            cleanup_old_files()
            stats_after = get_file_stats()
            
            if stats_before['total_files'] == stats_after['total_files']:
                await status_msg.edit_text("✅ نیازی به پاکسازی نیست، فضای کافی موجود است")
                return
                
            files_removed = stats_before['total_files'] - stats_after['total_files']
            space_freed = stats_before['total_size_mb'] - stats_after['total_size_mb']
            
            await status_msg.edit_text(
                f"♻️ پاکسازی انجام شد:\n"
                f"🗑️ {files_removed} فایل حذف شد\n"
                f"💾 {space_freed:.1f} MB فضا آزاد شد"
            )
            return
            
        except Exception as e:
            await message.reply_text(f"❌ خطا در پاکسازی: {str(e)}")
            return

    # برای سایر دستورات ناشناخته
    command = message.text.split()[0] if message.text else "دستور نامشخص"
    help_button = InlineKeyboardButton("📖 راهنما", callback_data="help_info")
    keyboard = InlineKeyboardMarkup([[help_button]])
    
    await message.reply_text(
        f"❓ دستور `{command}` شناخته نشده است.\n\n"
        "برای مشاهده لیست دستورات موجود، از /help استفاده کنید یا "
        "روی دکمه راهنما کلیک کنید.",
        reply_markup=keyboard
    )

async def graceful_cleanup():
    """
    پاکسازی منابع و توقف ایمن برنامه
    """
    global running
    
    if not running:
        return
        
    running = False
    print("\n⚠️ در حال توقف ایمن برنامه...")
    
    # لغو تمام دانلودهای فعال
    if 'download_manager' in globals():
        for download in download_manager.active_downloads.values():
            if download.task and not download.task.done():
                download.task.cancel()
    
    # لغو تمام تسک‌های پس‌زمینه
    for task in background_tasks:
        if not task.done():
            task.cancel()
    
    # منتظر اتمام تسک‌ها می‌مانیم
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
    
    # توقف ربات
    try:
        await bot.stop()
    except Exception as e:
        print(f"⚠️ خطا در توقف ربات: {e}")
    
    print("✅ ربات با موفقیت متوقف شد")

async def main():
    """
    تابع اصلی اجرای ربات با مدیریت خطا
    """
    global running
    
    try:
        # دریافت event loop
        loop = asyncio.get_running_loop()
        
        def handle_signals():
            """مدیریت سیگنال‌های توقف"""
            if running:
                asyncio.create_task(graceful_cleanup())
            else:
                print("\n⚠️ در حال توقف اجباری برنامه...")
                sys.exit(1)
        
        # تنظیم signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, handle_signals)
        
        # شروع تسک‌های پس‌زمینه
        cleanup_task = asyncio.create_task(cleanup_scheduler())
        memory_task = asyncio.create_task(memory_manager.monitor_memory())
        downloads_task = asyncio.create_task(download_manager.monitor_downloads())
        
        # اضافه کردن به لیست تسک‌های پس‌زمینه
        background_tasks.update([cleanup_task, memory_task, downloads_task])
        
        # شروع ربات
        await bot.start()
        
        # تنظیم دستورات در BotFather
        try:
            await bot.set_bot_commands([
                types.BotCommand(command=cmd, description=desc)
                for cmd, desc in BOT_COMMANDS
            ])
        except Exception as e:
            print(f"⚠️ خطا در تنظیم دستورات: {e}")
        
        print("✅ ربات با موفقیت راه‌اندازی شد")
        
        # منتظر می‌مانیم تا برنامه متوقف شود
        while running:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"❌ خطای اصلی برنامه: {e}")
        traceback.print_exc()
    finally:
        # اطمینان از توقف ایمن در هر شرایط
        if running:
            await graceful_cleanup()

if __name__ == "__main__":
    # تنظیم لاگ کردن خطاها (فقط در کنسول)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    # ثبت handler برای خطاهای پیش‌بینی نشده (فقط نمایش در کنسول)
    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        print("\n❌ خطای پیش‌بینی نشده:", file=sys.stderr)
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        logger.error("خطای پیش‌بینی نشده:", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_uncaught_exception
    
    # تهیه متن وضعیت پروکسی
    proxy_text = "غیرفعال"
    if proxy_config:
        scheme = proxy_config.get('scheme', 'socks5').upper()
        host = proxy_config.get('hostname', '')
        port = proxy_config.get('port', '')
        proxy_text = f"{scheme} - {host}:{port}"

    startup_info = [
        "🤖 ربات تلگرام در حال راه‌اندازی...",
        f"📂 مسیر: {DOWNLOAD_PATH}",
        f"🔒 {'بدون کاربر مجاز' if not ALLOWED_CHAT_IDS else f'{len(ALLOWED_CHAT_IDS)} کاربر مجاز'}",
        f"🌐 پروکسی: {proxy_text}"
    ]
    print("\n".join(startup_info) + "\n")
    
    # تنظیم event loop برای لینوکس
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n⚠️ درخواست توقف از طرف کاربر دریافت شد...")
    except Exception as e:
        print(f"❌ خطا در اجرای برنامه: {e}")
        logger.error("خطای اصلی برنامه:", exc_info=True)
    finally:
        try:
            loop.close()
        except Exception as e:
            print(f"❌ خطا در بستن event loop: {e}")
            logger.error("خطا در بستن event loop:", exc_info=True)
