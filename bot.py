import telebot
from telebot import types
from tinydb import TinyDB, Query
from datetime import datetime, date
import time
import random
import uuid
import re
import html
import logging
from config import TOKEN, ADMIN_ID

bot = telebot.TeleBot(TOKEN)
db = TinyDB('data.json')
User = Query()
broadcast_storage = {}
BOT_USERNAME = bot.get_me().username

def get_user_data(user_id, chat_id=None):
    user = db.search(User.user_id == user_id)
    if not user:
        return {
            'user_id': user_id,
            'iq_all': 0,
            'today_iq': 0,
            'last_iq': 0,
            'chat_id': chat_id if chat_id else 0,
            'today_date': datetime.now().strftime('%Y-%m-%d'),
            'active_in_chats': [chat_id] if chat_id else []
        }
    if 'active_in_chats' not in user[0]:
        user[0]['active_in_chats'] = [chat_id] if chat_id else []
        save_user_data(user[0])
    return user[0]

def save_user_data(data):
    db.upsert(data, User.user_id == data['user_id'])

def format_user_link(user_id, name):
    safe_name = html.escape(name)
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'

def is_group_chat(message):
    return message.chat.type != 'private'

def send_welcome_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "👉 Добавить бота в группу (чат)",
        url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
    ))
    bot.send_message(chat_id,
        "Привет! <b>🧠 IQ-Метр</b> — бот-линейка для групп (чатов)\n\n"
        "Раз в час игрок может ввести команду /iq, чтобы проверить IQ 🧠\n"
        "Мои команды — /help",
        reply_markup=markup,
        parse_mode='HTML'
    )

def set_default_commands():
    commands = [
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("help", "Справка по командам"),
        types.BotCommand("iq", "Проверить IQ"),
        types.BotCommand("stats", "Групповая статистика"),
        types.BotCommand("top", "ТОП IQ"),
    ]
    bot.set_my_commands(commands)

@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_group_chat(message):
        send_welcome_message(message.chat.id)
        return
    bot.reply_to(message, "<b>Бот запущен!</b> Используйте /iq чтобы начать игру", parse_mode='HTML')

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message,
        "<b>Как начать работу с ботом?</b>\n"
        "- Необходимо добавить бота в группу (чат)\n\n"
        "<b>Команды бота:</b>\n"
        "/start - запустить бота\n"
        "/iq - начать игру\n"
        "/stats - статистика\n"
        "/top - топ игроков и групп\n"
        "/help - помощь по боту",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['iq'])
def iq_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data = get_user_data(user_id, chat_id)
    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    user_link = format_user_link(user_id, full_name)
    current_time = time.time()
    time_diff = current_time - user_data['last_iq']
    
    if chat_id not in user_data['active_in_chats']:
        user_data['active_in_chats'].append(chat_id)
        save_user_data(user_data)

    if time_diff < 3600:
        minutes_left = int((3600 - time_diff) / 60)
        bot.reply_to(message, f"<i>{user_link}, повтори через {minutes_left} мин. ⏳\n"
                         f"🧠 Текущий IQ - <b>{user_data['iq_all']}</b> баллов.</i>", parse_mode='HTML')
        return
    iq_amount = round(random.uniform(0.5, 5.9), 1)
    current_date = datetime.now().strftime('%Y-%m-%d')
    if user_data['today_date'] != current_date:
        user_data['today_iq'] = 0
        user_data['today_date'] = current_date
    user_data['iq_all'] += iq_amount
    user_data['today_iq'] += iq_amount
    user_data['last_iq'] = time.time()
    save_user_data(user_data)
    bot.reply_to(message, f"<i>{user_link}, твой IQ вырос на <b>{iq_amount}</b> баллов!\n"
                     f"🧠 Всего IQ: <b>{user_data['iq_all']}</b> баллов.</i>", parse_mode='HTML')

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if not is_group_chat(message):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
        "👉 Добавить бота в группу (чат)",
        url=f"https://t.me/{BOT_USERNAME}?startgroup=true" ))
        bot.reply_to(message, "<b>IQ-Метр 🧠 работает только в группах (чатах)</b>", 
        reply_markup=markup,
        parse_mode='HTML')
        return
    chat_id = message.chat.id
    users = db.search(User.active_in_chats.test(lambda x: chat_id in x))
    sorted_users = sorted(users, key=lambda x: x['iq_all'], reverse=True)[:10]
    response = "<b>🧠 Топ 10 IQ-игроков чата</b>\n\n"
    for i, user in enumerate(sorted_users, 1):
        full_name = bot.get_chat_member(chat_id, user['user_id']).user.full_name
        user_link = format_user_link(user['user_id'], full_name)
        response += f"{i}. {user_link} - {user['iq_all']} баллов\n"
    response += "\nЧтобы попасть в этот список, начните игру с помощью команды /iq\n" \
               "ТОП лучших игроков - /top"
    bot.reply_to(message, response, parse_mode='HTML')

@bot.message_handler(commands=['top'])
def top_command(message):
    if not is_group_chat(message):
        bot.reply_to(message, "<b>IQ-Метр 🧠 работает только в группах (чатах)</b>", parse_mode='HTML')
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 Посмотреть ТОП игроков", callback_data="top_players"))
    markup.add(types.InlineKeyboardButton("👥 Посмотреть ТОП чатов", callback_data="top_chats"))
    bot.send_message(message.chat.id, "<i>🧠 ТОП лучших игроков и чатов</i>", reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "<b>У вас нет доступа к админ-панели</b>", parse_mode='HTML')
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Статистика", callback_data="stats"))
    markup.add(types.InlineKeyboardButton("Рассылка", callback_data="broadcast"))
    
    bot.send_message(message.chat.id, "<b>Админ панель</b>", reply_markup=markup, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "top_players":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Сегодня", callback_data="players_today"))
        markup.add(types.InlineKeyboardButton("За всё время", callback_data="players_all"))
        markup.add(types.InlineKeyboardButton("Назад", callback_data="back_main"))
        bot.edit_message_text("<i>🧠 ТОП лучших игроков вселенной\n\nВыберите период:</i>",
                            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "top_chats":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Сегодня", callback_data="chats_today"))
        markup.add(types.InlineKeyboardButton("За всё время", callback_data="chats_all"))
        markup.add(types.InlineKeyboardButton("Назад", callback_data="back_main"))
        bot.edit_message_text("<i>🧠 ТОП лучших чатов\n\nВыберите период:</i>",
                            call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "players_today":
        users = db.all()
        today = datetime.now().strftime('%Y-%m-%d')
        sorted_users = sorted([u for u in users if u['today_date'] == today],
                            key=lambda x: x['today_iq'], reverse=True)[:15]
        response = "<i>🧠 ТОП лучших игроков СЕГОДНЯ:\n\n"
        for i, user in enumerate(sorted_users, 1):
            full_name = bot.get_chat_member(user['chat_id'], user['user_id']).user.full_name
            user_link = format_user_link(user['user_id'], full_name)
            response += f"{i}. {user_link} - {user['today_iq']} баллов\n"
        response += "</i>"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Назад", callback_data="top_players"))
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "players_all":
        users = sorted(db.all(), key=lambda x: x['iq_all'], reverse=True)[:15]
        response = "<i>🧠 ТОП лучших игроков ЗА ВСЁ ВРЕМЯ:\n\n"
        for i, user in enumerate(users, 1):
            full_name = bot.get_chat_member(user['chat_id'], user['user_id']).user.full_name
            user_link = format_user_link(user['user_id'], full_name)
            response += f"{i}. {user_link} - {user['iq_all']} баллов\n"
        response += "</i>"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Назад", callback_data="top_players"))
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "chats_today":
        today = datetime.now().strftime('%Y-%m-%d')
        chats = {}
        for user in db.all():
            if user['today_date'] == today and user.get('active_in_chats'):
                for chat_id in user['active_in_chats']:
                    if chat_id and chat_id < 0:
                        chats[chat_id] = chats.get(chat_id, 0) + user['today_iq']
        sorted_chats = sorted(chats.items(), key=lambda x: x[1], reverse=True)[:15]
        response = "<i>🧠 ТОП лучших чатов СЕГОДНЯ:\n\n"
        for i, (chat_id, iq) in enumerate(sorted_chats, 1):
            chat = bot.get_chat(chat_id)
            chat_name = chat.title or chat.username or f"Чат {chat_id}"
            response += f"{i}. {chat_name} - {iq} баллов\n"
        response += "</i>"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Назад", callback_data="top_chats"))
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "chats_all":
        chats = {}
        for user in db.all():
            if user.get('active_in_chats'):
                for chat_id in user['active_in_chats']:
                    if chat_id and chat_id < 0:
                        chats[chat_id] = chats.get(chat_id, 0) + user['iq_all']
        sorted_chats = sorted(chats.items(), key=lambda x: x[1], reverse=True)[:15]
        response = "<i>🧠 ТОП лучших чатов ЗА ВСЁ ВРЕМЯ:\n\n"
        for i, (chat_id, iq) in enumerate(sorted_chats, 1):
            chat = bot.get_chat(chat_id)
            chat_name = chat.title or chat.username or f"Чат {chat_id}"
            response += f"{i}. {chat_name} - {iq} баллов\n"
        response += "</i>"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Назад", callback_data="top_chats"))
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "back_main":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👤 Посмотреть ТОП игроков", callback_data="top_players"))
        markup.add(types.InlineKeyboardButton("👥 Посмотреть ТОП чатов", callback_data="top_chats"))
        bot.edit_message_text("🧠 ТОП лучших игроков и чатов",
                            call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif call.data == "stats":
        total_users = len(db.all())
        today = datetime.now().strftime('%Y-%m-%d')
        today_users = sum(1 for user in db.all() if 'today_date' in user and user['today_date'] == today)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Назад", callback_data="back"))
        stats_text = (
            "<b>📊 Статистика</b>\n\n"
            "<b>Активность:</b>\n"
            f"Сегодня: <code>{today_users}</code> пользователей\n"
            f"Всего: <code>{total_users}</code> пользователей"
        )
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data == "broadcast":
        bot.edit_message_text(
            "<b>Создание рассылки</b>\n\n"
            "Отправьте текст, фото, видео или стикер для рассылки.\n"
            "Текст может отсутствовать, если вы хотите отправить только медиа/кнопки.\n"
            "Поддерживается HTML:\n"
            "<b>жирный</b>, <i>курсив</i>, <code>код</code>, <a href='http://example.com'>ссылка</a>",
            call.message.chat.id, call.message.message_id, parse_mode='HTML'
        )
        bot.register_next_step_handler(call.message, process_broadcast_content)
    elif call.data == "back":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Статистика", callback_data="stats"))
        markup.add(types.InlineKeyboardButton("Рассылка", callback_data="broadcast"))
        bot.edit_message_text("<b>Админ панель</b>", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode='HTML')
    elif call.data.startswith("add_buttons|"):
        broadcast_id = call.data.split("|")[1]
        bot.send_message(call.message.chat.id, 
            "<b>Добавление кнопок</b>\n\n"
            "Формат: <code>[Название | Ссылка]</code>\n"
            "Пример: <code>[YouTube | https://youtube.com]</code>\n\n"
            "Для нескольких кнопок - каждая с новой строки:\n"
            "<pre>"
            "[YouTube | https://youtube.com]\n"
            "[Telegram | https://t.me]"
            "</pre>",
            parse_mode='HTML'
        )
        bot.register_next_step_handler(call.message, process_broadcast_buttons, broadcast_id)
    elif call.data.startswith("send_broadcast|"):
        broadcast_id = call.data.split("|")[1]
        show_broadcast_preview(call.message, broadcast_id)
    elif call.data.startswith("confirm_broadcast|"):
        broadcast_id = call.data.split("|")[1]
        send_broadcast(call.message, broadcast_id)
    elif call.data.startswith("cancel_broadcast|"):
        broadcast_id = call.data.split("|")[1]
        bot.send_message(call.message.chat.id, "<b>Рассылка отменена</b>", parse_mode='HTML')
        if broadcast_id in broadcast_storage:
            del broadcast_storage[broadcast_id]

@bot.message_handler(func=lambda message: message.chat.type == 'private')
def handle_private_messages(message):
    send_welcome_message(message.chat.id)

def process_broadcast_content(message):
    if message.text == 'Отменить':
        bot.reply_to(message, "<b>Рассылка отменена</b>", reply_markup=types.ReplyKeyboardRemove(), parse_mode='HTML')
        return
    
    broadcast_data = {}
    if message.text:
        broadcast_data['text'] = message.text
    if message.photo:
        broadcast_data['photo'] = message.photo[-1].file_id
        if message.caption:  
            broadcast_data['text'] = message.caption
    if message.video:
        broadcast_data['video'] = message.video.file_id
        if message.caption:  
            broadcast_data['text'] = message.caption
    if message.text:
        broadcast_data['text'] = message.text
        if message.entities:
            broadcast_data['entities'] = message.entities
    if message.caption:
        broadcast_data['text'] = message.caption
        if message.caption_entities:
            broadcast_data['entities'] = message.caption_entities
    
    broadcast_id = str(uuid.uuid4())
    broadcast_storage[broadcast_id] = broadcast_data
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Добавить кнопки", callback_data=f"add_buttons|{broadcast_id}"))
    markup.add(types.InlineKeyboardButton("Отправить без кнопок", callback_data=f"send_broadcast|{broadcast_id}"))
    
    bot.reply_to(message, "<b>Хотите добавить кнопки к сообщению?</b>", reply_markup=markup, parse_mode='HTML')

def process_broadcast_buttons(message, broadcast_id):
    if message.text == 'Отменить':
        bot.reply_to(message, "<b>Рассылка отменена</b>", reply_markup=types.ReplyKeyboardRemove(), parse_mode='HTML')
        if broadcast_id in broadcast_storage:
            del broadcast_storage[broadcast_id]
        return
    
    markup = types.InlineKeyboardMarkup()
    buttons_text = message.text.split('\n')
    
    for button in buttons_text:
        if button.strip():
            match = re.match(r'\[(.*?)\s*\|\s*(https?://\S+)\]', button.strip())
            if match:
                button_text, url = match.groups()
                markup.add(types.InlineKeyboardButton(button_text, url=url))
            else:
                bot.reply_to(message, "<b>Ошибка в формате кнопки. Используйте [Название | Ссылка]</b>", parse_mode='HTML')
                if broadcast_id in broadcast_storage:
                    del broadcast_storage[broadcast_id]
                return
    
    broadcast_dict = broadcast_storage.get(broadcast_id, {})
    broadcast_dict['buttons'] = markup
    broadcast_storage[broadcast_id] = broadcast_dict
    
    show_broadcast_preview(message, broadcast_id)

def show_broadcast_preview(message, broadcast_id):
    broadcast_dict = broadcast_storage.get(broadcast_id, {})
    
    if 'photo' in broadcast_dict:
        bot.send_photo(message.chat.id, 
                      broadcast_dict['photo'], 
                      caption=broadcast_dict.get('text', ''), 
                      reply_markup=broadcast_dict.get('buttons'),
                      parse_mode='HTML')
    elif 'video' in broadcast_dict:
        bot.send_video(message.chat.id, 
                      broadcast_dict['video'],
                      caption=broadcast_dict.get('text', ''),
                      reply_markup=broadcast_dict.get('buttons'),
                      parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, 
                        broadcast_dict.get('text', ''),
                        reply_markup=broadcast_dict.get('buttons'),
                        parse_mode='HTML')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отправить", callback_data=f"confirm_broadcast|{broadcast_id}"))
    markup.add(types.InlineKeyboardButton("Отменить", callback_data=f"cancel_broadcast|{broadcast_id}"))
    bot.send_message(message.chat.id, "<b>Отправляем рассылку?</b>", reply_markup=markup, parse_mode='HTML')

def send_broadcast(message, broadcast_id):
    broadcast_dict = broadcast_storage.get(broadcast_id, {})
    
    success_count = 0
    failed_count = 0
    
    all_chats = set()
    for user in db.all():
        if 'active_in_chats' in user:
            all_chats.update(user['active_in_chats'])
    
    all_chats.discard(0)
    
    for chat_id in all_chats:
        try:
            if 'photo' in broadcast_dict:
                bot.send_photo(
                            chat_id,
                            broadcast_dict['photo'],
                            caption=broadcast_dict.get('text', ''),
                            caption_entities=broadcast_dict.get('entities'),
                            reply_markup=broadcast_dict.get('buttons')
                        )
            elif 'video' in broadcast_dict:
                bot.send_video(chat_id, 
                            broadcast_dict['video'],
                            caption=broadcast_dict.get('text', ''),
                            caption_entities=broadcast_dict.get('entities'),
                            reply_markup=broadcast_dict.get('buttons'),
                            parse_mode='HTML')
            else:
                bot.send_message(
                            chat_id,
                            broadcast_dict.get('text', ''),
                            entities=broadcast_dict.get('entities'),
                            reply_markup=broadcast_dict.get('buttons')
                        )
            success_count += 1
        except Exception as e:
            failed_count += 1
            logging.error(f"Ошибка отправки в чат {chat_id}: {str(e)}")
    
    bot.send_message(message.chat.id, 
                    f"<b>Рассылка завершена</b>\n"
                    f"Отправлено: <code>{success_count}</code> чатам\n"
                    f"Не удалось: <code>{failed_count}</code>",
                    parse_mode='HTML')
    
    if broadcast_id in broadcast_storage:
        del broadcast_storage[broadcast_id]

if __name__ == '__main__':
    set_default_commands()
    bot.polling(none_stop=True)