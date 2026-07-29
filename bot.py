import os
import random
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================== CONFIGURAZIONE ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8133423814

SITE_URL = "https://fornitoreeuro.store"          # cambia se hai un altro sito
CONTACT_URL = "https://t.me/gustavoeuro"
# ====================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Memoria
user_captcha = {}          # user_id -> risposta corretta
admin_reply_to = {}        # admin_id -> user_id
USERS_FILE = "users.json"


def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)


users = load_users()


def generate_captcha():
    a = random.randint(15, 30)
    b = random.randint(5, 12)
    correct = a - b

    # genera 2 risposte sbagliate
    wrong1 = correct + random.choice([-3, -2, 2, 3, 4])
    wrong2 = correct + random.choice([-4, -1, 1, 5])
    while wrong1 == correct or wrong1 < 0:
        wrong1 = correct + random.choice([-3, -2, 2, 3])
    while wrong2 == correct or wrong2 == wrong1 or wrong2 < 0:
        wrong2 = correct + random.choice([-4, -1, 1, 5])

    options = [correct, wrong1, wrong2]
    random.shuffle(options)

    return a, b, correct, options


# -------------------- /start --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    a, b, correct, options = generate_captcha()
    user_captcha[user_id] = correct

    keyboard = [
        [
            InlineKeyboardButton(str(options[0]), callback_data=f"cap_{options[0]}"),
            InlineKeyboardButton(str(options[1]), callback_data=f"cap_{options[1]}"),
            InlineKeyboardButton(str(options[2]), callback_data=f"cap_{options[2]}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🔐 *Verifica di sicurezza*\n\n"
        f"Quanto fa *{a} − {b}* ?\n\n"
        f"Scegli la risposta corretta:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# -------------------- CALLBACK (CAPTCHA + PULSANTI) --------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # ——— CAPTCHA ———
    if data.startswith("cap_"):
        answer = int(data.split("_")[1])

        if user_id not in user_captcha:
            await query.edit_message_text("⏳ Sessione scaduta. Scrivi /start")
            return

        if answer == user_captcha[user_id]:
            del user_captcha[user_id]

            # salva utente
            users.add(user_id)
            save_users(users)

            keyboard = [
                [InlineKeyboardButton("🌐 Visita il sito", url=SITE_URL)],
                [InlineKeyboardButton("📩 Contattami", url=CONTACT_URL)],
                [InlineKeyboardButton("⚠️ Se sei limitato scrivimi qui", callback_data="limited")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            caption = (
                "✅ *Verifica completata!*\n\n"
                "Benvenuto su *GustavoEuro*.\n"
                "Scegli un'opzione qui sotto:"
            )

            try:
                with open("welcome.jpg", "rb") as photo:
                    await query.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
            except FileNotFoundError:
                await query.message.reply_text(
                    caption,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )

            await query.edit_message_text("✅ Risposta corretta!")
        else:
            # risposta sbagliata → nuovo captcha
            a, b, correct, options = generate_captcha()
            user_captcha[user_id] = correct

            keyboard = [
                [
                    InlineKeyboardButton(str(options[0]), callback_data=f"cap_{options[0]}"),
                    InlineKeyboardButton(str(options[1]), callback_data=f"cap_{options[1]}"),
                    InlineKeyboardButton(str(options[2]), callback_data=f"cap_{options[2]}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"❌ Risposta sbagliata.\n\n"
                f"Quanto fa *{a} − {b}* ?\n"
                f"Scegli di nuovo:",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        return

    # ——— Se sei limitato ———
    if data == "limited":
        await query.message.reply_text(
            "✍️ *Scrivi pure qui sotto il tuo messaggio.*\n"
            "Ti risponderò il prima possibile.",
            parse_mode="Markdown"
        )
        return

    # ——— Admin vuole rispondere ———
    if data.startswith("reply_"):
        if user_id != ADMIN_ID:
            return
        target_id = int(data.split("_")[1])
        admin_reply_to[user_id] = target_id
        await query.message.reply_text(
            f"✍️ Stai rispondendo all'utente `{target_id}`.\n\n"
            f"Scrivi ora il messaggio:",
            parse_mode="Markdown"
        )


# -------------------- MESSAGGI --------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text = update.message.text.strip()

    # Admin sta rispondendo a qualcuno
    if user_id == ADMIN_ID and user_id in admin_reply_to:
        target_id = admin_reply_to[user_id]
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"📩 *Risposta da GustavoEuro:*\n\n{text}",
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ Messaggio inviato all'utente.")
        except Exception as e:
            await update.message.reply_text(f"❌ Errore: {e}")
        finally:
            del admin_reply_to[user_id]
        return

    # Messaggio da utente normale
    if user_id != ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("💬 Rispondi a questo utente", callback_data=f"reply_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        forward_text = (
            f"📨 *Nuovo messaggio*\n\n"
            f"👤 {user.first_name or ''} {user.last_name or ''}\n"
            f"🔗 @{user.username or 'nessuno'}\n"
            f"🆔 `{user_id}`\n\n"
            f"💬 {text}"
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=forward_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            await update.message.reply_text(
                "✅ Messaggio inviato.\nTi risponderemo il prima possibile."
            )
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("❌ Errore nell'invio.")


# -------------------- BROADCAST (solo admin) --------------------
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "Uso:\n`/broadcast Il tuo messaggio qui`",
            parse_mode="Markdown"
        )
        return

    message = " ".join(context.args)
    sent = 0
    failed = 0

    await update.message.reply_text(f"📤 Invio in corso a {len(users)} utenti...")

    for uid in list(users):
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *Messaggio da GustavoEuro:*\n\n{message}",
                parse_mode="Markdown"
            )
            sent += 1
        except:
            failed += 1

    await update.message.reply_text(
        f"✅ Broadcast completato!\n\n"
        f"Inviati: {sent}\n"
        f"Falliti: {failed}"
    )


# -------------------- ERROR --------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")


# -------------------- MAIN --------------------
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN non impostato!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("✅ Bot gustavoeuro_bot avviato...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
