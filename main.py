from aiogram.utils.exceptions import InvalidQueryID
from dotenv import load_dotenv
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from messages import WELCOME_MESSAGE, STICKERS
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import random

load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


def fetch_reviews(dish):
    url = f"https://www.gastronom.ru/search?search={dish}&pageType=recipepage"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    recipes_links = []
    recipe_titles = []
    recipe_image_urls = []

    all_links = soup.find_all('a', class_="_link_iku8o_14", itemprop="url")
    for link in all_links:
        href = link.get('href')
        if href and "recipe" in href:
            recipes_links.append(f"https://www.gastronom.ru{href}")

        # Поиск названия блюда
        parent_div = link.find_next('a', class_="_name_iku8o_19")
        if parent_div:
            title_tag = parent_div.find('span', itemprop="name")
            if title_tag:
                recipe_titles.append(title_tag.get_text(strip=True))
            else:
                recipe_titles.append("Без названия")
        else:
            recipe_titles.append("Без названия")

        # URL изображения
        image_tag = link.find('img', itemprop="image")
        if image_tag:
            recipe_image_urls.append(image_tag.get('src'))
        else:
            recipe_image_urls.append(None)

    print("Найденные ссылки на рецепты:", recipes_links)
    print("Названия блюд:", recipe_titles)
    print("URL изображений:", recipe_image_urls)

    return recipes_links, recipe_titles, recipe_image_urls


def fetch_ingredients_from_first_recipe(recipes_links):
    if not recipes_links:
        return []

    first_link = recipes_links[0]
    response = requests.get(first_link)
    soup = BeautifulSoup(response.text, 'html.parser')

    ingredients_div = soup.find('div', class_="_ingredients_1r0sn_28")
    if not ingredients_div:
        return []

    ingredients = []
    ingredient_tags = ingredients_div.find_all('div', itemprop="recipeIngredient")
    for tag in ingredient_tags:
        ingredient = tag.get_text(strip=True)
        ingredients.append(ingredient)
    print("Ингредиенты", ingredients)
    return ingredients


def search_ingredient_online(ingredient):
    search_query = f"купить {ingredient} в москве"
    search_url = f"https://www.google.com/search?q={search_query}&tbm=shop"

    response = requests.get(search_url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    links = []
    for item in soup.find_all('a', href=True):
        href = item['href']
        if "url?q=" in href and not "webcache" in href:
            parsed_url = parse_qs(urlparse(href).query).get('q', [None])[0]
            if parsed_url:
                links.append(parsed_url)

    return links[0] if links else None

class RecipeStates(StatesGroup):
    waiting_for_recipe_name = State()

async def send_message(chat_id: int, text: str, reply_markup=None):
    await bot.send_message(chat_id, text, reply_markup=reply_markup)

async def send_message_with_menu(chat_id: int, text: str):
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text="я хочу стать женщиной...", callback_data="first_button"))
    await send_message(chat_id, text, reply_markup=keyboard)

async def send_sticker(chat_id: int, sticker_id: str):
    await bot.send_sticker(chat_id, sticker_id)

keyboard_inline = InlineKeyboardMarkup().add(InlineKeyboardButton(text="я хочу стать женщиной...", callback_data="first_button"))
button_menu = KeyboardButton("в меню")
keyboard_reply = ReplyKeyboardMarkup(resize_keyboard=True).add(button_menu)
keyboard_eating = InlineKeyboardMarkup().add(
    InlineKeyboardButton(text="стать примерной женой и приготовить ужин", callback_data="button_one"),
)

@dp.callback_query_handler(text="button_one")
async def button_one_handler(call: types.CallbackQuery):
    await call.message.answer("Введите блюдо:")
    await RecipeStates.waiting_for_recipe_name.set()
    await call.answer()

@dp.message_handler(state=RecipeStates.waiting_for_recipe_name, content_types=types.ContentType.TEXT)
async def recipe_name_handler(message: types.Message, state: FSMContext):
    if message.text == "в меню" or message.text == '/menu':
        await send_message_with_menu(message.chat.id, WELCOME_MESSAGE)
        await state.finish()  # Завершаем текущее состояние
        return

    recipe_name = message.text

    await message.answer("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
    recipe_links, recipe_titles, recipe_image_urls = fetch_reviews(recipe_name)

    if not recipe_links:
        await message.answer("Рецепты не найдены.")
        await state.finish()
        return

    await state.update_data(recipe_links=recipe_links, recipe_titles=recipe_titles, recipe_image_urls=recipe_image_urls)

    await show_recipe(message, state, recipe_index=0)

async def show_recipe(message: types.Message, state: FSMContext, recipe_index: int):
    data = await state.get_data()
    recipe_links = data['recipe_links']
    recipe_titles = data['recipe_titles']
    recipe_image_urls = data['recipe_image_urls']

    if recipe_index >= len(recipe_links):
        await message.answer("Больше рецептов нет.")
        await state.finish()
        return

    images_to_send = recipe_image_urls[recipe_index:recipe_index + 3]
    keyboard = InlineKeyboardMarkup(row_width=3)

    for i, image_url in enumerate(images_to_send):
        if image_url:
            # Получаем название рецепта для текущего изображения
            recipe_title = recipe_titles[recipe_index + i] if recipe_index + i < len(recipe_titles) else "Без названия"
            button = InlineKeyboardButton(
                text=f"Рецепт {i + 1}",
                callback_data=f"select_image_{recipe_index + i}"  # Индекс рецепта уникален
            )
            keyboard.add(button)
            # Отправляем изображение с подписью
            await bot.send_photo(message.chat.id, image_url, caption=recipe_title)

    await message.answer("Выберите рецепт:", reply_markup=keyboard)


next_recipe_keyboard = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("Да", callback_data="end_recipe_view"),
    InlineKeyboardButton("Нет", callback_data="show_next_recipe"),
)

@dp.callback_query_handler(lambda c: c.data == "recipe_accept", state=RecipeStates.waiting_for_recipe_name)
async def handle_recipe_accept(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Приятного аппетита!")
    await state.finish()
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "recipe_reject", state=RecipeStates.waiting_for_recipe_name)
async def handle_recipe_reject(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_recipe_index = data.get("current_recipe_index", 0)
    await show_recipe(call.message, state, recipe_index=current_recipe_index + 1)  # Показать следующий рецепт
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("select_image_"),
                           state=RecipeStates.waiting_for_recipe_name)
async def select_image_handler(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    if len(parts) != 3:
        await call.answer("Ошибка выбора рецепта.")
        return

    try:
        recipe_index = int(parts[2])
    except ValueError:
        await call.answer("Некорректный индекс рецепта.")
        return

    data = await state.get_data()
    recipe_links = data.get('recipe_links', [])
    recipe_titles = data.get('recipe_titles', [])

    if recipe_index < 0 or recipe_index >= len(recipe_links):
        await call.answer("Некорректный индекс рецепта.")
        return

    selected_recipe_link = recipe_links[recipe_index]
    selected_recipe_title = recipe_titles[recipe_index]
    ingredients = fetch_ingredients_from_first_recipe([selected_recipe_link])

    if not ingredients:
        await call.message.answer("Ингредиенты не найдены.")
        await state.finish()
        return

    await bot.send_message(call.message.chat.id, selected_recipe_title, reply_to_message_id=call.message.message_id)

    await call.message.answer(
        f"Ссылка на рецепт: [тык]({selected_recipe_link})",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    result_message = "🍴 **Ингредиенты для рецепта** 🍴\n\n"
    for idx, ingredient in enumerate(ingredients, start=1):
        purchase_link = search_ingredient_online(ingredient)
        if purchase_link:
            result_message += f"{idx}. **{ingredient}** 🛒 [Купить]({purchase_link})\n"
        else:
            result_message += f"{idx}. **{ingredient}** ❌ _Ссылка отсутствует_\n"

    await call.message.answer(
        result_message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    # Отправка кнопки "Устраивает ли рецепт?"
    try:
        await call.message.answer("Устраивает ли рецепт?", reply_markup=next_recipe_keyboard)
    except InvalidQueryID:
        print("Попытка ответить на устаревший запрос.")

    await state.update_data(current_recipe_index=recipe_index)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data in ["show_next_recipe", "end_recipe_view"], state=RecipeStates.waiting_for_recipe_name)
async def handle_next_recipe(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_recipe_index = data.get("current_recipe_index", 0)

    if call.data == "show_next_recipe":
        await show_recipe(call.message, state, recipe_index=current_recipe_index + 1)
    elif call.data == "end_recipe_view":
        await call.message.answer("Приятного аппетита!")
        await state.finish()

    await call.answer()


@dp.callback_query_handler(text=["first_button"])
async def check_button(call: types.CallbackQuery):
    await call.message.answer("Введите блюдо:")
    await RecipeStates.waiting_for_recipe_name.set()
    await call.answer()

@dp.message_handler(commands=['kushat'])
async def help_command(message: types.Message):
    await message.answer("Введите блюдо:")
    await RecipeStates.waiting_for_recipe_name.set()

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