import logging
import asyncio
import pytz
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types, filters
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from robot import database
import aiohttp
from aiohttp import ClientSession
import json
import os
import re
import subprocess
from io import StringIO

logging.basicConfig(level=logging.INFO)

API_TOKEN = '6930561361:AAHPQs0K5PnQS_TuPsyNCM343TYXU5Xl8Nc'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

database.initialize()

class Form(StatesGroup):
    token = State()

class SettingsStates(StatesGroup):
    operator_link = State()
    site = State()
    work_link = State()
    help_text = State()
    edit_card = State()
    edit_btc = State()
    edit_ltc = State()

class EditPaymentDetailsState(StatesGroup):
    editing = State()

class AddPaymentPhotoState(StatesGroup):
    adding_photo = State()

class MailingStates(StatesGroup):
    mailing_text = State()
    mailing_photo = State()
    daily_mailing_time = State()

class ProductAddStates(StatesGroup):
    city = State()
    category = State()
    product_name = State()
    product_kladtype = State()
    product_price = State()

class EditCoefficientState(StatesGroup):
    editing = State()

async def daily_mailing_task():
    print("Задача ежедневной рассылки запущена.")
    moscow_tz = pytz.timezone('Europe/Moscow')
    while True:
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        now_msk = now_utc.astimezone(moscow_tz)
        mailings = database.get_daily_mailings()
        for mailing in mailings:
            mailing_time = datetime.strptime(mailing[1], "%H:%M").time()
            current_time_msk = now_msk.time()
            if current_time_msk >= mailing_time and (datetime.combine(datetime.today(), current_time_msk) - datetime.combine(datetime.today(), mailing_time)) < timedelta(minutes=1):
                tokens = database.get_tokens()
                for token in tokens:
                    bot_child = Bot(token=token[0])
                    users = database.get_users_by_token(token[0])
                    for user in users:
                        user_id = user[0]
                        try:
                            if mailing[3]:  
                                absolute_photo_path = os.path.abspath(mailing[3])
                                with open(absolute_photo_path, 'rb') as photo_file:
                                    await bot_child.send_photo(user_id, photo=photo_file, caption=mailing[2], parse_mode='HTML')
                            else:
                                await bot_child.send_message(user_id, text=mailing[2], parse_mode='HTML')
                        except Exception as e:
                            logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                        await bot_child.close()
        await asyncio.sleep(60)  

main_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.add(KeyboardButton("➕Добавить Бота"), KeyboardButton("🤖 Текущие Боты"))
main_keyboard.add(KeyboardButton("🧑🏼‍💻Настройки"))

cancel_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
cancel_keyboard.add(KeyboardButton("❌ Отмена"))

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("Привет, я создан для управления твоим Ботом.", reply_markup=main_keyboard)

@dp.message_handler(commands=['delete'])
async def delete_everything(message: types.Message):
    database.clear_database()

    await message.answer("База данных очищена.")

@dp.message_handler(lambda message: message.text == "➕Добавить Бота", state="*")
async def add_bot(message: types.Message, state: FSMContext):
    await state.finish()  
    await Form.token.set()
    await message.answer("Отправь мне токен бота:", reply_markup=cancel_keyboard)

@dp.message_handler(state=Form.token)
async def process_token(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("Добавление бота отменено.", reply_markup=main_keyboard)
        return

    tokens = message.text.split('\n')
    for token in tokens:
        try:
            temp_bot = Bot(token=token)
            bot_user = await temp_bot.get_me()
            username = bot_user.username
            await temp_bot.close()

            database.add_token(token, username)  # Добавляем токен в базу данных
            await message.answer(f"Бот @{username} успешно добавлен.", reply_markup=main_keyboard)
        except Exception as e:
            await message.answer(f"Ошибка с токеном {token}: {e}", reply_markup=main_keyboard)

    restart_main()
    await state.finish()

@dp.message_handler(commands=['get'])
async def get_database_info(message: types.Message):
    database_info = database.get_full_database_info()
    link = await upload_text(database_info)
    await message.answer(f"Вот ссылка на данные из базы данных: {link}")

@dp.message_handler(commands=['delcity'])
async def command_delete_city(message: types.Message):
    city_ids = message.get_args().replace(" ", "").split(",")
    deleted_ids = []
    for city_id in city_ids:
        if city_id.isdigit():
            database.delete_city(int(city_id))
            deleted_ids.append(city_id)
    if deleted_ids:
        await message.reply(f"Города с ID {', '.join(deleted_ids)} и все связанные с ними товары удалены.")
    else:
        await message.reply("Пожалуйста, укажите корректные ID городов.")

@dp.message_handler(commands=['delproduct'])
async def command_delete_product(message: types.Message):
    product_ids = message.get_args().replace(" ", "").split(",")
    deleted_ids = []
    for product_id in product_ids:
        if product_id.isdigit():
            database.delete_product(int(product_id))
            deleted_ids.append(product_id)
    if deleted_ids:
        await message.reply(f"Товары с ID {', '.join(deleted_ids)} удалены.")
    else:
        await message.reply("Пожалуйста, укажите корректные ID товаров.")

@dp.message_handler(lambda message: message.text == "🤖 Текущие Боты", state="*")
async def current_bots(message: types.Message, state: FSMContext):
    await state.finish()
    bots = database.get_tokens()
    bots_info = StringIO()

    for index, bot in enumerate(bots, start=1):
        token, username = bot
        bots_info.write(f"{index}. Юзернейм: @{username}, Токен:\n{token}\n\n")

    bots_info.seek(0)
    await message.answer_document(types.InputFile(bots_info, filename="bots_info.txt"))

@dp.callback_query_handler(filters.Text(startswith="delete_"))
async def delete_bot(callback_query: types.CallbackQuery):
    bot_id = callback_query.data.split('_')[1]
    database.delete_token(bot_id)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id, 
                           "Бот успешно удален, изменения вступят в силу после перезапуска основного скрипта.")
    restart_main()

@dp.message_handler(lambda message: message.text == "🧑🏼‍💻Настройки", state="*")
async def settings(message: types.Message, state: FSMContext):
    await state.finish()
    total_users_count = database.get_total_users_count()  

    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(
        InlineKeyboardButton("Добавить товары", callback_data="settings_products"),
        InlineKeyboardButton("Саппорт", callback_data="edit_help"),
        InlineKeyboardButton("Оператор", callback_data="edit_operator"),
        InlineKeyboardButton("Работа", callback_data="edit_work"),
        InlineKeyboardButton("Сайт", callback_data="edit_site"), 
        InlineKeyboardButton("Реквезиты", callback_data="payment"),
        InlineKeyboardButton("Рассылка", callback_data="settings_mailing"),
        InlineKeyboardButton("Ежедневные рассылки", callback_data="daily_mailing_check")
    )
    settings_text = "Выберите, что хотите сделать:\n\nОбщее количество пользователей: " + str(total_users_count)
    await message.answer(settings_text, reply_markup=inline_kb)

@dp.callback_query_handler(lambda c: c.data == 'edit_operator')
async def edit_operator_link(callback_query: types.CallbackQuery):
    await SettingsStates.operator_link.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите новую ссылку для 'Оператор':",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_settings"))
    )

@dp.callback_query_handler(lambda c: c.data == 'edit_work')
async def edit_work_link(callback_query: types.CallbackQuery):
    await SettingsStates.work_link.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите новую ссылку для 'Работа':",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_settings"))
    )

@dp.callback_query_handler(lambda c: c.data == 'edit_site')
async def edit_site(callback_query: types.CallbackQuery):
    await SettingsStates.site.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите новую ссылку для 'Сайт':",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_settings"))
    )

@dp.message_handler(state=SettingsStates.site)
async def process_new_site(message: types.Message, state: FSMContext):
    new_link = message.text
    database.set_site(new_link)
    await state.finish()
    await message.answer("Ссылка 'Сайт' обновлена.")

@dp.message_handler(state=SettingsStates.operator_link)
async def process_new_operator_link(message: types.Message, state: FSMContext):
    new_link = message.text
    database.set_operator_link(new_link)
    await state.finish()
    await message.answer("Ссылка 'Оператор' обновлена.")

@dp.message_handler(state=SettingsStates.work_link)
async def process_new_work_link(message: types.Message, state: FSMContext):
    new_link = message.text
    database.set_work_link(new_link)
    await state.finish()
    await message.answer("Ссылка 'Работа' обновлена.")

@dp.callback_query_handler(lambda c: c.data == 'settings_products')
async def add_product_start(callback_query: types.CallbackQuery):
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await bot.send_message(callback_query.from_user.id, "Введите название города:", reply_markup=markup)
    await ProductAddStates.city.set()

@dp.message_handler(state=ProductAddStates.city, content_types=types.ContentTypes.TEXT)
async def process_city(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['city'] = message.text
    await bot.send_message(message.chat.id, "Введите название товара:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.product_name.set()

@dp.message_handler(state=ProductAddStates.product_name, content_types=types.ContentTypes.TEXT)
async def process_product_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['product_name'] = message.text
    await bot.send_message(message.chat.id, "Введите тип товара (тайник или др.), если его нет, отправьте <code>0</code>:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")), parse_mode="HTML")
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_kladtype, content_types=types.ContentTypes.TEXT)
async def process_product_kladtype(message: types.Message, state: FSMContext):
    kladtype = message.text
    async with state.proxy() as data:
        data['product_kladtype'] = kladtype
    await bot.send_message(message.chat.id, 
                           "Введите данные в формате: *грамм:цена(районы)*\n\nПример:\n0.5г:1500(центр, суздальский)\n1г:1900(центр, суздальский)\n1.5г:2200(центр, суздальский)", 
                           reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")), 
                           parse_mode="HTML")
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_price, content_types=types.ContentTypes.TEXT)
async def process_product_price(message: types.Message, state: FSMContext):
    price_data = message.text
    price_entries = price_data.split('\n')

    async with state.proxy() as data:
        city_id = database.add_city_if_not_exists(data['city'])

        for entry in price_entries:
            try:
                weight_price, districts = entry.split('(')
                districts = districts.strip(')')
                weight, price = weight_price.split(':')
                price = float(price.strip())

                product_name_with_weight = f"{data['product_name']} {weight}"
                product_id = database.add_product(product_name_with_weight, city_id)
                database.add_product_details(product_id, data['product_kladtype'], price, districts)
            except ValueError as e:
                await message.answer(f"Ошибка при обработке строки '{entry}': {e}")
                continue

        await message.answer("Товары успешно добавлены.", parse_mode="HTML")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'settings_mailing')
async def mailing_start(callback_query: types.CallbackQuery):
    await bot.send_message(
        callback_query.from_user.id,
        "Введите текст сообщения для рассылки (поддерживается HTML разметка):",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await MailingStates.mailing_text.set()

@dp.message_handler(state=MailingStates.mailing_text, content_types=types.ContentTypes.TEXT)
async def process_mailing_text(message: types.Message, state: FSMContext):
    await state.update_data(mailing_text=message.text)
    skip_photo_button = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="skip_photo"))
    await message.answer("Теперь отправьте фотографию для рассылки или нажмите 'Пропустить'", reply_markup=skip_photo_button)
    await MailingStates.next()

@dp.callback_query_handler(lambda c: c.data == 'skip_photo', state=MailingStates.mailing_photo)
async def skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(mailing_photo=None)
    data = await state.get_data()
    mailing_text = data['mailing_text']
    await bot.send_message(
        callback_query.from_user.id,
        "Вы пропустили добавление фото.\n\n" + mailing_text,
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("🕝 Ежедневная рассылка", callback_data="daily_mailing")
        ).add(InlineKeyboardButton("❌ Отменить", callback_data="cancel")),
        parse_mode='HTML'
    )

@dp.message_handler(content_types=['photo'], state=MailingStates.mailing_photo)
async def process_mailing_photo(message: types.Message, state: FSMContext):
    file_info = await bot.get_file(message.photo[-1].file_id)
    file_url = f'https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}'
    file_name = f"temp_{message.photo[-1].file_id}.jpg"
    await download_file(file_url, file_name)
    await state.update_data(mailing_photo=file_name)
    data = await state.get_data()
    mailing_text = data['mailing_text']
    await message.answer(
        "Все верно?\n\n" + mailing_text,
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("🕝 Ежедневная рассылка", callback_data="daily_mailing")
        ).add(InlineKeyboardButton("❌ Отменить", callback_data="cancel")),
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == 'confirm_send', state=MailingStates.mailing_photo)
async def confirm_and_send_mailing(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mailing_text = data['mailing_text']
    mailing_photo = data.get('mailing_photo')

    tokens = database.get_tokens()
    for token in tokens:
        bot_token = token[0]
        users = database.get_users_by_token(bot_token)
        bot_child = Bot(token=bot_token)

        for user in users:
            user_id = user[0]
            try:
                if mailing_photo:
                    absolute_photo_path = os.path.abspath(mailing_photo)
                    with open(absolute_photo_path, 'rb') as photo_file:
                        await bot_child.send_photo(user_id, photo=photo_file, caption=mailing_text, parse_mode='HTML')
                else:
                    await bot_child.send_message(user_id, text=mailing_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

        await bot_child.close()

    if mailing_photo:
        os.remove(mailing_photo)  

    await bot.answer_callback_query(callback_query.id, "Рассылка выполнена.")
    await state.finish()
   
@dp.callback_query_handler(lambda c: c.data == 'daily_mailing', state=MailingStates.mailing_photo)
async def request_daily_mailing_time(callback_query: CallbackQuery, state: FSMContext):
    await bot.send_message(
        callback_query.from_user.id,
        "Введите время для ежедневной рассылки в формате ЧЧ:ММ (например, 17:00):"
    )
    await MailingStates.daily_mailing_time.set()

@dp.message_handler(state=MailingStates.daily_mailing_time, content_types=types.ContentTypes.TEXT)
async def set_daily_mailing_time(message: Message, state: FSMContext):
    time = message.text

    
    if not re.match(r"^(2[0-3]|[01]?[0-9]):([0-5]?[0-9])$", time):
        await message.reply("Пожалуйста, введите время в правильном формате (например, 17:00).")
        return

    data = await state.get_data()
    mailing_text = data['mailing_text']
    mailing_photo = data.get('mailing_photo', None)
    mailing_photo_path = os.path.abspath(mailing_photo) if mailing_photo else None

    
    database.add_daily_mailing(time, mailing_text, mailing_photo_path)

    await bot.send_message(
        message.chat.id,
        f"Ежедневная рассылка задана на {time}."
    )
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'cancel_mail', state="*")
async def cancel_mailing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Рассылка отменена.")
    await bot.send_message(callback_query.from_user.id, "Рассылка отменена.")

@dp.callback_query_handler(lambda c: c.data == 'cancel_settings', state="*")
async def cancel_mailing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Отменено.")
    await bot.send_message(callback_query.from_user.id, "Отменено.")

@dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
async def cancel_mailing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Отменено.")
    await bot.send_message(callback_query.from_user.id, "Отменено.")

@dp.callback_query_handler(lambda c: c.data == 'daily_mailing_check')
async def check_daily_mailings(callback_query: types.CallbackQuery):
    mailings = database.get_daily_mailings()
    if not mailings:
        await bot.send_message(callback_query.from_user.id, "Ежедневные рассылки отсутствуют.")
        return

    markup = InlineKeyboardMarkup()
    for mailing in mailings:
        button_text = f"{mailing[1]} - {mailing[2][:10]}..."  
        callback_data = f"view_{mailing[0]}"  
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await bot.send_message(callback_query.from_user.id, "Вот текущие ежедневные рассылки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('view_'))
async def view_daily_mailing(callback_query: types.CallbackQuery):
    mailing_id = int(callback_query.data.split('_')[1])
    mailing = database.get_daily_mailing_by_id(mailing_id)
    
    if not mailing:
        await bot.answer_callback_query(callback_query.id, "Рассылка не найдена.")
        return

    text = f"Текст: {mailing[2]}\nВремя: {mailing[1]}"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑 Удалить", callback_data=f"deletemail_{mailing[0]}"))

    if mailing[3]:
        with open(os.path.abspath(mailing[3]), 'rb') as photo_file:
            await bot.send_photo(callback_query.from_user.id, photo=photo_file, caption=text, reply_markup=markup)
    else:
        await bot.send_message(callback_query.from_user.id, text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('deletemail_'))
async def delete_daily_mailing_handler(callback_query: types.CallbackQuery):
    mailing_id = int(callback_query.data.split('_')[1])
    mailing = database.get_daily_mailing_by_id(mailing_id)

    if mailing and mailing[3]:
        try:
            os.remove(os.path.abspath(mailing[3]))  
        except Exception as e:
            logging.error(f"Ошибка при удалении файла: {e}")

    database.delete_daily_mailing(mailing_id)

    
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

    
    mailings = database.get_daily_mailings()
    if not mailings:
        await bot.send_message(callback_query.from_user.id, "Ежедневные рассылки отсутствуют.")
        return

    markup = InlineKeyboardMarkup()
    for mailing in mailings:
        button_text = f"{mailing[1]} - {mailing[2][:10]}..."  
        callback_data = f"view_{mailing[0]}"  
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await bot.send_message(callback_query.from_user.id, "Вот текущие ежедневные рассылки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'edit_help')
async def edit_help(callback_query: types.CallbackQuery):
    current_text = database.get_help_text()
    await bot.send_message(
        callback_query.from_user.id,
        f"Введите новую ссылку для помощи:\n\nТекущая:\n{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.help_text.set()

@dp.message_handler(state=SettingsStates.help_text)
async def process_new_help_text(message: types.Message, state: FSMContext):
    new_text = message.text
    database.set_help_text(new_text)
    await message.answer("Ссылка помощи обновлен.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'payment')
async def payment_options(callback_query: types.CallbackQuery):
    payment_methods = database.get_payment_methods()
    enabled_method_types = {method[0] for method in payment_methods}

    method_order = ['card', 'sbp', 'btc', 'ltc']  # Желаемый порядок методов
    method_names = {
        'card': 'Карта',
        'sbp': 'СБП',
        'btc': 'Биткоин',
        'ltc': 'Лайткоин'
    }

    inline_kb = InlineKeyboardMarkup(row_width=1)
    for method_type in method_order:
        if method_type in enabled_method_types:
            inline_kb.add(InlineKeyboardButton(method_names[method_type], callback_data=f"options_{method_type}"))

    await callback_query.message.edit_text(
        "Выберите метод оплаты для изменения:",
        reply_markup=inline_kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith('options_'))
async def payment_method_options(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = callback_query.data.split('_')[1]
    await state.update_data(payment_type=payment_type)

    inline_kb = InlineKeyboardMarkup(row_width=1)
    inline_kb.add(InlineKeyboardButton("Изменить реквизиты", callback_data=f"editpayment_{payment_type}"))
    inline_kb.add(InlineKeyboardButton("Изменить коэффициент", callback_data=f"editcoefficient_{payment_type}"))
    if payment_type in ['btc', 'ltc']:
        inline_kb.add(InlineKeyboardButton("Добавить фото", callback_data=f"add_photo_{payment_type}"))
    
    current_status = database.get_payment_method_status(payment_type)
    status_button_text = "Выключить" if current_status else "Включить"
    inline_kb.add(InlineKeyboardButton(status_button_text, callback_data=f"toggle_status_{payment_type}"))

    await callback_query.message.edit_text(
        f"Выберите действие для '{payment_type}':",
        reply_markup=inline_kb
    )
@dp.callback_query_handler(lambda c: c.data.startswith('editcoefficient_'))
async def edit_coefficient(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = callback_query.data.split('_')[1]
    current_coefficient = database.get_payment_coefficient(payment_type)
    await state.update_data(payment_type=payment_type)

    await callback_query.message.edit_text(
        f"Введите новый коэффициент для '{payment_type}':\n\nТекущий: {current_coefficient}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await EditCoefficientState.editing.set()

@dp.message_handler(state=EditCoefficientState.editing)
async def process_new_coefficient(message: types.Message, state: FSMContext):
    try:
        new_coefficient = float(message.text)
        payment_type = (await state.get_data()).get('payment_type')

        database.set_payment_coefficient(payment_type, new_coefficient)
        
        await message.answer(f"Коэффициент для '{payment_type}' обновлен на {new_coefficient}.")
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите действительное число.")

@dp.callback_query_handler(lambda c: c.data.startswith('editpayment_'))
async def edit_payment_details(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Введите новые реквизиты:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await EditPaymentDetailsState.editing.set()

@dp.callback_query_handler(lambda c: c.data.startswith('add_photo_'))
async def add_payment_photo(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Загрузите новое фото:",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await AddPaymentPhotoState.adding_photo.set()

@dp.message_handler(content_types=['photo'], state=AddPaymentPhotoState)
async def process_payment_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    photo_path = os.path.join(script_dir, f'photos/{photo.file_id}.jpg')

    os.makedirs(os.path.join(script_dir, 'photos'), exist_ok=True)

    await photo.download(destination_file=photo_path)

    payment_type = (await state.get_data()).get('payment_type')
    database.set_payment_photo(payment_type, photo_path)

    await message.answer(f"Фото для '{payment_type}' обновлено.")
    await state.finish()

@dp.message_handler(state=EditPaymentDetailsState.editing)
async def process_new_payment_details(message: types.Message, state: FSMContext):
    new_details = message.text
    payment_type = (await state.get_data()).get('payment_type')
    
    database.set_payment_details(payment_type, new_details)
    
    await message.answer(f"Реквизиты для '{payment_type}' обновлены.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('toggle_status_'))
async def toggle_payment_status(callback_query: types.CallbackQuery, state: FSMContext):
    payment_type = (await state.get_data()).get('payment_type')
    current_status = database.get_payment_method_status(payment_type)
    new_status = not current_status
    database.set_payment_method_status(payment_type, new_status)

    inline_kb = callback_query.message.reply_markup
    for button in inline_kb.inline_keyboard:
        if button[0].callback_data == callback_query.data:
            button[0].text = "Выключить" if new_status else "Включить"
            break

    await callback_query.message.edit_reply_markup(reply_markup=inline_kb)

@dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
async def cancel_editing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Редактирование отменено.")
    await bot.send_message(callback_query.from_user.id, "Редактирование отменено.", reply_markup=main_keyboard)

async def download_file(file_url, file_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            if resp.status == 200:
                with open(file_name, 'wb') as f:
                    f.write(await resp.read())

async def upload_text(get_text) -> str:
    async with ClientSession() as session:
        
        try:
            response = await session.post(
                "http://pastie.org/pastes/create",
                data={"language": "plaintext", "content": get_text}
            )
            get_link = response.url
            if "create" in str(get_link):
                raise Exception("Не удалось загрузить на первый хостинг")
        except Exception as e:
            
            response = await session.post(
                "https://www.friendpaste.com",
                json={"language": "text", "title": "", "snippet": get_text}
            )
            get_link = json.loads(await response.read())['url']

    return get_link

main_process = None

def start_main():
    global main_process

    if main_process is not None:
        main_process.terminate()
        main_process.wait()

    path_to_main_py = os.path.join(os.getcwd(), 'robot', 'main.py')

    main_process = subprocess.Popen(['python3', path_to_main_py], cwd='robot')

def restart_main():
    global main_process

    if main_process is not None:
        main_process.terminate()
        main_process.wait()

    path_to_main_py = os.path.join(os.getcwd(), 'robot', 'main.py')

    main_process = subprocess.Popen(['python3', path_to_main_py], cwd='robot')

async def on_startup(_):
    start_main()
    asyncio.create_task(daily_mailing_task())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
