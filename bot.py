import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from datetime import datetime
# import requests
from aiogramcalendar import create_calendar, process_calendar_selection
import aiohttp
from config import API_TOKEN, WEATHER_TOKEN


# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
# For example use simple MemoryStorage for Dispatcher.
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# States
class BotStates(StatesGroup):
    started = State()
    picked_weather = State()
    picked_rates = State()
    picked_rates_date = State()


start_kb = types.ReplyKeyboardMarkup(resize_keyboard=True,)
start_kb.row('Погода', 'Курс UAH/USD')

rates_kb = types.ReplyKeyboardMarkup(resize_keyboard=True,)
rates_kb.row('Курс на сегодня', 'Курс на дату', 'Отмена')

cancel_kb = types.ReplyKeyboardMarkup(resize_keyboard=True,)
cancel_kb.row('Отмена')


# starting bot when user sends `/start` command
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await BotStates.started.set()
    await message.reply("Привет!\nВыбери что тебе интересно: погода или курс валют", reply_markup=start_kb)


# cancel everything
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals=['cancel', 'отмена'], ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await BotStates.started.set()
    await message.answer('Отменено.', reply_markup=start_kb)


# picking weather or currency rate
@dp.message_handler(state=BotStates.started)
async def first_pick(message: types.Message, state: FSMContext):
    if message.text == 'Погода':
        await BotStates.picked_weather.set()
        await message.answer("Введите город в котором нужна погода", reply_markup=cancel_kb)
    elif message.text == 'Курс UAH/USD':
        await BotStates.picked_rates.set()
        await message.answer("Курс валют запрашивается с официального сайта НБУ - bank.gov.ua", reply_markup=rates_kb)
    else:
        await message.reply("Нажмите на кнопку, выбери прогноз погоды или курс валют")


# picked currency rate
@dp.message_handler(state=BotStates.picked_rates)
async def currency_pick(message: types.Message, state: FSMContext):
    if message.text == 'Курс на сегодня':
        rate = await getcurrateuah()
        await message.answer(f'По данным НБУ курс UAH/USD сегодня {str(rate)}', reply_markup=start_kb)
        await BotStates.started.set()
    elif message.text == 'Курс на дату':
        await BotStates.picked_rates_date.set()
        await message.answer("Задайте дату: ", reply_markup=create_calendar())
    else:
        await message.answer("Выбери на какую дату нужен курс валют")


@dp.callback_query_handler(state=BotStates.picked_rates_date)
async def calendar_handle(callback_query):
    selected, date = await process_calendar_selection(bot, callback_query)
    if selected:
        rate = await getcurrateuah(date=date.strftime("%Y%m%d"))
        await bot.send_message(chat_id=callback_query.from_user.id,
                               text=f'По данным НБУ курс UAH/USD на {date.strftime("%d/%m/%Y")} - {str(rate)}',
                               reply_markup=start_kb)
        await BotStates.started.set()


# picked weather
@dp.message_handler(state=BotStates.picked_weather)
async def weather_pick(message: types.Message, state: FSMContext):
    c, w = await getweather(city=message.text)
    await message.answer(f"В городе {c['name_ru']} сейчас {w['weather'][0]['description']}, температура {w['main']['temp']}°C", reply_markup=start_kb)
    await BotStates.started.set()


async def getcurrateuah(currency='USD', date=datetime.now().strftime("%Y%m%d")):  # https://bank.gov.ua/ua/open-data/api-dev
    url = 'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=' + currency + '&date=' + date + '&json'
    print(url)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as res:
                res2 = await res.json()
        except Exception as inst:
            print(type(inst))
            print(inst.args)
            print(inst)
        else:
            print(res2)
            return res2[0]['rate']


async def getweather(city=''):
    url = 'https://noxplode.pythonanywhere.com/api/weather/' + city
    print(url)
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={'Authorization': WEATHER_TOKEN}) as res:
            print(res.status)
            res2 = await res.json()
            print(res2)
            c = res2['city']
            w = res2['weatherdata']
            return c, w


if __name__ == '__main__':
    executor.start_polling(dp)
