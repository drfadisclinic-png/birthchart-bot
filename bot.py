import os
import logging
from datetime import datetime

import telebot
from flask import Flask, request

import pytz
import swisseph as swe
from hijridate import Gregorian
from timezonefinder import TimezoneFinder
from convertdate import hebrew, indian_civil, coptic
import geonamescache

# =====================
# إعدادات أساسية
# =====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود في Environment Variables")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
app = Flask(__name__)

# =====================
# تخزين حالة المستخدم
# =====================
user_states = {}

# =====================
# أدوات مساعدة
# =====================
gc = geonamescache.GeonamesCache(min_city_population=15000)
tf = TimezoneFinder()

def convert_to_24(hour, ampm):
    hour = int(hour)
    if ampm.startswith("مس") and hour < 12:
        return hour + 12
    if ampm.startswith("ص") and hour == 12:
        return 0
    return hour

def get_zodiac(day, month):
    signs = [
        ("Capricorn", 20), ("Aquarius", 19), ("Pisces", 20),
        ("Aries", 20), ("Taurus", 21), ("Gemini", 21),
        ("Cancer", 22), ("Leo", 23), ("Virgo", 23),
        ("Libra", 23), ("Scorpio", 23), ("Sagittarius", 22),
        ("Capricorn", 31)
    ]
    return signs[month][0] if day >= signs[month - 1][1] else signs[month - 1][0]

zodiac_ar = {
    "Aries": "الحمل", "Taurus": "الثور", "Gemini": "الجوزاء",
    "Cancer": "السرطان", "Leo": "الأسد", "Virgo": "العذراء",
    "Libra": "الميزان", "Scorpio": "العقرب",
    "Sagittarius": "القوس", "Capricorn": "الجدي",
    "Aquarius": "الدلو", "Pisces": "الحوت"
}

# =====================
# الحساب الكامل
# =====================
def calculate_birth_chart(day, month, year, hour, minute, ampm, city, country):
    hour24 = convert_to_24(hour, ampm)

    # المدينة
    cities = [
        c for c in gc.get_cities().values()
        if c["name"].lower() == city.lower()
    ]
    if not cities:
        raise ValueError("لم يتم العثور على المدينة")

    city_data = sorted(cities, key=lambda x: x.get("population", 0), reverse=True)[0]
    lat = float(city_data["latitude"])
    lon = float(city_data["longitude"])

    tzname = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    tz = pytz.timezone(tzname)

    dt_local = tz.localize(datetime(year, month, day, hour24, minute))
    dt_utc = dt_local.astimezone(pytz.utc)

    jd = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        dt_utc.hour + dt_utc.minute / 60
    )

    # الأبراج
    western = zodiac_ar[get_zodiac(day, month)]

    moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
    moon_sign = list(zodiac_ar.values())[int(moon_lon / 30)]

    houses = swe.houses(jd, lat, lon)[0]
    asc_sign = list(zodiac_ar.values())[int(houses[0] / 30)]

    hijri = Gregorian(year, month, day).to_hijri()

    return f"""
━━━━━━━━━━━━━━━━━━
🌟 *نتيجة الحساب الفلكي*
━━━━━━━━━━━━━━━━━━

📍 *المكان:* {city}, {country}
🕓 *المنطقة الزمنية:* {tzname}

📅 *الميلادي:* {day:02d}/{month:02d}/{year}
🕌 *الهجري:* {hijri.day}/{hijri.month}/{hijri.year}

☀️ *البرج الشمسي:* {western}
🌙 *القمر:* {moon_sign}
⬆️ *الطالع:* {asc_sign}
━━━━━━━━━━━━━━━━━━
"""

# =====================
# أوامر البوت
# =====================
@bot.message_handler(commands=["start"])
def start(message):
    user_states[message.from_user.id] = {"step": 1, "data": {}}
    bot.send_message(message.chat.id, "👋 *مرحباً*\nأرسل اسمك:")

@bot.message_handler(func=lambda m: True)
def handler(message):
    uid = message.from_user.id
    if uid not in user_states:
        bot.reply_to(message, "استخدم /start أولاً")
        return

    state = user_states[uid]
    text = message.text.strip()

    if state["step"] == 1:
        state["data"]["name"] = text
        state["step"] = 2
        bot.reply_to(message, "📅 أرسل تاريخ الميلاد:\n`15/5/1990`")

    elif state["step"] == 2:
        try:
            d, m, y = map(int, text.split("/"))
            state["data"]["date"] = (d, m, y)
            state["step"] = 3
            bot.reply_to(message, "🕐 الوقت:\n`14 30 مساءً`")
        except:
            bot.reply_to(message, "❌ الصيغة خطأ")

    elif state["step"] == 3:
        try:
            h, m, ampm = text.split()
            state["data"]["time"] = (int(h), int(m), ampm)
            state["step"] = 4
            bot.reply_to(message, "📍 المكان:\n`Amman Jordan`")
        except:
            bot.reply_to(message, "❌ الصيغة خطأ")

    elif state["step"] == 4:
        city, country = text.split(" ", 1)
        d = state["data"]

        result = calculate_birth_chart(
            d["date"][0], d["date"][1], d["date"][2],
            d["time"][0], d["time"][1], d["time"][2],
            city, country
        )

        bot.send_message(message.chat.id, result)
        del user_states[uid]
        bot.send_message(message.chat.id, "🔄 /start لحساب جديد")

# =====================
# Webhook (Render)
# =====================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(
        request.stream.read().decode("utf-8")
    )
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running"

# =====================
# تشغيل السيرفر
# =====================
if __name__ == "__main__":
    logger.info("🤖 Bot started (Webhook mode)")
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
