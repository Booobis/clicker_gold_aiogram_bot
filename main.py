import asyncio, random
import aiosqlite
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiogram.types import Message
import config

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, limit=1):
        self.limit = limit
        self.chat_spam_count = {}

    async def on_pre_process_message(self, message: Message, data: dict):
        chat_id = message.chat.id

        if chat_id in self.chat_spam_count:
            if self.chat_spam_count[chat_id] >= self.limit:
                await message.answer("Хватит спамить!")
                raise CancelHandler()

            self.chat_spam_count[chat_id] += 1
        else:
            self.chat_spam_count[chat_id] = 1

class withdraw(StatesGroup):
    count = State()
    akk = State()

async def create_db():
    async with aiosqlite.connect('mydb.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS users (userid INTEGER PRIMARY KEY, balance INTEGER)')
        await db.commit()


async def get_user_balance(message: types.Message, gold):
    async with aiosqlite.connect('mydb.db') as db:
        user_id = message.from_user.id
        await db.execute('INSERT OR IGNORE INTO users (userid, balance) VALUES (?, ?)', (user_id, 0))
        await db.execute('UPDATE users SET balance = balance + ? WHERE userid = ?', (gold, user_id,))
        await db.commit()

    await message.answer(f'Вам выдано {gold} голды! 💰️')

async def add_user(message: types.Message):
    async with aiosqlite.connect('mydb.db') as db:
        user_id = message.from_user.id
        await db.execute('INSERT OR IGNORE INTO users (userid, balance) VALUES (?,?)', (user_id, 0))
        await db.commit()

async def get_balance(message: types.Message):
    async with aiosqlite.connect('mydb.db') as db:
        user_id = message.from_user.id
        f = await db.execute("SELECT balance FROM users WHERE userid =?", (user_id,))
        await db.commit()
        result = await f.fetchone()
        if result is not None:
            return result[0]
        else:
            return None
async def minus_balance(message: types.Message, gold):
    async with aiosqlite.connect('mydb.db') as db:
        user_id = message.from_user.id
        await db.execute('UPDATE users SET balance = balance -? WHERE userid =?', (gold,user_id,))

def kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Получить голду 💰️')
    btn2 = types.KeyboardButton('Профиль 🎫')
    btn3 = types.KeyboardButton('Вывести баланс 📥')
    kb.add(btn1, btn2, btn3)
    return kb

bot = Bot(token=config.token)
dp = Dispatcher(bot, storage=MemoryStorage())

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer('Привет! Это бот для заработка голды!')
    await add_user(message)
    await message.answer('Выберите действие:', reply_markup=kb())

@dp.message_handler(state=withdraw.count)
async def withdraw_count(message: types.Message, state: FSMContext):
    u = message.text
    if not isinstance(u, int):
        await state.finish()
        return await message.answer('Введите число!')
    await state.update_data(count=u)
    balance = await get_balance(message)
    if int(balance) >= int(u) > int(config.min):
        await bot.send_message(message.from_user.id, f'Введите ваш аккаунт:')
        await withdraw.akk.set()
    else:
        await bot.send_message(message.from_user.id, f'Недостаточно голды! Вывод от 200')

@dp.message_handler(state=withdraw.akk)
async def withdraw_akk(message: types.Message, state: FSMContext):
    await state.update_data(akk=message.text)
    u = message.text

    f = await state.get_data()
    await minus_balance(message, f["count"])

    await bot.send_message(message.from_user.id, f'Вы успешно вывели {f["count"]} голды!')
    k = types.InlineKeyboardMarkup()
    f = types.InlineKeyboardButton('Саппорт ️', url=f'https://t.me/{config.support}')
    k.add(f)
    await bot.send_message(config.support_id, f'Совершен вывод! {message.from_user.id}, gold: {f["count"]}')
    await bot.send_message(message.from_user.id, f'Отпишите саппорту для дальнейших действий', reply_markup=k)
    await state.finish()
@dp.message_handler(content_types=["text"])
async def all(msg: types.Message):
    if msg.text == 'Получить голду 💰️':
        gold = round(random.random(), 3)
        await get_user_balance(msg, gold)
    elif msg.text == 'Профиль 🎫':
        await bot.send_message(msg.from_user.id, f'''
Ваш профиль 🎫
Ваш уникальный айди: `{msg.from_user.id}`.

Ваш баланс: `{await get_balance(msg)}` голды.
''', reply_markup=kb(), parse_mode='Markdown')
    elif msg.text == 'Вывести баланс 📥':
        await bot.send_message(msg.from_user.id, f'Введите сумму вывода:')
        await withdraw.count.set()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db())
    executor.start_polling(dp, skip_updates=True)
    dp.middleware.setup(AntiSpamMiddleware(limit=1))
