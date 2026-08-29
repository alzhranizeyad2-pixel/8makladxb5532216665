import os
import json
import re
import urllib.parse
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
from urllib3.exceptions import InsecureRequestWarning

# ============ PORT FIX ============
PORT = int(os.environ.get("PORT", 10000))
print(f"🚀 Starting bot on port: {PORT}")

# Bot Token
BOT_TOKEN = "7168370915:AAE-PfYTjsxPr5uKx62_M_ykp0Ek6uHQqq4"

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

ACCOUNT_HEADERS = {
    "Host": "www.netflix.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.netflix.com/browse",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

FLAG_MAP = {
    "AF": "🇦🇫", "AX": "🇦🇽", "AL": "🇦🇱", "DZ": "🇩🇿", "AS": "🇦🇸",
    "AD": "🇦🇩", "AO": "🇦🇴", "AI": "🇦🇮", "AQ": "🇦🇶", "AG": "🇦🇬",
    "AR": "🇦🇷", "AM": "🇦🇲", "AW": "🇦🇼", "AU": "🇦🇺", "AT": "🇦🇹",
    "AZ": "🇦🇿", "BS": "🇧🇸", "BH": "🇧🇭", "BD": "🇧🇩", "BB": "🇧🇧",
    "BY": "🇧🇾", "BE": "🇧🇪", "BZ": "🇧🇿", "BJ": "🇧🇯", "BM": "🇧🇲",
    "BT": "🇧🇹", "BO": "🇧🇴", "BA": "🇧🇦", "BW": "🇧🇼", "BV": "🇧🇻",
    "BR": "🇧🇷", "IO": "🇮🇴", "BN": "🇧🇳", "BG": "🇧🇬", "BF": "🇧🇫",
    "BI": "🇧🇮", "CV": "🇨🇻", "KH": "🇰🇭", "CM": "🇨🇲", "CA": "🇨🇦",
    "KY": "🇰🇾", "CF": "🇨🇫", "TD": "🇹🇩", "CL": "🇨🇱", "CN": "🇨🇳",
    "CX": "🇨🇽", "CC": "🇨🇨", "CO": "🇨🇴", "KM": "🇰🇲", "CG": "🇨🇬",
    "CD": "🇨🇩", "CK": "🇨🇰", "CR": "🇨🇷", "CI": "🇨🇮", "HR": "🇭🇷",
    "CU": "🇨🇺", "CW": "🇨🇼", "CY": "🇨🇾", "CZ": "🇨🇿", "DK": "🇩🇰",
    "DJ": "🇩🇯", "DM": "🇩🇲", "DO": "🇩🇴", "EC": "🇪🇨", "EG": "🇪🇬",
    "SV": "🇸🇻", "GQ": "🇬🇶", "ER": "🇪🇷", "EE": "🇪🇪", "SZ": "🇸🇿",
    "ET": "🇪🇹", "FK": "🇫🇰", "FO": "🇫🇴", "FJ": "🇫🇯", "FI": "🇫🇮",
    "FR": "🇫🇷", "GF": "🇬🇫", "PF": "🇵🇫", "TF": "🇹🇫", "GA": "🇬🇦",
    "GM": "🇬🇲", "GE": "🇬🇪", "DE": "🇩🇪", "GH": "🇬🇭", "GI": "🇬🇮",
    "GR": "🇬🇷", "GL": "🇬🇱", "GD": "🇬🇩", "GP": "🇬🇵", "GU": "🇬🇺",
    "GT": "🇬🇹", "GG": "🇬🇬", "GN": "🇬🇳", "GW": "🇬🇼", "GY": "🇬🇾",
    "HT": "🇭🇹", "HM": "🇭🇲", "VA": "🇻🇦", "HN": "🇭🇳", "HK": "🇭🇰",
    "HU": "🇭🇺", "IS": "🇮🇸", "IN": "🇮🇳", "ID": "🇮🇩", "IR": "🇮🇷",
    "IQ": "🇮🇶", "IE": "🇮🇪", "IM": "🇮🇲", "IL": "🇮🇱", "IT": "🇮🇹",
    "JM": "🇯🇲", "JP": "🇯🇵", "JE": "🇯🇪", "JO": "🇯🇴", "KZ": "🇰🇿",
    "KE": "🇰🇪", "KI": "🇰🇮", "KP": "🇰🇵", "KR": "🇰🇷", "KW": "🇰🇼",
    "KG": "🇰🇬", "LA": "🇱🇦", "LV": "🇱🇻", "LB": "🇱🇧", "LS": "🇱🇸",
    "LR": "🇱🇷", "LY": "🇱🇾", "LI": "🇱🇮", "LT": "🇱🇹", "LU": "🇱🇺",
    "MO": "🇲🇴", "MG": "🇲🇬", "MW": "🇲🇼", "MY": "🇲🇾", "MV": "🇲🇻",
    "ML": "🇲🇱", "MT": "🇲🇹", "MH": "🇲🇭", "MQ": "🇲🇶", "MR": "🇲🇷",
    "MU": "🇲🇺", "YT": "🇾🇹", "MX": "🇲🇽", "FM": "🇫🇲", "MD": "🇲🇩",
    "MC": "🇲🇨", "MN": "🇲🇳", "ME": "🇲🇪", "MS": "🇲🇸", "MA": "🇲🇦",
    "MZ": "🇲🇿", "MM": "🇲🇲", "NA": "🇳🇦", "NR": "🇳🇷", "NP": "🇳🇵",
    "NL": "🇳🇱", "NC": "🇳🇨", "NZ": "🇳🇿", "NI": "🇳🇮", "NE": "🇳🇪",
    "NG": "🇳🇬", "NU": "🇳🇺", "NF": "🇳🇫", "MK": "🇲🇰", "MP": "🇲🇵",
    "NO": "🇳🇴", "OM": "🇴🇲", "PK": "🇵🇰", "PW": "🇵🇼", "PS": "🇵🇸",
    "PA": "🇵🇦", "PG": "🇵🇬", "PY": "🇵🇾", "PE": "🇵🇪", "PH": "🇵🇭",
    "PN": "🇵🇳", "PL": "🇵🇱", "PT": "🇵🇹", "PR": "🇵🇷", "QA": "🇶🇦",
    "RE": "🇷🇪", "RO": "🇷🇴", "RU": "🇷🇺", "RW": "🇷🇼", "BL": "🇧🇱",
    "SH": "🇸🇭", "KN": "🇰🇳", "LC": "🇱🇨", "MF": "🇲🇫", "PM": "🇵🇲",
    "VC": "🇻🇨", "WS": "🇼🇸", "SM": "🇸🇲", "ST": "🇸🇹", "SA": "🇸🇦",
    "SN": "🇸🇳", "RS": "🇷🇸", "SC": "🇸🇨", "SL": "🇸🇱", "SG": "🇸🇬",
    "SX": "🇸🇽", "SK": "🇸🇰", "SI": "🇸🇮", "SB": "🇸🇧", "SO": "🇸🇴",
    "ZA": "🇿🇦", "GS": "🇬🇸", "SS": "🇸🇸", "ES": "🇪🇸", "LK": "🇱🇰",
    "SD": "🇸🇩", "SR": "🇸🇷", "SJ": "🇸🇯", "SE": "🇸🇪", "CH": "🇨🇭",
    "SY": "🇸🇾", "TW": "🇹🇼", "TJ": "🇹🇯", "TZ": "🇹🇿", "TH": "🇹🇭",
    "TL": "🇹🇱", "TG": "🇹🇬", "TK": "🇹🇰", "TO": "🇹🇴", "TT": "🇹🇹",
    "TN": "🇹🇳", "TR": "🇹🇷", "TM": "🇹🇲", "TC": "🇹🇨", "TV": "🇹🇻",
    "UG": "🇺🇬", "UA": "🇺🇦", "AE": "🇦🇪", "GB": "🇬🇧", "US": "🇺🇸",
    "UM": "🇺🇲", "UY": "🇺🇾", "UZ": "🇺🇿", "VU": "🇻🇺", "VE": "🇻🇪",
    "VN": "🇻🇳", "VG": "🇻🇬", "VI": "🇻🇮", "WF": "🇼🇫", "EH": "🇪🇭",
    "YE": "🇾🇪", "ZM": "🇿🇲", "ZW": "🇿🇼"
}

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


def get_full_country_name(code):
    countries = {
        "AF": "Afghanistan", "AX": "Aland Islands", "AL": "Albania", "DZ": "Algeria",
        "AS": "American Samoa", "AD": "Andorra", "AO": "Angola", "AI": "Anguilla",
        "AQ": "Antarctica", "AG": "Antigua and Barbuda", "AR": "Argentina", "AM": "Armenia",
        "AW": "Aruba", "AU": "Australia", "AT": "Austria", "AZ": "Azerbaijan",
        "BS": "Bahamas", "BH": "Bahrain", "BD": "Bangladesh", "BB": "Barbados",
        "BY": "Belarus", "BE": "Belgium", "BZ": "Belize", "BJ": "Benin",
        "BM": "Bermuda", "BT": "Bhutan", "BO": "Bolivia", "BQ": "Bonaire, Sint Eustatius and Saba",
        "BA": "Bosnia and Herzegovina", "BW": "Botswana", "BV": "Bouvet Island", "BR": "Brazil",
        "IO": "British Indian Ocean Territory", "BN": "Brunei Darussalam", "BG": "Bulgaria",
        "BF": "Burkina Faso", "BI": "Burundi", "CV": "Cabo Verde", "KH": "Cambodia",
        "CM": "Cameroon", "CA": "Canada", "KY": "Cayman Islands", "CF": "Central African Republic",
        "TD": "Chad", "CL": "Chile", "CN": "China", "CX": "Christmas Island",
        "CC": "Cocos (Keeling) Islands", "CO": "Colombia", "KM": "Comoros", "CG": "Congo",
        "CD": "Congo, Democratic Republic of the", "CK": "Cook Islands", "CR": "Costa Rica",
        "CI": "Cote d'Ivoire", "HR": "Croatia", "CU": "Cuba", "CW": "Curacao",
        "CY": "Cyprus", "CZ": "Czech Republic", "DK": "Denmark", "DJ": "Djibouti",
        "DM": "Dominica", "DO": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt",
        "SV": "El Salvador", "GQ": "Equatorial Guinea", "ER": "Eritrea", "EE": "Estonia",
        "SZ": "Eswatini", "ET": "Ethiopia", "FK": "Falkland Islands", "FO": "Faroe Islands",
        "FJ": "Fiji", "FI": "Finland", "FR": "France", "GF": "French Guiana",
        "PF": "French Polynesia", "TF": "French Southern Territories", "GA": "Gabon",
        "GM": "Gambia", "GE": "Georgia", "DE": "Germany", "GH": "Ghana",
        "GI": "Gibraltar", "GR": "Greece", "GL": "Greenland", "GD": "Grenada",
        "GP": "Guadeloupe", "GU": "Guam", "GT": "Guatemala", "GG": "Guernsey",
        "GN": "Guinea", "GW": "Guinea-Bissau", "GY": "Guyana", "HT": "Haiti",
        "HM": "Heard Island and McDonald Islands", "VA": "Holy See (Vatican City State)",
        "HN": "Honduras", "HK": "Hong Kong", "HU": "Hungary", "IS": "Iceland",
        "IN": "India", "ID": "Indonesia", "IR": "Iran", "IQ": "Iraq",
        "IE": "Ireland", "IM": "Isle of Man", "IL": "Israel", "IT": "Italy",
        "JM": "Jamaica", "JP": "Japan", "JE": "Jersey", "JO": "Jordan",
        "KZ": "Kazakhstan", "KE": "Kenya", "KI": "Kiribati", "KR": "South Korea",
        "KW": "Kuwait", "KG": "Kyrgyzstan", "LA": "Laos", "LV": "Latvia",
        "LB": "Lebanon", "LS": "Lesotho", "LR": "Liberia", "LY": "Libya",
        "LI": "Liechtenstein", "LT": "Lithuania", "LU": "Luxembourg", "MO": "Macau",
        "MG": "Madagascar", "MW": "Malawi", "MY": "Malaysia", "MV": "Maldives",
        "ML": "Mali", "MT": "Malta", "MH": "Marshall Islands", "MQ": "Martinique",
        "MR": "Mauritania", "MU": "Mauritius", "YT": "Mayotte", "MX": "Mexico",
        "FM": "Micronesia", "MD": "Moldova", "MC": "Monaco", "MN": "Mongolia",
        "ME": "Montenegro", "MS": "Montserrat", "MA": "Morocco", "MZ": "Mozambique",
        "MM": "Myanmar", "NA": "Namibia", "NR": "Nauru", "NP": "Nepal",
        "NL": "Netherlands", "NC": "New Caledonia", "NZ": "New Zealand", "NI": "Nicaragua",
        "NE": "Niger", "NG": "Nigeria", "NU": "Niue", "NF": "Norfolk Island",
        "MK": "North Macedonia", "MP": "Northern Mariana Islands", "NO": "Norway",
        "OM": "Oman", "PK": "Pakistan", "PW": "Palau", "PS": "Palestine",
        "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
        "PH": "Philippines", "PN": "Pitcairn", "PL": "Poland", "PT": "Portugal",
        "PR": "Puerto Rico", "QA": "Qatar", "RE": "Reunion", "RO": "Romania",
        "RU": "Russian Federation", "RW": "Rwanda", "BL": "Saint Barthelemy",
        "SH": "Saint Helena, Ascension and Tristan da Cunha", "KN": "Saint Kitts and Nevis",
        "LC": "Saint Lucia", "MF": "Saint Martin (French part)", "PM": "Saint Pierre and Miquelon",
        "VC": "Saint Vincent and the Grenadines", "WS": "Samoa", "SM": "San Marino",
        "ST": "Sao Tome and Principe", "SA": "Saudi Arabia", "SN": "Senegal",
        "RS": "Serbia", "SC": "Seychelles", "SL": "Sierra Leone", "SG": "Singapore",
        "SX": "Sint Maarten", "SK": "Slovakia", "SI": "Slovenia", "SB": "Solomon Islands",
        "SO": "Somalia", "ZA": "South Africa", "GS": "South Georgia and the South Sandwich Islands",
        "SS": "South Sudan", "ES": "Spain", "LK": "Sri Lanka", "SD": "Sudan",
        "SR": "Suriname", "SJ": "Svalbard and Jan Mayen", "SE": "Sweden", "CH": "Switzerland",
        "SY": "Syrian Arab Republic", "TW": "Taiwan", "TJ": "Tajikistan", "TZ": "Tanzania",
        "TH": "Thailand", "TL": "Timor-Leste", "TG": "Togo", "TK": "Tokelau",
        "TO": "Tonga", "TT": "Trinidad and Tobago", "TN": "Tunisia", "TR": "Turkey",
        "TM": "Turkmenistan", "TC": "Turks and Caicos Islands", "TV": "Tuvalu",
        "UG": "Uganda", "UA": "Ukraine", "AE": "United Arab Emirates", "GB": "United Kingdom",
        "US": "United States", "UM": "United States Minor Outlying Islands", "UY": "Uruguay",
        "UZ": "Uzbekistan", "VU": "Vanuatu", "VE": "Venezuela", "VN": "Vietnam",
        "VG": "Virgin Islands (British)", "VI": "Virgin Islands (U.S.)", "WF": "Wallis and Futuna",
        "EH": "Western Sahara", "YE": "Yemen", "ZM": "Zambia", "ZW": "Zimbabwe"
    }
    return countries.get(code, code)


def decode_unicode_escape(text):
    if not text:
        return text
    try:
        return text.encode('utf-8').decode('unicode_escape')
    except:
        return text


def parse_cookie_line(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return {}
    
    if '\t' in line:
        parts = line.split('\t')
        if len(parts) >= 7:
            return {parts[5]: parts[6]}
    
    parts = re.split(r'\s{2,}', line)
    if len(parts) >= 7:
        return {parts[5]: parts[6]}
    
    parts = re.split(r'\s+', line)
    if len(parts) >= 7:
        return {parts[-2]: parts[-1]}
    
    return {}


def _decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value


def extract_cookie_dict(text):
    cookie_dict = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cookie_dict.update(parse_cookie_line(line))

    if not cookie_dict.get(REQUIRED_COOKIE):
        match = re.search(r'NetflixId\s+([^\s]+)', text)
        if match:
            cookie_dict['NetflixId'] = _decode_cookie_value(match.group(1))
        
        if not cookie_dict.get(REQUIRED_COOKIE):
            match = re.search(r'NetflixId[=:]\s*([^;\s]+)', text)
            if match:
                cookie_dict['NetflixId'] = _decode_cookie_value(match.group(1))

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        for cookie in data:
            name = cookie.get("name")
            value = cookie.get("value")
            if name in COOKIE_KEYS and isinstance(value, str):
                cookie_dict[name] = _decode_cookie_value(value)
    elif isinstance(data, dict):
        if any(key in data for key in COOKIE_KEYS):
            for key in COOKIE_KEYS:
                value = data.get(key)
                if isinstance(value, str):
                    cookie_dict[key] = _decode_cookie_value(value)
        elif isinstance(data.get("cookies"), list):
            for cookie in data["cookies"]:
                name = cookie.get("name")
                value = cookie.get("value")
                if name in COOKIE_KEYS and isinstance(value, str):
                    cookie_dict[name] = _decode_cookie_value(value)

    return cookie_dict


def build_cookie_string(cookie_dict):
    cookies = []
    for key, value in cookie_dict.items():
        if key in COOKIE_KEYS and value:
            cookies.append(f"{key}={value}")
    return "; ".join(cookies)


def build_nftoken_link_pc(token):
    return f"https://netflix.com/browse?nftoken={token}"


def build_nftoken_link_phone(token):
    return f"https://netflix.com/unsupported?nftoken={token}"


# ==================== Extraction Functions ====================
def extract_netflix_country(response):
    country = "unknown"
    try:
        match = re.search(r'"currentCountry":"([^"]+)"', response)
        if match:
            country = decode_unicode_escape(match.group(1))
    except:
        pass
    return country


def extract_netflix_email(response):
    email = "unknown"
    patterns = [
        r'"profileEmailAddress":"([^"]+)"',
        r'"emailAddress":"([^"]+)"'
    ]
    for pattern in patterns:
        try:
            match = re.search(pattern, response)
            if match:
                email = decode_unicode_escape(match.group(1))
                if '@' in email and '.' in email:
                    break
        except:
            pass
    return email


def extract_netflix_maxStreams(response):
    maxStreams = "unknown"
    try:
        match = re.search(r'"maxStreams":\{"fieldType":"Numeric","value":(\d+)', response)
        if match:
            maxStreams = match.group(1)
        else:
            match = re.search(r'"maxStreams":(\d+)', response)
            if match:
                maxStreams = match.group(1)
    except:
        pass
    return maxStreams


def extract_netflix_localizedPlanName(response):
    localizedPlanName = "unknown"
    try:
        match = re.search(r'"localizedPlanName":\{"fieldType":"String","value":"([^"]+)"', response)
        if match:
            localizedPlanName = decode_unicode_escape(match.group(1))
        else:
            match = re.search(r'"localizedPlanName":"([^"]+)"', response)
            if match:
                localizedPlanName = decode_unicode_escape(match.group(1))
    except:
        pass
    return localizedPlanName


def extract_netflix_videoQuality(response):
    videoQuality = "unknown"
    try:
        match = re.search(r'"videoQuality":\{"fieldType":"String","value":"([^"]+)"', response)
        if match:
            videoQuality = decode_unicode_escape(match.group(1))
        else:
            match = re.search(r'"videoQuality":"([^"]+)"', response)
            if match:
                videoQuality = decode_unicode_escape(match.group(1))
    except:
        pass
    return videoQuality


def extract_netflix_memberSince(response):
    memberSince = "unknown"
    try:
        match = re.search(r'"memberSince":"([^"]+)"', response)
        if match:
            memberSince = match.group(1)
        else:
            match = re.search(r'"memberSince":\{"fieldType":"Numeric","value":(\d+)}', response)
            if match:
                timestamp = int(match.group(1)) / 1000
                memberSince = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    except:
        pass
    return memberSince


def extract_netflix_nextBillingDate(response):
    nextBillingDate = "unknown"
    try:
        match = re.search(r'"nextBillingDate":\{"fieldType":"String","value":"([^"]+)"', response)
        if match:
            nextBillingDate = decode_unicode_escape(match.group(1))
        else:
            match = re.search(r'"nextBillingDate":"([^"]+)"', response)
            if match:
                nextBillingDate = decode_unicode_escape(match.group(1))
    except:
        pass
    return nextBillingDate


def extract_netflix_canChangePlan(response):
    canChangePlan = "unknown"
    try:
        match = re.search(r'"canChangePlan":\{"fieldType":"Boolean","value":(true|false)', response)
        if match:
            canChangePlan = match.group(1)
        else:
            match = re.search(r'"canChangePlan":(true|false)', response)
            if match:
                canChangePlan = match.group(1)
    except:
        pass
    return canChangePlan


def extract_netflix_isPaused(response):
    isPaused = "unknown"
    try:
        match = re.search(r'"isPaused":\{"fieldType":"Boolean","value":(true|false)', response)
        if match:
            isPaused = match.group(1)
        else:
            match = re.search(r'"isPaused":(true|false)', response)
            if match:
                isPaused = match.group(1)
    except:
        pass
    return isPaused


def extract_netflix_isPendingPause(response):
    isPendingPause = "unknown"
    try:
        match = re.search(r'"isPendingPause":\{"fieldType":"Boolean","value":(true|false)', response)
        if match:
            isPendingPause = match.group(1)
        else:
            match = re.search(r'"isPendingPause":(true|false)', response)
            if match:
                isPendingPause = match.group(1)
    except:
        pass
    return isPendingPause


def extract_netflix_membershipStatus(response):
    membershipStatus = "unknown"
    try:
        match = re.search(r'"membershipStatus":"([^"]+)"', response)
        if match:
            membershipStatus = match.group(1)
    except:
        pass
    return membershipStatus


def extract_netflix_planPrice(response):
    planPrice = "unknown"
    try:
        match = re.search(r'"planPrice":\{"fieldType":"String","value":"([^"]+)"', response)
        if match:
            planPrice = decode_unicode_escape(match.group(1))
        else:
            match = re.search(r'"planPrice":"([^"]+)"', response)
            if match:
                planPrice = decode_unicode_escape(match.group(1))
    except:
        pass
    return planPrice


def extract_netflix_planId(response):
    planId = "unknown"
    try:
        match = re.search(r'"planId":\{"fieldType":"String","value":"([^"]+)"', response)
        if match:
            planId = match.group(1)
        else:
            match = re.search(r'"planId":"([^"]+)"', response)
            if match:
                planId = match.group(1)
    except:
        pass
    return planId


def extract_netflix_name(response):
    name = "unknown"
    try:
        match = re.search(r'"name":"([^"]+)"', response)
        if match:
            name = decode_unicode_escape(match.group(1))
    except:
        pass
    return name


def extract_netflix_guid(response):
    guid = "unknown"
    try:
        match = re.search(r'"guid":"([^"]+)"', response)
        if match:
            guid = match.group(1)
    except:
        pass
    return guid


def identify_plan_type(plan_name):
    if not plan_name or plan_name == "unknown":
        return "Unknown"
    plan_name_lower = plan_name.lower()
    if "premium" in plan_name_lower:
        return "Premium"
    elif "standard" in plan_name_lower or "ستاندرد" in plan_name_lower:
        return "Standard"
    elif "basic" in plan_name_lower or "بيسك" in plan_name_lower:
        return "Basic"
    elif "mobile" in plan_name_lower or "موبايل" in plan_name_lower:
        return "Mobile"
    else:
        return plan_name


def extract_all_netflix_data(response):
    data = {
        "country": extract_netflix_country(response),
        "email": extract_netflix_email(response),
        "maxStreams": extract_netflix_maxStreams(response),
        "localizedPlanName": extract_netflix_localizedPlanName(response),
        "videoQuality": extract_netflix_videoQuality(response),
        "memberSince": extract_netflix_memberSince(response),
        "nextBillingDate": extract_netflix_nextBillingDate(response),
        "canChangePlan": extract_netflix_canChangePlan(response),
        "isPaused": extract_netflix_isPaused(response),
        "isPendingPause": extract_netflix_isPendingPause(response),
        "membershipStatus": extract_netflix_membershipStatus(response),
        "planPrice": extract_netflix_planPrice(response),
        "planId": extract_netflix_planId(response),
        "name": extract_netflix_name(response),
        "guid": extract_netflix_guid(response),
        "planType": identify_plan_type(extract_netflix_localizedPlanName(response))
    }
    return data


def fetch_account_info(cookie_dict):
    """Fetch account info from netflix.com/account"""
    url = "https://www.netflix.com/account"
    
    # Build cookie string
    cookies = {}
    for key in COOKIE_KEYS:
        if key in cookie_dict and cookie_dict[key]:
            cookies[key] = cookie_dict[key]
    
    try:
        response = requests.get(
            url,
            headers=ACCOUNT_HEADERS,
            cookies=cookies,
            timeout=30,
            verify=False,
            allow_redirects=True
        )
        response.raise_for_status()
        response_text = response.text
        
        # Extract data using the functions
        data = extract_all_netflix_data(response_text)
        return data
        
    except Exception as e:
        print(f"Error fetching account info: {e}")
        return None


def fetch_nftoken(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        raise ValueError("Missing required cookie: NetflixId")

    headers = dict(BASE_HEADERS)
    cookie_string = build_cookie_string(cookie_dict)
    headers["Cookie"] = cookie_string

    response = requests.get(
        API_URL,
        params=QUERY_PARAMS,
        headers=headers,
        timeout=30,
        verify=False,
    )
    response.raise_for_status()

    data = response.json()
    
    token = None
    expires = None
    
    if isinstance(data, dict):
        value = data.get("value")
        if isinstance(value, dict):
            account = value.get("account")
            if isinstance(account, dict):
                token_obj = account.get("token")
                if isinstance(token_obj, dict):
                    default = token_obj.get("default")
                    if isinstance(default, dict):
                        token = default.get("token")
                        expires = default.get("expires")
        
        if not token:
            token = data.get("token")
            expires = data.get("expires")
        
        if not token:
            account = data.get("account")
            if isinstance(account, dict):
                token = account.get("token")
                expires = account.get("expires")

    if not token:
        raise ValueError("No token found in response. Cookie may be expired.")

    if isinstance(expires, int) and len(str(expires)) == 13:
        expires //= 1000

    return token, expires


def format_expiry(expires):
    if not isinstance(expires, (int, float)):
        return "Unknown"
    try:
        return datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(expires)


# ==================== Telegram Bot Handlers ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Netflix Token Generator Bot*\n\n"
        "Send me your Netflix cookies in Netscape format and I'll generate login links with account details.\n\n"
        "Example:\n"
        "`.netflix.com\\tTRUE\\t/\\tTRUE\\t...\\tNetflixId\\t...`",
        parse_mode="Markdown"
    )


async def handle_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cookie_text = update.message.text.strip()

    await update.message.reply_text("⏳ Processing your cookies...")

    try:
        cookie_dict = extract_cookie_dict(cookie_text)
        
        if not cookie_dict:
            await update.message.reply_text(
                "❌ No valid cookies found!\n"
                "Make sure they contain NetflixId."
            )
            return

        if REQUIRED_COOKIE not in cookie_dict:
            await update.message.reply_text(
                f"❌ NetflixId not found!\n"
                f"Found: {', '.join(cookie_dict.keys()) if cookie_dict else 'nothing'}"
            )
            return

        # Get token from API
        token, expires = fetch_nftoken(cookie_dict)
        
        # Get account info from netflix.com/account
        account_info = fetch_account_info(cookie_dict)
        
        pc_link = build_nftoken_link_pc(token)
        phone_link = build_nftoken_link_phone(token)
        expiry_str = format_expiry(expires)
        
        # Use account info or fallback to Unknown
        if account_info:
            country_code = account_info.get('country', 'unknown')
            flag = FLAG_MAP.get(country_code, '🌍')
            country_full = get_full_country_name(country_code)
            
            status_map = {
                "CURRENT_MEMBER": "✅ Active",
                "FORMER_MEMBER": "⏸️ Cancelled",
                "NEVER_MEMBER": "🆓 Free"
            }
            status = status_map.get(account_info.get('membershipStatus', ''), account_info.get('membershipStatus', 'Unknown'))
            
            email = account_info.get('email', 'Unknown')
            if email == 'unknown' or not email or '@' not in email:
                email = 'Not Available'
            
            message = (
                f"✅ *Token Generated Successfully!*\n\n"
                f"📧 *Email:* `{email}`\n"
                f"🌍 *Country:* {flag} {country_full} ({country_code})\n"
                f"📺 *Plan:* {account_info.get('localizedPlanName', 'Unknown')}\n"
                f"📊 *Plan Type:* {account_info.get('planType', 'Unknown')}\n"
                f"🖥️ *Video Quality:* {account_info.get('videoQuality', 'Unknown')}\n"
                f"📱 *Max Streams:* {account_info.get('maxStreams', 'Unknown')}\n"
                f"💰 *Price:* {account_info.get('planPrice', 'Unknown')}\n"
                f"📅 *Member Since:* {account_info.get('memberSince', 'Unknown')}\n"
                f"📆 *Next Billing:* {account_info.get('nextBillingDate', 'Unknown')}\n"
                f"📌 *Status:* {status}\n"
                f"⏰ *Token Expires:* {expiry_str}\n\n"
                f"🔗 *Login Links:*"
            )
        else:
            # Fallback if account info fetch fails
            message = (
                f"✅ *Token Generated Successfully!*\n\n"
                f"⚠️ *Could not fetch account details.*\n"
                f"⏰ *Token Expires:* {expiry_str}\n\n"
                f"🔗 *Login Links:*"
            )

        # Create buttons
        keyboard = [
            [InlineKeyboardButton("💻 PC / Browser", url=pc_link)],
            [InlineKeyboardButton("📱 Phone / Mobile", url=phone_link)],
            [InlineKeyboardButton("🌐 Open Netflix", url="https://netflix.com")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Request failed: {str(e)}")
    except ValueError as e:
        await update.message.reply_text(f"❌ Failed: {str(e)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Unexpected error: {str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 How to use:\n\n"
        "1. Send the cookies to this bot\n"
        "2. Get login links (PC & Phone) with account details\n\n"
        "⚠️ *Note:* Cookies must be fresh!\n"
        "The token link expires in about 1 hour.\n\n"
        "Use browser extensions like 'EditThisCookie' to export cookies."
    )


def main():
    print("🤖 Netflix Token Bot is starting...")
    print(f"📡 Port: {PORT}")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookies))

    print("✅ Bot is running with polling! 🚀")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
