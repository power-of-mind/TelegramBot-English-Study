import os

import telebot
import random
from telebot import types, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

from connection_db import get_db_connection
from handlers_db import (
    initialize_db, ensure_user_exists, fill_common_words_table, get_random_words,
    get_word_id, check_user_word_relation, add_user_word_relation, add_word,
    delete_user_word_relation
)

# Определение команд
class Command:
    ADD_WORD = "Добавить слово ➕"
    DELETE_WORD = "Удалить слово 🔙"
    NEXT = "Следующее слово ➡️"

# Определение состояний
class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    other_words = State()
    adding_new_word = State()
    saving_new_word = State()
    deleting_word = State()

# Создание хранилища состояний
state_storage = StateMemoryStorage()

# Создание объекта бота
token_bot = os.getenv("TOKEN")
bot = telebot.TeleBot(token_bot, state_storage=state_storage)

common_words = [
    ("Peace", "Мир"), ("Green", "Зелёный"), ("White", "Белый"),
    ("Hello", "Привет"), ("Car", "Машина"), ("Sky", "Небо"),
    ("Tree", "Дерево"), ("Book", "Книга"), ("Love", "Любовь"),
    ("Friend", "Друг")
]

# Подключение к базе данных, создание таблиц, заполнение словаря
with get_db_connection() as conn:
    initialize_db()
    fill_common_words_table()

print('Start telegram bot...')

def create_cards(message):
    """Создает клавиатуру и карточки, определяет состояние."""
    cid = message.chat.id

    # Получаем случайные слова
    words = get_random_words(cid, limit=4)
    print(f"Случайные слова: {words}")

    if not words or len(words) < 4:
        bot.send_message(cid, "Нет доступных слов!\nДобавьте новые через 'Добавить слово ➕'.")
        print("Недостаточно слов для создания карточек.")
        return

    # Извлекаем целевое слово и другие варианты
    target_word, translate_word = words[0]
    other_words = [w[0] for w in words[1:]]

    # Перемешиваем варианты
    options = other_words + [target_word]
    random.shuffle(options)

    # Создаем клавиатуру
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [types.KeyboardButton(option) for option in options]
    buttons.append(types.KeyboardButton(Command.NEXT))
    buttons.append(types.KeyboardButton(Command.ADD_WORD))
    buttons.append(types.KeyboardButton(Command.DELETE_WORD))
    markup.add(*buttons)

    # Устанавливаем состояние для пользователя
    bot.set_state(user_id=message.from_user.id, chat_id=message.chat.id, state=MyStates.target_word)
    with bot.retrieve_data(user_id=message.from_user.id, chat_id=message.chat.id) as data:
        data["target_word"] = target_word
        data["translate_word"] = translate_word

    # Отправляем сообщение
    greeting = f"Выбери перевод слова:\n🇷🇺 {translate_word}"
    bot.send_message(cid, greeting, reply_markup=markup)

def send_main_menu(chat_id):
    """Отправляет основное меню."""
    markup = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [
        types.KeyboardButton(Command.ADD_WORD),
        types.KeyboardButton(Command.DELETE_WORD),
        types.KeyboardButton(Command.NEXT)
    ]
    markup.add(*buttons)
    bot.send_message(chat_id, "Выберите дальнейшее действие:", reply_markup=markup)

# # Обработчики

@bot.message_handler(commands=["start"])
def send_welcome(message):
    cid = message.chat.id
    username = message.chat.username or "Unknown"
    ensure_user_exists(cid, username)

    print("Starting bot for the first time...")

    # Отправка приветственного сообщения
    with open("sticker.png", "rb") as sti:
        bot.send_sticker(cid, sti)
    bot.send_message(cid, f"Приветствую, {message.from_user.first_name}!\nЯ {bot.get_me().first_name}! "
                              f"Начнём учить язык 🇬🇧\nУ тебя есть возможность использовать тренажёр,\nкак конструктор, "
                              f"и собирать свою собственную базу для обучения.\nДля этого воспользуйся инструментами:\n"
                              f"- добавить слово ➕\n"
                              f"- удалить слово 🔙\n"
                              f"Приступим ⬇️", parse_mode="html"
                         )
    create_cards(message)

@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_word(message):
    create_cards(message)

@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word_start(message):
    cid = message.chat.id
    bot.set_state(user_id=message.from_user.id, chat_id=cid, state=MyStates.adding_new_word)
    bot.send_message(cid, "Введите слово, которое вы хотите добавить, на английском:")

@bot.message_handler(state=MyStates.adding_new_word)
def handle_add_new_word(message):
    cid = message.chat.id
    target_word = message.text.strip().capitalize()

    # Проверка наличия слова в таблице words
    word_id = get_word_id(target_word)

    if word_id:
        # Слово есть, проверяем связь с пользователем
        relation_id = check_user_word_relation(cid, target_word)
        if relation_id:
            # Связь уже есть
            bot.send_message(cid, "Такое слово уже есть в вашем словаре.")
            send_main_menu(cid)
        else:
            # Связи нет, создаем
            add_user_word_relation(cid, target_word)
            bot.send_message(cid, f"Слово добавлено '{target_word}' успешно добавлено.")
        # Удаляем состояние
        bot.delete_state(user_id=message.from_user.id, chat_id=cid)
    else:
        # Слова нет, сохраняем в состояние и переходим к следующему шагу
        with bot.retrieve_data(user_id=message.from_user.id, chat_id=cid) as data:
            data["target_word"] = target_word
        bot.set_state(user_id=message.from_user.id, chat_id=cid, state=MyStates.saving_new_word)
        bot.send_message(cid, f"Теперь введите перевод для слова '{target_word}':")

@bot.message_handler(state=MyStates.saving_new_word)
def handle_save_new_word(message):
    cid = message.chat.id
    translate_word = message.text.strip().capitalize()

    # Извлекаем target_word из состояния
    with bot.retrieve_data(user_id=message.from_user.id, chat_id=cid) as data:
        target_word = data.get("target_word")
        if not target_word:
            bot.send_message(cid, "Ошибка: не найдено слово для сохранения. Начните заново.")
            bot.delete_state(user_id=message.from_user.id, chat_id=cid)
            return

    # Добавляем слово в таблицу words
    add_word(target_word, translate_word)

    # Создаем связь пользователя и слова
    add_user_word_relation(cid, target_word)

    # Отправляем сообщение
    bot.send_message(cid, f"Слово '{target_word}' и перевод '{translate_word}' успешно добавлены.")

    # Удаляем состояние
    bot.delete_state(user_id=message.from_user.id, chat_id=cid)
    send_main_menu(cid)

@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word_start(message):
    cid = message.chat.id
    bot.set_state(user_id=message.from_user.id, chat_id=message.chat.id, state=MyStates.deleting_word)
    bot.send_message(cid, "Введите слово, которое хотите удалить, на английском:")

@bot.message_handler(state=MyStates.deleting_word)
def handle_delete_word(message):
    cid = message.chat.id
    word_to_delete = message.text.strip()
    # Проверяем наличие слова в словаре
    word_id = get_word_id(word_to_delete)
    if word_id:
        # Проверяем наличие связи
        if check_user_word_relation(cid, word_to_delete):
            delete_user_word_relation(cid, word_to_delete)
            bot.send_message(cid, f"Слово '{word_to_delete}' успешно удалено.")
        else:
            bot.send_message(cid, "Слово не найдено в вашем словаре.")
    else:
        bot.send_message(cid, "Слово не найдено в вашем словаре.")
        bot.delete_state(user_id=message.from_user.id, chat_id=cid)
    send_main_menu(cid)

@bot.message_handler(func=lambda message: True, content_types=["text"])
def message_reply(message):
    user_response = message.text.strip()
    print(f"Ответ пользователя: {user_response}")

    # Проверяем текущее состояние
    state = bot.get_state(user_id=message.from_user.id, chat_id=message.chat.id)
    print(f"Полученное состояние для пользователя {message.from_user.id}, чат {message.chat.id}: {state}")

    if state != MyStates.target_word.name:
        bot.send_message(message.chat.id, "Ошибка! Начните заново со /start.")
        return

    # Извлекаем данные из состояния
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data.get("target_word")
        translate_word = data.get("translate_word")
        attempts = data.get("attempts", 0)
        print(f"Данные из состояний: target_word={target_word}, translate_word={translate_word}")

    if not target_word or not translate_word:
        bot.send_message(message.chat.id, "Ошибка! Попробуй снова начать со /start.")
        return

    # Если пользователь ответил правильно
    if user_response.strip().lower() == target_word.strip().lower():
        try:
            # update_word_to_user_dict(message.from_user.id, target_word, translate_word)
            bot.send_message(message.chat.id, f"✅ Правильно!\n{target_word} => {translate_word}!")
        except ValueError as e:
            print(f"Ошибка при обновлении слова: {e}")
        data.clear()
        return

    # Если пользователь ответил неправильно
    attempts += 1
    data["attempts"] = attempts
    if attempts < 3:
        bot.send_message(
            message.chat.id, f"❌ Неправильно! Попробуй снова.\nПеревод слова: {translate_word}\n"
                             f"Попытка {attempts} из 3."
        )
    else:
        bot.send_message(
            message.chat.id, f"К сожалению, вы исчерпали попытки.\n"f"Правильный перевод: {target_word}"
        )
        data.clear()

bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)