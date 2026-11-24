"""بوت متجر تليجرام (النسخة 2).
البداية: اختيار الدولة -> زرار Products ( المنتجات ) تحت -> الأقسام -> المنتجات -> السعر بعملة الدولة.
صاحب المتجر (ADMIN_CHAT_ID) بيدير المنتجات من جوه تليجرام بأمر /admin.
الكتالوج بيتحفظ كملف catalog.json مثبّت في شات الأدمن مع البوت.
"""
import asyncio, io, json, os, threading, logging
from urllib.parse import quote
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (InlineKeyboardButton as B, InlineKeyboardMarkup as M, InputMediaDocument,
                      KeyboardButton, ReplyKeyboardMarkup, Update)
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

CATALOG_VERSION = 2
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
           "stale": "القائمة اتحدثت، اضغط /start من جديد."},
    "en": {"choose_country": "اختار دولتك 🌍\nChoose your country",
           "country_ok": "✅ Selected: {flag} {c}",
           "hint": "Tap Products ( المنتجات ) below to see the categories 👇",
           "menu": "Choose a category:", "pick": "Choose:", "pick_product": "Choose a product:",
           "price": "Price", "order": "Order now", "back": "Back", "home": "Home",
           "lang_btn": "اللغة / Language", "unavail": "Not available right now",
           "ordered": "Done ✅ your order for {p} is recorded.\nContinue with us from here, pick what suits you 👇",
           "wa": "WhatsApp", "tg": "Telegram", "start": "Send /start to open the store 🛍",
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
    return (isinstance(c, dict) and c.get("version") == CATALOG_VERSION
            and isinstance(c.get("categories"), list))


async def load_from_telegram(bot):
    """بيجيب آخر نسخة محفوظة (الملف المثبّت في شات الأدمن)."""
    try:
        chat = await bot.get_chat(ADMIN_ID)
        pm = chat.pinned_message
        if pm and pm.document and pm.document.file_name == BACKUP_NAME:
            f = await bot.get_file(pm.document.file_id)
            data = json.loads(bytes(await f.download_as_bytearray()).decode("utf-8"))
            if valid_catalog(data):
                STATE["cat"] = data
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


def price_text(p, country, lang):
    c = COUNTRIES[country]
    v = p.get("prices", {}).get(c["key"])
    if v is None:
        return "-"
    if country == "xx":
        return f"{num(v)} $" if lang == "ar" else f"${num(v)}"
    return f'{num(v)} {c["cur_ar"] if lang == "ar" else c["cur_en"]}'


def title_of(path, lang):
    """عنوان الشاشة: القسم، أو القسم - النوع."""
    idx = path.split(".")
    top = cat()["categories"][int(idx[0])]
    if len(idx) == 1:
        return label(top, lang)
    child = get_node(path)
    return f'{name_of(top, lang)} - {name_of(child, lang)} {child.get("emoji", "")}'.strip()


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
    rows.append([B("🌐 " + T[lang]["lang_btn"], callback_data="lang")])
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


def product_screen(path, ctx):
    lang, country = L(ctx), C(ctx)
    p = get_node(path)
    c = COUNTRIES[country]
    text = (f'📦 {name_of(p, lang)}\n\n💰 {T[lang]["price"]}\n'
            f'{c["flag"]} {price_text(p, country, lang)}')
    rows = [[B("🛒 " + T[lang]["order"], callback_data=f"o:{path}")], nav_row(path, lang)]
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


def products_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton(PRODUCTS_BTN)]], resize_keyboard=True, is_persistent=True)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("await", None)
    ctx.user_data["country"] = None
    await update.message.reply_text(T["ar"]["choose_country"], reply_markup=country_picker())


async def safe_edit(q, text, kb):
    try:
        await q.edit_message_text(text, reply_markup=kb)
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def customer_button(q, ctx, data):
    lang = L(ctx)
    if data.startswith("c:"):
        k = data[2:]
        if k not in COUNTRIES:
            return
        ctx.user_data["country"] = k
        c = COUNTRIES[k]
        await safe_edit(q, T[lang]["country_ok"].format(flag=c["flag"], c=c[lang]), None)
        await ctx.bot.send_message(q.message.chat_id, T[lang]["hint"], reply_markup=products_keyboard())
        return
    if not C(ctx):
        await safe_edit(q, T["ar"]["choose_country"], country_picker())
        return
    if data == "home":
        t, kb = main_menu(ctx)
        await safe_edit(q, t, kb)
    elif data == "lang":
        ctx.user_data["lang"] = "en" if lang == "ar" else "ar"
        t, kb = main_menu(ctx)
        await safe_edit(q, t, kb)
    elif data.startswith("n:"):
        t, kb = node_screen(data[2:], ctx)
        await safe_edit(q, t, kb)
    elif data.startswith("p:"):
        t, kb = product_screen(data[2:], ctx)
        await safe_edit(q, t, kb)
    elif data.startswith("o:"):
        path = data[2:]
        p = get_node(path)
        country = C(ctx)
        c = COUNTRIES[country]
        u = q.from_user
        who = u.full_name + (f" (@{u.username})" if u.username else "")
        shown = price_text(p, country, "ar")
        where = title_of(parent_path(path), "ar") if parent_path(path) else ""
        await ctx.bot.send_message(
            ADMIN_ID,
            f'🔔 طلب جديد\n📦 {p["name"]}\n📁 {where}\n💰 {shown}\n'
            f'🌍 الدولة: {c["flag"]} {c["ar"]}\n🗣 اللغة: {"العربية" if lang == "ar" else "English"}\n'
            f'👤 {who}\n🆔 {u.id}\n🔗 tg://user?id={u.id}')
        rows = contact_rows(name_of(p, lang), price_text(p, country, lang), lang)
        rows.append([B("🏠 " + T[lang]["home"], callback_data="home")])
        await safe_edit(q, T[lang]["ordered"].format(p=name_of(p, lang)), M(rows))


# ---------- لوحة الأدمن ----------
def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID


HELP = ("لوحة التحكم 🛠\n\n"
        "/admin ← فتح لوحة الأقسام والمنتجات\n"
        "/add ← إضافة منتج جديد\n"
        "/list ← عرض كل المنتجات بأسعارها\n"
        "/cancel ← إلغاء أي عملية شغالة\n\n"
        "من اللوحة تقدر تضيف منتج أو قسم، وتعدّل الاسم والأسعار (مصر / دولار / سعودية)، وتمسح.")


def prices_line(p):
    pr = p.get("prices", {})
    return f'{num(pr.get("egp", "-"))} جنيه / {num(pr.get("usd", "-"))}$ / {num(pr.get("sar", "-"))} ريال'


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
        kb = M([[B("✏️ الأسعار", callback_data=f"a:ep:{arg}")],
                [B("✏️ الاسم", callback_data=f"a:en:{arg}"), B("✏️ الاسم EN", callback_data=f"a:een:{arg}")],
                [B("🗑 مسح", callback_data=f"a:del:{arg}")],
                [B("⬅️ رجوع", callback_data=f"a:n:{parent_path(arg)}")]])
        await safe_edit(q, f'📦 {p["name"]} ({p.get("en", "-")})\n💰 {prices_line(p)}', kb)
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
    if act == "add_name":
        st.update(act="add_en", name=text)
        await update.message.reply_text("الاسم بالإنجليزي إيه؟ (أو ابعت - لو هتسيبه زي العربي)")
        return True
    if act == "add_en":
        st.update(act="add_price", en="" if text == "-" else text, step=0, prices={})
        await update.message.reply_text(f"السعر {PRICE_STEPS[0][1]} كام؟ (أرقام بس)")
        return True
    if act in ("add_price", "ep"):
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
    if text == " ".join(PRODUCTS_BTN.split()):
        if not C(ctx):
            await update.message.reply_text(T["ar"]["choose_country"], reply_markup=country_picker())
            return
        t, kb = main_menu(ctx)
        await update.message.reply_text(t, reply_markup=kb)
        return
    await update.message.reply_text(T[L(ctx)]["start"], reply_markup=products_keyboard() if C(ctx) else None)


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
    STATE["cat"] = data
    ok = await save_catalog(ctx.bot)
    await update.message.reply_text("الكتالوج اتحدّث من الملف ✅" + ("" if ok else " (لكن النسخة الاحتياطية فشلت)"))


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    await q.answer()
    if data.startswith("a:") and q.from_user.id != ADMIN_ID:
        return
    try:
        if data.startswith("a:"):
            await admin_button(q, ctx, data)
        else:
            await customer_button(q, ctx, data)
    except (IndexError, ValueError, KeyError):
        await q.edit_message_text(T[L(ctx)]["stale"])


async def on_error(update, ctx):
    logging.error("error", exc_info=ctx.error)


async def post_init(app):
    await load_from_telegram(app.bot)


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
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    app.run_polling()


if __name__ == "__main__":
    main()
