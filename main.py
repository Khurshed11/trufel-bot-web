import telebot
from telebot import types
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
import json
import sqlite3

import config
import database as db

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(config.BOT_TOKEN, state_storage=state_storage)

db.init_db()

# --- СОСТОЯНИЯ ---
class OrderStates(StatesGroup):
    waiting_for_delivery_type = State()
    waiting_for_address = State()
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_comment = State()

class AdminStates(StatesGroup):
    choosing_category = State()
    waiting_for_name = State()
    waiting_for_photo = State()
    waiting_for_desc = State()
    waiting_for_price = State()
    waiting_for_category_name = State()
    waiting_for_new_value = State()
    waiting_for_new_cat_value = State() # Новое состояние для изменения имени категории

# --- КЛАВИАТУРЫ ---
def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    webapp_button = types.KeyboardButton(
        text="✨ Открыть Витрину Худжанда 📱", 
        web_app=types.WebAppInfo(url=config.WEBAPP_URL)
    )
    markup.row(webapp_button)
    markup.row("🛒 Моя Корзина", "🌸 Визитка и Доставка")
    return markup

def admin_back_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🔙 Назад в админку")
    return markup

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start_command(message):
    admin_text = ""
    if message.from_user.id in config.ADMIN_IDS:
        admin_text = "\n\n👑 *Вы зашли как кондитер-администратор!* Чтобы управлять меню, отправьте команду: /admin"
        
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 🌸\n\n"
        "Мы готовим самые нежные трайфлы и пирожные в Худжанде, чтобы сделать твой день чуточку слаще и счастливее. 🥰\n"
        "Каждый десерт готовится с огромной любовью исключительно из свежих ингредиентов! ✨\n\n"
        "Выбирай вкусняшки на нашей витрине ниже. Ждем твоего заказа! 👇" + admin_text
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")

# --- ВИЗИТКА И ДОСТАВКА ---
@bot.message_handler(func=lambda m: m.text == "🌸 Визитка и Доставка")
def business_card(message):
    card_text = (
        "✨ **SHUKRONS CAKE — СЛАДКАЯ ВИЗИТКА (ХУДЖАНД)** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👩‍🍳 **Кондитер:** Шухратзода Шукрона\n"
        "📸 **Наш Instagram:** [shukrons_cake](https://www.instagram.com/shukrons_cake?igsh=MXJ5cTd0OGgwa2JrcA==) 🍓\n"
        "📞 **Телефон для связи:** `+992 99 999 20 99`\n"
        "🧁 **Специализация:** Нежнейшие трайфлы, mini-десерты, домашние блинные торты и хрустящие песочные корзинки.\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🚗 **Условия доставки:**\n"
        "• Мы отправляем ваши сладости по через городское такси.\n"
        "• 🚕 Стоимость поездки вы **оплачиваете сами напрямую таксисту** при получении десерта.\n"
        "• Самовывоз — бесплатно! Будем безумно рады вашей улыбке при встрече. 🥰\n\n"
        "💳 **Оплата:** Перевод на карту **Банк Эсхата** / **Душанбе Сити** (номер `999992099`) после подтверждения вашего заказа."
    )
    bot.send_message(message.chat.id, card_text, parse_mode="Markdown", disable_web_page_preview=True)

# Словарь для хранения RAM-сессий корзин
user_carts = {}

# --- КОРЗИНА ---
@bot.message_handler(func=lambda message: message.text == "🛒 Моя Корзина")
def show_cart(message):
    user_id = message.chat.id
    if user_id not in user_carts or not user_carts[user_id]['items']:
        bot.send_message(
            user_id, 
            "Ваша корзинка пуста... 🥺\nНо это легко исправить на нашей яркой витрине! 🧁"
        )
        return
    
    cart = user_carts[user_id]
    items = cart['items']
    total_price = cart['total_price']
    
    text = "<b>🛒 ВАША КОРЗИНА</b>\n\n"
    for item in items:
        text += f"• {item['name']} — {item['quantity']} шт. x {item['price']} смн. = {item['cost']} смн.\n"
        
    text += f"\n<b>Итого к оплате: {total_price} смн.</b>\n\n"
    text += "Подтверждаем заказ? Нажмите кнопку <b>💞 Оформить заказ</b> ниже, чтобы выбрать тип доставки! 👇"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("❌ Очистить", callback_data="clear_cart"),
        types.InlineKeyboardButton("💞 Оформить заказ", callback_data="checkout")
    )
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
def handle_clear_cart(call):
    db.clear_cart(call.from_user.id)
    if call.message.chat.id in user_carts:
        user_carts[call.message.chat.id] = {'items': [], 'total_price': 0}
    bot.answer_callback_query(call.id, "Корзинка очищена")
    bot.edit_message_text("Ой, корзинка опустела... Ждем новых вкусностей! 🧺", call.message.chat.id, call.message.message_id)

# --- ОФОРМЛЕНИЕ ЗАКАЗА ---
@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def start_checkout(call):
    bot.answer_callback_query(call.id)
    bot.set_state(call.from_user.id, OrderStates.waiting_for_delivery_type, call.message.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🚗 Доставка", "🏃 Самовывоз")
    bot.send_message(call.message.chat.id, "Как бы вы хотели получить ваши вкусняшки? ✨", reply_markup=markup)

@bot.message_handler(state=OrderStates.waiting_for_delivery_type)
def process_delivery_type(message):
    if message.text not in ["🚗 Доставка", "🏃 Самовывоз"]:
        bot.send_message(message.chat.id, "Пожалуйста, выберите один из вариантов на кнопочках ниже.")
        return
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['delivery_type'] = message.text

    if message.text == "🚗 Доставка":
        bot.set_state(message.from_user.id, OrderStates.waiting_for_address, message.chat.id)
        bot.send_message(message.chat.id, "Напишите, пожалуйста, ваш адрес  (улица, дом, ориентир), куда привезти сладости: 🌸", reply_markup=types.ReplyKeyboardRemove())
    else:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['address'] = "Самовывоз"
        bot.set_state(message.from_user.id, OrderStates.waiting_for_phone, message.chat.id)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📱 Отправить номер телефона", request_contact=True))
        bot.send_message(message.chat.id, "Поделитесь, пожалуйста, вашим номером телефона, чтобы мы связались с вами:", reply_markup=markup)

@bot.message_handler(state=OrderStates.waiting_for_address)
def process_address(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['address'] = message.text
        
    bot.set_state(message.from_user.id, OrderStates.waiting_for_phone, message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📱 Отправить номер телефона", request_contact=True))
    bot.send_message(message.chat.id, "Поделитесь, пожалуйста, вашим номером телефона, чтобы мы держали связь: 💞", reply_markup=markup)

@bot.message_handler(state=OrderStates.waiting_for_phone, content_types=['text', 'contact'])
def process_phone(message):
    phone = message.contact.phone_number if message.content_type == 'contact' else message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['phone'] = phone
        
    bot.set_state(message.from_user.id, OrderStates.waiting_for_name, message.chat.id)
    bot.send_message(message.chat.id, "Как нам называть вас при общении? 😊 (Ваше имя):", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(state=OrderStates.waiting_for_name)
def process_name(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['name'] = message.text
        
    bot.set_state(message.from_user.id, OrderStates.waiting_for_comment, message.chat.id)
    bot.send_message(message.chat.id, "Оставьте теплое пожелание или важный комментарий к заказу (например: 'без клубники' или 'сделайте надпись С ДР'). Если нет комментариев — напишите 'нет':")

@bot.message_handler(state=OrderStates.waiting_for_comment)
def process_comment_and_finish(message):
    comment = message.text
    user_id = message.from_user.id
    
    with bot.retrieve_data(user_id, message.chat.id) as data:
        delivery_type = data['delivery_type']
        address = data['address']
        phone = data['phone']
        name = data['name']
        
    bot.delete_state(user_id, message.chat.id)
    
    items_text = ""
    total_price = 0
    if user_id in user_carts:
        for item in user_carts[user_id]['items']:
            items_text += f"🧁 {item['name']} — {item['quantity']} шт. ({item['cost']} сомони)\n"
        total_price = user_carts[user_id]['total_price']
        user_carts[user_id] = {'items': [], 'total_price': 0}
        
    order_text = (
        f"🚨 **ПОЛУЧЕН НОВЫЙ СЛАДКИЙ ЗАКАЗ!**\n\n"
        f"👤 **Имя:** {name}\n"
        f"📞 **Телефон:** {phone}\n"
        f"📦 **Способ:** {delivery_type}\n"
        f"📍 **Адрес:** {address}\n"
        f"💬 **Комментарий:** {comment}\n\n"
        f"🛍️ **Что заказали:**\n{items_text}\n"
        f"💰 **Сумма заказа: {total_price} сомони**"
    )
    
    bot.send_message(
        message.chat.id, 
        f"🎉 **Ура! Ваш заказ оформлен!**\n\nМы уже начали готовить десерты. Кондитер свяжется с вами по номеру {phone} для согласования времени доставки и оплаты. Спасибо, что вы с нами! Хорошего и сладкого вам дня! 💕", 
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown"
    )
    
    for admin_id in config.ADMIN_IDS:
        try:
            bot.send_message(admin_id, order_text, parse_mode="Markdown")
        except Exception:
            pass

# --- АДМИН-МЕНЮ ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    bot.delete_state(message.from_user.id, message.chat.id)
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Добавить вкусняшку", "📁 Добавить категорию")
    markup.add("📋 Управление меню", "📁 Управление категориями") # Добавили новую кнопку управления категориями
    markup.add("🔙 В обычное меню")
    
    bot.send_message(
        message.chat.id, 
        "👑 Секретная комната кондитера. Управляйте вашим меню:", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "🔙 В обычное меню")
def back_to_menu(message):
    bot.send_message(message.chat.id, "Возвращаемся к гостям!", reply_markup=main_menu_keyboard())

# --- УПРАВЛЕНИЕ МЕНЮ (ПРОСМОТР, ИЗМЕНЕНИЕ И УДАЛЕНИЕ ТОВАРОВ) ---
@bot.message_handler(func=lambda m: m.text == "📋 Управление меню" and m.from_user.id in config.ADMIN_IDS)
def admin_manage_menu(message):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, description FROM products')
    products = cursor.fetchall()
    conn.close()
    
    if not products:
        bot.send_message(message.chat.id, "📭 В меню пока нет ни одного десерта.")
        return
        
    bot.send_message(message.chat.id, "👇 Список ваших товаров. Выберите нужное действие:")
    
    for prod in products:
        prod_id, name, price, desc = prod
        text = f"🧁 *{name}*\n💰 Цена: {price} смн.\n📄 Описание: {desc}"
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn_edit = types.InlineKeyboardButton(text="✏️ Изменить", callback_data=f"editselect_{prod_id}")
        btn_delete = types.InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_{prod_id}")
        keyboard.add(btn_edit, btn_delete)
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def callback_delete_product(call):
    if call.from_user.id not in config.ADMIN_IDS:
        return
    product_id = int(call.data.split("_")[1])
    
    db.delete_product_by_id(product_id)
    
    try:
        bot.answer_callback_query(call.id, "🗑 Товар успешно удален!")
    except Exception:
        pass
        
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Этот десерт был полностью удален из базы и витрины Vercel."
        )
    except Exception:
        bot.send_message(call.message.chat.id, "❌ Товар удален, но сообщение не удалось обновить.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("editselect_"))
def callback_edit_select_field(call):
    if call.from_user.id not in config.ADMIN_IDS:
        return
    product_id = int(call.data.split("_")[1])
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📝 Название", callback_data=f"field_name_{product_id}"),
        types.InlineKeyboardButton("💰 Цена", callback_data=f"field_price_{product_id}"),
        types.InlineKeyboardButton("📄 Описание", callback_data=f"field_description_{product_id}"),
        types.InlineKeyboardButton("🖼 Фотографию", callback_data=f"field_image_id_{product_id}")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="Что именно вы хотите изменить в этом товаре?",
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("field_"))
def callback_field_chosen(call):
    if call.from_user.id not in config.ADMIN_IDS:
        return
    parts = call.data.split("_")
    field_name = parts[1]
    if len(parts) == 4:
        field_name = "image_id"
        product_id = int(parts[3])
    else:
        product_id = int(parts[2])
    
    field_titles = {
        "name": "новое НАЗВАНИЕ десерта",
        "price": "новую ЦЕНУ в сомони (только цифры)",
        "description": "новое ОПИСАНИЕ (состав, вес, эмодзи)",
        "image_id": "отправьте новое фото десерта (или ссылку на изображение)"
    }
    
    bot.set_state(call.from_user.id, AdminStates.waiting_for_new_value, call.message.chat.id)
    
    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        data['edit_field'] = field_name
        data['edit_product_id'] = product_id
        
    bot.send_message(call.message.chat.id, f"✍️ Введите {field_titles.get(field_name, 'данные')}:")
    bot.answer_callback_query(call.id)

@bot.message_handler(state=AdminStates.waiting_for_new_value, content_types=['text', 'photo'])
def process_field_update(message):
    user_id = message.from_user.id
    
    with bot.retrieve_data(user_id, message.chat.id) as data:
        field_name = data['edit_field']
        product_id = data['edit_product_id']
        
    new_value = ""
    
    if field_name == "image_id":
        if message.content_type == 'photo':
            try:
                photo_id = message.photo[-1].file_id
                file_info = bot.get_file(photo_id)
                new_value = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка обработки фото: {e}. Попробуйте ещё раз:")
                return
        else:
            new_value = message.text.strip()
    else:
        if message.content_type != 'text':
            bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте текстовое значение:")
            return
        new_value = message.text.strip()
        
        if field_name == "price":
            try:
                new_value = float(new_value)
            except ValueError:
                bot.send_message(message.chat.id, "❌ Цена должна состоять только из цифр (например, 35 или 42.5). Попробуйте снова:")
                return

    db.update_product_field(product_id, field_name, new_value)
    bot.delete_state(user_id, message.chat.id)
    
    bot.send_message(message.chat.id, "✅ Изменения применены! Витрина  успешно обновлена автоматически. 🚀")


# --- УПРАВЛЕНИЕ КАТЕГОРИЯМИ (ПРОСМОТР, ИЗМЕНЕНИЕ И УДАЛЕНИЕ) ---
@bot.message_handler(func=lambda m: m.text == "📁 Управление категориями" and m.from_user.id in config.ADMIN_IDS)
def admin_manage_categories(message):
    categories = db.get_categories()
    
    if not categories:
        bot.send_message(message.chat.id, "📭 В базе данных пока нет ни одной категории.")
        return
        
    bot.send_message(message.chat.id, "📂 Список ваших категорий меню. При удалении категории удалятся и входящие в неё товары!")
    
    for cat_id, cat_name in categories:
        text = f"📁 *Категория:* {cat_name} (ID: {cat_id})"
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn_edit = types.InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"catedit_{cat_id}")
        btn_delete = types.InlineKeyboardButton(text="❌ Удалить", callback_data=f"catdel_{cat_id}")
        keyboard.add(btn_edit, btn_delete)
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("catdel_"))
def callback_delete_category(call):
    if call.from_user.id not in config.ADMIN_IDS:
        return
    cat_id = int(call.data.split("_")[1])
    
    # Каскадное удаление (удаляем категорию и товары в ней)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE category_id = ?', (cat_id,))
    cursor.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
    conn.commit()
    conn.close()
    
    try:
        bot.answer_callback_query(call.id, "🗑 Категория и её товары удалены!")
    except Exception:
        pass
        
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ Эта категория и все её десерты были полностью стерты из базы."
        )
    except Exception:
        bot.send_message(call.message.chat.id, "❌ Категория удалена.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("catedit_"))
def callback_edit_category_start(call):
    if call.from_user.id not in config.ADMIN_IDS:
        return
    cat_id = int(call.data.split("_")[1])
    
    bot.set_state(call.from_user.id, AdminStates.waiting_for_new_cat_value, call.message.chat.id)
    
    with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
        data['edit_cat_id'] = cat_id
        
    bot.send_message(call.message.chat.id, "✍️ Напишите новое название для этой категории (вместе с эмодзи):", reply_markup=admin_back_keyboard())
    bot.answer_callback_query(call.id)

@bot.message_handler(state=AdminStates.waiting_for_new_cat_value)
def process_category_rename(message):
    if message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    user_id = message.from_user.id
    new_name = message.text.strip()
    
    if new_name.startswith("/"):
        bot.send_message(message.chat.id, "❌ Название не должно начинаться с '/'", reply_markup=admin_back_keyboard())
        return

    with bot.retrieve_data(user_id, message.chat.id) as data:
        cat_id = data['edit_cat_id']

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute('UPDATE categories SET name = ? WHERE id = ?', (new_name, cat_id))
    conn.commit()
    conn.close()
    
    bot.delete_state(user_id, message.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Добавить вкусняшку", "📁 Добавить категорию")
    markup.add("📋 Управление меню", "📁 Управление категориями")
    markup.add("🔙 В обычное меню")
    
    bot.send_message(message.chat.id, f"✅ Категория успешно переименована в *{new_name}*! Витрина обновится сама.", reply_markup=markup, parse_mode="Markdown")


# --- ДОБАВЛЕНИЕ НОВОГО ТОВАРА ---
@bot.message_handler(func=lambda m: m.text == "➕ Добавить вкусняшку" and m.from_user.id in config.ADMIN_IDS)
def admin_add_product_start(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.set_state(message.from_user.id, AdminStates.choosing_category, message.chat.id)
    
    categories = db.get_categories()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat_id, cat_name in categories:
        markup.add(f"{cat_id}. {cat_name}")
    
    markup.add("🔙 Назад в админку")
    bot.send_message(message.chat.id, "Куда добавим новый шедевр?", reply_markup=markup)

@bot.message_handler(state=AdminStates.choosing_category)
def admin_choose_category(message):
    if message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    try:
        cat_id = int(message.text.split(".")[0])
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ Пожалуйста, выберите категорию кнопкой на экране!")
        return

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_cat_id'] = cat_id

    bot.set_state(message.from_user.id, AdminStates.waiting_for_name, message.chat.id)
    bot.send_message(message.chat.id, "Напишите милое название десерта:", reply_markup=admin_back_keyboard())

@bot.message_handler(state=AdminStates.waiting_for_name)
def admin_input_name(message):
    if message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    if message.text.startswith("/") or (len(message.text) > 2 and message.text[1] == '.'):
        bot.send_message(message.chat.id, "⚠️ Ой, похоже на случайное нажатие кнопки. Пожалуйста, напишите текстовое название десерта вручную:", reply_markup=admin_back_keyboard())
        return

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_name'] = message.text
        
    bot.set_state(message.from_user.id, AdminStates.waiting_for_photo, message.chat.id)
    bot.send_message(message.chat.id, "Отправьте одну самую аппетитную фотографию десерта (или ссылку):", reply_markup=admin_back_keyboard())

@bot.message_handler(state=AdminStates.waiting_for_photo, content_types=['text', 'photo'])
def admin_input_photo(message):
    if message.content_type == 'text' and message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    image_url = ""
    if message.content_type == 'photo':
        try:
            photo_id = message.photo[-1].file_id
            file_info = bot.get_file(photo_id)
            image_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Не удалось обработать фото: {e}. Отправьте еще раз.", reply_markup=admin_back_keyboard())
            return
    else:
        image_url = message.text.strip()

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_photo_url'] = image_url
        
    bot.set_state(message.from_user.id, AdminStates.waiting_for_desc, message.chat.id)
    bot.send_message(message.chat.id, "Напишите состав, вес и аллергены:", reply_markup=admin_back_keyboard())

@bot.message_handler(state=AdminStates.waiting_for_desc)
def admin_input_desc(message):
    if message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['new_desc'] = message.text
        
    bot.set_state(message.from_user.id, AdminStates.waiting_for_price, message.chat.id)
    bot.send_message(message.chat.id, "Укажите цену в сомони (только цифры):", reply_markup=admin_back_keyboard())

@bot.message_handler(state=AdminStates.waiting_for_price)
def admin_input_price(message):
    if message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    try:
        price = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Ой, введите цену только цифрами (например: 35):", reply_markup=admin_back_keyboard())
        return
        
    user_id = message.from_user.id
    with bot.retrieve_data(user_id, message.chat.id) as data:
        cat_id = data['new_cat_id']
        name = data['new_name']
        photo_url = data['new_photo_url']
        desc = data['new_desc']
        
    db.add_product(cat_id, name, desc, price, photo_url)
    bot.delete_state(user_id, message.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Добавить вкусняшку", "📁 Добавить категорию")
    markup.add("📋 Управление меню", "📁 Управление категориями")
    markup.add("🔙 В обычное меню")
    bot.send_message(message.chat.id, f"🎉 Сладость '{name}' успешно добавлена в меню по цене {price} сомони!", reply_markup=markup)


# --- ДОБАВЛЕНИЕ НОВОЙ КАТЕГОРИИ ---
@bot.message_handler(func=lambda m: m.text == "📁 Добавить категорию" and m.from_user.id in config.ADMIN_IDS)
def admin_add_category_start(message):
    bot.delete_state(message.from_user.id, message.chat.id)
    bot.set_state(message.from_user.id, AdminStates.waiting_for_category_name, message.chat.id)
    bot.send_message(
        message.chat.id, 
        "✍️ Напишите название для новой категории.\nРекомендую использовать красивый эмодзи в начале (например: 🍩 Пончики):",
        reply_markup=admin_back_keyboard()
    )

@bot.message_handler(state=AdminStates.waiting_for_category_name)
def admin_input_category_name(message):
    if message.text == "🔙 Назад в админку":
        global_admin_back(message)
        return

    user_id = message.from_user.id
    category_name = message.text.strip()
    
    if category_name.startswith("/"):
        bot.send_message(message.chat.id, "❌ Название категории не должно начинаться с '/'", reply_markup=admin_back_keyboard())
        return

    success = db.add_new_category(category_name)
    bot.delete_state(user_id, message.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Добавить вкусняшку", "📁 Добавить категорию")
    markup.add("📋 Управление меню", "📁 Управление категориями")
    markup.add("🔙 В обычное меню")
    
    if success:
        bot.send_message(message.chat.id, f"🎉 Категория *{category_name}* успешно создана!", reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, f"⚠️ Категория с названием '{category_name}' уже существует!", reply_markup=markup)


# --- ПОШАГОВЫЙ ОБРАБОТЧИК КНОПКИ "НАЗАД" ---
@bot.message_handler(state="*", func=lambda m: m.text == "🔙 Назад в админку" and m.from_user.id in config.ADMIN_IDS)
def global_admin_back(message):
    user_id = message.from_user.id
    current_state = bot.get_state(user_id, message.chat.id)
    
    # С шага НАЗВАНИЯ -> назад на ВЫБОР КАТЕГОРИИ
    if current_state == AdminStates.waiting_for_name.name:
        bot.set_state(user_id, AdminStates.choosing_category, message.chat.id)
        categories = db.get_categories()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for cat_id, cat_name in categories:
            markup.add(f"{cat_id}. {cat_name}")
        markup.add("🔙 Назад в админку")
        bot.send_message(message.chat.id, "🔙 Выберите категорию для товара заново:", reply_markup=markup)
        
    # С шага ФОТО -> назад на ВВОД НАЗВАНИЯ
    elif current_state == AdminStates.waiting_for_photo.name:
        bot.set_state(user_id, AdminStates.waiting_for_name, message.chat.id)
        bot.send_message(message.chat.id, "🔙 Изменяем название десерта. Введите имя:", reply_markup=admin_back_keyboard())
        
    # С шага ОПИСАНИЯ -> назад на ОТПРАВКУ ФОТО
    elif current_state == AdminStates.waiting_for_desc.name:
        bot.set_state(user_id, AdminStates.waiting_for_photo, message.chat.id)
        bot.send_message(message.chat.id, "🔙 Отправьте фото или ссылку на изображение заново:", reply_markup=admin_back_keyboard())
        
    # С шага ЦЕНЫ -> назад на ВВОД ОПИСАНИЯ
    elif current_state == AdminStates.waiting_for_price.name:
        bot.set_state(user_id, AdminStates.waiting_for_desc, message.chat.id)
        bot.send_message(message.chat.id, "🔙 Перепишите состав, вес и аллергены десерта:", reply_markup=admin_back_keyboard())
        
    # Из всех остальных мест -> сброс в главное меню админки
    else:
        bot.delete_state(user_id, message.chat.id)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("➕ Добавить вкусняшку", "📁 Добавить категорию")
        markup.add("📋 Управление меню", "📁 Управление категориями")
        markup.add("🔙 В обычное меню")
        bot.send_message(message.chat.id, "🪐 Возвращаемся в главное меню админ-панели:", reply_markup=markup)


@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        raw_data = message.web_app_data.data
        data = json.loads(raw_data)
        
        incoming_items = data.get('items', [])
        
        if not incoming_items:
            bot.send_message(message.chat.id, "🛒 Ваша корзина пуста.")
            return

        if message.chat.id not in user_carts:
            user_carts[message.chat.id] = {'items': [], 'total_price': 0}
            
        current_cart = user_carts[message.chat.id]

        for new_item in incoming_items:
            found = False
            for old_item in current_cart['items']:
                if old_item['name'] == new_item['name']:
                    old_item['quantity'] += new_item['quantity']
                    old_item['cost'] = old_item['quantity'] * old_item['price']
                    found = True
                    break
            
            if not found:
                current_cart['items'].append(new_item)

        current_cart['total_price'] = sum(item['cost'] for item in current_cart['items'])

        text = "<b>🌸 ДЕСЕРТЫ ДОБАВЛЕНЫ В КОРЗИНУ! 🌸</b>\n\n"
        text += "<b>Текущий состав вашей корзины:</b>\n"
        for item in current_cart['items']:
            text += f"• {item['name']} — {item['quantity']} шт. (<i>{item['cost']} смн.</i>)\n"
            
        text += f"\n<b>💰 Общая сумма: {current_cart['total_price']} смн.</b>\n\n"
        text += "Нажмите кнопку <b>🛒 Моя Корзина</b> в меню бота, чтобы проверить заказ, указать адрес и оформить доставку! 🥰"
        
        bot.send_message(message.chat.id, text, parse_mode="HTML")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при разборе данных витрины: {e}")

bot.add_custom_filter(telebot.custom_filters.StateFilter(bot))

if __name__ == '__main__':
    print("🤖 Бот успешно запущен в режиме сомони...")
    bot.infinity_polling(skip_pending=True)