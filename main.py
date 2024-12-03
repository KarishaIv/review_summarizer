from dotenv import load_dotenv
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from messages import WELCOME_MESSAGE, EATING_MESSAGE, STICKERS
import random

load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

async def send_message(chat_id: int, text: str, reply_markup=None):
    await bot.send_message(chat_id, text, reply_markup=reply_markup)

async def send_message_with_menu(chat_id: int, text: str):
    await send_message(chat_id, text, reply_markup=keyboard_reply)

async def send_sticker(chat_id: int, sticker_id: str):
    await bot.send_sticker(chat_id, sticker_id)

keyboard_inline = InlineKeyboardMarkup().add(InlineKeyboardButton(text="я хочу кушать...", callback_data="first_button"))
button_menu = KeyboardButton("в меню")
keyboard_reply = ReplyKeyboardMarkup(resize_keyboard=True).add(button_menu)
keyboard_eating = InlineKeyboardMarkup().add(
    InlineKeyboardButton(text="один", callback_data="button_one"),
    InlineKeyboardButton(text="два", callback_data="button_two")
)

@dp.callback_query_handler(text=["first_button"])
async def check_button(call: types.CallbackQuery):
    await send_message(call.message.chat.id, EATING_MESSAGE, reply_markup=keyboard_eating)
    await call.answer()

@dp.message_handler(commands=['kushat'])
async def help_command(message: types.Message):
    await send_message(message.chat.id, EATING_MESSAGE, reply_markup=keyboard_eating)

'''     старт      '''
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await send_message(message.chat.id, WELCOME_MESSAGE, reply_markup=keyboard_inline)

@dp.message_handler(lambda message: message.text == "в меню")
async def menu_button_click(message: types.Message):
    await send_message_with_menu(message.chat.id, WELCOME_MESSAGE)

'''     menu      '''
@dp.message_handler(commands=['menu'])
async def menu_command(message: types.Message):
    await send_message_with_menu(message.chat.id, WELCOME_MESSAGE)

'''     обработка команды /fact для отправки стикера '''
@dp.message_handler(commands=['fact'])
async def fact_command(message: types.Message):
    sticker_id = random.choice(STICKERS)
    await send_sticker(message.chat.id, sticker_id)
    if random.random() < 0.3:
        await send_message(message.chat.id, "все хватит заебал")

'''     просто повыебываться      '''
@dp.message_handler(content_types=['text'])
async def else_msg(message: types.Message):
    if message.text not in ['пенис', 'хуй']:
        await send_message_with_menu(message.chat.id, f'{message.text}? че за хуйню высрал')
    else:
        response = "нет хуй" if message.text == 'пенис' else "пенис"
        await send_message_with_menu(message.chat.id, response)


if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    except KeyboardInterrupt:
        print("Bot stopped by user.")
