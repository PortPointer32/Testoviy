import os
import sys
from aiogram import Dispatcher, types
import keyboards
import database
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.callback_data import CallbackData
import aiohttp
import random
import logging
import time
import json
from sys import path
import asyncio

path.append('')

logging.basicConfig(level=logging.INFO)

class ReplenishBalanceStates(StatesGroup):
    enter_amount = State()
    choose_method = State()
    choose_payment_method = State()

class CaptchaState(StatesGroup):
    input = State()

async def update_crypto_rates():
    global btc_price, ltc_price
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,litecoin&vs_currencies=rub'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            btc_price = data['bitcoin']['rub']
            ltc_price = data['litecoin']['rub']

async def periodic_crypto_update():
    while True:
        await update_crypto_rates()
        await asyncio.sleep(900)  

async def show_categories(message: types.Message):
    await message.answer("Выберите категорию:", reply_markup=get_inline_keyboard())
    
def get_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    cities = database.get_cities()
    city_buttons = [InlineKeyboardButton(city[1], callback_data=f"city_{city[0]}") for city in cities]
    
    for i in range(0, len(city_buttons), 2):
        buttons_to_add = city_buttons[i:i+2]
        markup.row(*buttons_to_add)

    operator_url = database.get_operator_link()
    help_url = database.get_help_text()
    work_url = database.get_work_link()

    
    markup.add(InlineKeyboardButton("Баланс (0 руб.)", callback_data="balance"))
    markup.add(InlineKeyboardButton("Мои боты", callback_data="my_bots"))
    markup.add(InlineKeyboardButton("Реферальная программа", callback_data="referall"))
    markup.add(InlineKeyboardButton("Последний заказ", callback_data="last_order"))
    markup.add(InlineKeyboardButton("Бонус", callback_data="bon_us"))
    markup.add(InlineKeyboardButton("Оператор", url=operator_url))
    markup.add(InlineKeyboardButton("Тех.поддержка", url=help_url))
    markup.add(InlineKeyboardButton("Работа", url=work_url))

    return markup

async def update_crypto_rates():
    global btc_price, ltc_price
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,litecoin&vs_currencies=rub'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            btc_price = data['bitcoin']['rub']
            ltc_price = data['litecoin']['rub']

async def periodic_crypto_update():
    while True:
        await update_crypto_rates()
        await asyncio.sleep(900)  

btc_price = 0
ltc_price = 0

def correct_minute_form(minutes):
    if 10 <= minutes % 100 <= 20:
        return 'минут'
    elif minutes % 10 == 1:
        return 'минуту'
    elif 2 <= minutes % 10 <= 4:
        return 'минуты'
    else:
        return 'минут'

async def send_random_captcha(message: types.Message, state: FSMContext):
    captcha_dir = os.path.join(os.path.dirname(__file__), '..', 'captcha')
    
    captcha_files = [f for f in os.listdir(captcha_dir) if f.endswith('.jpg')]
    
    if not captcha_files:
        await message.answer("Ошибка: файлы капчи не найдены.")
        return
    
    captcha_file = random.choice(captcha_files)
    captcha_path = os.path.join(captcha_dir, captcha_file)

    with open(captcha_path, 'rb') as photo:
        await message.answer_photo(
            photo=photo, 
            caption=f"Привет {message.from_user.first_name}. Пожалуйста, решите капчу с цифрами на этом изображении, чтобы убедиться, что вы человек."
        )
        async with state.proxy() as data:
            data['captcha_answer'] = captcha_file.rstrip('.jpg')

async def register_handlers(dp: Dispatcher, bot_token):
    @dp.message_handler(commands=['start'], state="*")
    async def cmd_start(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        if not database.check_user_exists(user_id, bot_token):
            await CaptchaState.input.set()
            await send_random_captcha(message, state)
        else:
            await state.finish()
            await message.answer("Привет", reply_markup=keyboards.main_keyboard())
            await show_categories(message)
    
    @dp.message_handler(state=CaptchaState.input)
    async def handle_captcha_input(message: types.Message, state: FSMContext):
        async with state.proxy() as data:
            correct_answer = data.get('captcha_answer')
        
        if message.text == correct_answer:
            user_id = message.from_user.id
            database.add_user(user_id, bot_token)  
            await state.finish()
            await message.answer("Привет", reply_markup=keyboards.main_keyboard())
            await show_categories(message)
        else:
            await send_random_captcha(message, state)

    @dp.message_handler(lambda message: message.text == "Главное меню", state="*")
    async def handle_main_menu(message: types.Message, state: FSMContext):
        await state.finish()
        await show_categories(message)

    @dp.callback_query_handler(lambda c: c.data == 'last_order')
    async def initiate_replenish_balance(callback_query: types.CallbackQuery):
        await callback_query.answer()
        await ReplenishBalanceStates.enter_amount.set()
        await callback_query.message.answer("точно по метке 2-3 см , синяю изо,точно по кординатам \nhttps://deposit.pictures/p/fkfmvfrk78efedec06oexxdcd18\nhttps://deposit.pictures/p/pocdemdcev54edce5cldeik54kc")

        @dp.callback_query_handler(lambda c: c.data == 'bon_us')
        async def handle_bon_us(callback_query: types.CallbackQuery):
            await callback_query.answer("Для получения бонуса совершите 5 покупок в течении текущей недели", show_alert=True)
    
    @dp.callback_query_handler(lambda c: c.data == 'balance')
    async def initiate_replenish_balance(callback_query: types.CallbackQuery):
        await callback_query.answer()
        await ReplenishBalanceStates.enter_amount.set()
        await callback_query.message.answer("Введите сумму на которую вы хотите пополнить баланс:")
    
    @dp.message_handler(state=ReplenishBalanceStates.enter_amount)
    async def enter_replenish_amount(message: types.Message, state: FSMContext):
        if not message.text.isdigit() or int(message.text) < 1000:
            await message.reply("Введите корректную сумму (не менее 1000 рублей).")
        else:
            await state.update_data(amount=int(message.text))
            await ReplenishBalanceStates.choose_payment_method.set()
    
            enabled_methods = database.get_enabled_payment_methods()
            enabled_method_types = [method[0] for method in enabled_methods]
            
            method_order = ['card', 'sbp', 'btc', 'ltc']  # Желаемый порядок методов
            inline_kb = InlineKeyboardMarkup(row_width=1)
    
            for method in method_order:
                if method in enabled_method_types:
                    method_label = {
                        'card': "Оплата на карту💳",
                        'sbp': "Оплата СБП",
                        'btc': "Bitcoin",
                        'ltc': "Litecoin"
                    }.get(method, method.upper())
                    inline_kb.add(InlineKeyboardButton(method_label, callback_data=f"method_{method}"))
    
            await message.answer("Выберите способ оплаты:", reply_markup=inline_kb)
    
    @dp.callback_query_handler(state=ReplenishBalanceStates.choose_payment_method)
    async def choose_payment_method(callback_query: types.CallbackQuery, state: FSMContext):
        payment_method = callback_query.data.split('_')[1]
        await state.update_data(payment_method=payment_method)
        user_data = await state.get_data()
        amount = user_data['amount']
        order_number = ''.join([str(random.randint(0, 9)) for _ in range(8)])
    
        payment_details_raw, photo_path = database.get_payment_details(payment_method)
        payment_details_list = payment_details_raw.split('\n')
        payment_details = random.choice(payment_details_list)
    
        final_amount = calculate_final_amount(amount, payment_method)
        currency = payment_method.upper()

    
        if payment_method in ['btc', 'ltc']:
            await callback_query.message.answer_photo(
                photo=open(photo_path, 'rb') if photo_path else None,
                caption=f"Оплатите <b>{final_amount}</b> {currency} на адрес <b>{payment_details}</b>",
                parse_mode='HTML'
            )
        elif payment_method == 'sbp':
            instructions = get_payment_instructions(order_number, final_amount)
            await callback_query.message.answer(text=instructions, parse_mode='HTML')
            await callback_query.message.answer(
                f"Заявка № {order_number}. Для оплаты, переведите через СБП на этот номер счета:\n\n"
                f"<b>Райффайзен Банк\n{payment_details}</b>\n\n"
                f"Сумма <b>{final_amount}</b> руб.\n\n"
                "‼️ Перевёл на другой банк/киви/теле2 - ДЕНЬГИ ПОТЕРЯЛ\n"
                "‼️ это НЕ НОМЕР ТЕЛЕФОНА а НОМЕР СЧЕТА\n"
                "‼️ у вас есть 30 мин на оплату, после чего платёж не будет зачислен\n"
                "‼️ ПЕРЕВЁЛ НЕТОЧНУЮ СУММУ - ОПЛАТИЛ ЧУЖОЙ ЗАКАЗ",
                parse_mode='HTML'
            )
        else:
            await callback_query.message.answer(text=get_payment_instructions(order_number, final_amount), parse_mode='HTML')
            await callback_query.message.answer(
                f"Заявка на оплату № {order_number}. Переведите на банковскую карту <b>{final_amount}</b> рублей удобным для вас способом. Важно пополнить ровную сумму.\n<b>{payment_details}</b>\n‼️ это <b>НЕ СБЕРБАНК!</b>\n‼️ у вас есть 30 мин на оплату, после чего платёж не будет зачислен\n<b>‼️ ПЕРЕВЁЛ НЕТОЧНУЮ СУММУ - ОПЛАТИЛ ЧУЖОЙ ЗАКАЗ</b>",
                parse_mode='HTML'
            )
    
        current_time = time.time()
        payment_issue_callback_data = f"issue_{current_time}"
        await callback_query.message.answer(
            "Если в течение часа средства не выдались автоматически, то нажмите на кнопку - 'Проблема с оплатой'",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Проблема с оплатой?", callback_data=payment_issue_callback_data))
        )
        await state.finish()

    @dp.callback_query_handler(lambda c: c.data.startswith('city_'))
    async def process_city_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        city_id = int(callback_query.data.split('_')[1])
    
        products = database.get_products_by_city(city_id)
        markup = InlineKeyboardMarkup(row_width=1)
        for product in products:
            product_name = product[1]
            product_id = product[0]
            price = int(database.get_product_price(product_id))
            markup.add(InlineKeyboardButton(f"{product_name} ({price} руб.)", callback_data=f"product_{product_id}_{city_id}"))
        await callback_query.message.answer("Выберите продукт", reply_markup=markup)
    
    @dp.callback_query_handler(lambda c: c.data.startswith('product_'))
    async def process_product_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        product_id, city_id = map(int, callback_query.data.split('_')[1:])
    
        product_details = database.get_product_details(product_id)
        markup = InlineKeyboardMarkup(row_width=1)
        for detail in product_details:
            districts = detail[2].split(',')
            for district in districts:
                markup.add(InlineKeyboardButton(district, callback_data=f"district_{product_id}_{city_id}_{district}"))
    
        await callback_query.message.answer("выберите район", reply_markup=markup)
    @dp.callback_query_handler(lambda c: c.data.startswith('district_'))
    async def process_district_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        _, product_id, city_id, district = callback_query.data.split('_')
    
        product_details = database.get_product_details(int(product_id))
    
        klad_types = set()
        for detail in product_details:
            types_in_detail = detail[0].split(',')
            klad_types.update(types_in_detail)
    
        if len(klad_types) > 1 and '0' in klad_types:
            klad_types.remove('0')
    
        if len(klad_types) == 1 and '0' in klad_types:
            await send_purchase_message(callback_query, int(product_id), int(city_id), district, '0')
            return
    
        markup = InlineKeyboardMarkup(row_width=1)
        for klad_type in klad_types:
            markup.add(InlineKeyboardButton(klad_type, callback_data=f"kladtype_{product_id}_{city_id}_{district}_{klad_type}"))
    
        await callback_query.message.answer("Выберите тип", reply_markup=markup)
    
    async def send_purchase_message(callback_query: types.CallbackQuery, product_id, city_id, district, klad_type):
        product_name = database.get_product_name(product_id)
        city_name = database.get_city_name(city_id)
        order_number = ''.join([str(random.randint(0, 9)) for _ in range(8)])
        klad_type_text = "" if klad_type == '0' else f" ({klad_type})"
    
        message_text = (
            f"Номер покупки № <b>{order_number}</b>\n"
            f"Город:<b> {city_name}</b>\n"
            f"Район(станция): <b>{district}</b>\n"
            f"Товар и объем: <b>{product_name}{klad_type_text}</b>\n"
            "Для проведения оплаты нажмите на кнопку <b>ОПЛАТИТЬ</b>\n"
            "После того, как Вы нажмете кнопку оплаты, у вас есть 30 минут на оплату"
        )
    
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("Оплатить", callback_data=f"pay_{order_number}_{product_id}"))
        markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    
        await callback_query.message.answer(message_text, reply_markup=markup, parse_mode='HTML')
    
    @dp.callback_query_handler(lambda c: c.data.startswith('kladtype_'))
    async def process_kladtype_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        _, product_id, city_id, district, klad_type = callback_query.data.split('_')
        await send_purchase_message(callback_query, int(product_id), int(city_id), district, klad_type)
        
    @dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
    async def process_payment(callback_query: types.CallbackQuery):
        await callback_query.answer()
        _, order_number, product_id = callback_query.data.split('_')
        product_id = int(product_id)
        price = database.get_product_price(product_id)
    
        enabled_methods = database.get_enabled_payment_methods()
        enabled_method_types = [method[0] for method in enabled_methods]
    
        method_order = ['card', 'sbp', 'btc', 'ltc']
        method_labels = {
            'card': "Оплата на карту💳",
            'sbp': "Оплата СБП",
            'btc': "Bitcoin",
            'ltc': "Litecoin"
        }
    
        inline_kb = InlineKeyboardMarkup(row_width=1)
        for method in method_order:
            if method in enabled_method_types:
                inline_kb.add(InlineKeyboardButton(method_labels[method], callback_data=f"method_{method}_{order_number}_{price}"))
    
        await callback_query.message.answer("Ваш актуальный баланс 0 руб..\nЧем вы будете оплачивать?", reply_markup=inline_kb)
    
    @dp.callback_query_handler(lambda c: c.data.startswith('method_'))
    async def buy_choose_payment_method(callback_query: types.CallbackQuery):
        await callback_query.answer()
        parts = callback_query.data.split('_')
        method = parts[1]
        order_number = parts[2]
        price = float(parts[3])
    
        payment_details_raw, photo_path = database.get_payment_details(method)
        payment_details_list = payment_details_raw.split('\n')
        payment_details = random.choice(payment_details_list)
    
        final_amount = calculate_final_amount(price, method)
        currency = method.upper()
    
        if method in ['btc', 'ltc']:
            photo = open(photo_path, 'rb') if photo_path else None
            caption = f"Оплатите <b>{final_amount}</b> {currency} на адрес <b>{payment_details}</b>"
            await callback_query.message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode='HTML'
            )
            if photo:
                photo.close()
        elif method == 'sbp':
            instructions = get_payment_instructions(order_number, final_amount)
            await callback_query.message.answer(text=instructions, parse_mode='HTML')
            await callback_query.message.answer(
                f"Заявка № {order_number}. Для оплаты, переведите через СБП на этот номер счета:\n\n"
                f"<b>Райффайзен Банк\n{payment_details}</b>\n\n"
                f"Сумма <b>{final_amount}</b> руб.\n\n"
                "‼️ Перевёл на другой банк/киви/теле2 - ДЕНЬГИ ПОТЕРЯЛ\n"
                "‼️ это НЕ НОМЕР ТЕЛЕФОНА а НОМЕР СЧЕТА\n"
                "‼️ у вас есть 30 мин на оплату, после чего платёж не будет зачислен\n"
                "‼️ ПЕРЕВЁЛ НЕТОЧНУЮ СУММУ - ОПЛАТИЛ ЧУЖОЙ ЗАКАЗ",
                parse_mode='HTML'
            )
        else:
            payment_instructions = get_payment_instructions(order_number, final_amount)
            await callback_query.message.answer(payment_instructions, parse_mode='HTML')
            await callback_query.message.answer(
                f"Заявка на оплату № {order_number}. Переведите на банковскую карту <b>{final_amount}</b> рублей удобным для вас способом.\n"
                f"<b>{payment_details}</b>\n‼️ это <b>НЕ СБЕРБАНК!</b>\n"
                "‼️ у вас есть 30 мин на оплату, после чего платёж не будет зачислен\n"
                "‼️ ПЕРЕВЁЛ НЕТОЧНУЮ СУММУ - ОПЛАТИЛ ЧУЖОЙ ЗАКАЗ",
                parse_mode='HTML'
            )
    
        current_time = time.time()
        payment_issue_callback_data = f"issue_{current_time}"
        await callback_query.message.answer(
            "Если в течение часа средства не выдались автоматически, то нажмите на кнопку - 'Проблема с оплатой'",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Проблема с оплатой?", callback_data=payment_issue_callback_data))
        )

    @dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
    async def handle_cancel(callback_query: types.CallbackQuery, state: FSMContext):
        await callback_query.answer()
        await state.finish()
        
        await show_categories(callback_query.message)
    @dp.callback_query_handler(lambda c: c.data.startswith('issue_'))
    async def issue(callback_query: types.CallbackQuery):
        parts = callback_query.data.split('_')
        issue_time = float(parts[1])  
    
        current_time = time.time()
        if current_time - issue_time < 1800:  
            time_left = int((1800 - (current_time - issue_time)) / 60)  
            minute_form = correct_minute_form(time_left)
            await callback_query.answer(f"Подождите еще {time_left} {minute_form} и в случае неполучения средств нажмите на кнопку еще раз.", show_alert=True)
        else:
            await callback_query.message.answer("Отправьте мне скриншот произведенной оплаты")

    @dp.callback_query_handler(lambda c: c.data == 'my_bots')
    async def handle_my_bots(callback_query: types.CallbackQuery):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Добавить бота", callback_data="add_bot"))
        await callback_query.message.answer("Ваши боты:\nУ вас нету ботов!", reply_markup=markup)
    
    @dp.callback_query_handler(lambda c: c.data == 'referall')
    async def handle_referall(callback_query: types.CallbackQuery):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Добавить бота", callback_data="add_bot"))
        await callback_query.message.answer(
            "Делитесь своими ботами с друзьями и получайте 150руб. с каждого его оплаченного заказа.\nВаши боты:\nУ вас нету ботов!",
            reply_markup=markup)
    
    @dp.callback_query_handler(lambda c: c.data == 'add_bot')
    async def handle_add_bot(callback_query: types.CallbackQuery):
        await callback_query.message.answer("Добавление бота доступно после первой покупки")


def calculate_final_amount(amount, payment_method):
    coefficient = database.get_payment_coefficient(payment_method)
    amount = float(amount) * coefficient

    if payment_method in ['card', 'sbp']:
        return round(amount)
    elif payment_method == 'btc':
        if btc_price and btc_price > 0:
            return round(amount / btc_price, 8)
        else:
            raise ValueError("Неверная цена BTC для расчета.")
    elif payment_method == 'ltc':
        if ltc_price and ltc_price > 0:
            return round(amount / ltc_price, 5)
        else:
            raise ValueError("Неверная цена LTC для расчета.")

def get_payment_instructions(order_number, amount):
    instructions = (
        f"✅ ВЫДАННЫЕ РЕКВИЗИТЫ ДЕЙСТВУЮТ 30 МИНУТ\n"
        f"✅ ВЫ ПОТЕРЯЕТЕ ДЕНЬГИ, ЕСЛИ ОПЛАТИТЕ ПОЗЖЕ\n"
        f"✅ ПЕРЕВОДИТЕ ТОЧНУЮ СУММУ. НЕВЕРНАЯ СУММА НЕ БУДЕТ ЗАЧИСЛЕНА.\n"
        f"✅ ОПЛАТА ДОЛЖНА ПРОХОДИТЬ ОДНИМ ПЛАТЕЖОМ.\n"
        f"✅ ПРОБЛЕМЫ С ОПЛАТОЙ? ПЕРЕЙДИТЕ ПО ССЫЛКЕ : <a href='http://ut2.guru/doctor'>doctor</a>(нажать)\n"
        f"Предоставить чек об оплате и\n"
        f"ID:  <b>{order_number}</b>\n"
        f"✅ С ПРОБЛЕМНОЙ ЗАЯВКОЙ ОБРАЩАЙТЕСЬ НЕ ПОЗДНЕЕ 24 ЧАСОВ С МОМЕНТА ОПЛАТЫ."
    )
    return instructions
