from aiogram.utils.exceptions import InvalidQueryID
from dotenv import load_dotenv
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from messages import WELCOME_MESSAGE
from urllib.parse import urlparse, parse_qs
import urllib
import urllib.request
import requests
import urllib.request
from http.cookiejar import CookieJar
import pymorphy2
import re
from bs4 import BeautifulSoup
from urllib.parse import quote
import json


YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
FOLDER_ID="FOLDER_ID"
YANDEX_IAM_TOKEN = "YANDEX_IAM_TOKEN"


load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class RandomRecipeState(StatesGroup):
    waiting_for_cuisine_type = State()
    generating_recipe = State()

# Инициализация морфологического анализатора
morph = pymorphy2.MorphAnalyzer()

# Стоп-слова
STOPWORDS = {"и", "с", "в", "на", "для", "по", "из", "а", "или", "от", "без"}

def lemmatize_word(word):
    """Приведение слова к нормальной форме (лемматизация)"""
    return morph.parse(word)[0].normal_form

def lemmatize_text(text):
    """Лемматизация текста: удаляет стоп-слова и приводит к леммам"""
    words = re.split(r"[^\w]+", text.lower())  # Разбиваем на слова
    return [lemmatize_word(word) for word in words if word and word not in STOPWORDS]

def fetch_reviews(dish):
    url = f"https://www.gastronom.ru/search?search={quote(dish)}&pageType=recipepage"
    print(url)

    try:
        req = urllib.request.Request(url, None)
        cj = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        response = opener.open(req)

        raw_response = response.read().decode('utf-8', errors='ignore')
        response.close()

        soup = BeautifulSoup(raw_response, 'html.parser')

        # Лемматизируем запрос пользователя
        user_keywords = set(lemmatize_text(dish))

        recipes_links = []
        recipe_titles = []
        recipe_image_urls = []

        all_links = soup.find_all('a', class_="_link_iku8o_14", itemprop="url")
        for link in all_links:
            href = link.get('href')
            if href and "recipe" in href:
                parent_div = link.find_next('a', class_="_name_iku8o_19")
                if parent_div:
                    title_tag = parent_div.find('span', itemprop="name")
                    if title_tag:
                        recipe_title = title_tag.get_text(strip=True).lower()

                        # Лемматизируем заголовок рецепта
                        title_keywords = set(lemmatize_text(recipe_title))

                        # Проверяем, что все ключевые слова запроса есть в заголовке
                        if user_keywords.issubset(title_keywords):
                            recipes_links.append(f"https://www.gastronom.ru{href}")
                            recipe_titles.append(recipe_title)

                            image_tag = link.find('img', itemprop="image")
                            recipe_image_urls.append(
                                image_tag.get('src') if image_tag else None
                            )


        print("Найденные ссылки:", recipes_links)
        print("Названия блюд:", recipe_titles)
        print("URL изображений:", recipe_image_urls)

        return recipes_links, recipe_titles, recipe_image_urls

    except urllib.request.HTTPError as inst:
        output = format(inst)
        print(output)
        return [], [], []


def fetch_ingredients_from_first_recipe(recipes_links):
    if not recipes_links:
        return [], None  # Возвращаем список ингредиентов и количество порций

    first_link = recipes_links[0]
    response = requests.get(first_link)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Ищем блок с количеством порций
    portions_div = soup.find('div', class_="_text_1prcq_11", itemprop="recipeYield")
    portions = None
    if portions_div:
        portions_text = portions_div.get_text(strip=True)
        if "Порций:" in portions_text:
            portions = portions_text.split("Порций:")[-1].strip()  # Извлекаем количество порций

    # Ищем ингредиенты
    ingredients_div = soup.find('div', class_="_ingredients_1r0sn_28")
    if not ingredients_div:
        return [], portions

    ingredients = []
    ingredient_tags = ingredients_div.find_all('div', itemprop="recipeIngredient")
    for tag in ingredient_tags:
        ingredient = tag.get_text(strip=True)
        ingredients.append(ingredient)

    print("Ингредиенты:", ingredients)
    print("Количество порций:", portions)
    return ingredients, portions



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
    ingredients, portions = fetch_ingredients_from_first_recipe([selected_recipe_link])

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
    await call.message.answer(f"Кол-во порций в рецепте: {portions}")

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



# Обработка команды /random
@dp.message_handler(commands=['random'])
async def random_command(message: types.Message):
    # Создаём клавиатуру с кнопкой "Без разницы"
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton(text="Без разницы", callback_data="random_any_cuisine")
    )
    # Сообщение с инструкцией
    await message.answer("Введите тип кухни (например, итальянская, японская) или выберите 'Без разницы':",
                         reply_markup=keyboard)
    # Устанавливаем состояние
    await RandomRecipeState.waiting_for_cuisine_type.set()


# Функция отправки запроса к Yandex LLM API
def extract_event_details(request_text):
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = form_payload(request_text)
    response = requests.post(YANDEX_API_URL, headers=headers, data=payload)

    if response.status_code == 200:
        result = response.json()
        text = result['result']['alternatives'][0]['message']['text']
        return text
    else:
        raise Exception(f"Ошибка при вызове Yandex LLM API: {response.status_code} {response.text}")


# Обработка кнопки "Без разницы"
@dp.callback_query_handler(lambda call: call.data == "random_any_cuisine", state=RandomRecipeState.waiting_for_cuisine_type)
async def random_any_cuisine_handler(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(flag=True)
    await call.message.answer("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
    await call.answer()
    await process_random_recipe(call.message, state)

# Обработка текста с типом кухни
@dp.message_handler(state=RandomRecipeState.waiting_for_cuisine_type, content_types=types.ContentType.TEXT)
async def random_cuisine_handler(message: types.Message, state: FSMContext):
    cuisine_type = message.text.strip().lower()
    await state.update_data(flag=False, cuisine_type=cuisine_type)
    await message.answer("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
    await process_random_recipe(message, state)


# Функция формирования тела запроса к Yandex LLM API
def form_payload(request_text):
    return json.dumps({
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 1,
            "maxTokens": 2000
        },
        "messages": [
            {
                "role": "system",
                "text": "Ты - ассистент, который предлагает 1 идею блюда кухни, которую введет пользователь. "
                        "Анализируй запросы пользователя и возвращай следующую информацию: "
                        "1. Название блюда, 2. рецепт блюда, 3. список ингредиентов на 2 порции с граммовками. "
                        "Ингредиенты пиши в одну строчку через запятую"
                        "Формат ответа: Блюдо: название. Рецепт: рецепт. Список ингредиентов на 2 порции: ингредиенты."
            },
            {
                "role": "user",
                "text": request_text
            }
        ]
    })

# Функция для парсинга результата от Yandex GPT
def parse_gpt_result(result):
    try:
        dish_name_start = result.find("Блюдо: ") + len("Блюдо: ")
        dish_name_end = result.find(". Рецепт: ")
        recipe_start = dish_name_end + len(". Рецепт: ")
        recipe_end = result.find(". Список ингредиентов на 2 порции: ")
        ingredients_start = recipe_end + len(". Список ингредиентов на 2 порции: ")

        dish_name = result[dish_name_start:dish_name_end].strip()
        recipe = result[recipe_start:recipe_end].strip()
        ingredients_list = result[ingredients_start:].strip()

        ingredients = [ing.strip() for ing in ingredients_list.split(",")]
        return dish_name, recipe, ingredients
    except Exception as e:
        raise ValueError(f"Ошибка при разборе результата GPT: {e}")

async def process_random_recipe(message_or_call, state: FSMContext, is_callback=False):
    """
    Обрабатывает запрос рецепта, выводит блюдо, ингредиенты и рецепт,
    а также обеспечивает возможность запросить другой рецепт.
    """
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        flag = data.get('flag', False)
        cuisine_type = data.get('cuisine_type', None) if not flag else "любой"

        request_text = (
            f"Предложи одно блюдо {cuisine_type} кухни, рецепт и список ингредиентов на 2 порции."
        )

        # Если это callback (повторный запрос), уведомляем о загрузке нового рецепта
        if is_callback:
            # Проверяем, является ли message_or_call объектом CallbackQuery
            if isinstance(message_or_call, types.CallbackQuery):
                await message_or_call.message.answer("Ищу другой рецепт...")
            else:
                await message_or_call.answer("Ищу другой рецепт...")

        # Запрашиваем рецепт у GPT
        result = extract_event_details(request_text)
        dish_name, recipe, ingredients = parse_gpt_result(result)

        # Формируем сообщение
        result_message = f"🍴 **{dish_name}** 🍴\n\n"
        result_message += f"**Рецепт:** {recipe}\n\n"
        result_message += f"**Количество порций в рецепте: 2**\n\n"
        result_message += "**Ингредиенты:**\n"

        for idx, ingredient in enumerate(ingredients, start=1):
            purchase_link = search_ingredient_online(ingredient)
            if purchase_link:
                result_message += f"{idx}. {ingredient} 🛒 [Купить]({purchase_link})\n"
            else:
                result_message += f"{idx}. {ingredient} ❌ _Ссылка отсутствует_\n"

        # Отправка результата
        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.message.answer(result_message, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await message_or_call.answer(result_message, parse_mode="Markdown", disable_web_page_preview=True)

        # Создаём клавиатуру для следующего действия
        next_recipe_keyboard = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Да", callback_data="accept_recipe"),
            InlineKeyboardButton("Нет", callback_data="reject_recipe")
        )

        # Отправка вопроса "Устраивает ли рецепт?"
        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.message.answer("Устраивает ли рецепт?", reply_markup=next_recipe_keyboard)
        else:
            await message_or_call.answer("Устраивает ли рецепт?", reply_markup=next_recipe_keyboard)

        # Обновляем состояние
        await state.set_state(RandomRecipeState.generating_recipe.state)
        await state.update_data(previous_request_text=request_text)

    except Exception as e:
        # Обработка ошибок
        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.message.answer(f"Ошибка при запросе: {e}")
        else:
            await message_or_call.answer(f"Ошибка при запросе: {e}")

# Обработка повторного запроса (когда пользователь нажимает "Нет")
@dp.callback_query_handler(lambda call: call.data == "reject_recipe", state=RandomRecipeState.generating_recipe)
async def handle_reject_recipe(call: types.CallbackQuery, state: FSMContext):
    await process_random_recipe(call, state, is_callback=True)

# Обработка принятия рецепта (когда пользователь нажимает "Да")
@dp.callback_query_handler(lambda call: call.data == "accept_recipe", state=RandomRecipeState.generating_recipe)
async def handle_accept_recipe(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Приятного аппетита! 🍽")
    await state.finish()
    await call.answer()

if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    except KeyboardInterrupt:
        print("Bot stopped by user.")