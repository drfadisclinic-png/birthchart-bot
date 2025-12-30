import telebot
import os
import logging
import threading
from datetime import datetime
from hijridate import Gregorian
import swisseph as swe
import pytz
from timezonefinder import TimezoneFinder
from convertdate import hebrew, indian_civil, coptic
import geonamescache  # ✅ بدون معاملات

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# حفظ حالة المستخدمين
user_states = {}

def calculate_birth_chart(day, month, year, hour, minute, ampm, city, country):
    """ضع كود الحساب الأصلي هنا"""
    return f"""
🌟 **برج فلكي - {city}, {country}**

**الشمس**: الحمل • **القمر**: السرطان • **الطالع**: العذراء

*أضف منطق الحساب الكامل هنا*
    """

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_states[user_id] = {'step': 1, 'data': {}}
    bot.send_message(message.chat.id, 
        "👋 *مرحباً!* أرسل اسمك:", parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = message.from_user.id
    if user_id not in user_states:
        bot.reply_to(message, "📝 استخدم /start أولاً")
        return
    
    state = user_states[user_id]
    text = message.text.strip()
    
    if state['step'] == 1:  # الاسم
        state['data']['name'] = text
        state['step'] = 2
        bot.reply_to(message, "📅 *تاريخ الميلاد*:\n`15/5/1990`", parse_mode='Markdown')
        
    elif state['step'] == 2:  # التاريخ
        try:
            day, month, year = map(int, text.split('/'))
            state['data']['date'] = (day, month, year)
            state['step'] = 3
            bot.reply_to(message, "🕐 *الوقت*:\n`14 30 مساءً`", parse_mode='Markdown')
        except:
            bot.reply_to(message, "❌ *خطأ!* `يوم/شهر/سنة`", parse_mode='Markdown')
            
    elif state['step'] == 3:  # الوقت
        try:
            parts = text.split()
            h, m = map(int, parts[:2])
            state['data']['time'] = (h, m, parts[2] if len(parts)>2 else 'صباحاً')
            state['step'] = 4
            bot.reply_to(message, "📍 *المكان*:\n`Amman Jordan`", parse_mode='Markdown')
        except:
            bot.reply_to(message, "❌ *خطأ!* `14 30 مساءً`", parse_mode='Markdown')
            
    elif state['step'] == 4:  # المكان
        parts = text.split()
        city = parts[0]
        country = ' '.join(parts[1:])
        state['data']['place'] = (city, country)
        
        # عرض الملخص والحساب
        data = state['data']
        summary = f"""
🔍 *ملخص {data['name']}*
📅 {data['date'][0]}/{data['date'][1]}/{data['date'][2]}
🕐 {data['time'][0]}:{data['time'][1]} {data['time'][2]}
📍 {city}, {country}
        """
        
        bot.send_message(message.chat.id, summary, parse_mode='Markdown')
        
        # الحساب
        result = calculate_birth_chart(
            data['date'][0], data['date'][1], data['date'][2],
            data['time'][0], data['time'][1], data['time'][2],
            city, country
        )
        bot.send_message(message.chat.id, result, parse_mode='Markdown')
        
        # تنظيف
        del user_states[user_id]
        bot.send_message(message.chat.id, "🔄 /start لمحاولة جديدة")

# 🚀 Render.com Webhook بدلاً من polling
from flask import Flask, request

app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'ok'

def run_bot():
    logger.info("🤖 البوت يعمل!")
    bot.infinity_polling(none_stop=True, interval=0)

if __name__ == '__main__':
    # تشغيل البوت في thread منفصل
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # تشغيل Flask server لـ Render
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
