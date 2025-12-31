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
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from flask import Flask, request

# ------------------ Flask ------------------
app = Flask(__name__)

# ------------------ ENV ------------------
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # https://xxxx.onrender.com

# ------------------ Telegram App ------------------
application = Application.builder().token(TOKEN).build()

# ------------------ States ------------------
DATE, TIME, LOCATION = range(3)

# ------------------ Zodiac ------------------
zodiac_ar = {
    "Aries": "الحمل", "Taurus": "الثور", "Gemini": "الجوزاء", "Cancer": "السرطان",
    "Leo": "الأسد", "Virgo": "العذراء", "Libra": "الميزان", "Scorpio": "العقرب",
    "Sagittarius": "القوس", "Capricorn": "الجدي", "Aquarius": "الدلو", "Pisces": "الحوت"
}

chinese_ar = {
    "Rat": "الفأر", "Ox": "الثور", "Tiger": "النمر", "Rabbit": "الأرنب",
    "Dragon": "التنين", "Snake": "الثعبان", "Horse": "الحصان",
    "Goat": "العنزة", "Monkey": "القرد", "Rooster": "الديك",
    "Dog": "الكلب", "Pig": "الخنزير"
}

# ------------------ Cities ------------------
gc = geonamescache.GeonamesCache()
countries = gc.get_countries()
country_code_by_name = {c["name"]: code for code, c in countries.items()}

# ------------------ Helpers ------------------
def convert_to_24_hour(hour, am_pm):
    hour = int(hour)
    if am_pm == "مساءً" and hour < 12:
        return hour + 12
    if am_pm == "صباحًا" and hour == 12:
        return 0
    return hour


def get_zodiac(day, month):
    signs = [
        ("Capricorn", 20), ("Aquarius", 19), ("Pisces", 20), ("Aries", 20),
        ("Taurus", 21), ("Gemini", 21), ("Cancer", 22), ("Leo", 23),
        ("Virgo", 23), ("Libra", 23), ("Scorpio", 23), ("Sagittarius", 22),
        ("Capricorn", 31)
    ]
    return signs[month][0] if day >= signs[month - 1][1] else signs[month - 1][0]


def get_chinese_zodiac(year):
    animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
               "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    return animals[year % 12]


def get_location(city, country):
    code = country_code_by_name.get(country)
    if not code:
        raise ValueError("الدولة غير موجودة")

    cities = [
        c for c in gc.get_cities().values()
        if c["countrycode"] == code and c["name"] == city
    ]

    if not cities:
        raise ValueError("المدينة غير موجودة")

    c = cities[0]
    lat, lon = float(c["latitude"]), float(c["longitude"])

    if code == "JO":
        return lat, lon, "Asia/Amman"

    tf = TimezoneFinder()
    tz = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    return lat, lon, tz


def calculate_for_bot(date_str, time_str, location_str):
    day, month, year = map(int, date_str.split("/"))
    hm, am_pm = time_str.split()
    hour, minute = map(int, hm.split(":"))
    hour24 = convert_to_24_hour(hour, am_pm)

    country, city = map(str.strip, location_str.split(","))

    lat, lon, tzname = get_location(city, country)
    tz = pytz.timezone(tzname)

    dt = tz.localize(datetime(year, month, day, hour24, minute))
    utc = dt.astimezone(pytz.utc)

    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60)

    western = get_zodiac(day, month)
    chinese = get_chinese_zodiac(year)

    moon_lon = swe.calc_ut(jd, swe.MOON)[0][0]
    moon_sign = list(zodiac_ar.values())[int(moon_lon / 30)]

    houses = swe.houses(jd, lat, lon)[0]
    asc_sign = list(zodiac_ar.values())[int(houses[0] / 30)]

    hijri = Gregorian(year, month, day).to_hijri()
    heb = hebrew.from_gregorian(year, month, day)
    ind = indian_civil.from_gregorian(year, month, day)
    cop = coptic.from_gregorian(year, month, day)

    return f"""
📍 {city}, {country}
🕒 {hour24:02d}:{minute:02d}
🔮 الغربي: {zodiac_ar[western]}
🐉 الصيني: {chinese_ar[chinese]}
🌙 القمر: {moon_sign}
⬆️ الطالع: {asc_sign}
🕌 الهجري: {hijri}
📆 العبري: {heb}
📆 الهندي: {ind}
📆 القبطي: {cop}
"""


# ------------------ Handlers ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل تاريخ الميلاد: يوم/شهر/سنة")
    return DATE


async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["date"] = update.message.text
    await update.message.reply_text("أرسل الوقت: 07:30 صباحًا")
    return TIME


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time"] = update.message.text
    await update.message.reply_text("أرسل الدولة والمدينة: الأردن, عمان")
    return LOCATION


async def get_location_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["location"] = update.message.text
    result = calculate_for_bot(
        context.user_data["date"],
        context.user_data["time"],
        context.user_data["location"]
    )
    await update.message.reply_text(result)
    return ConversationHandler.END


conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        DATE: [MessageHandler(filters.TEXT, get_date)],
        TIME: [MessageHandler(filters.TEXT, get_time)],
        LOCATION: [MessageHandler(filters.TEXT, get_location_step)],
    },
    fallbacks=[]
)

application.add_handler(conv)

# ------------------ Webhook ------------------
@app.route(f"/{TOKEN}", methods=["POST"])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"


# ------------------ Start ------------------
if __name__ == "__main__":
    application.bot.set_webhook(f"{APP_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
