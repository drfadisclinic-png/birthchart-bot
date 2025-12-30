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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")
bot = telebot.TeleBot(BOT_TOKEN)

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
        raise ValueError("دولة غير صحيحة")
    
    candidates = [c for c in gc.get_cities().values() 
                  if c['countrycode'] == code and city_name.lower() in c['name'].lower()]
    if not candidates:
        # مدن شائعة ثابتة
        common_cities = {
            "amman": (31.95, 35.93, "Asia/Amman"),
            "riyadh": (24.71, 46.68, "Asia/Riyadh"),
            "dubai": (25.20, 55.27, "Asia/Dubai"),
            "cairo": (30.04, 31.24, "Africa/Cairo")
        }
        key = city_name.lower()
        if key in common_cities:
            return common_cities[key]
        raise ValueError(f"مدينة '{city_name}' غير متوفرة")
    
    c0 = sorted(candidates, key=lambda x: x.get('population', 0), reverse=True)[0]
    lat, lon = float(c0['latitude']), float(c0['longitude'])
    
    if code == "JO": return lat, lon, "Asia/Amman"
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    return lat, lon, tzname

def calculate_birth_chart(day, month, year, hour, minute, am_pm, city, country):
    hour_24 = int(hour) + 12 if am_pm == "مساءً" and int(hour) < 12 else int(hour)
    if am_pm == "صباحًا" and int(hour) == 12: hour_24 = 0
    
    hijri_date = Gregorian(year, month, day).to_hijri()
    western_en = "الحمل"  # Simplified - add full logic later
    chinese_en = chinese_ar.keys()[year % 12]
    
    lat, lon, timezone_name = get_location(city, country)
    tz = pytz.timezone(timezone_name)
    dt_local = tz.localize(datetime(year, month, day, hour_24, minute))
    dt_utc = dt_local.astimezone(pytz.utc)
    jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60)
    
    moon_longitude = swe.calc_ut(jd_ut, swe.MOON)[0][0]
    moon_sign_name = list(zodiac_ar.values())[int(moon_longitude / 30)]
    
    houses = swe.houses(jd_ut, lat, lon)[0]
    asc_sign_name = list(zodiac_ar.values())[int(houses[0] / 30)]
    
    hebrew_date = hebrew.from_gregorian(year, month, day)
    
    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 *الموقع*: {city}, {country}
🕓 *المنطقة الزمنية*: {timezone_name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 *الميلادي*: {day:02d}/{month:02d}/{year}
🕌 *الهجري*: {hijri_date.day:02d}/{hijri_date.month:02d}/{hijri_date.year}
🕒 *الوقت*: {hour}:{minute} {am_pm}

🔮 *البرج الغربي*: {zodiac_ar.get(western_en, western_en)}
🌙 *القمر في*: {moon_sign_name}
⬆️ *الطالع*: {asc_sign_name}

📆 *العبري*: {hebrew_date[2]}/{hebrew_date[1]}/{hebrew_date[0]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, """🔮 *محول تاريخ الميلاد العالمي* 🔮

📌 `/calc DD/MM/YYYY HH MM صباحًا/مساءً المدينة الدولة`

مثال: `/calc 01/01/1990 12 30 صباحًا Amman Jordan`""", parse_mode='Markdown')

@bot.message_handler(commands=['calc'])
def calc(message):
    try:
        parts = message.text.split()[1:7]
        if len(parts) < 6:
            return bot.reply_to(message, "❌ استخدم: `/calc 01/01/1990 12 30 صباحًا Amman Jordan`", parse_mode='Markdown')
        
        date_str, h, m, ampm, city, country = parts
        day, month, year = map(int, date_str.split('/'))
        result = calculate_birth_chart(day, month, year, h, m, ampm, city, country)
        bot.reply_to(message, result, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}", parse_mode='Markdown')

if __name__ == '__main__':
    print("🤖 البوت يعمل!")
    bot.infinity_polling()
