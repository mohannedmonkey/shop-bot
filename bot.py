"""بوت متجر تليجرام.
- العملاء بيتصفحوا الأقسام والمنتجات ويضغطوا "اطلب الآن".
- صاحب المتجر (ADMIN_CHAT_ID) بيدير المنتجات من جوه تليجرام بأمر /admin.
- الكتالوج بيتحفظ كملف catalog.json مثبّت في شات الأدمن مع البوت، فمبيضيعش لما السيرفر يعيد التشغيل.
"""
import io, json, os, copy, threading, logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (InlineKeyboardButton as B, InlineKeyboardMarkup as M,
                      InputMediaDocument, Update)
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, ContextTypes, filters)

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_CHAT_ID"])
HERE = os.path.dirname(os.path.abspath(__file__))
BACKUP_NAME = "catalog.json"
BACKUP_CAPTION = "💾 نسخة احتياطية من منتجات المتجر. متمسحهاش ومتفكّش التثبيت."
STATE = {"cat": None, "pin_id": None}
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫،", "0123456789..")


# ---------- الكتالوج ----------
def seed_catalog():
    with open(os.path.join(HERE, "catalog.json"), encoding="utf-8") as f:
        return json.load(f)


def cat():
    if STATE["cat"] is None:
        STATE["cat"] = seed_catalog()
    return STATE["cat"]


def valid_catalog(c):
    return isinstance(c, dict) and isinstance(c.get("categories"), list)


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
    except Exception:
        logging.exception("could not load pinned backup")
    return False


async def save_catalog(bot):
    """بيحفظ الكتالوج الحالي في شات الأدمن (بيعدّل الملف المثبّت أو يعمل واحد جديد)."""
    raw = json.dumps(cat(), ensure_ascii=False, indent=2).encode("utf-8")

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


def fmt_price(p):
    return f"{p:g}" if isinstance(p, (int, float)) else str(p)


def cur():
    return cat().get("currency", "")


# ---------- واجهة العميل ----------
def menu_for(path):
    node = get_node(path)
    pre = path + "." if path else ""
    rows = [[B(c["name"], callback_data=f"n:{pre}{i}")] for i, c in enumerate(node.get("children", []))]
    for i, p in enumerate(node.get("products", [])):
        rows.append([B(f'{p["name"]} - {fmt_price(p["price"])} {cur()}', callback_data=f"p:{pre}{i}")])
    nav = []
    if path:
        up = parent_path(path)
        nav.append(B("⬅️ رجوع", callback_data=f"n:{up}" if up else "home"))
    nav.append(B("🏠 الرئيسية", callback_data="home"))
    rows.append(nav)
    return M(rows)


def welcome():
    return cat().get("welcome", "اختار القسم:")


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("await", None)
    await update.message.reply_text(welcome(), reply_markup=menu_for(""))


async def customer_button(q, ctx, data):
    if data == "home":
        await q.edit_message_text(welcome(), reply_markup=menu_for(""))
    elif data.startswith("n:"):
        path = data[2:]
        await q.edit_message_text(f'{get_node(path)["name"]}\nاختار:', reply_markup=menu_for(path))
    elif data.startswith("p:"):
        path = data[2:]
        p = get_node(path)
        up = parent_path(path)
        text = f'📦 {p["name"]}\n\n💰 السعر: {fmt_price(p["price"])} {cur()}\n\n{p.get("description","")}'
        rows = [[B("🛒 اطلب الآن", callback_data=f"o:{path}")],
                [B("⬅️ رجوع", callback_data=f"n:{up}" if up else "home"),
                 B("🏠 الرئيسية", callback_data="home")]]
        await q.edit_message_text(text, reply_markup=M(rows))
    elif data.startswith("o:"):
        p = get_node(data[2:])
        u = q.from_user
        who = u.full_name + (f" (@{u.username})" if u.username else "")
        await ctx.bot.send_message(
            ADMIN_ID,
            f'🔔 طلب جديد\n📦 {p["name"]}\n💰 {fmt_price(p["price"])} {cur()}\n'
            f'👤 {who}\n🆔 {u.id}\n🔗 tg://user?id={u.id}')
        await q.edit_message_text(
            f'تمام ✅ طلبك على {p["name"]} اتبعت. هنتواصل معاك قريب لإتمام الطلب.',
            reply_markup=M([[B("🏠 الرئيسية", callback_data="home")]]))


# ---------- لوحة الأدمن ----------
def is_admin(update):
    return update.effective_user and update.effective_user.id == ADMIN_ID


HELP = ("لوحة التحكم 🛠\n\n"
        "/admin ← فتح لوحة الأقسام والمنتجات\n"
        "/add ← إضافة منتج جديد\n"
        "/list ← عرض كل المنتجات بأسعارها\n"
        "/cancel ← إلغاء أي عملية شغالة\n\n"
        "من اللوحة تقدر تضيف منتج أو قسم، وتعدّل الاسم والسعر والوصف، وتمسح.")


def admin_panel(path, hint=""):
    node = get_node(path)
    pre = path + "." if path else ""
    title = "📂 الرئيسية" if path == "" else f'📂 {node["name"]}'
    rows = [[B("📁 " + c["name"], callback_data=f"a:n:{pre}{i}")] for i, c in enumerate(node.get("children", []))]
    for i, p in enumerate(node.get("products", [])):
        rows.append([B(f'📦 {p["name"]} - {fmt_price(p["price"])}', callback_data=f"a:p:{pre}{i}")])
    if path:
        if not node.get("children"):
            rows.append([B("➕ منتج جديد هنا", callback_data=f"a:add:{path}")])
        if not node.get("products"):
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
    t, kb = admin_panel("", "اختار القسم اللي هتضيف فيه المنتج (أو اعمل قسم جديد)، وبعدها اضغط ➕ منتج جديد هنا.")
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
        for p in n.get("products", []):
            yield name, p
        yield from walk(n.get("children", []), name + " ← ")


async def list_cmd(update, ctx):
    if not is_admin(update):
        return
    lines, last = [], None
    for where, p in walk(cat()["categories"]):
        if where != last:
            lines.append(f"\n📁 {where}")
            last = where
        lines.append(f'  • {p["name"]} - {fmt_price(p["price"])} {cur()}')
    text = "\n".join(lines).strip() or "مفيش منتجات لسه."
    for i in range(0, len(text), 3800):
        await update.message.reply_text(text[i:i + 3800])


async def admin_button(q, ctx, data):
    _, act, arg = (data.split(":", 2) + [""])[:3]
    ctx.user_data.pop("await", None)

    async def show(path, hint=""):
        t, kb = admin_panel(path, hint)
        await q.edit_message_text(t, reply_markup=kb)

    if act == "n":
        await show(arg)
    elif act == "p":
        p = get_node(arg)
        kb = M([[B("✏️ السعر", callback_data=f"a:ep:{arg}"), B("✏️ الوصف", callback_data=f"a:ed:{arg}")],
                [B("✏️ الاسم", callback_data=f"a:en:{arg}"), B("🗑 مسح", callback_data=f"a:del:{arg}")],
                [B("⬅️ رجوع", callback_data=f"a:n:{parent_path(arg)}")]])
        await q.edit_message_text(
            f'📦 {p["name"]}\n💰 {fmt_price(p["price"])} {cur()}\n\n{p.get("description","")}', reply_markup=kb)
    elif act in ("ep", "ed", "en"):
        ctx.user_data["await"] = {"act": act, "path": arg}
        q_text = {"ep": "ابعت السعر الجديد (أرقام بس):", "ed": "ابعت الوصف الجديد:", "en": "ابعت الاسم الجديد:"}[act]
        await q.edit_message_text(q_text + "\n(للإلغاء اكتب /cancel)")
    elif act == "add":
        ctx.user_data["await"] = {"act": "add_name", "path": arg}
        await q.edit_message_text("اسم المنتج إيه؟ مثال: Google Play 10$\n(للإلغاء اكتب /cancel)")
    elif act == "newcat":
        ctx.user_data["await"] = {"act": "newcat", "path": arg}
        await q.edit_message_text("اسم القسم الجديد إيه؟ (ممكن تحط إيموجي في الأول)\n(للإلغاء اكتب /cancel)")
    elif act == "cn":
        ctx.user_data["await"] = {"act": "cn", "path": arg}
        await q.edit_message_text("ابعت الاسم الجديد للقسم:\n(للإلغاء اكتب /cancel)")
    elif act in ("del", "cd"):
        n = get_node(arg)
        what = "المنتج" if act == "del" else "القسم بكل اللي جواه"
        kb = M([[B("✅ أيوه امسح", callback_data=f"a:{act}y:{arg}"),
                 B("❌ لأ", callback_data=f"a:n:{parent_path(arg)}")]])
        await q.edit_message_text(f'متأكد إنك عايز تمسح {what}: {n["name"]}؟', reply_markup=kb)
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
    ok = True
    if act == "add_name":
        st.update(act="add_price", name=text)
        await update.message.reply_text("السعر كام؟ (أرقام بس)")
        return True
    if act in ("add_price", "ep"):
        try:
            price = float(text.translate(AR_DIGITS))
            price = int(price) if price == int(price) else price
        except ValueError:
            await update.message.reply_text("ابعت السعر أرقام بس، زي 280")
            return True
        if act == "add_price":
            st.update(act="add_desc", price=price)
            await update.message.reply_text("اكتب وصف المنتج (أو ابعت - لو مش عايز وصف)")
            return True
        get_node(path)["price"] = price
        done = "السعر اتعدّل ✅"
        back = parent_path(path)
    elif act == "add_desc":
        node = get_node(path)
        node.setdefault("products", []).append({
            "name": st["name"], "price": st["price"], "description": "" if text == "-" else text})
        done = f'المنتج {st["name"]} اتضاف ✅'
        back = path
    elif act == "ed":
        get_node(path)["description"] = "" if text == "-" else text
        done, back = "الوصف اتعدّل ✅", parent_path(path)
    elif act == "en":
        get_node(path)["name"] = text
        done, back = "الاسم اتعدّل ✅", parent_path(path)
    elif act == "cn":
        get_node(path)["name"] = text
        done, back = "اسم القسم اتعدّل ✅", parent_path(path)
    elif act == "newcat":
        parent = get_node(path)
        if path == "":
            cat()["categories"].append({"name": text})
            back = ""
        else:
            parent.setdefault("children", []).append({"name": text})
            back = path
        done = f"القسم {text} اتضاف ✅"
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
    await update.message.reply_text("اكتب /start لفتح المتجر 🛍")


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
    if data.startswith("a:") and not (q.from_user.id == ADMIN_ID):
        await q.answer()
        return
    await q.answer()
    try:
        if data.startswith("a:"):
            await admin_button(q, ctx, data)
        else:
            await customer_button(q, ctx, data)
    except (IndexError, ValueError, KeyError):
        await q.edit_message_text("القائمة اتحدثت، اضغط /start من جديد.")


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
