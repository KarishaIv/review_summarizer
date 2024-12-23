from imports import *

load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class RecipeStates(StatesGroup):
    waiting_for_recipe_name = State()

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

'''     kushat      '''

@dp.message_handler(commands=['kushat'])
async def kushat_command(message: types.Message):
    await message.answer("Введите блюдо:")
    await RecipeStates.waiting_for_recipe_name.set()

@dp.callback_query_handler(lambda c: c.data == "kushat")
async def handle_kushat_callback(call: types.CallbackQuery):
    await kushat_command(call.message)

async def send_message(chat_id: int, text: str, reply_markup=None):
    await bot.send_message(chat_id, text, reply_markup=reply_markup)

async def send_message_with_menu(chat_id: int, text: str):
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton(text="я хочу стать женщиной...", callback_data="first_button"))
    await send_message(chat_id, text, reply_markup=keyboard)

keyboard_inline = InlineKeyboardMarkup().add(InlineKeyboardButton(text="я хочу стать женщиной...", callback_data="first_button"))
button_menu = KeyboardButton("в меню")
keyboard_reply = ReplyKeyboardMarkup(resize_keyboard=True).add(button_menu)


@dp.callback_query_handler(text=["first_button"])
async def check_button(call: types.CallbackQuery):
    await call.message.answer("Введите блюдо:")
    await RecipeStates.waiting_for_recipe_name.set()
    await call.answer()




@dp.callback_query_handler(lambda c: c.data == "menu", state='*')
async def handle_menu_callback(call: types.CallbackQuery, state: FSMContext):
    # Программно вызываем обработчик команды /menu
    await state.finish()
    await menu_command(call.message)
    await call.answer()

@dp.callback_query_handler(text="button_one")
async def button_one_handler(call: types.CallbackQuery):
    await call.message.answer("Введите блюдо:")
    await RecipeStates.waiting_for_recipe_name.set()
    await call.answer()


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

# запрос к сайту с рецептами
def fetch_reviews(dish):
    url = f"https://www.gastronom.ru/search?search={quote(dish)}&pageType=recipepage"
    print(url)

    try:
        # Создаем SSL контекст
        context = ssl.create_default_context(cafile=certifi.where())
        cj = CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=context)  # Добавляем обработчик HTTPS с контекстом
        )

        req = urllib.request.Request(url, None)
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


# Достаем ингридиенты из рецепта
def fetch_ingredients_from_recipe(recipes_links):
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
            portions = portions_text.split("Порций:")[-1].strip()

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


# Ищем ссылки на продукты для рецепта в интернете
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

# показываем первые <=3 найденных блюда
async def show_recipe(message: types.Message, state: FSMContext, recipe_index: int):
    data = await state.get_data()
    recipe_links = data['recipe_links']
    recipe_titles = data['recipe_titles']
    recipe_image_urls = data['recipe_image_urls']

    if recipe_index >= len(recipe_links):
        await message.answer("Больше рецептов нет.")
        await state.finish()
        return

    # Получаем до 3 изображений для отображения
    images_to_send = recipe_image_urls[recipe_index:recipe_index + 3]
    keyboard = InlineKeyboardMarkup(row_width=3)

    for i, image_url in enumerate(images_to_send):
        if image_url:
            # Получаем название рецепта для текущего изображения
            recipe_title = recipe_titles[recipe_index + i] if recipe_index + i < len(recipe_titles) else "Без названия"
            button = InlineKeyboardButton(
                text=f"Рецепт {i + 1}",
                callback_data=f"select_image_{recipe_index + i}"  # Уникальный индекс рецепта
            )
            keyboard.add(button)
            # Отправляем изображение с подписью
            await bot.send_photo(message.chat.id, image_url, caption=recipe_title)

    # Добавляем кнопки "Следующие варианты" и "В меню"
    keyboard.add(
        InlineKeyboardButton(
            text="Следующие варианты",
            callback_data="next_recipe_set"
        )
    )

    keyboard.add(
        InlineKeyboardButton(
            text="В меню",
            callback_data="menu"
        )
    )
    await message.answer("Выберите рецепт:", reply_markup=keyboard)


# показываем пользователю рецепт с продуктами
@dp.callback_query_handler(lambda c: c.data.startswith("select_image_"),
                           state=RecipeStates.waiting_for_recipe_name)
async def show_recipe_to_user(call: types.CallbackQuery, state: FSMContext):
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

    # Извлекаем ингредиенты и кол-во порций
    ingredients, portions = fetch_ingredients_from_recipe([selected_recipe_link])

    if not ingredients:
        await call.message.answer("Ингредиенты не найдены.")
        await state.finish()
        return

    # Отправляем название рецепта
    await bot.send_message(
        call.message.chat.id,
        selected_recipe_title,
        reply_to_message_id=call.message.message_id
    )

    # Отправляем ссылку на рецепт
    await call.message.answer(
        f"Ссылка на рецепт: [тык]({selected_recipe_link})",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    # Отправляем количество порций
    await call.message.answer(f"Кол-во порций в рецепте: {portions}")

    # Готовим сообщение со списком ингредиентов
    result_message = "🍴 **Ингредиенты для рецепта** 🍴\n\n"

    for idx, ingredient in enumerate(ingredients, start=1):

        # Далее мы приводим запрос к виду "ингридиент - граммовка", если это возможно
        if "-" in ingredient or "–" in ingredient:
            formatted_ingredient = ingredient.strip()
            if formatted_ingredient:
                formatted_ingredient = formatted_ingredient[0].upper() + formatted_ingredient[1:]
        else:
            match = re.search(
                r'^(.*?)(\d+(?:\.\d+)?\s*(?:г|кг|мл|ст\.л\.?|ч\.л\.?|шт\.?|зубчик\(а\)|веточка\(и\)|пакетик\(и\)|стакана?))$',
                ingredient.strip(),
                re.IGNORECASE
            )
            if match:
                name = match.group(1).strip()
                quantity = match.group(2).strip()

                if name:
                    name = name[0].upper() + name[1:]

                formatted_ingredient = f"{name} - {quantity}"
            else:
                formatted_ingredient = ingredient.strip()
                if formatted_ingredient:
                    formatted_ingredient = (
                        formatted_ingredient[0].upper() + formatted_ingredient[1:]
                    )

        # Ссылка "купить"
        purchase_link = search_ingredient_online(formatted_ingredient)
        if purchase_link:
            result_message += f"{idx}. **{formatted_ingredient}** 🛒 [Купить]({purchase_link})\n"
        else:
            result_message += f"{idx}. **{formatted_ingredient}** ❌ _Ссылка отсутствует_\n"

    # Отправляем пользователю список ингредиентов
    await call.message.answer(
        result_message,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )

    # Спрашиваем, устраивает ли рецепт
    try:
        await call.message.answer("Устраивает ли рецепт?", reply_markup=next_recipe_keyboard)
    except InvalidQueryID:
        print("Попытка ответить на устаревший запрос.")

    await state.update_data(current_recipe_index=recipe_index)
    await call.answer()

# Обработчик для кнопки "Следующие варианты"
@dp.callback_query_handler(lambda call: call.data == "next_recipe_set", state=RecipeStates.waiting_for_recipe_name)
async def handle_next_recipe_set(call: types.CallbackQuery, state: FSMContext):
    # Получаем текущий индекс рецепта из состояния
    data = await state.get_data()
    current_recipe_index = data.get("current_recipe_index", 0)

    # Увеличиваем индекс для показа следующих рецептов
    new_recipe_index = current_recipe_index + 3
    await state.update_data(current_recipe_index=new_recipe_index)

    # Отображаем следующие рецепты
    await show_recipe(call.message, state, recipe_index=new_recipe_index)

    # Закрываем всплывающее уведомление
    await call.answer()

next_recipe_keyboard = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("Да", callback_data="recipe_accept"),
    InlineKeyboardButton("Нет", callback_data="recipe_reject")
).row(
    InlineKeyboardButton("В меню", callback_data="menu")
)

# обработчик "Да", когда пользователю понравился предложенный рецепт
@dp.callback_query_handler(lambda c: c.data == "recipe_accept", state=RecipeStates.waiting_for_recipe_name)
async def handle_recipe_accept(call: types.CallbackQuery, state: FSMContext):

    keyboard = InlineKeyboardMarkup(row_width=3)

    keyboard.add(
        InlineKeyboardButton("Выбрать новое блюдо", callback_data="kushat"),
    )

    keyboard.add(
        InlineKeyboardButton("В меню", callback_data="menu")
    )

    await call.message.answer("Приятного аппетита!", reply_markup=keyboard)
    await state.finish()
    await call.answer()

# обработчик "Нет", когда пользователю не понравился предложенный рецепт
@dp.callback_query_handler(lambda c: c.data == "recipe_reject", state=RecipeStates.waiting_for_recipe_name)
async def handle_recipe_reject(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_recipe_index = data.get("current_recipe_index", 0)
    await show_recipe(call.message, state, recipe_index=current_recipe_index + 1)  # Показать следующий рецепт
    await call.answer()



@dp.callback_query_handler(lambda call: call.data == "next_recipe_set", state=RecipeStates.waiting_for_recipe_name)
async def handle_next_recipe_set(call: types.CallbackQuery, state: FSMContext):
    # Получаем текущий индекс рецепта
    data = await state.get_data()
    current_recipe_index = data.get("current_recipe_index", 0)

    # Увеличиваем индекс для показа следующих рецептов
    new_recipe_index = current_recipe_index + 3
    await state.update_data(current_recipe_index=new_recipe_index)

    # Отображаем следующие рецепты
    await show_recipe(call.message, state, recipe_index=new_recipe_index)

    await call.answer()

# Обрабатываем запрос следующего рецепта
@dp.callback_query_handler(lambda c: c.data in ["show_next_recipe", "end_recipe_view"], state=RecipeStates.waiting_for_recipe_name)
async def handle_next_recipe(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_recipe_index = data.get("current_recipe_index", 0)

    if call.data == "show_next_recipe":
        await show_recipe(call.message, state, recipe_index=current_recipe_index + 1)
    elif call.data == "end_recipe_view":
        keyboard = InlineKeyboardMarkup(row_width=3)

        keyboard.add(
            InlineKeyboardButton("Выбрать новое блюдо", callback_data="kushat"),
        )

        keyboard.add(
            InlineKeyboardButton("В меню", callback_data="menu")
        )
        await call.message.answer("Приятного аппетита!", reply_markup=keyboard)
        await state.finish()

    await call.answer()
