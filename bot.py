import os
from datetime import datetime
import pytz
from hijridate import Gregorian
import swisseph as swe
from timezonefinder import TimezoneFinder
from convertdate import hebrew, indian_civil, coptic
import geonamescache

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from flask import Flask, request

# --- Flask app ---
app = Flask(__name__)

# --- متغيرات البوت ---
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # رابط HTTPS الخاص بـ Render

# --- Conversation states ---
DATE, TIME, LOCATION = range(3)

# --- الأبراج ---
zodiac_ar = {
    "Aries": "الحمل", "Taurus": "الثور", "Gemini": "الجوزاء", "Cancer": "السرطان",
    "Leo": "الأسد", "Virgo": "العذراء", "Libra": "الميزان", "Scorpio": "العقرب",
    "Sagittarius": "القوس", "Capricorn": "الجدي", "Aquarius": "الدلو", "Pisces": "الحوت"
}
chinese_ar = {
    "Rat": "الفأر", "Ox": "الثور", "Tiger": "النمر", "Rabbit": "الأرنب",
    "Dragon": "التنين", "Snake": "الثعبان", "Horse": "الحصان", "Goat": "العنزة",
    "Monkey": "القرد", "Rooster": "الديك", "Dog": "الكلب", "Pig": "الخنزير"
}

# --- قاعدة بيانات المدن ---
gc = geonamescache.GeonamesCache()
countries_dict = gc.get_countries()
country_names = [c['name'] for c in countries_dict.values()]
country_code_by_name = {c['name']: code for code, c in countries_dict.items()}

# --- دوال مساعدة ---
def convert_to_24_hour(hour, am_pm):
    hour = int(hour)
    if am_pm == "مساءً" and hour < 12:
        return hour + 12
    elif am_pm == "صباحًا" and hour == 12:
        return 0
    return hour

def get_zodiac(day, month):
    zodiac_signs = [
        ("Capricorn", 20), ("Aquarius", 19), ("Pisces", 20), ("Aries", 20),
        ("Taurus", 21), ("Gemini", 21), ("Cancer", 22), ("Leo", 23),
        ("Virgo", 23), ("Libra", 23), ("Scorpio", 23), ("Sagittarius", 22), ("Capricorn", 31)
    ]
    return zodiac_signs[month][0] if day >= zodiac_signs[month - 1][1] else zodiac_signs[month - 1][0]

def get_chinese_zodiac(year):
    animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    return animals[year % 12]

def get_location(city_name, country_name):
    code = country_code_by_name.get(country_name or "")
    if not code or not city_name:
        raise ValueError("يجب اختيار الدولة والمدينة من القوائم")
    candidates = [c for c in gc.get_cities().values()
                  if c['countrycode'] == code and c['name'] == city_name and c.get('population',0)>=15000]
    if not candidates:
        raise ValueError("المدينة غير موجودة في قاعدة البيانات لهذه الدولة")
    c0 = sorted(candidates, key=lambda x: x.get('population', 0), reverse=True)[0]
    lat = float(c0['latitude'])
    lon = float(c0['longitude'])
    if code == "JO":
        return lat, lon, "Asia/Amman"
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    return lat, lon, tzname

# --- حساب الأبراج والتقاويم ---
def calculate_for_bot(date_str, time_str, location_str):
    try:
        day, month, year = map(int, date_str.split('/'))
        hour_min, am_pm = time_str.split()
        hour, minute = map(int, hour_min.split(':'))
        hour_24 = convert_to_24_hour(hour, am_pm)
        country, city = map(str.strip, location_str.split(','))
        lat, lon, timezone_name = get_location(city, country)
        tz = pytz.timezone(timezone_name)
        dt_local = tz.localize(datetime(year, month, day, hour_24, minute))
        dt_utc = dt_local.astimezone(pytz.utc)
        jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60)

        western_en = get_zodiac(day, month)
        chinese_en = get_chinese_zodiac(year)
        western_ar_name = zodiac_ar.get(western_en, western_en)
        chinese_ar_name = chinese_ar.get(chinese_en, chinese_en)

        moon_longitude = swe.calc_ut(jd_ut, swe.MOON)[0][0]
        moon_sign = int(moon_longitude / 30)
        moon_sign_name = list(zodiac_ar.values())[moon_sign]

        houses = swe.houses(jd_ut, lat, lon)[0]
        ascendant_deg = houses[0]
        asc_sign = int(ascendant_deg / 30)
        asc_sign_name = list(zodiac_ar.values())[asc_sign]

        hijri_date = Gregorian(year, month, day).to_hijri()
        hebrew_date = hebrew.from_gregorian(year, month, day)
        indian_date = indian_civil.from_gregorian(year, month, day)
        coptic_date = coptic.from_gregorian(year, month, day)
        buddhist_year = year + 543
        japanese_era = "ريوا" if year >= 2019 else "هيسي" if year >= 1989 else "شووا"
        japanese_year = year - (2019 if japanese_era == "ريوا" else 1989 if japanese_era == "هيسي" else 1926) + 1

        result = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 الموقع: {city}, {country} | 🕓 المنطقة الزمنية: {timezone_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 الميلادي: {day:02d}/{month:02d}/{year}
🕌 الهجري: {hijri_date.day:02d}/{hijri_date.month:02d}/{hijri_date.year}
🕒 الوقت: {hour:02d}:{minute:02d} {am_pm} ↦ {hour_24:02d}:{minute:02d} (24h)

🔮 البرج الغربي: {western_ar_name} ({western_en})
🐉 البرج الصيني: {chinese_ar_name} ({chinese_en})
🌙 القمر في: {moon_sign_name}
⬆️ الطالع: {asc_sign_name}

📆 العبري: يوم {hebrew_date[2]}, شهر {hebrew_date[1]}, سنة {hebrew_date[0]}
📆 الهندي (Saka): يوم {indian_date[2]}, شهر {indian_date[1]}, سنة {indian_date[0]}
📆 القبطي: يوم {coptic_date[2]}, شهر {coptic_date[1]}, سنة {coptic_date[0]}
📆 البوذي: سنة {buddhist_year}
📆 الياباني: عصر {japanese_era}، سنة {japanese_year}
"""
        return result
    except Exception as e:
        return f"حدث خطأ أثناء الحساب: {str(e)}"

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

# --- Conversation handler ---
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
        TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
        LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_location)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

# --- Application ---
application = Application.builder().token(TOKEN).build()
application.add_handler(conv_handler)

# --- Flask webhook route ---
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

# --- Run Flask ---
if __name__ == "__main__":
    application.bot.set_webhook(f"{APP_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
