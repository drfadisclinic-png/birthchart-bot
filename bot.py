import telebot
import os
import logging
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
bot = telebot.TeleBot(BOT_TOKEN)

# Geonames setup
gc = geonamescache.GeonamesCache(min_city_population=15000)
countries_dict = gc.get_countries()
countries_list = sorted([(c['name'], code) for code, c in countries_dict.items()], key=lambda x: x[0])
country_code_by_name = {name: code for name, code in countries_list}

# Zodiac data
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
    return zodiac_signs[month-1][0] if day >= zodiac_signs[month-1][1] else zodiac_signs[(month-2)%12][0]

def get_chinese_zodiac(year):
    animals = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake", "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
    return animals[year % 12]

def get_location_from_selection(city_name, country_name):
    code = country_code_by_name.get(country_name, "")
    if not code or not city_name:
        raise ValueError("المدينة/الدولة غير صحيحة")
    candidates = [c for c in gc.get_cities().values() if c['countrycode'] == code and c['name'].lower() == city_name.lower()]
    if not candidates:
        raise ValueError(f"المدينة '{city_name}' غير موجودة في {country_name}")
    c0 = sorted(candidates, key=lambda x: x.get('population', 0), reverse=True)[0]
    lat = float(c0['latitude'])
    lon = float(c0['longitude'])
    if code == "JO":
        return lat, lon, "Asia/Amman"
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    return lat, lon, tzname

def calculate_birth_chart(day, month, year, hour, minute, am_pm, city, country):
    try:
        hour_24 = convert_to_24_hour(hour, am_pm)
        
        # Calendars
        hijri_date = Gregorian(year, month, day).to_hijri()
        western_en = get_zodiac(day, month)
        chinese_en = get_chinese_zodiac(year)
        western_ar = zodiac_ar.get(western_en, western_en)
        chinese_ar_name = chinese_ar.get(chinese_en, chinese_en)
        
        # Location & Timezone
        lat, lon, timezone_name = get_location_from_selection(city, country)
        tz = pytz.timezone(timezone_name)
        dt_local = tz.localize(datetime(year, month, day, hour_24, minute))
        dt_utc = dt_local.astimezone(pytz.utc)
        jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute / 60)
        
        # Astrology
        moon_longitude = swe.calc_ut(jd_ut, swe.MOON)[0][0]
        moon_sign = int(moon_longitude / 30)
        moon_sign_name = list(zodiac_ar.values())[moon_sign]
        
        houses = swe.houses(jd_ut, lat, lon)[0]
        ascendant_deg = houses[0]
        asc_sign = int(ascendant_deg / 30)
        asc_sign_name = list(zodiac_ar.values())[asc_sign]
        
        # Additional calendars
        hebrew_date = hebrew.from_gregorian(year, month, day)
        indian_date = indian_civil.from_gregorian(year, month, day)
        coptic_date = coptic.from_gregorian(year, month, day)
        buddhist_year = year + 543
        japanese_era = "ريوا" if year >= 2019 else "هيسي" if year >= 1989 else "شووا"
        japanese_year = year - (2019 if japanese_era == "ريوا" else 1989 if japanese_era == "هيسي" else 1926) + 1
        
        result = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 *الموقع*: {city}, {country} | 🕓 *المنطقة الزمنية*: {timezone_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 *الميلادي*: {day:02d}/{month:02d}/{year}
🕌 *الهجري*: {hijri_date.day:02d}/{hijri_date.month:02d}/{hijri_date.year}
🕒 *الوقت*: {hour:02d}:{minute:02d} {am_pm} ↦ {hour_24:02d}:{minute:02d} (24h)

🔮 *البرج الغربي*: {western_ar} ({western_en})
🐉 *البرج الصيني*: {chinese_ar_name} ({chinese_en})
🌙 *القمر في*: {moon_sign_name}
⬆️ *الطالع*: {asc_sign_name}

📆 *العبري*: يوم {hebrew_date[2]}, شهر {hebrew_date[1]}, سنة {hebrew_date[0]}
📆 *الهندي (Saka)*: يوم {indian_date[2]}, شهر {indian_date[1]}, سنة {indian_date[0]}
📆 *القبطي*: يوم {coptic_date[2]}, شهر {coptic_date[1]}, سنة {coptic_date[0]}
📆 *البوذي*: سنة {buddhist_year}
📆 *الياباني*: عصر {japanese_era}، سنة {japanese_year}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        return result
        
    except Exception as e:
        raise Exception(f"خطأ في الحساب: {str(e)}")

@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    welcome = """
🔮 *محول تاريخ الميلاد العالمي* 🔮

📌 *الاستخدام:*
`/calc DD/MM/YYYY HH MM صباحًا/مساءً المدينة الدولة`

*مثال:*
`/calc 01/01/1990 12 30 صباحًا Amman Jordan`

📍 *مدن شائعة*: Amman, Riyadh, Dubai, Cairo, London, Paris, New York
✨ *يعمل 24/7 مجاناً!*
    """
    bot.reply_to(message, welcome, parse_mode='Markdown')

@bot.message_handler(commands=['calc'])
def calculate_handler(message):
    try:
        parts = message.text.split()[1:]
        if len(parts) < 6:
            bot.reply_to(message, 
                "❌ *البيانات ناقصة!*\n\n"
                "📋 `/calc 01/01/1990 12 30 صباحًا Amman Jordan`\n\n"
                "*الترتيب: التاريخ | الساعة | الدقيقة | الفترة | المدينة | الدولة*",
                parse_mode='Markdown')
            return

        date_str, hour_str, minute_str, am_pm, city, country = parts[:6]
        day, month, year = map(int, date_str.split('/'))
        hour, minute = int(hour_str), int(minute_str)

        result = calculate_birth_chart(day, month, year, hour, minute, am_pm, city, country)
        bot.reply_to(message, result, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"❌ *خطأ*: {str(e)}\n\nجرب `/start` للمساعدة", parse_mode='Markdown')

if __name__ == '__main__':
    logger.info("🤖 البوت يعمل على Render.com...")
    bot.infinity_polling()
