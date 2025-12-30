import telebot
import os
import logging
from datetime import datetime
from hijridate import Gregorian
import pytz
from timezonefinder import TimezoneFinder
from convertdate import hebrew, indian_civil, coptic
import geonamescache

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Token
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# Geonames setup
gc = geonamescache.GeonamesCache(min_city_population=15000)
countries_dict = gc.get_countries()
countries_list = sorted([(c['name'], code) for code, c in countries_dict.items()], key=lambda x: x[0])
country_code_by_name = {name: code for name, code in countries_list}

# Zodiac translations
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

@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    welcome_text = """
🔮 *مرحباً بك في محول تاريخ الميلاد العالمي* 🔮

📌 *الاستخدام:*
`/calc DD/MM/YYYY HH MM صباحًا/مساءً المدينة الدولة`

*مثال:*
`/calc 01/01/1990 12 30 صباحًا Amman Jordan`

📍 *مدن متوفرة*: Amman, Riyadh, Dubai, Cairo, London, New York, Paris...

✨ البوت يعمل 24/7 مجاناً!
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

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

        # Basic calculations
        hijri_date = Gregorian(year, month, day).to_hijri()
        western_en = "الحمل" if month == 4 and day >= 20 or month == 3 else "الثور"  # Simplified
        chinese_en = list(chinese_ar.keys())[year % 12]
        
        result = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 *الموقع*: {city}, {country}
🕓 *الوقت*: {hour:02d}:{minute:02d} {am_pm}

📅 *الميلادي*: {day:02d}/{month:02d}/{year}
🕌 *الهجري*: {hijri_date.day:02d}/{hijri_date.month:02d}/{hijri_date.year}
🔮 *البرج الغربي*: {western_en}
🐉 *البرج الصيني*: {chinese_ar[chinese_en]}

*المزيد قريباً...* ✨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
        
        bot.reply_to(message, result.strip(), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, f"❌ *خطأ*: {str(e)}\n\nجرب `/start` مرة أخرى", parse_mode='Markdown')

if __name__ == '__main__':
    logger.info("🤖 البوت يعمل...")
    bot.infinity_polling()
