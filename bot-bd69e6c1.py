"""بوت متجر تليجرام (النسخة 5).
البداية: اختيار الدولة -> زرار Products ( المنتجات ) تحت -> الأقسام -> المنتجات -> السعر بعملة الدولة.
صاحب المتجر (ADMIN_CHAT_ID) بيدير المنتجات من جوه تليجرام بأمر /admin.
الكتالوج بيتحفظ كملف catalog.json مثبّت في شات الأدمن مع البوت.
"""
import asyncio, difflib, io, json, os, threading, logging, time, random, html, re, calendar, base64, math
from decimal import Decimal, ROUND_CEILING
import hashlib
import urllib.request, urllib.error, urllib.parse
from urllib.parse import quote
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (InlineKeyboardButton as B, InlineKeyboardMarkup as M, InputMediaDocument,
                      KeyboardButton, ReplyKeyboardMarkup, Update)
try:
    from telegram import CopyTextButton  # يحتاج python-telegram-bot 21.7 أو أحدث
except ImportError:  # نسخة أقدم: الزرار بيبعت القيمة في رسالة تتنسخ بلمسة
    CopyTextButton = None
from telegram.error import BadRequest
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters)

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_CHAT_ID"])

# ===== إعدادات التواصل (غيّرها من هنا أو من Environment في Render) =====
CONTACT_TELEGRAM = os.environ.get("CONTACT_TELEGRAM", "monkey_hack0").lstrip("@")
CONTACT_WHATSAPP_1 = os.environ.get("CONTACT_WHATSAPP_1", "201005754119")  # بدون + وبدون مسافات
CONTACT_WHATSAPP_2 = os.environ.get("CONTACT_WHATSAPP_2", "201288104948")
# =====================================================================

# ===== الدفع داخل البوت =====  (الطلبات الجديدة: pay_mode())
# USDT لمحفظتك مباشرة على أكتر من شبكة، والبوت بيتأكد من الشبكة لوحده.
# حط عنوان كل شبكة في Render > Environment: USDT_TRC20_ADDRESS و USDT_BEP20_ADDRESS و USDT_APTOS_ADDRESS.
# أي شبكة من غير عنوان بتختفي. لو مفيش ولا عنوان زرار الدفع مبيظهرش.
TRONGRID_KEY = os.environ.get("TRONGRID_API_KEY", "").strip()  # اختياري (مجاني) لو حصل ضغط على TronGrid
TRON_API = os.environ.get("TRON_API", "https://api.trongrid.io").rstrip("/")
BSC_RPC = os.environ.get("BSC_RPC", "https://bsc-dataseed.binance.org").strip()
ETH_RPC = os.environ.get("ETH_RPC", "https://ethereum-rpc.publicnode.com").strip()
SOLANA_RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com").strip()
TONCENTER = os.environ.get("TONCENTER_API", "https://toncenter.com/api/v3").rstrip("/")
TONCENTER_KEY = os.environ.get("TONCENTER_API_KEY", "").strip()  # اختياري (من غيره 1 طلب في الثانية)
APTOS_INDEXER = os.environ.get("APTOS_INDEXER", "https://api.mainnet.aptoslabs.com/v1/graphql").strip()
APTOS_KEY = os.environ.get("APTOS_API_KEY", "").strip()  # اختياري
WALLET_TTL = 1800  # مهلة الدفع بالثواني (30 دقيقة)
GRACE = 300        # سماح إضافي لتأخر تأكيد الشبكة
# طريقة بديلة جاهزة لو احتجتها بعدين: CryptoBot (Crypto Pay API). بتشتغل بس لو مفيش عنوان محفظة وفيه توكن.
CRYPTO_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN", "").strip()
CRYPTO_API = os.environ.get("CRYPTO_PAY_API", "https://pay.crypt.bot/api").rstrip("/")  # للتجربة: https://testnet-pay.crypt.bot/api
POLL_SECONDS = 20
INVOICE_TTL = 3600  # صلاحية الفاتورة بالثواني
# =====================================================================

# ===== رأس المتجر: بيظهر في /start وفي وصف البوت على تليجرام =====
STORE_HEADER = (
    "🎯𝓶𝓸𝓷𝓴𝓮𝔂 | متجر🎯\n"
    "للهاكات المدفوعه | 𝙁𝙤𝙧 𝙥𝙖𝙞𝙙 𝙝𝙖𝙘𝙠𝙨\n"
    "𝐕𝐈𝐏 | 𝘼𝙣𝙙𝙧𝙤𝙞𝙙 📱 | 𝐈𝐩𝐡𝐨𝐧𝐞 📱 | 𝐩𝐜 🖥 | 𝐕𝐈𝐏\n"
    "𝙍𝙤𝙤𝙩 ؛ 𝙣𝙤 𝙍𝙤𝙤𝙩  |  روت ؛ بدون روت\n"
    "𝙏𝙝𝙚 𝙤𝙣𝙡𝙮 𝙖𝙙𝙢𝙞𝙣 𝙤𝙛 𝙩𝙝𝙚 𝙨𝙩𝙤𝙧𝙚\n"
    "@monkey_hack0"
)
STORE_SHORT = "🎯𝓶𝓸𝓷𝓴𝓮𝔂 | متجر🎯 للهاكات المدفوعه | @monkey_hack0"

# ===== دولة أخرى: أسماء الدول والعملات وأسعار الصرف =====
# سعر الصرف = كام وحدة من العملة مقابل 1 دولار. الأرقام دي تقريبية، عدّلها من /admin > 💱 اسعار الصرف
PROOFS_URL = os.environ.get("PROOFS_URL", "https://t.me/+hJ1qoJXdp9M2NjY0").strip()
PROOFS_BTN = "🖼 الاثباتات"
LANG_BTN = "🌐 اللغة"
CHANNELS_URL = os.environ.get("CHANNELS_URL", "https://whatsapp.com/channel/0029Va9LxTt5Ui2dgI1zdu3Y").strip()
CHANNELS_TEXT = {"ar": "📢 قنوات monkey\n\nاختر القناة", "en": "📢 monkey Channels\n\nChoose a channel"}
# قايمة القنوات: (الاسم بالعربي, الاسم بالانجليزي, اللينك). لإضافة قناة ضيف سطر هنا. بتتوزع زرارين في الصف لوحدها.
CHANNELS = [("قناة الواتساب", "WhatsApp channel", CHANNELS_URL)]
# أزرار الكيبورد اللي تحت (كل زرار في صف لوحده). أي زرار جديد يتحط تحت في صف جديد.
# الترتيب: 🌐 اللغة دايما آخر زرار. أي زرار جديد يتحط فوقها.
KB_LABELS = {"ar": {"products": "Products ( المنتجات )", "proofs": "🖼 الاثباتات", "channels": "📢 قنوات monkey", "terms": "📜 شروط الاستخدام", "pay": "💳 طرق الدفع", "lang": "🌐 اللغة"},
             "en": {"products": "🛒 Products", "proofs": "🖼 Proofs", "channels": "📢 monkey Channels", "terms": "📜 Terms of Use", "pay": "💳 Payment methods", "lang": "🌐 Language"}}
PROOFS_TEXT_EN = ("🖼 Store proofs: photos and videos in our customers' own voice from real sales that were delivered. "
                  "Our work is seen and heard, not just claimed 👌\n\n"
                  "The proofs are in front of you and the decision is yours: whoever trusts it, deal with us, and whoever doubts it, better not to 🤝\n\n"
                  "Tap the button below and see for yourself 🔥")


CARD_PAYMENTS_ENABLED = os.environ.get("CARD_PAYMENTS_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
CARD_TYPES = {"r": {"key": "razer", "ar": "رايزر جولد", "en": "Razer Gold", "icon": "🎁"},
              "i": {"key": "itunes", "ar": "ايتونز", "en": "iTunes", "icon": "🍎"}}
CARD_DEFAULT_PCT = 30

# محافظ P2P (فودافون كاش / برق / إنجاز باي): تحويل يدوي على رقم واسم، مفيش تأكيد تلقائي ولا موافقة أدمن.
# كل وسيلة ظاهرة افتراضيا؛ للقفل: VF_CASH_ENABLED=false (أو BARQ_ENABLED / ENJAZ_ENABLED) في Render.
VF_CASH_ENABLED = os.environ.get("VF_CASH_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
BARQ_ENABLED = os.environ.get("BARQ_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
ENJAZ_ENABLED = os.environ.get("ENJAZ_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
VF_CASH_NUMBER = os.environ.get("VF_CASH_NUMBER", "01005754119").strip()
VF_CASH_NAME = os.environ.get("VF_CASH_NAME", "مهند").strip()
BARQ_NUMBER = os.environ.get("BARQ_NUMBER", "01005754119").strip()
BARQ_NAME = os.environ.get("BARQ_NAME", "مهند").strip()
ENJAZ_NUMBER = os.environ.get("ENJAZ_NUMBER", "01005754119").strip()
ENJAZ_NAME = os.environ.get("ENJAZ_NAME", "مهند").strip()
ENJAZ_VIDEO_URL = os.environ.get("ENJAZ_VIDEO_URL", "https://youtu.be/JAG_RB3soAg").strip()
# خطوات برق بيكتبها هو بنفسه من Render > Environment (سطور عادية أو \n). لحد ما يكتبها: قريباً.
BARQ_STEPS_TEXT = os.environ.get("BARQ_STEPS_TEXT", "قريباً…").strip().replace("\\n", "\n")
BARQ_STEPS_TEXT_EN = os.environ.get("BARQ_STEPS_TEXT_EN", "Coming soon…").strip().replace("\\n", "\n")
TERMS_TEXT = {"ar": ("💡 إرشادات يجب الالتزام بها\n\n"
                     "١- يجب عليك متابعة قناة الملفات الخاصة بالهاك الذي تستخدمه وتثبيتها، لتطّلع على أي تحذير أو تحديث.\n"
                     "٢- الالتزام باللعب بطريقة احترافية وآمنة، وتجنّب التقارير قدر الإمكان.\n"
                     "٣- عدم استخدام أي ملفات خارجية غير تلك المنشورة في قناة الملفات الخاصة بالهاك.\n"
                     "٤- اعلم أن أي هاك يحتاج إلى تحديثات، وقد يستغرق التحديث ساعات أو يومًا أو أكثر؛ ويُعوَّض ذلك بتمديد مدة المفتاح بما يعادل مدة التوقف، فلا تُزعج الموزّع أو المطوّر.\n"
                     "٥- عند حدوث أي تحديث داخلي، أيًا كان الهاك الذي تستخدمه، يجب عليك تسجيل الخروج من حسابك فورًا، ثم إجراء الاختبار والتجربة بحساب ضيف أو حساب غير أساسي لمدة ٥ مباريات."),
              "en": ("💡 Guidelines you must follow\n\n"
                     "1- You must follow and pin the files channel of the hack you use, so you see any warning or update.\n"
                     "2- Play in a professional and safe way, and avoid reports as much as possible.\n"
                     "3- Do not use any external files other than those posted in the hack's files channel.\n"
                     "4- Know that any hack needs updates, and an update can take hours, a day or more. This is compensated by extending the key duration by the downtime, so do not bother the distributor or the developer.\n"
                     "5- When any internal update happens, whichever hack you use, you must log out of your account immediately, then test it with a guest or non-main account for 5 matches.")}


def kb_kind(text):
    t = " ".join((text or "").split())
    for lab in KB_LABELS.values():
        for k, v in lab.items():
            if t == " ".join(v.split()):
                return k
    return None
PROOFS_TEXT = ("🖼 اثباتات المتجر: صور وفيديوهات بصوت عملائنا من عمليات بيع حقيقية اتسلمت. شغلنا بيتشاف وبيتسمع مش بيتقال 👌\n\n"
               "الاثباتات قدامك، والقرار قرارك: اللي واخد الثقة يتعامل، واللي شاكك الأفضل له ميتعاملش 🤝\n\n"
               "دوس على الزرار تحت وشوف بنفسك 🔥")
CURRENCIES = {  # كود: (الاسم بالعربي, سعر مقابل 1 دولار)
    "USD": ("دولار", 1), "EUR": ("يورو", 0.92), "GBP": ("جنيه استرليني", 0.79), "CAD": ("دولار كندي", 1.37),
    "AUD": ("دولار استرالي", 1.52), "NZD": ("دولار نيوزيلندي", 1.65), "AED": ("درهم اماراتي", 3.67),
    "KWD": ("دينار كويتي", 0.31), "QAR": ("ريال قطري", 3.64), "BHD": ("دينار بحريني", 0.376),
    "OMR": ("ريال عماني", 0.385), "JOD": ("دينار اردني", 0.71), "IQD": ("دينار عراقي", 1310),
    "LBP": ("ليرة لبنانية", 89500), "LYD": ("دينار ليبي", 4.8), "TND": ("دينار تونسي", 3.1),
    "DZD": ("دينار جزائري", 135), "MAD": ("درهم مغربي", 10), "SDG": ("جنيه سوداني", 600),
    "YER": ("ريال يمني", 250), "TRY": ("ليرة تركية", 34), "INR": ("روبية هندية", 83),
    "PKR": ("روبية باكستانية", 280), "BDT": ("تاكا بنجلاديشية", 117), "IDR": ("روبية اندونيسية", 15800),
    "MYR": ("رينجت ماليزي", 4.7), "SGD": ("دولار سنغافوري", 1.35), "THB": ("بات تايلندي", 36),
    "PHP": ("بيزو فلبيني", 57), "VND": ("دونج فيتنامي", 25000), "JPY": ("ين ياباني", 150),
    "KRW": ("وون كوري", 1350), "CNY": ("يوان صيني", 7.2), "HKD": ("دولار هونج كونج", 7.8),
    "CHF": ("فرنك سويسري", 0.88), "SEK": ("كرونة سويدية", 10.5), "NOK": ("كرونة نرويجية", 10.7),
    "DKK": ("كرونة دنماركية", 6.9), "PLN": ("زلوتي بولندي", 4), "CZK": ("كرونة تشيكية", 23),
    "HUF": ("فورنت مجري", 360), "RON": ("ليو روماني", 4.6), "RUB": ("روبل روسي", 92),
    "UAH": ("هريفنيا اوكرانية", 41), "BRL": ("ريال برازيلي", 5), "MXN": ("بيزو مكسيكي", 17),
    "ARS": ("بيزو ارجنتيني", 900), "CLP": ("بيزو تشيلي", 940), "COP": ("بيزو كولومبي", 4000),
    "PEN": ("سول بيروفي", 3.75), "ZAR": ("راند جنوب افريقي", 18.5), "NGN": ("نايرا نيجيرية", 1500),
    "KES": ("شلن كيني", 130), "GHS": ("سيدي غاني", 15), "ETB": ("بير اثيوبي", 120),
    "AZN": ("مانات اذربيجاني", 1.7), "KZT": ("تينغي كازاخستاني", 470), "GEL": ("لاري جورجي", 2.7),
    "LKR": ("روبية سريلانكية", 300), "NPR": ("روبية نيبالية", 133),
    "SAR": ("ريال سعودي", 3.75), "EGP": ("جنيه مصري", 48),
}
# رمز الدولة | عربي | English | العملة | أسماء تانية (بفاصلة)
COUNTRY_DATA = """AE|الامارات|United Arab Emirates|AED|الإمارات العربية المتحدة,امارات,UAE,دبي,ابوظبي,Dubai
KW|الكويت|Kuwait|KWD|
QA|قطر|Qatar|QAR|
BH|البحرين|Bahrain|BHD|
OM|عمان|Oman|OMR|سلطنة عمان
JO|الاردن|Jordan|JOD|
IQ|العراق|Iraq|IQD|
LB|لبنان|Lebanon|LBP|
SY|سوريا|Syria|USD|سورية
PS|فلسطين|Palestine|USD|
LY|ليبيا|Libya|LYD|
TN|تونس|Tunisia|TND|
DZ|الجزائر|Algeria|DZD|
MA|المغرب|Morocco|MAD|
SD|السودان|Sudan|SDG|
YE|اليمن|Yemen|YER|
TR|تركيا|Turkey|TRY|Turkiye
CA|كندا|Canada|CAD|
US|امريكا|United States|USD|الولايات المتحدة,الولايات المتحدة الامريكية,USA,America,US
GB|بريطانيا|United Kingdom|GBP|المملكة المتحدة,انجلترا,UK,England,Britain
AU|استراليا|Australia|AUD|
NZ|نيوزيلندا|New Zealand|NZD|
DE|المانيا|Germany|EUR|
FR|فرنسا|France|EUR|
IT|ايطاليا|Italy|EUR|
ES|اسبانيا|Spain|EUR|
PT|البرتغال|Portugal|EUR|
NL|هولندا|Netherlands|EUR|Holland
BE|بلجيكا|Belgium|EUR|
AT|النمسا|Austria|EUR|
IE|ايرلندا|Ireland|EUR|
GR|اليونان|Greece|EUR|
FI|فنلندا|Finland|EUR|
SE|السويد|Sweden|SEK|
NO|النرويج|Norway|NOK|
DK|الدنمارك|Denmark|DKK|
CH|سويسرا|Switzerland|CHF|
PL|بولندا|Poland|PLN|
CZ|التشيك|Czech Republic|CZK|Czechia
HU|المجر|Hungary|HUF|
RO|رومانيا|Romania|RON|
RU|روسيا|Russia|RUB|
UA|اوكرانيا|Ukraine|UAH|
CY|قبرص|Cyprus|EUR|
MT|مالطا|Malta|EUR|
SK|سلوفاكيا|Slovakia|EUR|
SI|سلوفينيا|Slovenia|EUR|
HR|كرواتيا|Croatia|EUR|
LT|ليتوانيا|Lithuania|EUR|
LV|لاتفيا|Latvia|EUR|
EE|استونيا|Estonia|EUR|
LU|لوكسمبورج|Luxembourg|EUR|
IN|الهند|India|INR|
PK|باكستان|Pakistan|PKR|
BD|بنجلاديش|Bangladesh|BDT|
ID|اندونيسيا|Indonesia|IDR|
MY|ماليزيا|Malaysia|MYR|
SG|سنغافورة|Singapore|SGD|
TH|تايلاند|Thailand|THB|
PH|الفلبين|Philippines|PHP|
VN|فيتنام|Vietnam|VND|
JP|اليابان|Japan|JPY|
KR|كوريا الجنوبية|South Korea|KRW|كوريا,Korea
CN|الصين|China|CNY|
HK|هونج كونج|Hong Kong|HKD|
BR|البرازيل|Brazil|BRL|
MX|المكسيك|Mexico|MXN|
AR|الارجنتين|Argentina|ARS|
CL|تشيلي|Chile|CLP|
CO|كولومبيا|Colombia|COP|
PE|بيرو|Peru|PEN|
ZA|جنوب افريقيا|South Africa|ZAR|
NG|نيجيريا|Nigeria|NGN|
KE|كينيا|Kenya|KES|
GH|غانا|Ghana|GHS|
ET|اثيوبيا|Ethiopia|ETB|
AZ|اذربيجان|Azerbaijan|AZN|
KZ|كازاخستان|Kazakhstan|KZT|
GE|جورجيا|Georgia|GEL|
LK|سريلانكا|Sri Lanka|LKR|
NP|نيبال|Nepal|NPR|
"""
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})


def norm_name(s):
    s = (s or "").lower().translate(_ALEF)
    s = "".join(ch for ch in s if ch.isalnum() or ch == " ")  # يشيل التشكيل والرموز
    s = "".join(ch for ch in s if not "\u064b" <= ch <= "\u065f")
    s = s.replace("ال", "", 1) if s.startswith("ال") and len(s) > 4 else s
    return " ".join(s.split())


def _flag(iso):
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in iso)


WORLD = {}   # iso -> dict
_NAME_IDX = {}  # الاسم المنسّق -> iso


def _build_world():
    for line in COUNTRY_DATA.strip().splitlines():
        iso, ar, en, cur, alias = (line.split("|") + [""])[:5]
        WORLD[iso] = {"iso": iso, "ar": ar, "en": en, "cur": cur, "flag": _flag(iso)}
        for nm in [ar, en] + [a for a in alias.split(",") if a]:
            _NAME_IDX.setdefault(norm_name(nm), iso)
    for iso, names in (("EG", ("مصر", "Egypt")), ("SA", ("السعودية", "Saudi Arabia", "Saudi", "KSA", "المملكة العربية السعودية"))):
        WORLD[iso] = {"iso": iso, "ar": names[0], "en": names[1], "cur": "", "flag": _flag(iso)}
        for nm in names:
            _NAME_IDX.setdefault(norm_name(nm), iso)


_build_world()


def find_country(text):
    """بيرجّع (iso, []) لو متأكد، أو (None, [iso...]) لو في اقتراحات، أو (None, []) لو مش لاقي."""
    q = norm_name(text)
    if len(q) < 2:
        return None, []
    if q in _NAME_IDX:
        return _NAME_IDX[q], []
    found = []
    if len(q) >= 3:  # بداية الاسم أو جزء منه
        for nm, iso in _NAME_IDX.items():
            if (nm.startswith(q) or q in nm.split()) and iso not in found:
                found.append(iso)
    for nm in difflib.get_close_matches(q, list(_NAME_IDX), n=5, cutoff=0.72):
        if _NAME_IDX[nm] not in found:
            found.append(_NAME_IDX[nm])
    if len(found) == 1:
        return found[0], []
    return None, found[:3]


def get_rate(code):
    r = (cat().get("rates") or {}).get(code)
    try:
        r = float(r)
    except (TypeError, ValueError):
        r = None
    return r if r and r > 0 else CURRENCIES[code][1]


def convert_usd(usd, code):
    v = float(usd) * get_rate(code) * (1 + float(cat().get("margin") or 0) / 100)
    step = 0.5 if get_rate(code) < 100 else (1 if get_rate(code) < 1000 else 10)
    v = max(step, round(v / step) * step)
    return v


def where_label(ctx, lang="ar", k=None, iso=None):
    """علم واسم الدولة اللي العميل اختارها (للدولة الأخرى: اللي كتبها)."""
    if ctx is not None:
        k = ctx.user_data.get("country")
        iso = ctx.user_data.get("ocn")
    if k == "xx" and iso in WORLD:
        w = WORLD[iso]
        return f'{w["flag"]} {w["ar"] if lang == "ar" else w["en"]}'
    c = COUNTRIES.get(k or "xx", COUNTRIES["xx"])
    return f'{c["flag"]} {c[lang]}'


def other_cur(ctx):
    """عملة 'دولة أخرى' اللي العميل اختارها (USD لو مفيش)."""
    code = ctx.user_data.get("ocur") or "USD"
    return code if code in CURRENCIES else "USD"


# ===========================================================

CATALOG_VERSION = 5
GROUP_NAME = "PUBG Mobile"
GROUP_EMOJI = "🪖"
GROUP_MEMBERS = ["PUBG Android [Non-ROOT]", "PUBG Android [ROOT]", "PUBG [IOS]", "PUBG EMULATOR [PC]"]
PLATFORM_NAMES = ("ايفون", "اندرويد")
# أقسام نصوصها من صاحب المتجر مباشرة (بتتحدّث كاملة عند الترقية للنسخة 5)
FORCE_SECTIONS = ("APP PLUS STORES ( متجر بلص )", "Apple Certifications (شهادات ايفون)")
OLD_DEFAULTS = {
    "delivery": ("بيوصلك بعد تأكيد الطلب على واتساب أو تليجرام",),
    "warranty": ("لو حصلت مشكلة في الاشتراك بنعوضك",),
}
PRODUCTS_BTN = "Products ( المنتجات )"
HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_NAME = "catalog.json"
BACKUP_CAPTION = "💾 نسخة احتياطية من منتجات المتجر. متمسحهاش ومتفكّش التثبيت."
STATE = {"cat": None, "pin_id": None}
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫،", "0123456789..")
PAGE = 8

COUNTRIES = {
    "eg": {"flag": "🇪🇬", "ar": "مصر", "en": "Egypt", "key": "egp", "cur_ar": "جنيه مصري", "cur_en": "EGP"},
    "sa": {"flag": "🇸🇦", "ar": "السعودية", "en": "Saudi Arabia", "key": "sar", "cur_ar": "ريال سعودي", "cur_en": "SAR"},
    "xx": {"flag": "🌍", "ar": "دولة أخرى", "en": "Other country", "key": "usd", "cur_ar": "دولار", "cur_en": "USD"},
}
T = {
    "ar": {"choose_country": "اختار دولتك 🌍\nChoose your country",
           "country_ok": "✅ تم اختيار: {flag} {c}",
           "hint": "دوس على Products ( المنتجات ) تحت عشان تشوف الأقسام 👇",
           "menu": "اختار القسم:", "pick": "اختار:", "pick_product": "اختار المنتج:",
           "price": "السعر", "order": "اطلب الآن", "back": "رجوع", "home": "الرئيسية",
           "lang_btn": "اللغة / Language", "unavail": "غير متوفرة حاليًا",
           "ordered": "تمام ✅ طلبك على {p} اتسجل.\nكمّل الطلب معانا من هنا واختار الطريقة اللي تناسبك 👇",
           "wa": "واتساب", "tg": "تليجرام", "start": "اكتب /start لفتح المتجر 🛍",
           "pick_method": "اختار طريقة الطلب 👇", "pay_btn": "ادفع الآن داخل البوت",
           "invoice": "💰 فاتورة الدفع جاهزة\n📦 {p}\n💵 المبلغ: {usd} دولار (يتحول لأي عملة كريبتو تختارها)\n⏳ الفاتورة صالحة لمدة ساعة\n\nاضغط افتح الفاتورة وادفع بأي عملة (USDT / TON / BTC وغيرها). بعد الدفع اضغط تحقق من الدفع أو استنى لحظات والبوت هيبلغك.",
           "pick_net": "اختار الشبكة اللي هتدفع بيها USDT 👇\n📦 {p}",
           "w_invoice": "💰 الدفع بـ USDT - شبكة {net}\n📦 {p}\n🧾 رقم الطلب: {n}\n\n💵 المبلغ بالظبط:\n<code>{amount}</code> USDT\n\n📍 عنوان المحفظة ({short}):\n<code>{addr}</code>\n\n⚠️ مهم:\n• ابعت USDT على شبكة {net} بس. أي شبكة تانية الفلوس هتضيع.\n• ابعت المبلغ بالظبط بالكسور {amount} (المبلغ هو اللي بيحدد طلبك).\n• قدامك 30 دقيقة من دلوقتي.\n• بعد التحويل البوت بيتأكد لوحده خلال دقيقة أو اتنين وهيبلغك.\n\nاستخدم زراري النسخ تحت 👇",
           "cancel": "إلغاء الطلب", "canceled": "اتلغى الطلب ✅", "copy_amt": "نسخ المبلغ", "copy_addr": "نسخ العنوان",
           "open_inv": "افتح الفاتورة في CryptoBot", "check": "تحقق من الدفع",
           "not_paid": "لسه الدفع موصلش. لو دفعت استنى دقيقة وجرب تاني.",
           "paid": "✅ تم الدفع بنجاح\n🧾 رقم الطلب: {n}\n📦 {p}\nهنتواصل معاك دلوقتي لتسليم الاشتراك 🙌",
           "expired": "⌛ الفاتورة (طلب رقم {n}) انتهت صلاحيتها. اطلب من جديد لو لسه عايز.",
           "pay_err": "حصلت مشكلة في إنشاء الفاتورة. جرب تاني بعد شوية أو كمّل الطلب بواتساب/تليجرام.",
           "stale": "القائمة اتحدثت، اضغط /start من جديد."},
    "en": {"choose_country": "اختار دولتك 🌍\nChoose your country",
           "country_ok": "✅ Selected: {flag} {c}",
           "hint": "Tap Products ( المنتجات ) below to see the categories 👇",
           "menu": "Choose a category:", "pick": "Choose:", "pick_product": "Choose a product:",
           "price": "Price", "order": "Order now", "back": "Back", "home": "Home",
           "lang_btn": "اللغة / Language", "unavail": "Not available right now",
           "ordered": "Done ✅ your order for {p} is recorded.\nContinue with us from here, pick what suits you 👇",
           "wa": "WhatsApp", "tg": "Telegram", "start": "Send /start to open the store 🛍",
           "pick_method": "Choose how to order 👇", "pay_btn": "Pay now inside the bot",
           "invoice": "💰 Payment invoice ready\n📦 {p}\n💵 Amount: {usd} USD (paid in any crypto you choose)\n⏳ The invoice is valid for 1 hour\n\nTap Open invoice and pay with any coin (USDT / TON / BTC and more). After paying tap Check payment, or wait a moment and the bot will notify you.",
           "pick_net": "Choose the network to pay USDT on 👇\n📦 {p}",
           "w_invoice": "💰 Pay with USDT - {net} network\n📦 {p}\n🧾 Order #{n}\n\n💵 Exact amount:\n<code>{amount}</code> USDT\n\n📍 Wallet address ({short}):\n<code>{addr}</code>\n\n⚠️ Important:\n• Send USDT on the {net} network only. Any other network and the funds are lost.\n• Send the exact amount with decimals {amount} (the amount identifies your order).\n• You have 30 minutes from now.\n• After the transfer the bot confirms automatically within a minute or two and will notify you.\n\nUse the copy buttons below 👇",
           "cancel": "Cancel order", "canceled": "Order canceled ✅", "copy_amt": "Copy amount", "copy_addr": "Copy address",
           "open_inv": "Open invoice in CryptoBot", "check": "Check payment",
           "not_paid": "Payment not received yet. If you paid, wait a minute and try again.",
           "paid": "✅ Payment received\n🧾 Order #{n}\n📦 {p}\nWe will contact you now to deliver your subscription 🙌",
           "expired": "⌛ The invoice (order #{n}) expired. Order again if you still want it.",
           "pay_err": "Could not create the invoice. Try again shortly, or continue the order on WhatsApp/Telegram.",
           "stale": "The menu was updated, press /start again."},
}


# ---------- الكتالوج ----------
def seed_catalog():
    with open(os.path.join(HERE, "catalog.json"), encoding="utf-8") as f:
        return json.load(f)


def cat():
    if STATE["cat"] is None:
        STATE["cat"] = seed_catalog()
    return STATE["cat"]


def valid_catalog(c):
    return (isinstance(c, dict) and c.get("version") in (2, 3, 4, CATALOG_VERSION)
            and isinstance(c.get("categories"), list))


def _index(nodes, out, trail=()):
    for n in nodes:
        t = trail if (n["name"] == GROUP_NAME and n.get("children")) else trail + (n["name"],)
        for p in n.get("products", []) or []:
            out[t + (p["name"],)] = p
        _index(n.get("children", []) or [], out, t)
    return out


def migrate(data):
    """نسخة 2 القديمة: بنضيف الوصف والإعدادات العامة من الكتالوج الأصلي من غير ما نمس الأسعار."""
    data.setdefault("orders", {"next": 1001, "items": []})
    if data.get("version") == CATALOG_VERSION:
        return data
    seed = seed_catalog()
    seed_idx = _index(seed["categories"], {})
    for key, p in _index(data["categories"], {}).items():
        sp = seed_idx.get(key)
        if not sp:
            continue
        if key[0] in FORCE_SECTIONS:  # نصوص صاحب المتجر لهذه الأقسام بتحل محل القديم
            p["info"] = json.loads(json.dumps(sp.get("info", {})))
        else:
            info = p.setdefault("info", {})
            for k, v in (sp.get("info") or {}).items():
                info.setdefault(k, json.loads(json.dumps(v)))
        if sp.get("photo") and not p.get("photo"):
            p["photo"] = dict(sp["photo"])
    # الإعدادات العامة: لو لسه النص القديم بنبدله بالجديد، ولو هو عدّله بنسيبه
    defs = data.setdefault("defaults", {})
    for k, old in OLD_DEFAULTS.items():
        cur = defs.get(k)
        if not cur or (cur.get("ar") or "").strip() in old:
            defs[k] = seed["defaults"][k]
    # تجميع أقسام ببجي الأربعة تحت زرار PUBG Mobile
    cats = data["categories"]
    if not any(c["name"] == GROUP_NAME and c.get("children") for c in cats):
        members = [c for c in cats if c["name"] in GROUP_MEMBERS]
        if members:
            pos = next(i for i, c in enumerate(cats) if c["name"] in GROUP_MEMBERS)
            cats[:] = [c for c in cats if c["name"] not in GROUP_MEMBERS]
            cats.insert(pos, {"name": GROUP_NAME, "emoji": GROUP_EMOJI, "children": members})
    data["version"] = CATALOG_VERSION
    return data


async def load_from_telegram(bot):
    """بيجيب آخر نسخة محفوظة (الملف المثبّت في شات الأدمن)."""
    try:
        chat = await bot.get_chat(ADMIN_ID)
        pm = chat.pinned_message
        if pm and pm.document and pm.document.file_name == BACKUP_NAME:
            f = await bot.get_file(pm.document.file_id)
            data = json.loads(bytes(await f.download_as_bytearray()).decode("utf-8"))
            if valid_catalog(data):
                STATE["cat"] = migrate(data)
                STATE["pin_id"] = pm.message_id
                logging.info("catalog loaded from pinned backup")
                return True
            logging.info("pinned backup is an old format, using built-in catalog")
    except Exception:
        logging.exception("could not load pinned backup")
    return False


async def save_catalog(bot):
    raw = json.dumps(cat(), ensure_ascii=False, indent=1).encode("utf-8")

    def doc():
        return io.BytesIO(raw)

    if STATE["pin_id"]:
        try:
            await bot.edit_message_media(
                chat_id=ADMIN_ID, message_id=STATE["pin_id"],
                media=InputMediaDocument(doc(), filename=BACKUP_NAME, caption=BACKUP_CAPTION))
            return True
        except Exception as e:
            if "not modified" in str(e).lower():
                return True
            logging.warning("edit backup failed: %s", e)
    try:
        m = await bot.send_document(ADMIN_ID, doc(), filename=BACKUP_NAME,
                                    caption=BACKUP_CAPTION, disable_notification=True)
        await bot.pin_chat_message(ADMIN_ID, m.message_id, disable_notification=True)
        STATE["pin_id"] = m.message_id
        return True
    except Exception:
        logging.exception("save backup failed")
        return False


def get_node(path):
    node = {"name": "الرئيسية", "children": cat()["categories"]}
    if path == "":
        return node
    for i in path.split("."):
        items = node.get("children") if node.get("children") is not None else node.get("products", [])
        node = items[int(i)]
    return node


def parent_path(path):
    return path.rsplit(".", 1)[0] if "." in path else ""


def num(p):
    return f"{p:g}" if isinstance(p, (int, float)) else str(p)


def name_of(node, lang):
    return node.get("en") or node["name"] if lang == "en" else node["name"]


def label(node, lang):
    e = node.get("emoji", "")
    return f"{e} {name_of(node, lang)}".strip()


def price_text(p, country, lang, cur="USD"):
    c = COUNTRIES[country]
    v = p.get("prices", {}).get(c["key"])
    if v is None:
        return "-"
    if country == "xx":
        if cur != "USD" and cur in CURRENCIES:
            cv = num(convert_usd(v, cur))
            return f"{cv} {CURRENCIES[cur][0]} (~)" if lang == "ar" else f"{cv} {cur} (approx.)"
        return f"{num(v)} $" if lang == "ar" else f"${num(v)}"
    return f'{num(v)} {c["cur_ar"] if lang == "ar" else c["cur_en"]}'


def title_of(path, lang):
    """عنوان الشاشة: القسم، أو القسم - النوع (ايفون/اندرويد)."""
    node = get_node(path)
    if node.get("name") in PLATFORM_NAMES and "." in path:
        parent = get_node(parent_path(path))
        return f'{name_of(parent, lang)} - {name_of(node, lang)} {node.get("emoji", "")}'.strip()
    return label(node, lang)


# ---------- واجهة العميل ----------
def L(ctx):
    return ctx.user_data.get("lang", "ar")


def C(ctx):
    return ctx.user_data.get("country")


def country_picker():
    rows = [[B(f'{v["flag"]} {v["ar"]}', callback_data=f"c:{k}")] for k, v in COUNTRIES.items()]
    return M(rows)


def nav_row(path, lang):
    up = parent_path(path)
    return [B("⬅️ " + T[lang]["back"], callback_data=f"n:{up}" if up else "home"),
            B("🏠 " + T[lang]["home"], callback_data="home")]


def main_menu(ctx):
    lang = L(ctx)
    buttons = [B(label(c, lang), callback_data=f"n:{i}") for i, c in enumerate(cat()["categories"])]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return T[lang]["menu"], M(rows)


def node_screen(path, ctx):
    lang = L(ctx)
    node = get_node(path)
    pre = path + "."
    title = title_of(path, lang)
    kids, prods = node.get("children") or [], node.get("products") or []
    if kids:
        btns = [B(label(c, lang), callback_data=f"n:{pre}{i}") for i, c in enumerate(kids)]
        rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
        text = f'{title}\n{T[lang]["pick"]}'
    elif prods:
        rows = [[B("📦 " + name_of(p, lang), callback_data=f"p:{pre}{i}")] for i, p in enumerate(prods)]
        text = f'{title}\n{T[lang]["pick_product"]}'
    else:
        rows = []
        text = f'{title}\n\n⚠️ {T[lang]["unavail"]}'
    rows.append(nav_row(path, lang))
    return text, M(rows)


FIELD_LABELS = {  # الحقل: (إيموجي, عنوان عربي, عنوان إنجليزي)
    "features": ("✅", "المميزات", "Features"),
    "duration": ("⏱️", "المدة", "Duration"),
    "delivery": ("📩", "التسليم", "Delivery"),
    "warranty": ("🔄", "الضمان", "Warranty"),
}


def features_block(t, lang):
    """المميزات: كل سطر أو كل جزء بين • بيظهر كنقطة. لو أول سطر بينتهي بنقطتين بيبقى هو العنوان."""
    lines = [x.strip() for x in t.split("\n") if x.strip()]
    head = "المميزات:" if lang == "ar" else "Features:"
    if lines and lines[0].rstrip().endswith((":", "：")):
        head = lines.pop(0)
    items = []
    for ln in lines:
        items += [x.strip() for x in ln.split(" • ") if x.strip()]
    return "✅ " + head + "".join("\n• " + i for i in items)


def info_text(p, field, lang):
    """نص الحقل بلغة العميل. لو الإنجليزي فاضي بنرجع للعربي. لو المنتج مفيهوش الحقل بناخد الافتراضي العام."""
    v = (p.get("info") or {}).get(field)
    if not v:
        v = (cat().get("defaults") or {}).get(field)
    if not v:
        return ""
    return (v.get(lang) or v.get("ar") or "").strip()


def product_body(p, lang):
    lines = []
    d = info_text(p, "desc", lang)
    if d:
        lines.append(f"🛡️ {d}")
    for f in ("features", "duration", "delivery"):
        t = info_text(p, f, lang)
        if t:
            if f == "features":
                lines.append(features_block(t, lang))
                continue
            e, ar, en = FIELD_LABELS[f]
            lines.append(f"{e} {ar if lang == 'ar' else en}: {t}")
    q = p.get("qty")
    if q is not None and q != "":
        lines.append(f"📦 {'المتاح' if lang == 'ar' else 'Available'}: {num(q)}")
    t = info_text(p, "warranty", lang)
    if t:
        e, ar, en = FIELD_LABELS["warranty"]
        lines.append(f"{e} {ar if lang == 'ar' else en}: {t}")
    t = info_text(p, "notes", lang)
    if t:
        lines.append(t)
    return "\n".join(lines)


def product_screen(path, ctx):
    lang, country = L(ctx), C(ctx)
    p = get_node(path)
    c = COUNTRIES[country]
    body = product_body(p, lang)
    text = (f'📦 {name_of(p, lang)}\n\n' + (body + "\n\n" if body else "") +
            f'💰 {T[lang]["price"]}\n{where_label(ctx, lang).split(" ")[0]} {price_text(p, country, lang, other_cur(ctx))}')
    rows = [[B("🟢 " + T[lang]["order"], callback_data=f"o:{path}")], nav_row(path, lang)]
    return text, M(rows)


def contact_rows(pname, price, lang):
    msg = quote(f"{'أهلا، عايز اطلب' if lang == 'ar' else 'Hi, I want to order'}: {pname} ({price})")
    rows = []
    w = []
    if CONTACT_WHATSAPP_1:
        w.append(B("💬 " + T[lang]["wa"] + " 1", url=f"https://wa.me/{CONTACT_WHATSAPP_1}?text={msg}"))
    if CONTACT_WHATSAPP_2:
        w.append(B("💬 " + T[lang]["wa"] + " 2", url=f"https://wa.me/{CONTACT_WHATSAPP_2}?text={msg}"))
    if w:
        rows.append(w)
    if CONTACT_TELEGRAM:
        rows.append([B("✈️ " + T[lang]["tg"] + f" @{CONTACT_TELEGRAM}", url=f"https://t.me/{CONTACT_TELEGRAM}")])
    return rows


def products_keyboard(lang="ar"):
    lab = KB_LABELS.get(lang, KB_LABELS["ar"])
    return ReplyKeyboardMarkup([[KeyboardButton(lab[k])] for k in ("products", "proofs", "channels", "terms", "pay", "lang")],
                               resize_keyboard=True, is_persistent=True)


ASK_COUNTRY = ("🌍 اكتب اسم دولتك\nمثال: الامارات، كندا، Canada\n\nType your country name")


async def finish_country(msg, ctx, label_txt, extra):
    """بيمسح رسالة الاختيار ويبعت التأكيد مع كيبورد المنتجات والاثباتات."""
    try:
        await msg.delete()
    except Exception:
        pass
    await ctx.bot.send_message(msg.chat_id, T[L(ctx)]["country_ok"].format(flag=label_txt.split(" ")[0], c=" ".join(label_txt.split(" ")[1:])) + extra,
                               reply_markup=products_keyboard(L(ctx)))


async def apply_country(msg, ctx, iso, q=None):
    """iso: كود دولة من القائمة، أو usd للكمل بالدولار."""
    ctx.user_data.pop("await_country", None)
    if iso == "usd" or iso not in WORLD:
        ctx.user_data.update(country="xx", ocur="USD", ocn=None)
        await finish_country(msg, ctx, "🌍 دولة أخرى", "\nالاسعار بالدولار (USD)")
        return
    w = WORLD[iso]
    if iso == "EG":
        ctx.user_data.update(country="eg", ocur=None, ocn=None)
        await finish_country(msg, ctx, f'{w["flag"]} {w["ar"]}', "")
        return
    if iso == "SA":
        ctx.user_data.update(country="sa", ocur=None, ocn=None)
        await finish_country(msg, ctx, f'{w["flag"]} {w["ar"]}', "")
        return
    cur = w["cur"] if w["cur"] in CURRENCIES else "USD"
    ctx.user_data.update(country="xx", ocur=cur, ocn=iso)
    note = f'\nالعملة: {CURRENCIES[cur][0]} ({cur})\nالاسعار تقريبية حسب سعر الصرف' if cur != "USD" else "\nالاسعار بالدولار (USD)"
    await finish_country(msg, ctx, f'{w["flag"]} {w["ar"]}', note)


def pm_screen(lang):
    rows = []
    if PAYMENTS_ENABLED and enabled_nets():
        rows.append([B("💰 " + ("عملات رقمية" if lang == "ar" else "Crypto"), callback_data="cryp")])
    if CARD_PAYMENTS_ENABLED:
        rows += [[b] for b in card_rows_info(lang)]
    rows += p2p_rows("", lang)
    rows.append([B("🏠 " + T[lang]["home"], callback_data="home")])
    rows.append([B("🌐 " + T[lang]["lang_btn"], callback_data="lg:pick")])
    t = ("💳 طرق الدفع\n\nاختر طريقة الدفع لتشوف التفاصيل:\nالدفع بيتم من داخل صفحة المنتج عند الطلب." if lang == "ar"
         else "💳 Payment methods\n\nPick a method to see the details:\nYou pay from the product page when you order.")
    return t, M(rows)


def crypto_screen(lang):
    """شاشة العملات الرقمية: شبكات USDT المتاحة، صف لكل شبكة."""
    rows = [[B("USDT " + NETWORKS[k]["label"].split(" ")[0], callback_data=f"pi:{k}")] for k in enabled_nets()]
    rows.append([B("⬅️ " + T[lang]["back"], callback_data="pm")])
    rows.append([B("🏠 " + T[lang]["home"], callback_data="home")])
    t = ("💰 عملات رقمية\n\nاختر شبكة USDT اللي هتدفع عليها:\nالدفع بيتم من داخل صفحة المنتج عند الطلب." if lang == "ar"
         else "💰 Crypto\n\nChoose the USDT network you'll pay on:\nYou pay from the product page when you order.")
    return t, M(rows)


def card_rows_info(lang):
    return [B(f'{c["icon"]} {c[lang]} ' + ("(امريكي)" if lang == "ar" else "(US)"), callback_data=f"pi:{k}") for k, c in CARD_TYPES.items()]


def pi_screen(k, lang):
    back_cb = "cryp" if k in NETWORKS else "pm"
    back = [B("⬅️ " + T[lang]["back"], callback_data=back_cb), B("🏠 " + T[lang]["home"], callback_data="home")]
    if k in CARD_TYPES:
        c = CARD_TYPES[k]
        pct = card_pct(c["key"])
        if lang == "ar":
            t = (f'{c["icon"]} {c["ar"]} (امريكي فقط)\n\n١- اختر المنتج واضغط طلب\n٢- اختر الدفع بكارت {c["ar"]}\n'
                 f'٣- ابعت كود الكارت\n٤- بعد التأكيد بيوصلك المنتج\n\nلازم يكون كارت امريكي. قيمة الكارت = سعر المنتج + {num(pct)}%، '
                 f'والرقم بيظهر لك بالظبط قبل ما تبعت الكود.')
        else:
            t = (f'{c["icon"]} {c["en"]} (US only)\n\n1- Pick the product and tap order\n2- Choose to pay with {c["en"]} card\n'
                 f'3- Send the card code\n4- You get the product after confirmation\n\nIt must be a US card. Card value = product price + {num(pct)}%, '
                 f'and you see the exact number before sending the code.')
    elif k in NETWORKS:
        lab = NETWORKS[k]["label"]
        if lang == "ar":
            t = (f'💳 USDT - {lab}\n\n١- اختر المنتج واضغط طلب\n٢- اختر ادفع الآن داخل البوت ثم الشبكة دي\n'
                 f'٣- حوّل المبلغ بالظبط (بالكسور) على العنوان اللي هيظهر لك\n٤- البوت بيأكد لوحده وبيوصلك المنتج')
        else:
            t = (f'💳 USDT - {lab}\n\n1- Pick the product and tap order\n2- Choose Pay now inside the bot, then this network\n'
                 f'3- Send the exact amount (with decimals) to the address shown\n4- The bot confirms by itself and you get the product')
    else:
        return pm_screen(lang)
    return t, M([back])


# ---------- محافظ P2P (فودافون كاش / برق / إنجاز باي) ----------
P2P_METHODS = {"vf": {"ar": "📲 فودافون كاش", "en": "📲 Vodafone Cash", "number": VF_CASH_NUMBER, "name": VF_CASH_NAME},
               "barq": {"ar": "💳 برق (للسعوديين)", "en": "💳 Barq (for Saudis)", "number": BARQ_NUMBER, "name": BARQ_NAME},
               "enjaz": {"ar": "🏦 إنجاز باي (للسعوديين)", "en": "🏦 Enjaz Pay (for Saudis)", "number": ENJAZ_NUMBER, "name": ENJAZ_NAME}}


def p2p_on(k):
    return {"vf": VF_CASH_ENABLED, "barq": BARQ_ENABLED, "enjaz": ENJAZ_ENABLED}.get(k, False)


def p2p_rows(path, lang):
    """أزرار محافظ P2P. path فاضي = من قائمة طرق الدفع (من غير منتج)."""
    return [[B(P2P_METHODS[k][lang], callback_data=f"p2:{k}:{path}")] for k in ("vf", "barq", "enjaz") if p2p_on(k)]


def sar_price_of(p):
    try:
        v = float((p.get("prices") or {}).get("sar"))
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def enjaz_egp(p):
    """سعر إنجاز باي بالجنيه: ريال -> دولار -> جنيه بأسعار /admin، تقريب لأعلى لجنيه صحيح."""
    sar = sar_price_of(p)
    if sar is None:
        return None
    return max(1, math.ceil(convert_usd(sar / get_rate("SAR"), "EGP")))


def p2p_price_value(k, p, lang):
    """قيمة السعر كنص قصير (زي '832 جنيه') حسب الطريقة؛ None لو مفيش سعر مناسب (السطر بيختفي)."""
    pr = p.get("prices") or {}
    if k == "vf":
        v = pr.get("egp")
        try:
            ok = float(v) > 0
        except (TypeError, ValueError):
            ok = False
        if not ok:
            return None
        return f"{num(v)} جنيه" if lang == "ar" else f"{num(v)} EGP"
    sar = sar_price_of(p)
    if sar is None:
        return None
    if k == "barq":
        return f"{num(sar)} ريال سعودي" if lang == "ar" else f"{num(sar)} SAR"
    egp = enjaz_egp(p)
    return (f"{num(egp)} جنيه (من {num(sar)} ريال سعودي)" if lang == "ar"
            else f"{num(egp)} EGP (from {num(sar)} SAR)")


def p2p_screen(k, path, lang):
    """شاشة محفظة P2P: الرقم والاسم ونسخهم، زرار «تم التحويل»، وقنوات التواصل."""
    if k not in P2P_METHODS or not p2p_on(k):
        return pm_screen(lang)
    m = P2P_METHODS[k]
    p = get_node(path) if path else None
    lines = [m[lang], ""]
    v = None
    if p is not None:
        lines.append(f"📦 {name_of(p, lang)}")
        v = p2p_price_value(k, p, lang)
        if v:
            lines.append(("💵 السعر: " if lang == "ar" else "💵 Price: ") + v)
        lines.append("")
    if lang == "ar":
        lines += ["حوّل على الرقم ده:", f"الرقم: {m['number']}", f"الاسم: {m['name']}", "",
                  "بعد التحويل ابعت صورة التحويل لمونكي وهيسلّمك طلبك ✅"]
    else:
        lines += ["Transfer to this number:", f"Number: {m['number']}", f"Name: {m['name']}", "",
                  "After transferring, send monkey the receipt photo on WhatsApp or Telegram and he'll deliver your order ✅"]
    pname = name_of(p, lang) if p is not None else m[lang]
    rows = [[B("📋 " + ("نسخ الرقم" if lang == "ar" else "Copy number"), callback_data=f"p2c:n:{k}"),
             B("📋 " + ("نسخ الاسم" if lang == "ar" else "Copy name"), callback_data=f"p2c:m:{k}")]]
    if k in ("enjaz", "barq"):
        steps_lab = ("خطوات التحويل من إنجاز باي" if k == "enjaz" else "خطوات التحويل من برق") if lang == "ar" \
            else ("Enjaz transfer steps" if k == "enjaz" else "Barq transfer steps")
        rows.append([B("📖 " + steps_lab, callback_data=f"p2s:{k}:{path}")])
    rows.append([B("✅ " + ("تم التحويل" if lang == "ar" else "Transfer sent"), callback_data=f"p2d:{k}:{path}")])
    rows += contact_rows(pname, v or "", lang)
    rows.append([B("⬅️ " + T[lang]["back"], callback_data=(f"p:{path}" if path else "pm")),
                 B("🏠 " + T[lang]["home"], callback_data="home")])
    return "\n".join(lines), M(rows)


def p2p_done_screen(k, path, lang):
    """بعد «تم التحويل»: تواصل مع مونكي بقنوات التواصل (مفيش رفع إيصال ولا موافقة أدمن)."""
    if k not in P2P_METHODS or not p2p_on(k):
        return pm_screen(lang)
    p = get_node(path) if path else None
    t = ("✅ تواصل مع مونكي الآن\n\n"
         "ابعت صورة التحويل (الإيصال) لمونكي على واتساب أو تليجرام، وهيراجعها ويسلّمك طلبك على طول 🙌"
         if lang == "ar" else
         "✅ Contact monkey now\n\n"
         "Send the transfer receipt (screenshot) to monkey on WhatsApp or Telegram, and he'll check it and deliver your order right away 🙌")
    pname = name_of(p, lang) if p is not None else P2P_METHODS[k][lang]
    v = p2p_price_value(k, p, lang) if p is not None else None
    rows = contact_rows(pname, v or "", lang)
    rows.append([B("⬅️ " + T[lang]["back"], callback_data=f"p2:{k}:{path}"),
                 B("🏠 " + T[lang]["home"], callback_data="home")])
    return t, M(rows)


def p2p_steps_screen(k, path, lang):
    """شاشة خطوات التحويل. إنجاز باي: خطوات مسار المحفظة + زرار فيديو. برق: نص بيكتبه هو (BARQ_STEPS_TEXT)."""
    back = [B("⬅️ " + T[lang]["back"], callback_data=f"p2:{k}:{path}"), B("🏠 " + T[lang]["home"], callback_data="home")]
    if k == "barq":
        title = "📖 خطوات التحويل من برق" if lang == "ar" else "📖 Barq transfer steps"
        body = BARQ_STEPS_TEXT if lang == "ar" else BARQ_STEPS_TEXT_EN
        return title + "\n\n" + body, M([back])
    if lang == "ar":
        t = ("📖 خطوات التحويل من إنجاز باي\n\n"
             "1. افتح تطبيق إنجاز باي وسجّل دخولك\n"
             "2. من الصفحة الرئيسية اختر «التحويل الدولي»\n"
             "3. اختر الدولة: مصر 🇪🇬\n"
             "4. اضغط «إضافة مستفيد جديد»\n"
             "5. اختر عملة الاستلام: جنيه مصري (EGP) مش دولار\n"
             "6. اختر «تحويل إلى محفظة» وحدد فودافون كاش\n"
             f"7. اكتب رقم المحفظة: {ENJAZ_NUMBER} والاسم: {ENJAZ_NAME}\n"
             "8. راجع الرسوم وسعر صرف الريال مقابل الجنيه قبل التأكيد\n"
             "9. اضغط تأكيد، التحويل لحظي ⚡\n"
             "10. من شاشة «تم التحويل» اضغط مشاركة واحفظ الإيصال وابعته لمونكي ✅")
    else:
        t = ("📖 Enjaz Pay transfer steps\n\n"
             "1. Open the Enjaz Pay app and log in\n"
             "2. From the home screen choose «International Transfer»\n"
             "3. Choose the country: Egypt 🇪🇬\n"
             "4. Tap «Add new beneficiary»\n"
             "5. Choose the receiving currency: Egyptian Pound (EGP), not USD\n"
             "6. Choose «Transfer to wallet» and pick Vodafone Cash\n"
             f"7. Enter the wallet number: {ENJAZ_NUMBER} and the name: {ENJAZ_NAME}\n"
             "8. Review the fees and the SAR to EGP rate before confirming\n"
             "9. Tap confirm, the transfer is instant ⚡\n"
             "10. On the «Transfer complete» screen tap share, save the receipt and send it to monkey ✅")
    rows = [[B("▶️ " + ("شاهد الفيديو" if lang == "ar" else "Watch the video"), url=ENJAZ_VIDEO_URL)],
            back]
    return t, M(rows)


async def set_language(msg, ctx, lang):
    ctx.user_data["lang"] = lang
    try:
        await msg.delete()
    except Exception:
        pass
    await ctx.bot.send_message(msg.chat_id, "✅ تم تغيير اللغة: العربية" if lang == "ar" else "✅ Language: English",
                               reply_markup=products_keyboard(lang))
    if C(ctx):
        t, kb = main_menu(ctx)
        await ctx.bot.send_message(msg.chat_id, t, reply_markup=kb)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("await", None)
    ctx.user_data["country"] = None
    ctx.user_data.pop("await_country", None)
    await update.message.reply_text(STORE_HEADER + "\n\n" + T["ar"]["choose_country"], reply_markup=country_picker())


async def safe_edit(q, text, kb, **kw):
    try:
        await q.edit_message_text(text, reply_markup=kb, **kw)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


# ---------- الصور ----------
async def send_node_photo(bot, chat_id, node):
    """بيبعت صورة القسم/المنتج (file_id محفوظ، أو الملف اللي في الريبو أول مرة)."""
    ph = node.get("photo")
    if not ph:
        return None
    if ph.get("file_id"):
        try:
            return await bot.send_photo(chat_id, ph["file_id"])
        except Exception:
            logging.warning("saved photo id failed, trying file")
    if ph.get("path"):
        try:
            fp = os.path.join(HERE, ph["path"])
            if not os.path.exists(fp):  # لو الصورة في الفولدر الرئيسي بس
                fp = os.path.join(HERE, os.path.basename(ph["path"]))
            with open(fp, "rb") as f:
                m = await bot.send_photo(chat_id, f)
            ph["file_id"] = m.photo[-1].file_id
            await save_catalog(bot)
            return m
        except Exception:
            logging.exception("photo send failed")
    return None


async def drop_photo(ctx):
    pm = ctx.user_data.pop("photo_msg", None)
    if pm:
        try:
            await ctx.bot.delete_message(*pm)
        except Exception:
            pass


async def show(q, ctx, text, kb, node=None):
    """بيعرض الشاشة. لو العنصر ليه صورة بتتبعت فوق التفاصيل."""
    await drop_photo(ctx)
    if node is not None and node.get("photo"):
        m = await send_node_photo(ctx.bot, q.message.chat_id, node)
        if m:
            ctx.user_data["photo_msg"] = (m.chat_id, m.message_id)
            try:
                await q.message.delete()
            except Exception:
                pass
            await ctx.bot.send_message(q.message.chat_id, text, reply_markup=kb)
            return
    await safe_edit(q, text, kb)


# ---------- الدفع داخل البوت (Crypto Pay API) ----------
def crypto_on():
    return bool(CRYPTO_TOKEN)


def _post_json(url, payload, headers=None):
    h = {"Content-Type": "application/json", "User-Agent": "shop-bot"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _rpc(method, params, url=None):
    body = _post_json(url or BSC_RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in body:
        raise RuntimeError(str(body["error"])[:200])
    return body["result"]


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def fetch_trc20(addr, orders_):
    """USDT على TRON عن طريق TronGrid. كل عنصر: tx, raw (أصغر وحدة), ts (ملي ثانية)."""
    min_ts = min(o["ts"] for o in orders_) * 1000 - 120000
    qs = urllib.parse.urlencode({"only_to": "true", "only_confirmed": "true", "limit": 200,
                                 "contract_address": NETWORKS["trc20"]["contract"], "min_timestamp": int(min_ts)})
    headers = {"User-Agent": "shop-bot"}
    if TRONGRID_KEY:
        headers["TRON-PRO-API-KEY"] = TRONGRID_KEY
    req = urllib.request.Request(f"{TRON_API}/v1/accounts/{addr}/transactions/trc20?{qs}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    out = []
    for tx in data.get("data", []):
        if tx.get("to") != addr or (tx.get("token_info") or {}).get("address") != NETWORKS["trc20"]["contract"]:
            continue
        if tx.get("type") not in (None, "Transfer"):
            continue
        out.append({"tx": tx["transaction_id"], "raw": int(tx["value"]), "ts": int(tx["block_timestamp"])})
    return out


def rpc_url(net):
    return {"bep20": BSC_RPC, "erc20": ETH_RPC}[net]


def block_now(net="bep20"):
    return int(_rpc("eth_blockNumber", [], rpc_url(net)), 16)


def fetch_evm(net):
    """USDT على سلاسل EVM (BNB Smart Chain / Ethereum): قراءة أحداث Transfer للمحفظة من RPC عام (من غير مفتاح)."""
    def run(addr, orders_):
        cfg = NETWORKS[net]
        url = rpc_url(net)
        latest = int(_rpc("eth_blockNumber", [], url), 16) - cfg["conf"]
        start = min((o.get("blk") or latest - cfg["span"]) for o in orders_) - 5
        start = max(start, latest - cfg["span"] * 5)
        to_topic = "0x" + "0" * 24 + addr[2:].lower()
        out, b = [], start
        while b <= latest:
            e = min(b + cfg["chunk"] - 1, latest)
            logs = _rpc("eth_getLogs", [{"fromBlock": hex(b), "toBlock": hex(e), "address": cfg["contract"],
                                         "topics": [TRANSFER_TOPIC, None, to_topic]}], url)
            for lg in logs:
                out.append({"tx": lg["transactionHash"], "raw": int(lg["data"], 16), "blk": int(lg["blockNumber"], 16)})
            b = e + 1
        return out
    return run


APTOS_QUERY = """query($addr: String!, $asset: String!) {
  fungible_asset_activities(where: {owner_address: {_eq: $addr}, asset_type: {_eq: $asset},
    type: {_eq: "0x1::fungible_asset::DepositEvent"}, is_transaction_success: {_eq: true}},
    order_by: {transaction_version: desc}, limit: 100) {
    transaction_version event_index amount transaction_timestamp } }"""


def aptos_norm(a):
    return "0x" + a[2:].lower().rjust(64, "0")


def fetch_aptos(addr, orders_):
    """USDt على Aptos عن طريق Aptos indexer (GraphQL)."""
    headers = {"Authorization": f"Bearer {APTOS_KEY}"} if APTOS_KEY else {}
    body = _post_json(APTOS_INDEXER, {"query": APTOS_QUERY, "variables": {
        "addr": aptos_norm(addr), "asset": aptos_norm(NETWORKS["aptos"]["contract"])}}, headers)
    if body.get("errors"):
        raise RuntimeError(str(body["errors"])[:200])
    out = []
    for r in body["data"]["fungible_asset_activities"]:
        ts = calendar.timegm(time.strptime(r["transaction_timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) * 1000
        out.append({"tx": f'{r["transaction_version"]}', "key": f'{r["transaction_version"]}:{r["event_index"]}',
                    "raw": int(r["amount"]), "ts": ts})
    return out


def fetch_ton(addr, orders_):
    """USDT jetton على TON عن طريق TON Center v3."""
    cfg = NETWORKS["ton"]
    qs = urllib.parse.urlencode({"owner_address": addr, "jetton_master": cfg["contract"], "direction": "in",
                                 "limit": 50, "sort": "desc",
                                 "start_utime": int(min(o["ts"] for o in orders_)) - 120})
    headers = {"User-Agent": "shop-bot"}
    if TONCENTER_KEY:
        headers["X-API-Key"] = TONCENTER_KEY
    req = urllib.request.Request(f"{TONCENTER}/jetton/transfers?{qs}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    out = []
    for t in data.get("jetton_transfers", []):
        if t.get("transaction_aborted"):
            continue
        h = t["transaction_hash"]
        try:  # tonviewer بيقبل الهاش hex
            hx = base64.b64decode(h + "=" * (-len(h) % 4)).hex()
        except Exception:
            hx = h
        out.append({"tx": hx, "key": h, "raw": int(t["amount"]), "ts": int(t["transaction_now"]) * 1000})
    return out


SOL_CACHE = {"ata": {}, "tx": {}}


def _sol(method, params):
    return _rpc(method, params, SOLANA_RPC)


def fetch_solana(addr, orders_):
    """USDT على Solana: بنجيب حساب التوكن بتاع المحفظة، وآخر عملياته، وبنحسب اللي دخل من الرصيد قبل/بعد."""
    cfg = NETWORKS["sol"]
    atas = SOL_CACHE["ata"].get(addr)
    if not atas:
        res = _sol("getTokenAccountsByOwner", [addr, {"mint": cfg["contract"]}, {"encoding": "jsonParsed"}])
        atas = [v["pubkey"] for v in res.get("value", [])]
        if atas:
            SOL_CACHE["ata"][addr] = atas
    min_s = min(o["ts"] for o in orders_) - 120
    out = []
    for ata in atas:
        sigs = _sol("getSignaturesForAddress", [ata, {"limit": 30, "commitment": "finalized"}])
        for sg in sigs:
            if sg.get("err") or (sg.get("blockTime") or 0) < min_s:
                continue
            sig = sg["signature"]
            if sig not in SOL_CACHE["tx"]:
                tx = _sol("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0,
                                                  "commitment": "finalized"}])
                meta = (tx or {}).get("meta") or {}
                def bal(key):
                    return sum(int(b["uiTokenAmount"]["amount"]) for b in meta.get(key) or []
                               if b.get("owner") == addr and b.get("mint") == cfg["contract"])
                SOL_CACHE["tx"][sig] = bal("postTokenBalances") - bal("preTokenBalances")
                if len(SOL_CACHE["tx"]) > 500:
                    SOL_CACHE["tx"].pop(next(iter(SOL_CACHE["tx"])))
            delta = SOL_CACHE["tx"][sig]
            if delta > 0:
                out.append({"tx": sig, "raw": delta, "ts": sg["blockTime"] * 1000})
    return out


def _is_hex_addr(a, n=40):
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{%d}" % n, a))


# كل شبكة: عنوانها من متغير بيئة. عشان تضيف شبكة جديدة ضيف هنا سطر + دالة fetch.
NETWORKS = {
    "trc20": {"label": "TRC20 (TRON)", "env": "USDT_TRC20_ADDRESS", "dec": 6, "fetch": fetch_trc20,
              "contract": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
              "valid": lambda a: a.startswith("T") and len(a) == 34 and a.isalnum(),
              "explorer": "https://tronscan.org/#/transaction/{tx}", "short": "TRON"},
    "bep20": {"label": "BEP20 (BNB Smart Chain)", "env": "USDT_BEP20_ADDRESS", "dec": 18,
              "contract": "0x55d398326f99059fF775485246999027B3197955", "conf": 3, "span": 4000, "chunk": 3000,
              "valid": lambda a: _is_hex_addr(a), "explorer": "https://bscscan.com/tx/{tx}", "short": "BSC"},
    "erc20": {"label": "ERC20 (Ethereum)", "env": "USDT_ERC20_ADDRESS", "dec": 6,
              "contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7", "conf": 2, "span": 300, "chunk": 500,
              "valid": lambda a: _is_hex_addr(a), "explorer": "https://etherscan.io/tx/{tx}", "short": "Ethereum"},
    "sol": {"label": "Solana", "env": "USDT_SOL_ADDRESS", "dec": 6, "fetch": fetch_solana,
            "contract": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "valid": lambda a: bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", a)),
            "explorer": "https://solscan.io/tx/{tx}", "short": "Solana"},
    "ton": {"label": "TON", "env": "USDT_TON_ADDRESS", "dec": 6, "fetch": fetch_ton,
            "contract": "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs",
            "valid": lambda a: bool(re.fullmatch(r"[UE]Q[A-Za-z0-9_-]{46}", a)),
            "explorer": "https://tonviewer.com/transaction/{tx}", "short": "TON"},
    "aptos": {"label": "Aptos", "env": "USDT_APTOS_ADDRESS", "dec": 6, "fetch": fetch_aptos,
              "contract": "0x357b0b74bc833e95a115ad22604854d6b0fca151cecd94111770e5d6ffc9dc2b",
              "valid": lambda a: bool(re.fullmatch(r"0x[0-9a-fA-F]{1,64}", a)),
              "explorer": "https://explorer.aptoslabs.com/txn/{tx}?network=mainnet", "short": "Aptos"},
}
for _k in ("bep20", "erc20"):
    NETWORKS[_k]["fetch"] = fetch_evm(_k)


def net_addr(k):
    a = os.environ.get(NETWORKS[k]["env"], "").strip()
    return a if a and NETWORKS[k]["valid"](a) else ""


def enabled_nets():
    return [k for k in NETWORKS if net_addr(k)]


PAYMENTS_ENABLED = os.environ.get("PAYMENTS_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")  # شغال افتراضيا. لقفله: PAYMENTS_ENABLED=false في Render


def pay_mode():
    if not PAYMENTS_ENABLED:
        return ""
    if enabled_nets():
        return "wallet"
    if CRYPTO_TOKEN:
        return "cryptobot"
    return ""


async def crypto(method, params=None, post=False):
    return await asyncio.to_thread(_crypto_call, method, params, post)


def _items(res):
    return res.get("items", []) if isinstance(res, dict) else (res or [])


def orders():
    return cat().setdefault("orders", {"next": 1001, "items": []})


def find_order(n):
    for o in orders()["items"]:
        if o["id"] == n:
            return o


def trim_orders():
    it = orders()["items"]
    done = [o for o in it if o["status"] not in ("pending", "card_pending")]
    if len(it) > 300:
        for o in done[: len(it) - 300]:
            it.remove(o)


def unique_amount(usd, net):
    """مبلغ فريد لكل طلب معلّق في نفس الشبكة: السعر + سنتات (مثال 20.05) عشان نربط التحويل بالطلب."""
    base = Decimal(str(usd))
    taken = {o.get("amount") for o in orders()["items"]
             if o["status"] == "pending" and o.get("kind") == "wallet" and o.get("net") == net}
    for k in random.sample(range(1, 100), 99):
        cand = format(base + Decimal(k) / 100, ".2f")
        if cand not in taken:
            return cand
    raise RuntimeError("no free amount")


def card_pct(key):
    try:
        v = float((cat().get("card_pct") or {}).get(key))
        return int(v) if v == int(v) else v
    except (TypeError, ValueError):
        return CARD_DEFAULT_PCT


def card_need(usd, key):
    """قيمة الكارت المطلوبة = سعر الدولار + النسبة، مقرّبة لأقرب سنت لفوق."""
    v = Decimal(str(usd)) * (1 + Decimal(str(card_pct(key))) / 100)
    return format(v.quantize(Decimal("0.01"), rounding=ROUND_CEILING), ".2f")


def card_format_ok(key, code):
    if key == "razer":  # كود رايزر جولد: 16 رقم (وبعض الاكواد 14)
        return code.isdigit() and len(code) in (14, 16)
    return code.isalnum() and 11 <= len(code) <= 20  # ايتونز: حروف وارقام


def usd_of(p):
    v = (p.get("prices") or {}).get("usd")
    return v if v not in (None, "", 0) else None


def card_rows(path, lang):
    return [B(f'{c["icon"]} {c[lang]} ' + ("(امريكي)" if lang == "ar" else "(US)"), callback_data=f"cd:{k}:{path}")
            for k, c in CARD_TYPES.items()]


async def create_order_invoice(ctx, q, path, net=None):
    p = get_node(path)
    usd = (p.get("prices") or {}).get("usd")
    mode = pay_mode()
    if not mode or usd in (None, "", 0):
        raise RuntimeError("payment unavailable")
    uid = q.from_user.id
    now = time.time()
    ttl = WALLET_TTL if mode == "wallet" else INVOICE_TTL
    if mode == "wallet" and net not in enabled_nets():
        raise RuntimeError("network unavailable")
    for o in orders()["items"]:  # نفس العميل ونفس المنتج ونفس الشبكة وطلب لسه صالح: نستخدمه
        if (o["status"] == "pending" and o["uid"] == uid and o["path"] == path
                and o.get("kind", "cryptobot") == mode and o.get("net") == net and now - o["ts"] < ttl - 120):
            return o
    n = orders()["next"]
    extra = {}
    if mode == "wallet":
        extra = {"kind": "wallet", "net": net, "amount": unique_amount(usd, net), "addr": net_addr(net)}
        if net in ("bep20", "erc20"):
            try:
                extra["blk"] = await asyncio.to_thread(block_now, net) - (10 if net == "bep20" else 3)
            except Exception as e:
                logging.warning("block number failed: %s", e)
    else:
        inv = await crypto("createInvoice", {
            "currency_type": "fiat", "fiat": "USD", "amount": str(num(usd)),
            "description": f'{p["name"]} (#{n})'[:900], "payload": f"order:{n}", "expires_in": INVOICE_TTL})
        extra = {"kind": "cryptobot", "invoice_id": inv["invoice_id"],
                 "url": inv.get("bot_invoice_url") or inv.get("pay_url")}
    orders()["next"] = n + 1
    where = title_of(parent_path(path), "ar") if parent_path(path) else ""
    u = q.from_user
    o = {"id": n, "path": path, "pname": p["name"], "where": where, "usd": usd, "country": C(ctx), "ocn": ctx.user_data.get("ocn"), "ocur": ctx.user_data.get("ocur"), "lang": L(ctx),
         "uid": uid, "chat": q.message.chat_id, "who": u.full_name + (f" (@{u.username})" if u.username else ""),
         "ts": now, "status": "pending", **extra}
    orders()["items"].append(o)
    trim_orders()
    await save_catalog(ctx.bot)
    return o


async def mark_paid(bot, o, inv):
    """بيتنفذ مرة واحدة لكل طلب: يبلّغ العميل والأدمن."""
    if o["status"] == "paid":
        return
    o["status"] = "paid"
    o["paid_at"] = int(time.time())
    o["paid_asset"] = inv.get("paid_asset") or inv.get("asset")
    o["paid_amount"] = inv.get("paid_amount") or inv.get("amount")
    await save_catalog(bot)
    lang = o.get("lang", "ar")
    pname = o["pname"]
    try:
        await bot.send_message(o["chat"], T[lang]["paid"].format(n=o["id"], p=pname))
    except Exception:
        logging.exception("notify customer failed")
    c = COUNTRIES.get(o.get("country") or "xx", COUNTRIES["xx"])
    try:
        await bot.send_message(
            ADMIN_ID,
            f'✅ طلب جديد مدفوع\n🧾 رقم الطلب: {o["id"]}\n📦 {pname}\n📁 {o.get("where", "")}\n'
            f'💵 المبلغ: {num(o["usd"])} دولار\n🪙 المدفوع: {o.get("paid_amount", "-")} {o.get("paid_asset", "")}\n'
            + (f'🌐 الشبكة: {NETWORKS[o["net"]]["label"]}\n' if o.get("net") in NETWORKS else "")
            + (f'🔎 {NETWORKS[o["net"]]["explorer"].format(tx=o["tx"])}\n' if o.get("tx") and o.get("net") in NETWORKS else "") +
            f'🌍 الدولة: {where_label(None, "ar", o.get("country"), o.get("ocn"))}\n👤 {o["who"]}\n🆔 {o["uid"]}\n🔗 tg://user?id={o["uid"]}\n'
            f'🚚 التسليم يدوي.')
    except Exception:
        logging.exception("notify admin failed")


async def mark_expired(bot, o):
    if o["status"] != "pending":
        return
    o["status"] = "expired"
    await save_catalog(bot)
    try:
        msg = T[o.get("lang", "ar")]["expired"].format(n=o["id"])
        if o.get("kind") == "wallet":
            msg += (f"\nلو حوّلت فلوس بالفعل كلمنا على تليجرام @{CONTACT_TELEGRAM} ومعاك رقم الطلب." if o.get("lang", "ar") == "ar"
                    else f"\nIf you already sent funds, message us on Telegram @{CONTACT_TELEGRAM} with the order number.")
        await bot.send_message(o["chat"], msg)
    except Exception:
        pass


async def sweep_wallet(bot, wl):
    seen = orders().setdefault("seen", [])
    by_net = {}
    for o in wl:
        by_net.setdefault(o["net"], []).append(o)
    for net, group in by_net.items():
        addr = net_addr(net)
        if not addr:
            continue
        cfg = NETWORKS[net]
        try:
            txs = await asyncio.to_thread(cfg["fetch"], addr, group)
        except Exception as e:
            logging.warning("%s check failed: %s", net, e)
            continue
        for tx in txs:
            key = f'{net}:{tx.get("key") or tx["tx"]}'
            if key in seen:
                continue
            for o in group:
                if o["status"] != "pending":
                    continue
                if int(Decimal(o["amount"]) * 10 ** cfg["dec"]) != tx["raw"]:
                    continue
                if tx.get("ts") is not None:
                    if not (o["ts"] * 1000 - 30000 <= tx["ts"] <= (o["ts"] + WALLET_TTL + GRACE) * 1000):
                        continue
                elif tx.get("blk") is not None and o.get("blk") and tx["blk"] < o["blk"] - 5:
                    continue
                o["tx"] = tx["tx"]
                seen.append(key)
                del seen[:-400]
                await mark_paid(bot, o, {"paid_asset": f'USDT ({cfg["short"]})', "paid_amount": o["amount"]})
                break
    for o in wl:
        if o["status"] == "pending" and time.time() > o["ts"] + WALLET_TTL + GRACE:
            await mark_expired(bot, o)


async def sweep_orders(bot):
    """بيسأل عن الطلبات المعلقة (الشبكة أو Crypto Pay) ويحدّث حالتها."""
    pend = [o for o in orders()["items"] if o["status"] == "pending"]
    wl = [o for o in pend if o.get("kind") == "wallet"]
    if wl:
        await sweep_wallet(bot, wl)
    pend = [o for o in pend if o.get("kind") != "wallet"]
    if not pend or not crypto_on():
        return
    for i in range(0, len(pend), 50):
        chunk = pend[i:i + 50]
        res = await crypto("getInvoices", {"invoice_ids": ",".join(str(o["invoice_id"]) for o in chunk), "count": 100})
        by_id = {x["invoice_id"]: x for x in _items(res)}
        for o in chunk:
            inv = by_id.get(o["invoice_id"])
            if inv and inv.get("status") == "paid":
                await mark_paid(bot, o, inv)
            elif inv and inv.get("status") == "expired":
                await mark_expired(bot, o)
            elif not inv and time.time() - o["ts"] > INVOICE_TTL + 3600:
                await mark_expired(bot, o)


async def poll_loop(bot):
    await asyncio.sleep(5)
    while True:
        try:
            await sweep_orders(bot)
        except Exception as e:
            logging.warning("poll failed: %s", e)
        await asyncio.sleep(POLL_SECONDS)


async def customer_button(q, ctx, data):
    lang = L(ctx)
    if data.startswith("c:"):
        k = data[2:]
        if k == "back":
            ctx.user_data.pop("await_country", None)
            await safe_edit(q, STORE_HEADER + "\n\n" + T["ar"]["choose_country"], country_picker())
            return
        if k not in COUNTRIES:
            return
        if k == "xx":  # دولة أخرى: العميل يكتب اسم دولته
            ctx.user_data["country"] = None
            ctx.user_data["await_country"] = True
            await safe_edit(q, ASK_COUNTRY, M([[B("⬅️ رجوع | Back", callback_data="c:back")]]))
            return
        ctx.user_data.pop("await_country", None)
        ctx.user_data["country"] = k
        c = COUNTRIES[k]
        await finish_country(q.message, ctx, f'{c["flag"]} {c[lang]}', "")
        return
    if data.startswith("oc:"):
        arg = data[3:]
        if arg == "retry":
            ctx.user_data["await_country"] = True
            await safe_edit(q, ASK_COUNTRY, M([[B("⬅️ رجوع | Back", callback_data="c:back")]]))
            return
        await apply_country(q.message, ctx, arg, q)
        return
    if not C(ctx):
        await safe_edit(q, T["ar"]["choose_country"], country_picker())
        return
    if data == "home":
        t, kb = main_menu(ctx)
        await show(q, ctx, t, kb)
    elif data == "pm":
        t, kb = pm_screen(lang)
        await safe_edit(q, t, kb)
    elif data == "cryp":
        t, kb = crypto_screen(lang)
        await safe_edit(q, t, kb)
    elif data.startswith("pi:"):
        t, kb = pi_screen(data[3:], lang)
        await safe_edit(q, t, kb)
    elif data.startswith("cd:"):
        _, k, path = data.split(":", 2)
        c, p = CARD_TYPES[k], get_node(path)
        usd = usd_of(p)
        if not usd or not CARD_PAYMENTS_ENABLED:
            return
        pct, need = card_pct(c["key"]), card_need(usd, c["key"])
        ctx.user_data["await_card"] = {"k": k, "path": path}
        if lang == "ar":
            t = (f'{c["icon"]} الدفع بكارت {c["ar"]} (امريكي)\n\n📦 {name_of(p, lang)}\n💵 السعر: {num(usd)} $\n'
                 f'➕ رسوم الكارت: {num(pct)}% ({format(Decimal(need) - Decimal(str(usd)), ".2f")} $)\n\n'
                 f'✅ قيمة الكارت المطلوبة: {need} $\n\nاشتري كارت {c["ar"]} امريكي بقيمة {need} $ او اكتر وابعت الكود هنا.\nمفيش باقي بيرجع.')
        else:
            t = (f'{c["icon"]} Pay with {c["en"]} card (US)\n\n📦 {name_of(p, lang)}\n💵 Price: ${num(usd)}\n'
                 f'➕ Card fee: {num(pct)}% (${format(Decimal(need) - Decimal(str(usd)), ".2f")})\n\n'
                 f'✅ Required card value: ${need}\n\nBuy a US {c["en"]} card worth ${need} or more and send the code here.\nNo change is returned.')
        await safe_edit(q, t, M([[B("⬅️ " + T[lang]["back"], callback_data=f"p:{path}"), B("🏠 " + T[lang]["home"], callback_data="home")]]))
    elif data == "lg:pick":
        await safe_edit(q, "🌐 اختار اللغة | Choose language",
                        M([[B("العربية", callback_data="lg:ar"), B("English", callback_data="lg:en")],
                           [B("⬅️ " + T[lang]["back"], callback_data="pm")]]))
    elif data in ("lg:ar", "lg:en"):
        await set_language(q.message, ctx, data[3:])
    elif data.startswith("n:"):
        t, kb = node_screen(data[2:], ctx)
        await show(q, ctx, t, kb, get_node(data[2:]) if data[2:] else None)
    elif data.startswith("p:"):
        t, kb = product_screen(data[2:], ctx)
        await show(q, ctx, t, kb, get_node(data[2:]))
    elif data.startswith("pay:") or data.startswith("pn:"):
        if data.startswith("pn:"):
            _, net, path = data.split(":", 2)
        else:
            path, net = data[4:], None
        p = get_node(path)
        if pay_mode() == "wallet" and net is None:
            nets = enabled_nets()
            if len(nets) > 1:
                rows = [[B("💳 USDT - " + NETWORKS[k]["label"], callback_data=f"pn:{k}:{path}")] for k in nets]
                rows.append([B("⬅️ " + T[lang]["back"], callback_data=f"p:{path}")])
                await safe_edit(q, T[lang]["pick_net"].format(p=name_of(p, lang)), M(rows))
                return
            net = nets[0]
        try:
            o = await create_order_invoice(ctx, q, path, net)
        except Exception as e:
            logging.warning("invoice failed: %s", e)
            await ctx.bot.send_message(q.message.chat_id, T[lang]["pay_err"])
            return
        if o.get("kind") == "wallet":
            text = T[lang]["w_invoice"].format(p=html.escape(name_of(p, lang)), n=o["id"], amount=o["amount"],
                                               addr=html.escape(o["addr"]), net=html.escape(NETWORKS[o["net"]]["label"]),
                                               short=html.escape(NETWORKS[o["net"]]["short"]))
            if CopyTextButton:
                copy_row = [B("📋 " + T[lang]["copy_amt"], copy_text=CopyTextButton(o["amount"])),
                            B("📋 " + T[lang]["copy_addr"], copy_text=CopyTextButton(o["addr"]))]
            else:
                copy_row = [B("📋 " + T[lang]["copy_amt"], callback_data=f'cp:m:{o["id"]}'),
                            B("📋 " + T[lang]["copy_addr"], callback_data=f'cp:a:{o["id"]}')]
            rows = [copy_row,
                    [B("🔄 " + T[lang]["check"], callback_data=f'chk:{o["id"]}')],
                    [B("❌ " + T[lang]["cancel"], callback_data=f'cx:{o["id"]}')],
                    [B("🏠 " + T[lang]["home"], callback_data="home")]]
            await safe_edit(q, text, M(rows), parse_mode="HTML")
        else:
            rows = [[B("💳 " + T[lang]["open_inv"], url=o["url"])],
                    [B("🔄 " + T[lang]["check"], callback_data=f'chk:{o["id"]}')],
                    [B("🏠 " + T[lang]["home"], callback_data="home")]]
            await safe_edit(q, T[lang]["invoice"].format(p=name_of(p, lang), usd=num(o["usd"])), M(rows))
    elif data.startswith("cp:"):
        _, what, oid = data.split(":", 2)
        o = find_order(int(oid))
        if o and o["uid"] == q.from_user.id and o.get("kind") == "wallet":
            val = o["amount"] if what == "m" else o["addr"]
            await ctx.bot.send_message(q.message.chat_id, f"<code>{html.escape(val)}</code>", parse_mode="HTML")
    elif data.startswith("cx:"):
        o = find_order(int(data[3:]))
        if o and o["uid"] == q.from_user.id and o["status"] == "pending":
            o["status"] = "canceled"
            await save_catalog(ctx.bot)
        t, kb = main_menu(ctx)
        await safe_edit(q, T[lang]["canceled"] + "\n\n" + t, kb)
    elif data.startswith("chk:"):
        o = find_order(int(data[4:]))
        if not o or o["uid"] != q.from_user.id:
            await q.answer(T[lang]["stale"], show_alert=True)
            return
        if o["status"] == "pending":
            try:
                await sweep_orders(ctx.bot)
            except Exception as e:
                logging.warning("check failed: %s", e)
        if o["status"] == "paid":
            await q.answer()
            return
        await q.answer(T[lang]["not_paid"], show_alert=True)
    elif data.startswith("p2:"):
        _, k, path = data.split(":", 2)
        t, kb = p2p_screen(k, path, lang)
        await safe_edit(q, t, kb)
    elif data.startswith("p2s:"):
        _, k, path = data.split(":", 2)
        t, kb = p2p_steps_screen(k, path, lang)
        await safe_edit(q, t, kb)
    elif data.startswith("p2d:"):
        _, k, path = data.split(":", 2)
        t, kb = p2p_done_screen(k, path, lang)
        await safe_edit(q, t, kb)
    elif data.startswith("p2c:"):
        _, what, k = data.split(":", 2)
        if k in P2P_METHODS:
            val = P2P_METHODS[k]["number"] if what == "n" else P2P_METHODS[k]["name"]
            await ctx.bot.send_message(q.message.chat_id, f"<code>{html.escape(val)}</code>", parse_mode="HTML")
    elif data.startswith("o:"):
        path = data[2:]
        p = get_node(path)
        country = C(ctx)
        c = COUNTRIES[country]
        u = q.from_user
        who = u.full_name + (f" (@{u.username})" if u.username else "")
        shown = price_text(p, country, "ar", other_cur(ctx))
        where = title_of(parent_path(path), "ar") if parent_path(path) else ""
        await ctx.bot.send_message(
            ADMIN_ID,
            f'🔔 طلب جديد\n📦 {p["name"]}\n📁 {where}\n💰 {shown}\n'
            f'🌍 الدولة: {where_label(ctx)}\n🗣 اللغة: {"العربية" if lang == "ar" else "English"}\n'
            f'👤 {who}\n🆔 {u.id}\n🔗 tg://user?id={u.id}')
        rows = []
        if pay_mode() and (p.get("prices") or {}).get("usd") not in (None, "", 0):
            rows.append([B("💳 " + T[lang]["pay_btn"], callback_data=f"pay:{path}")])
        if CARD_PAYMENTS_ENABLED and usd_of(p):
            rows.append(card_rows(path, lang))
        rows += p2p_rows(path, lang)
        rows += contact_rows(name_of(p, lang), price_text(p, country, lang, other_cur(ctx)), lang)
        rows.append([B("🏠 " + T[lang]["home"], callback_data="home")])
        await safe_edit(q, T[lang]["ordered"].format(p=name_of(p, lang)), M(rows))


# ---------- لوحة الأدمن ----------
def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID


HELP = ("لوحة التحكم 🛠\n\n"
        "/admin ← فتح لوحة الأقسام والمنتجات\n"
        "/add ← إضافة منتج جديد\n"
        "/list ← عرض كل المنتجات بأسعارها\n"
        "/orders ← آخر طلبات الدفع داخل البوت\n"
        "/cancel ← إلغاء أي عملية شغالة\n\n"
        "من اللوحة تقدر تضيف منتج أو قسم، وتعدّل الاسم والأسعار (مصر / دولار / سعودية)، وتمسح.")


def prices_line(p):
    pr = p.get("prices", {})
    return f'{num(pr.get("egp", "-"))} جنيه / {num(pr.get("usd", "-"))}$ / {num(pr.get("sar", "-"))} ريال'


def cf_panel():
    t = ("💳 رسوم الكروت (فوق سعر الدولار)\n\n" +
         "\n".join(f'{c["icon"]} {c["ar"]}: {num(card_pct(c["key"]))}%' for c in CARD_TYPES.values()) +
         "\n\nمثال: منتج 1 $ بنسبة 30% = كارت 1.30 $\nالتقريب: لأقرب سنت لفوق")
    kb = M([[B("✏️ " + c["ar"], callback_data=f"a:cfe:{k}") for k, c in CARD_TYPES.items()], [B("⬅️ رجوع", callback_data="a:n:")]])
    return t, kb


def fx_panel():
    rates = " | ".join(f"{c} {num(get_rate(c))}" for c in CURRENCIES if c != "USD")
    t = (f"💱 اسعار الصرف (كل 1 دولار = كام)\nالزيادة الحالية: {num(cat().get('margin') or 0)}%\n"
         f"التقريب: لأقرب 0.5\n\n{rates}\n\n"
         "الاسعار دي تقريبية، حدّثها بنفسك. مصر والسعودية ليهم اسعارهم الثابتة.")
    kb = M([[B("✏️ تعديل سعر", callback_data="a:fxe:"), B("➕ زيادة %", callback_data="a:fxm:")],
            [B("⬅️ رجوع", callback_data="a:n:")]])
    return t, kb


def admin_panel(path, hint="", page=0):
    node = get_node(path)
    pre = path + "." if path else ""
    title = "📂 الرئيسية" if path == "" else f'📂 {node["name"]}'
    kids, prods = node.get("children") or [], node.get("products") or []
    entries = []
    for i, c in enumerate(kids):
        entries.append(B("📁 " + label(c, "ar"), callback_data=f"a:n:{pre}{i}"))
    for i, p in enumerate(prods):
        entries.append(B(f'📦 {p["name"]} - {num(p["prices"].get("egp", "-"))}', callback_data=f"a:p:{pre}{i}"))
    pages = max(1, (len(entries) + PAGE - 1) // PAGE)
    page = max(0, min(page, pages - 1))
    rows = [[b] for b in entries[page * PAGE:(page + 1) * PAGE]]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(B("◀️", callback_data=f"a:n:{path}|{page - 1}"))
        nav.append(B(f"{page + 1}/{pages}", callback_data=f"a:n:{path}|{page}"))
        if page < pages - 1:
            nav.append(B("▶️", callback_data=f"a:n:{path}|{page + 1}"))
        rows.append(nav)
        title += f" (صفحة {page + 1}/{pages})"
    if path:
        if not kids:
            rows.append([B("➕ منتج جديد هنا", callback_data=f"a:add:{path}")])
        if not prods:
            rows.append([B("📁 قسم فرعي جديد هنا", callback_data=f"a:newcat:{path}")])
        rows.append([B("✏️ اسم القسم", callback_data=f"a:cn:{path}"),
                     B("🗑 مسح القسم", callback_data=f"a:cd:{path}")])
        rows.append([B("⬅️ رجوع", callback_data=f"a:n:{parent_path(path)}"),
                     B("🏠 الرئيسية", callback_data="a:n:")])
    else:
        rows.append([B("📁 قسم جديد", callback_data="a:newcat:")])
        rows.append([B("✏️ التسليم العام", callback_data="a:gd:"), B("✏️ الضمان العام", callback_data="a:gw:")])
        rows.append([B("💱 اسعار الصرف", callback_data="a:fx:"), B("💳 رسوم الكروت", callback_data="a:cf:")])
    return title + (f"\n{hint}" if hint else ""), M(rows)


async def admin_cmd(update, ctx):
    if not is_admin(update):
        return
    ctx.user_data.pop("await", None)
    t, kb = admin_panel("")
    await update.message.reply_text(t, reply_markup=kb)


async def add_cmd(update, ctx):
    if not is_admin(update):
        return
    ctx.user_data.pop("await", None)
    t, kb = admin_panel("", "اختار القسم اللي هتضيف فيه المنتج (لو فيه أنواع زي ايفون/اندرويد ادخل النوع)، وبعدها اضغط ➕ منتج جديد هنا.")
    await update.message.reply_text(t, reply_markup=kb)


async def help_cmd(update, ctx):
    if is_admin(update):
        await update.message.reply_text(HELP)


async def cancel_cmd(update, ctx):
    if is_admin(update):
        ctx.user_data.pop("await", None)
        await update.message.reply_text("اتلغت ✅ اكتب /admin للوحة التحكم.")


def walk(nodes, trail=""):
    for n in nodes:
        name = trail + n["name"]
        for p in n.get("products", []) or []:
            yield name, p
        yield from walk(n.get("children", []) or [], name + " ← ")


async def list_cmd(update, ctx):
    if not is_admin(update):
        return
    lines, last = [], None
    for where, p in walk(cat()["categories"]):
        if where != last:
            lines.append(f"\n📁 {where}")
            last = where
        lines.append(f'  • {p["name"]}: {prices_line(p)}')
    text = "\n".join(lines).strip() or "مفيش منتجات لسه."
    for i in range(0, len(text), 3800):
        await update.message.reply_text(text[i:i + 3800])


FIELD_ACTS = {"fd": "desc", "ff": "features", "fu": "duration", "fl": "delivery", "fw": "warranty", "fn": "notes", "fq": "qty"}
FIELD_NAMES = {"desc": "الوصف", "features": "المميزات", "duration": "المدة", "delivery": "التسليم",
               "warranty": "الضمان", "notes": "الملاحظات (بتظهر تحت الضمان)", "qty": "العدد المتاح"}
PRICE_STEPS = [("egp", "بالجنيه المصري"), ("usd", "بالدولار"), ("sar", "بالريال السعودي")]


def parse_price(text):
    v = float(text.translate(AR_DIGITS))
    return int(v) if v == int(v) else v


async def admin_button(q, ctx, data):
    _, act, arg = (data.split(":", 2) + [""])[:3]
    ctx.user_data.pop("await", None)
    page = 0
    if "|" in arg:
        arg, pg = arg.split("|", 1)
        page = int(pg)

    async def show(path, hint="", pg=0):
        t, kb = admin_panel(path, hint, pg)
        await safe_edit(q, t, kb)

    if act == "n":
        await show(arg, "", page)
    elif act == "p":
        p = get_node(arg)
        kb = M([[B("✏️ الأسعار", callback_data=f"a:ep:{arg}"), B("✏️ المتاح", callback_data=f"a:fq:{arg}")],
                [B("✏️ الاسم", callback_data=f"a:en:{arg}"), B("✏️ الاسم EN", callback_data=f"a:een:{arg}")],
                [B("✏️ الوصف", callback_data=f"a:fd:{arg}"), B("✏️ المميزات", callback_data=f"a:ff:{arg}")],
                [B("✏️ المدة", callback_data=f"a:fu:{arg}"), B("✏️ التسليم", callback_data=f"a:fl:{arg}")],
                [B("✏️ الضمان", callback_data=f"a:fw:{arg}"), B("✏️ ملاحظات", callback_data=f"a:fn:{arg}")],
                [B("🖼 تغيير الصورة", callback_data=f"a:ph:{arg}")] +
                ([B("❌ حذف الصورة", callback_data=f"a:phd:{arg}")] if p.get("photo") else []),
                [B("🗑 مسح", callback_data=f"a:del:{arg}")],
                [B("⬅️ رجوع", callback_data=f"a:n:{parent_path(arg)}")]])
        await safe_edit(q, f'📦 {p["name"]} ({p.get("en", "-")})\n💰 {prices_line(p)}\n🖼 الصورة: {"موجودة" if p.get("photo") else "مفيش"}\n\n'
                           f'معاينة الصفحة (عربي):\n{product_body(p, "ar") or "(مفيش تفاصيل لسه)"}', kb)
    elif act in FIELD_ACTS:
        field = FIELD_ACTS[act]
        if act == "fq":
            ctx.user_data["await"] = {"act": "qty", "path": arg}
            await safe_edit(q, "ابعت العدد المتاح (رقم)، أو ابعت - لو مش عايز يظهر.\n(للإلغاء اكتب /cancel)", None)
        else:
            ctx.user_data["await"] = {"act": "fld", "field": field, "path": arg, "step": "ar"}
            extra = ("\nتقدر تبعت أكتر من سطر. كل سطر هيظهر نقطة. لو أول سطر بينتهي بنقطتين (:) بيبقى عنوان.\n" if field == "features" else "\nتقدر تبعت أكتر من سطر.\n" if field == "notes" else "\n")
            await safe_edit(q, f"ابعت {FIELD_NAMES[field]} بالعربي.{extra}ابعت - لو عايز تمسحه (لو ليه قيمة عامة هيستخدمها).\n(للإلغاء اكتب /cancel)", None)
    elif act == "ph":
        ctx.user_data["await"] = {"act": "photo", "path": arg}
        await safe_edit(q, "ابعت الصورة الجديدة للمنتج (كصورة عادية مش ملف).\n(للإلغاء اكتب /cancel)", None)
    elif act == "phd":
        get_node(arg).pop("photo", None)
        ok = await save_catalog(ctx.bot)
        await safe_edit(q, "الصورة اتمسحت ✅" + ("" if ok else "\n⚠️ حصلت مشكلة في حفظ النسخة الاحتياطية"),
                        M([[B("⬅️ رجوع", callback_data=f"a:p:{arg}")]]))
    elif act in ("gd", "gw"):
        field = "delivery" if act == "gd" else "warranty"
        ctx.user_data["await"] = {"act": "gfld", "field": field, "path": "", "step": "ar"}
        await safe_edit(q, f"ده {FIELD_NAMES[field]} العام لكل المنتجات اللي ملهاش نص خاص.\nابعت النص بالعربي:\n(للإلغاء اكتب /cancel)", None)
    elif act == "cf":
        t, kb = cf_panel()
        await safe_edit(q, t, kb)
    elif act == "cfe":
        ctx.user_data["await"] = {"act": "cfe", "path": arg}
        await safe_edit(q, f"ابعت نسبة رسوم كارت {CARD_TYPES[arg]['ar']} % فوق سعر الدولار (مثال 30):\n(للإلغاء اكتب /cancel)", None)
    elif act == "fx":
        t, kb = fx_panel()
        await safe_edit(q, t, kb)
    elif act == "fxe":
        ctx.user_data["await"] = {"act": "fxe", "path": ""}
        await safe_edit(q, "ابعت كود العملة وسعرها مقابل 1 دولار، زي:\nCAD 1.37\n(أو بعد كده كود تاني، كل واحد في رسالة)\n(للإلغاء اكتب /cancel)", None)
    elif act == "fxm":
        ctx.user_data["await"] = {"act": "fxm", "path": ""}
        await safe_edit(q, "ابعت نسبة الزيادة % على اسعار الدول الاخرى (0 = من غير زيادة):\n(للإلغاء اكتب /cancel)", None)
    elif act == "ep":
        ctx.user_data["await"] = {"act": "ep", "path": arg, "step": 0, "prices": {}}
        await safe_edit(q, f"ابعت السعر {PRICE_STEPS[0][1]} (أرقام بس):\n(للإلغاء اكتب /cancel)", None)
    elif act in ("en", "een"):
        ctx.user_data["await"] = {"act": act, "path": arg}
        await safe_edit(q, ("ابعت الاسم الجديد:" if act == "en" else "ابعت الاسم بالإنجليزي:") + "\n(للإلغاء اكتب /cancel)", None)
    elif act == "add":
        ctx.user_data["await"] = {"act": "add_name", "path": arg}
        await safe_edit(q, "اسم المنتج إيه؟ مثال: اشتراك يومي\n(للإلغاء اكتب /cancel)", None)
    elif act == "newcat":
        ctx.user_data["await"] = {"act": "newcat", "path": arg}
        await safe_edit(q, "اسم القسم الجديد إيه؟ (ممكن تحط إيموجي في الأول)\n(للإلغاء اكتب /cancel)", None)
    elif act == "cn":
        ctx.user_data["await"] = {"act": "cn", "path": arg}
        await safe_edit(q, "ابعت الاسم الجديد للقسم:\n(للإلغاء اكتب /cancel)", None)
    elif act in ("del", "cd"):
        n = get_node(arg)
        what = "المنتج" if act == "del" else "القسم بكل اللي جواه"
        kb = M([[B("✅ أيوه امسح", callback_data=f"a:{act}y:{arg}"),
                 B("❌ لأ", callback_data=f"a:n:{parent_path(arg)}")]])
        await safe_edit(q, f'متأكد إنك عايز تمسح {what}: {n["name"]}؟', kb)
    elif act in ("dely", "cdy"):
        up = parent_path(arg)
        parent = get_node(up)
        idx = int(arg.rsplit(".", 1)[-1])
        key = "products" if act == "dely" else "children"
        parent[key].pop(idx)
        if not parent.get(key) and up != "":
            parent.pop(key, None)
        ok = await save_catalog(ctx.bot)
        await show(up, "اتمسح ✅" + ("" if ok else "\n⚠️ حصلت مشكلة في حفظ النسخة الاحتياطية"))


async def admin_text(update, ctx):
    st = ctx.user_data.get("await")
    if not st:
        return False
    text = (update.message.text or "").strip()
    act, path = st["act"], st["path"]
    if act == "cfe":
        try:
            v = parse_price(text)
            assert 0 <= v <= 300
        except Exception:
            await update.message.reply_text("ابعت رقم بين 0 و 300، زي 30")
            return True
        cat().setdefault("card_pct", {})[CARD_TYPES[path]["key"]] = v
        ctx.user_data.pop("await", None)
        await save_catalog(ctx.bot)
        t, kb = cf_panel()
        await update.message.reply_text("اتعدّل ✅\n\n" + t, reply_markup=kb)
        return True
    if act in ("fxe", "fxm"):
        if act == "fxm":
            try:
                m = parse_price(text)
                assert 0 <= m <= 200
            except Exception:
                await update.message.reply_text("ابعت رقم بين 0 و 200، زي 5")
                return True
            cat()["margin"] = m
            ctx.user_data.pop("await", None)
            await save_catalog(ctx.bot)
            t, kb = fx_panel()
            await update.message.reply_text("اتعدّل ✅\n\n" + t, reply_markup=kb)
            return True
        parts = text.replace("=", " ").split()
        code = parts[0].upper() if parts else ""
        try:
            r = parse_price(parts[1])
            assert code in CURRENCIES and r > 0
        except Exception:
            await update.message.reply_text("الصيغة: كود العملة وبعده السعر، زي CAD 1.37\nالاكواد: " + " ".join(c for c in CURRENCIES if c != "USD"))
            return True
        cat().setdefault("rates", {})[code] = r
        await save_catalog(ctx.bot)
        await update.message.reply_text(f"{code} = {num(r)} ✅ (ابعت عملة تانية أو /cancel)")
        return True
    if act in ("fld", "gfld"):
        if st["step"] == "ar":
            st.update(step="en", ar="" if text == "-" else text)
            await update.message.reply_text("ابعته بالإنجليزي كمان (أو ابعت - عشان الإنجليزي يظهر زي العربي):")
            return True
        val = {"ar": st["ar"], "en": "" if text == "-" else text}
        if act == "gfld":
            cat().setdefault("defaults", {})[st["field"]] = val
            done, back = f'{FIELD_NAMES[st["field"]]} العام اتعدّل ✅', ""
        else:
            node = get_node(path)
            info = node.setdefault("info", {})
            if not val["ar"] and not val["en"]:
                info.pop(st["field"], None)
            else:
                info[st["field"]] = val
            done, back = f'{FIELD_NAMES[st["field"]]} اتعدّل ✅', parent_path(path)
    elif act == "qty":
        node = get_node(path)
        if text == "-":
            node.pop("qty", None)
        else:
            try:
                node["qty"] = parse_price(text)
            except ValueError:
                await update.message.reply_text("ابعت رقم بس، زي 5 (أو - عشان يتشال)")
                return True
        done, back = "العدد المتاح اتعدّل ✅", parent_path(path)
    elif act == "add_name":
        st.update(act="add_en", name=text)
        await update.message.reply_text("الاسم بالإنجليزي إيه؟ (أو ابعت - لو هتسيبه زي العربي)")
        return True
    elif act == "add_en":
        st.update(act="add_price", en="" if text == "-" else text, step=0, prices={})
        await update.message.reply_text(f"السعر {PRICE_STEPS[0][1]} كام؟ (أرقام بس)")
        return True
    elif act in ("add_price", "ep"):
        try:
            price = parse_price(text)
        except ValueError:
            await update.message.reply_text("ابعت السعر أرقام بس، زي 280")
            return True
        st["prices"][PRICE_STEPS[st["step"]][0]] = price
        st["step"] += 1
        if st["step"] < len(PRICE_STEPS):
            await update.message.reply_text(f"السعر {PRICE_STEPS[st['step']][1]} كام؟ (أرقام بس)")
            return True
        if act == "add_price":
            prod = {"name": st["name"], "prices": st["prices"]}
            if st["en"]:
                prod["en"] = st["en"]
            get_node(path).setdefault("products", []).append(prod)
            done, back = f'المنتج {st["name"]} اتضاف ✅', path
        else:
            get_node(path)["prices"] = st["prices"]
            done, back = "الأسعار اتعدّلت ✅", parent_path(path)
    elif act == "en":
        get_node(path)["name"] = text
        done, back = "الاسم اتعدّل ✅", parent_path(path)
    elif act == "een":
        get_node(path)["en"] = text
        done, back = "الاسم بالإنجليزي اتعدّل ✅", parent_path(path)
    elif act == "cn":
        get_node(path)["name"] = text
        done, back = "اسم القسم اتعدّل ✅", parent_path(path)
    elif act == "newcat":
        if path == "":
            cat()["categories"].append({"name": text})
            back = ""
        else:
            get_node(path).setdefault("children", []).append({"name": text})
            back = path
        done = f"القسم {text} اتضاف ✅ (من غير منتجات هيظهر للعميل غير متوفر)"
    else:
        return False
    ctx.user_data.pop("await", None)
    ok = await save_catalog(ctx.bot)
    t, kb = admin_panel(back, done + ("" if ok else "\n⚠️ حصلت مشكلة في حفظ النسخة الاحتياطية"))
    await update.message.reply_text(t, reply_markup=kb)
    return True


async def handle_card_code(update, ctx):
    st = ctx.user_data["await_card"]
    c, path = CARD_TYPES[st["k"]], st["path"]
    lang = L(ctx)
    p = get_node(path)
    usd = usd_of(p)
    code = re.sub(r"[\s\-]", "", update.message.text or "").upper()
    tries = [t for t in ctx.user_data.get("card_tries", []) if time.time() - t < 3600]
    if not card_format_ok(c["key"], code):
        tries.append(time.time())
        ctx.user_data["card_tries"] = tries
        if len(tries) >= 3:
            ctx.user_data.pop("await_card", None)
            await update.message.reply_text((f"الكود مش مظبوط. كلمنا على تليجرام @{CONTACT_TELEGRAM} وهنساعدك." if lang == "ar"
                                             else f"The code looks wrong. Message us on Telegram @{CONTACT_TELEGRAM} and we will help."))
        else:
            hint = ("16 رقم" if c["key"] == "razer" else "حروف وارقام")
            await update.message.reply_text((f"الكود مش مظبوط ({hint}). ابعته تاني زي ما هو مكتوب على الكارت." if lang == "ar"
                                             else "That code format looks wrong. Send it again exactly as printed on the card."))
        return
    h = hashlib.sha256(code.encode()).hexdigest()[:16]
    if any(o.get("chash") == h for o in orders()["items"]):
        await update.message.reply_text("الكود ده اتبعت قبل كده." if lang == "ar" else "This code was already submitted.")
        return
    ctx.user_data.pop("await_card", None)
    n = orders()["next"]
    orders()["next"] = n + 1
    need, pct = card_need(usd, c["key"]), card_pct(c["key"])
    u = update.effective_user
    o = {"id": n, "kind": "card", "ctype": c["key"], "path": path, "pname": p["name"],
         "where": title_of(parent_path(path), "ar") if parent_path(path) else "", "usd": usd, "need": need, "pct": pct,
         "last4": code[-4:], "chash": h, "country": C(ctx), "ocn": ctx.user_data.get("ocn"), "lang": lang,
         "uid": u.id, "chat": update.message.chat_id, "who": u.full_name + (f" (@{u.username})" if u.username else ""),
         "ts": time.time(), "status": "card_pending"}
    orders()["items"].append(o)
    trim_orders()
    await save_catalog(ctx.bot)
    try:
        await update.message.delete()  # نمسح رسالة العميل اللي فيها الكود
    except Exception:
        pass
    await ctx.bot.send_message(update.message.chat_id,
        (f"اتسجل الكارت (رقم الطلب {n}) ✅\nبيتراجع وهيجيلك تأكيد هنا." if lang == "ar"
         else f"Card received (order #{n}) ✅\nWe are checking it and you will get a confirmation here."),
        reply_markup=M([[B("🏠 " + T[lang]["home"], callback_data="home")]]))
    await ctx.bot.send_message(
        ADMIN_ID,
        f'🎁 كارت جديد #{n}\nالنوع: {c["icon"]} {c["ar"]} (امريكي)\nالكود: <code>{html.escape(code)}</code>\n'
        f'📦 {p["name"]}\n💵 السعر: {num(usd)} $\n✅ القيمة المطلوبة: {need} $ (+{num(pct)}%)\n'
        f'🌍 الدولة: {where_label(ctx)}\n👤 {o["who"]}\n🆔 {u.id}\n🔗 tg://user?id={u.id}',
        parse_mode="HTML",
        reply_markup=M([[B("اتشحن ✅", callback_data=f"ca:ok:{n}"), B("الكود غلط ❌", callback_data=f"ca:no:{n}")],
                        [B("قيمة اقل ⚠️", callback_data=f"ca:low:{n}")]]))
    asyncio.create_task(card_reminder(ctx.bot, n))


async def card_reminder(bot, n):
    await asyncio.sleep(900)
    o = find_order(n)
    if o and o["status"] == "card_pending":
        try:
            await bot.send_message(ADMIN_ID, f'⏰ كارت #{n} لسه مستني مراجعتك ({o["pname"]}).')
        except Exception:
            pass


async def card_admin(q, ctx, data):
    _, act, n = data.split(":")
    o = find_order(int(n))
    if not o or o.get("kind") != "card":
        return
    if o["status"] != "card_pending":
        await q.answer("اتعالج قبل كده", show_alert=True)
        return
    lang = o.get("lang", "ar")
    if act == "ok":
        o["status"], o["paid_at"] = "paid", int(time.time())
        msg = T[lang]["paid"].format(n=o["id"], p=o["pname"])
        note = "✅ اتأكد، سلّم المنتج للعميل"
    elif act == "no":
        o["status"] = "rejected"
        msg = (f"الكارت مقبولش (الكود غلط او مستخدم). ابعت كود تاني من صفحة المنتج او كلمنا @{CONTACT_TELEGRAM}." if lang == "ar"
               else f"The card was not accepted (wrong or used code). Send another code from the product page or message @{CONTACT_TELEGRAM}.")
        note = "❌ اترفض: الكود غلط"
    else:
        o["status"] = "rejected"
        msg = (f"قيمة الكارت اقل من المطلوب ({o['need']} $). ابعت كارت تاني بالقيمة المطلوبة او كلمنا @{CONTACT_TELEGRAM}." if lang == "ar"
               else f"The card value is below the required ${o['need']}. Send another card or message @{CONTACT_TELEGRAM}.")
        note = "⚠️ اترفض: قيمة اقل"
    await save_catalog(ctx.bot)
    try:
        await ctx.bot.send_message(o["chat"], msg)
    except Exception:
        logging.exception("notify card customer failed")
    try:
        await q.edit_message_text((q.message.text or "") + "\n\n" + note)
    except Exception:
        pass


async def on_text(update, ctx):
    if is_admin(update):
        try:
            if await admin_text(update, ctx):
                return
        except (IndexError, ValueError, KeyError):
            ctx.user_data.pop("await", None)
            await update.message.reply_text("حصل لخبطة في القائمة، اكتب /admin وابدأ من جديد.")
            return
    text = " ".join((update.message.text or "").split())
    kind = kb_kind(text)
    if kind:
        ctx.user_data.pop("await_card", None)
    if kind == "terms":
        lg = L(ctx)
        await update.message.reply_text(TERMS_TEXT[lg], reply_markup=M([[B("🏠 " + T[lg]["home"], callback_data="home")]]))
        return
    if kind == "pay":
        t, kb = pm_screen(L(ctx))
        await update.message.reply_text(t, reply_markup=kb)
        return
    if ctx.user_data.get("await_card") and not kind:
        await handle_card_code(update, ctx)
        return
    if kind == "lang":
        await update.message.reply_text("🌐 اختار اللغة | Choose language",
                                        reply_markup=M([[B("العربية", callback_data="lg:ar"), B("English", callback_data="lg:en")]]))
        return
    if kind == "proofs":
        lg = L(ctx)
        rows = []
        if PROOFS_URL:
            rows.append([B("🔗 فتح الاثباتات" if lg == "ar" else "🔗 Open proofs", url=PROOFS_URL)])
        rows.append([B("🏠 " + T[lg]["home"], callback_data="home")])
        await update.message.reply_text(PROOFS_TEXT if lg == "ar" else PROOFS_TEXT_EN, reply_markup=M(rows))
        return
    if kind == "channels":
        lg = L(ctx)
        btns = [B("🔗 " + (ar if lg == "ar" else en), url=u) for ar, en, u in CHANNELS if u]
        rows = [btns[k:k + 2] for k in range(0, len(btns), 2)]
        rows.append([B("🏠 " + T[lg]["home"], callback_data="home")])
        await update.message.reply_text(CHANNELS_TEXT[lg], reply_markup=M(rows))
        return
    if ctx.user_data.get("await_country") and kind != "products":
        iso, options = find_country(text)
        if iso:
            await apply_country(update.message, ctx, iso)
        elif options:
            rows = [[B(f'{WORLD[i]["flag"]} {WORLD[i]["ar"]}', callback_data=f"oc:{i}")] for i in options]
            rows.append([B("✏️ اكتب تاني | Retry", callback_data="oc:retry")])
            await update.message.reply_text("🤔 تقصد انهي دولة؟", reply_markup=M(rows))
        else:
            await update.message.reply_text(
                "❌ مش لاقي الدولة دي\nجرب تكتبها تاني، او كمل بالدولار",
                reply_markup=M([[B("✏️ اكتب تاني | Retry", callback_data="oc:retry")],
                                [B("💵 كمل بالدولار (USD)", callback_data="oc:usd")]]))
        return
    if kind == "products":
        if not C(ctx):
            await update.message.reply_text(T["ar"]["choose_country"], reply_markup=country_picker())
            return
        t, kb = main_menu(ctx)
        await update.message.reply_text(t, reply_markup=kb)
        return
    await update.message.reply_text(T[L(ctx)]["start"], reply_markup=products_keyboard(L(ctx)) if C(ctx) else None)


async def on_photo(update, ctx):
    """الأدمن بيبعت صورة بعد ما يختار تغيير الصورة لمنتج."""
    if not is_admin(update):
        return
    st = ctx.user_data.get("await")
    if not st or st.get("act") != "photo":
        return
    try:
        node = get_node(st["path"])
    except (IndexError, ValueError, KeyError):
        ctx.user_data.pop("await", None)
        await update.message.reply_text("حصل لخبطة في القائمة، اكتب /admin وابدأ من جديد.")
        return
    node["photo"] = {"file_id": update.message.photo[-1].file_id}
    ctx.user_data.pop("await", None)
    ok = await save_catalog(ctx.bot)
    await update.message.reply_text("الصورة اتغيّرت ✅ هتظهر فوق تفاصيل المنتج." + ("" if ok else "\n⚠️ حصلت مشكلة في حفظ النسخة الاحتياطية"))


STATUS_AR = {"card_pending": "🎁 كارت منتظر", "rejected": "❌ اترفض", "pending": "⏳ منتظر الدفع", "paid": "✅ مدفوع", "expired": "⌛ انتهى", "canceled": "❌ اتلغى"}


async def orders_cmd(update, ctx):
    if not is_admin(update):
        return
    items = list(reversed(orders()["items"]))[:20]
    if not items:
        await update.message.reply_text("مفيش طلبات دفع لسه." + ("" if pay_mode() else "\n(الدفع داخل البوت مش مفعّل: ضيف عنوان محفظة USDT في Render)"))
        return
    def line(o):
        if o.get("kind") == "card":
            return f'#{o["id"]} {STATUS_AR.get(o["status"], o["status"])} - {o["pname"]} - كارت {o["ctype"]} {o["need"]}$ (...{o["last4"]}) - {o["who"]}'
        return f'#{o["id"]} {STATUS_AR.get(o["status"], o["status"])} - {o["pname"]} - {o.get("amount") or num(o["usd"])}${(" " + NETWORKS[o["net"]]["short"]) if o.get("net") in NETWORKS else ""} - {o["who"]}'
    lines = [line(o) for o in items]
    await update.message.reply_text("آخر طلبات الدفع داخل البوت:\n\n" + "\n".join(lines))


async def on_document(update, ctx):
    """الأدمن يبعت ملف catalog.json فيحل محل الكتالوج الحالي."""
    if not is_admin(update) or update.message.document.file_name != BACKUP_NAME:
        return
    if update.message.document.file_size and update.message.document.file_size > 2_000_000:
        return
    f = await ctx.bot.get_file(update.message.document.file_id)
    try:
        data = json.loads(bytes(await f.download_as_bytearray()).decode("utf-8"))
        assert valid_catalog(data)
    except Exception:
        await update.message.reply_text("الملف مش بصيغة صحيحة ❌")
        return
    STATE["cat"] = migrate(data)
    ok = await save_catalog(ctx.bot)
    await update.message.reply_text("الكتالوج اتحدّث من الملف ✅" + ("" if ok else " (لكن النسخة الاحتياطية فشلت)"))


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    if not data.startswith("chk:"):
        await q.answer()
    if data.startswith(("a:", "ca:")) and q.from_user.id != ADMIN_ID:
        return
    try:
        if data.startswith("a:"):
            await admin_button(q, ctx, data)
        elif data.startswith("ca:"):
            await card_admin(q, ctx, data)
        else:
            await customer_button(q, ctx, data)
    except (IndexError, ValueError, KeyError):
        await q.edit_message_text(T[L(ctx)]["stale"])


async def on_error(update, ctx):
    logging.error("error", exc_info=ctx.error)


async def post_init(app):
    for fn, text in ((app.bot.set_my_description, STORE_HEADER), (app.bot.set_my_short_description, STORE_SHORT)):
        try:
            await fn(text)
        except Exception:
            logging.exception("could not set bot description")
    await load_from_telegram(app.bot)
    if pay_mode():
        app.bot_data["poll_task"] = asyncio.create_task(poll_loop(app.bot))
        logging.info("in-bot payments ON (%s, polling every %ss)", pay_mode(), POLL_SECONDS)
    else:
        logging.info("in-bot payments OFF (no CRYPTO_PAY_TOKEN)")


async def reload_cmd(update, ctx):
    if is_admin(update):
        ok = await load_from_telegram(ctx.bot)
        await update.message.reply_text("اتحمّل من النسخة المحفوظة ✅" if ok else "مفيش نسخة محفوظة، لسه شغال بالمنتجات الأصلية.")


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    do_HEAD = do_GET
    def log_message(self, *a): pass


def run_health():
    port = int(os.environ.get("PORT", "0"))
    if port:
        threading.Thread(target=HTTPServer(("0.0.0.0", port), Health).serve_forever, daemon=True).start()


def main():
    run_health()
    asyncio.set_event_loop(asyncio.new_event_loop())  # يشتغل على بايثون 3.14 كمان
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(CommandHandler("orders", orders_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    app.run_polling()


if __name__ == "__main__":
    main()
