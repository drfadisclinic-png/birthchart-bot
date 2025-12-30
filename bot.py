import os
from datetime import datetime
import pytz
from hijridate import Gregorian
import swisseph as swe
from timezonefinder import TimezoneFinder
from convertdate import hebrew, indian_civil, coptic
import geonamescache

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
from flask import Flask, request

# --- Flask app ---
flask_app = Flask(__name__)

# --- الأبراج والبيانات ---
zodiac_ar = {...}  # كما في الكود السابق
chinese_ar = {...}
gc = geonamescache.GeonamesCache()
countries_dict = gc.get_countries()
country_names = [c['name'] for c in countries_dict.values()]
country_code_by_name = {c['name']: code for code, c in countries_dict.items()}

# --- Conversation states ---
DATE, TIME, LOCATION = range(3)

# --- دوال مساعدة (كما في الكود السابق) ---
# convert_to_24_hour, get_zodiac, get_chinese_zodiac, get_location, calculate_for_bot

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا! أرسل تاريخ ميلادك بالصيغة: يوم/شهر/سنة")
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date'] = update.message.text
    await update.message.reply_text("أرسل الوقت: ساعة:دقيقة صباحًا/مساءً مثلا 07:30 صباحًا")
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time'] = update.message.text
    await update.message.reply_text("أرسل الدولة والمدينة مثلا: الأردن, عمان")
    return LOCATION

async def get_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    result = calculate_for_bot(
        context.user_data['date'],
        context.user_data['time'],
        context.user_data['location']
    )
    await update.message.reply_text(result)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء")
    return ConversationHandler.END

# --- Main ---
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # رابط Render الذي يعطيك HTTPS

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

application = Application.builder().token(TOKEN).build()
application.add_handler(conv_handler)

# --- Flask route for webhook ---
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

if __name__ == "__main__":
    # ضبط Webhook عند البداية
    application.bot.set_webhook(f"{APP_URL}/{TOKEN}")
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
