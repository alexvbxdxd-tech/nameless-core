import telebot

TOKEN = "8817751804:AAEV74FF1o_MKMKs9a_EGlLSYDQdEk_BeiI"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "⚡ NAMELESS CORE ONLINE")

bot.infinity_polling()