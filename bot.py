from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import API_TOKEN

import logging
import asyncio


# configuring loggint to console and file
file_handler = logging.FileHandler(filename='bot.log')
stdout_handler = logging.StreamHandler()
handlers = [file_handler, stdout_handler]

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(asctime)s - %(message)s', handlers=handlers)
logger = logging.getLogger('Bot Logger')

loop = asyncio.get_event_loop()

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN, parse_mode='HTML')
# For example use simple MemoryStorage for Dispatcher.
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage, loop=loop)


if __name__ == '__main__':
    from handlers import dp, send_to_admin
    executor.start_polling(dp, on_startup=send_to_admin)
