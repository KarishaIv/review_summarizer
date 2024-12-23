from imports import *
import json
from chosen_recipe import  search_ingredient_online, dp


YANDEX_API_URL = os.environ.get('YANDEX_API_URL')
FOLDER_ID = os.environ.get('FOLDER_ID')
YANDEX_IAM_TOKEN = os.environ.get('YANDEX_IAM_TOKEN')


class RandomRecipeState(StatesGroup):
    waiting_for_cuisine_type = State()
    generating_recipe = State()

# Обработка команды "/random"
@dp.message_handler(commands=['random'])
async def random_command(message: types.Message):
    # Создаём клавиатуру с кнопкой "Без разницы"
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton(text="Без разницы", callback_data="random_any_cuisine")
    )
    # Сообщение с инструкцией
    await message.answer("Введите тип кухни (например, итальянская, японская) или выберите 'Без разницы':",
                         reply_markup=keyboard)
    await RandomRecipeState.waiting_for_cuisine_type.set()

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
        ).row(
            InlineKeyboardButton("В меню", callback_data="menu")
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

# Обработка отклонения рецепта (когда пользователь нажимает "Нет")
@dp.callback_query_handler(lambda call: call.data == "reject_recipe", state=RandomRecipeState.generating_recipe)
async def handle_reject_recipe(call: types.CallbackQuery, state: FSMContext):
    # Переход к обработке следующих рецептов
    await process_random_recipe(call, state, is_callback=True)

# Обработка принятия рецепта (когда пользователь нажимает "Да")
@dp.callback_query_handler(lambda call: call.data == "accept_recipe", state=RandomRecipeState.generating_recipe)
async def handle_accept_recipe(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Приятного аппетита! 🍽")
    await state.finish()
    await call.answer()
