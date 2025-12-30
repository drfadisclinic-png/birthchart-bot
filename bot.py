import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
from datetime import datetime
from hijridate import Gregorian
import swisseph as swe
import pytz
from timezonefinder import TimezoneFinder
from convertdate import hebrew, indian_civil, coptic
import geonamescache

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")

# Global setup
gc = geonamescache.GeonamesCache(min_city_population=15000)
countries_dict = gc.get_countries()
countries_list = sorted([(c['name'], code) for code, c in countries_dict.items()], key=lambda x: x[0])
country_code_by_name = {name: code for name, code in countries_list}

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

def get_location(city_name, country_name):
    code = country_code_by_name.get(country_name, "")
    if not code:
        # Common cities fallback
        common = {
            ("Amman", "Jordan"): (31.95, 35.93, "Asia/Amman"),
            ("Riyadh", "Saudi Arabia"): (24.71, 46.68, "Asia/Riyadh"),
            ("Dubai", "United Arab Emirates"): (25.20, 55.27, "Asia/Dubai"),
            ("Cairo", "Egypt"): (30.04, 31.24, "Africa/Cairo")
        }
        key = (city_name.title(), country_name.title())
        if key in common:
            return common[key]
        return 31.95, 35.93, "Asia/Amman"  # Default Amman
    
    candidates = [c for c in gc.get_cities().values() 
                  if c['countrycode'] == code and city_name.lower() in c['name'].lower()]
    
    if candidates:
        c0 = sorted(candidates, key=lambda x: x.get('population', 0), reverse=True)[0]
        lat, lon = float(c0['latitude']), float(c0['longitude'])
        tf = TimezoneFinder()
        tzname = tf.timezone_at(lat=lat, lng=lon) or "UTC"
        return lat, lon, tzname
    
    return 31.95, 35.93, "Asia/Amman"  # Default

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
        ("Virgo", 23), ("Libra", 23), ("Scorpio", 23), ("Sagittarius", 22)
    ]
    if day >= zodiac_signs[month - 1][1]:
        return zodiac_signs[month - 1][0]
    return zodiac_signs[month - 2][0]

def get_chinese_zodiac(year):
    animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    return animals[year % 12]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """
🔮 *محول تاريخ الميلاد العالمي* 🔮

📌 *الاستخدام:*
`/calc DD/MM/YYYY HH MM صباحًا/مساءً المدينة الدولة`

*مثال:*
`/calc 01/01/1990 12 30 صباحًا Amman Jordan`

📍 *مدن شائعة*: Amman Jordan, Riyadh Saudi Arabia, Dubai United Arab Emirates
✨ *يعمل 24/7 مجاناً!*
    """
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args or len(context.args) < 6:
            await update.message.reply_text(
                "❌ *البيانات ناقصة!*\n\n"
                "📋 `/calc 01/01/1990 12 30 صباحًا Amman Jordan`\n\n"
                "*الترتيب: التاريخ | الساعة | الدقيقة | الفترة | المدينة | الدولة*",
                parse_mode='Markdown'
            )
            return

        date_str, hour_str, minute_str, am_pm, city, country = context.args[:6]
        day, month, year = map(int, date_str.split('/'))
        hour, minute = int(hour_str), int(minute_str)

        # Calculations
        hour_24 = convert_to_24_hour(hour, am_pm)
        hijri_date = Gregorian(year, month, day).to_hijri()
        western_en = get_zodiac(day, month)
        chinese_en = get_chinese_zodiac(year)
        western_ar = zodiac_ar.get(western_en, western_en)
        chinese_ar_name = chinese_ar.get(chinese_en, chinese_en)

        # Location & Astrology
        lat, lon, timezone_name = get_location(city, country)
        tz = pytz.timezone(timezone_name)
        dt_local = tz.localize(datetime(year, month, day, hour_24, minute))
        dt_utc = dt_local.astimezone(pytz.utc)
        jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60)

        moon_longitude = swe.calc_ut(jd_ut, swe.MOON)[0][0]
        moon_sign = int(moon_longitude / 30)
        moon_sign_name = list(zodiac_ar.values())[moon_sign]

        houses = swe.houses(jd_ut, lat, lon)[0]
        asc_sign = int(houses[0] / 30)
        asc_sign_name = list(zodiac_ar.values())[asc_sign]

        hebrew_date = hebrew.from_gregorian(year, month, day)
        coptic_date = coptic.from_gregorian(year, month, day)

        result = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 *الموقع*: {city}, {country} | 🕓 *المنطقة الزمنية*: {timezone_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 *الميلادي*: {day:02d}/{month:02d}/{year}
🕌 *الهجري*: {hijri_date.day:02d}/{hijri_date.month:02d}/{hijri_date.year}
🕒 *الوقت*: {hour:02d}:{minute:02d} {am_pm} ↦ {hour_24:02d}:{minute:02d}

🔮 *البرج الغربي*: {western_ar}
🐉 *البرج الصيني*: {chinese_ar_name}
🌙 *القمر في*: {moon_sign_name}
⬆️ *الطالع*: {asc_sign_name}

📆 *العبري*: {hebrew_date[2]}/{hebrew_date[1]}/{hebrew_date[0]}
📆 *القبطي*: {coptic_date[2]}/{coptic_date[1]}/{coptic_date[0]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

        await update.message.reply_text(result, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ *خطأ*: {str(e)}\n\nجرب `/start` للمساعدة", parse_mode='Markdown')

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("calc", calc))
    logger.info("🤖 البوت يعمل على Render.com!")
    app.run_polling()

if __name__ == '__main__':
    main()
