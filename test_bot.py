import telebot

# Вставьте сюда ваш токен напрямую для проверки
TOKEN =  "8884200742:AAEstKrlYaVyQ7CGxbgzakrDDH_YP-9BW2s"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def test_start(message):
    print(f"Получена команда /start от {message.from_user.id}")
    bot.send_message(message.chat.id, "Привет! Я работаю!")

print("Тестовый бот запущен...")
bot.infinity_polling()