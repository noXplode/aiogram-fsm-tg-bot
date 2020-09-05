from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from bot import bot, dp
from config import WEATHER_TOKEN, ADMIN_ID
from aiogramcalendar import calendar_callback, create_calendar, process_calendar_selection

from datetime import datetime
import logging
import aiohttp


def get_new_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession()


# creating HTTP session
session = get_new_session()


# States
class BotStates(StatesGroup):
    started = State()
    picked_weather = State()
    picked_rates = State()
    picked_rates_date = State()


start_kb = ReplyKeyboardMarkup(resize_keyboard=True,)
start_kb.row('Погода', 'Курс UAH/USD')

rates_kb = ReplyKeyboardMarkup(resize_keyboard=True,)
rates_kb.row('Курс на сегодня', 'Курс на дату', 'Отмена')

cancel_kb = ReplyKeyboardMarkup(resize_keyboard=True,)
cancel_kb.row('Отмена')


async def send_to_admin(dp):    # when bot is starting procedure
    await bot.send_message(chat_id=ADMIN_ID, text='Бот запущен')


# starting bot when user sends `/start` command
@dp.message_handler(commands=['start'])
async def cmd_start(message: Message, state: FSMContext):
    await BotStates.started.set()
    logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, current state BotStates:started")
    await message.reply(f"Привет, {message['chat']['first_name']}!\nВыбери что тебе интересно: погода или курс валют", reply_markup=start_kb)


# cancel everything
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals=['cancel', 'отмена'], ignore_case=True), state='*')
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, Cancelling state {await state.get_state()}")
    # Cancel state and inform user about it
    await BotStates.started.set()
    await message.answer('Отменено.', reply_markup=start_kb)


# picking weather or currency rate
@dp.message_handler(state=BotStates.started)
async def first_pick(message: Message, state: FSMContext):
    if message.text == 'Погода':
        await BotStates.picked_weather.set()
        logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, current state BotStates:picked_weather")
        async with state.proxy() as data:   # if theres cities in users state then add them to keyboard
            logging.info(f"{message['chat']['id']}, {data}")
            if 'cities' in data:
                if len(data['cities']) > 3:     # limit cities to 3
                    data['cities'] = data['cities'][-3:]
                city_kb = ReplyKeyboardMarkup(resize_keyboard=True,)
                city_kb.row()
                for city in data['cities']:
                    city_kb.insert(KeyboardButton(city))
                city_kb.row('Отмена')
                await message.answer("Введите город в котором нужна погода или выберите из ранее вводимых Вами", reply_markup=city_kb)
            else:
                await message.answer("Введите город в котором нужна погода", reply_markup=cancel_kb)
    elif message.text == 'Курс UAH/USD':
        await BotStates.picked_rates.set()
        logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, current state BotStates:picked_rates")
        await message.answer("Курс валют запрашивается с официального сайта НБУ - bank.gov.ua", reply_markup=rates_kb)
    else:
        await message.reply("Нажмите на кнопку, выбери прогноз погоды или курс валют")


# picked currency rate
@dp.message_handler(state=BotStates.picked_rates)
async def currency_pick(message: Message, state: FSMContext):
    if message.text == 'Курс на сегодня':
        try:
            rates = await getcurrateuah(session=session)
        except Exception:
            await message.answer('Сайт НБУ недоступен, попробуйте позже', reply_markup=start_kb)
        else:
            await message.answer('По данным НБУ курс валют на сегодня:', reply_markup=start_kb)
            for key, value in rates.items():
                await message.answer(f'UAH/{key} - {str(value)}', reply_markup=start_kb)
        finally:
            await BotStates.started.set()
            logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, current state BotStates:started")
            await message.answer(f"{message['chat']['first_name']}, выбери что тебе интересно: погода или курс валют", reply_markup=start_kb)
    elif message.text == 'Курс на дату':
        await BotStates.picked_rates_date.set()
        logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, current state BotStates:picked_rates_date")
        await message.answer("Задайте дату: ", reply_markup=create_calendar())
    else:
        await message.answer("Выбери на какую дату нужен курс валют")


# calendar date pick callback handler
@dp.callback_query_handler(calendar_callback.filter(), state=BotStates.picked_rates_date)
async def calendar_handle(callback_query: CallbackQuery, callback_data: dict):
    selected, date = await process_calendar_selection(callback_query, callback_data)
    logging.info(f"{callback_query.message.chat.id}, picked currency rates date: {date}")
    if selected:
        if date <= datetime.now():
            try:
                rates = await getcurrateuah(session=session, date=date.strftime("%Y%m%d"))
            except Exception:
                await callback_query.message.answer('Сайт НБУ недоступен, попробуйте позже', reply_markup=start_kb)
            else:
                await callback_query.message.answer(f'По данным НБУ курс валют на {date.strftime("%d/%m/%Y")}:', reply_markup=start_kb)
                for key, value in rates.items():
                    await callback_query.message.answer(f'UAH/{key} - {str(value)}', reply_markup=start_kb)
            finally:
                await BotStates.started.set()
                logging.info(f"{callback_query['message']['chat']['id']} {callback_query['message']['chat']['first_name']} @{callback_query['message']['chat']['username']}, current state BotStates:started")
                await callback_query.message.answer(f"{callback_query['message']['chat']['first_name']}, выбери что тебе интересно: погода или курс валют", reply_markup=start_kb)
        else:
            await callback_query.message.answer('Невозможно узнать курс, дата из будущего.\nВыберите корректную дату:',
                                                reply_markup=create_calendar())


# picked weather
@dp.message_handler(state=BotStates.picked_weather)
async def weather_pick(message: Message, state: FSMContext):
    logging.info(f"{message['chat']['id']}, typed for weather: {message.text}")
    try:
        c, w = await getweather(session=session, city=message.text)
    except aiohttp.ClientError:
        await message.answer("Не могу узнать погоду. Возможно неверно введен город.\nПопробуйте заново", reply_markup=start_kb)
    else:
        logging.info(f"{message['chat']['id']}, returned weather data: {c['name_ru']}, {w['weather'][0]['description']}, {w['main']['temp']}")
        async with state.proxy() as data:   # when weather retrieved, adding city to users state
            if 'cities' in data:
                if not c['name_ru'] in data['cities']:
                    data['cities'].append(c['name_ru'])
            else:
                data['cities'] = [c['name_ru'], ]
        await message.answer(f"В городе {c['name_ru']} сейчас {w['weather'][0]['description']}, температура {w['main']['temp']}°C", reply_markup=start_kb)
    finally:
        await BotStates.started.set()
        logging.info(f"{message['chat']['id']} {message['chat']['first_name']} @{message['chat']['username']}, current state BotStates:started")
        await message.answer(f"{message['chat']['first_name']}, выбери что тебе интересно: погода или курс валют", reply_markup=start_kb)


async def getcurrateuah(session=session, currency=['USD', 'EUR', 'RUB'], date=datetime.now().strftime("%Y%m%d"), retry=False):  # https://bank.gov.ua/ua/open-data/api-dev
    url = 'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange'
    rates = {}
    for curr in currency:
        params = {'valcode': curr, 'date': date, 'json': ''}
        try:
            async with session.get(url, params=params) as res:
                data = await res.json()
        except aiohttp.client_exceptions.ClientConnectorError:
            logging.exception("bank.gov.ua ClientConnectorError")       # if ClientConnectorError retry
            if retry is False:
                logging.info("rates retry")
                return await getcurrateuah(session=session, currency=currency, date=date, retry=True)
            else:
                raise aiohttp.client_exceptions.ClientConnectorError
        else:
            rates[curr] = data[0]['rate']
    logging.info(f"{rates}")
    return rates


async def getweather(session=session, city=''):
    url = 'https://noxplode.pythonanywhere.com/api/weather/' + city
    async with session.get(url, headers={'Authorization': WEATHER_TOKEN}) as res:
        if res.status == 200:
            res2 = await res.json()
            c = res2['city']
            w = res2['weatherdata']
            return c, w
        else:
            logging.exception(f"possible error, request status {res.status}")
            raise aiohttp.ClientError
