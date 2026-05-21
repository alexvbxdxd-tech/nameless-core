import os
import telebot

TOKEN = os.getenv("TOKEN")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(
        m,
        "⚡ NAMELESS CORE ONLINE"
    )

bot.infinity_polling()
