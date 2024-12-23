from imports import *
from main import dp


from chosen_recipe import (
    lemmatize_word,
    lemmatize_text,
    handle_recipe_accept,
    handle_next_recipe,
    handle_recipe_reject,
    recipe_name_handler,
    start_command,
    menu_command,
    kushat_command,
    handle_kushat_callback,
    check_button,
    button_one_handler,
    fetch_reviews,
    show_recipe,
    handle_next_recipe_set,
    search_ingredient_online,
    fetch_ingredients_from_recipe,
    show_recipe_to_user,
    RecipeStates
    )

from random_recipe import (
    form_payload,
    handle_reject_recipe,
    handle_accept_recipe,
    random_command,
    random_any_cuisine_handler,
    random_cuisine_handler,
    process_random_recipe,
)


FOLDER_ID = os.environ.get('FOLDER_ID')

@pytest.fixture
def callback_query():
    mock_cb = MagicMock(spec=CallbackQuery)
    mock_cb.message = AsyncMock()
    mock_cb.answer = AsyncMock()
    return mock_cb

@pytest.fixture
def fsm_context():
    mock_ctx = AsyncMock(spec=FSMContext)
    mock_ctx.finish = AsyncMock()
    return mock_ctx


@pytest.fixture
def message():
    """Мокаем объект Message."""
    mock_message = MagicMock(spec=types.Message)
    mock_message.chat = MagicMock(spec=Chat, id=123456789)
    mock_message.from_user = MagicMock(spec=User, id=987654321)
    mock_message.answer = AsyncMock()
    return mock_message



@pytest.mark.asyncio
async def test_start_command(message):
    """
    Тестируем команду /start. Ожидается отправка приветственного сообщения с клавиатурой.
    """
    with patch("chosen_recipe.send_message") as mock_send_message:
        await start_command(message)
        mock_send_message.assert_called_once_with(
            message.chat.id, ANY, reply_markup=ANY
        )

@pytest.mark.asyncio
async def test_menu_command(message):
    """
    Тестируем команду /menu. Ожидается отправка сообщения с меню.
    """
    with patch("chosen_recipe.send_message_with_menu") as mock_send_menu:
        await menu_command(message)
        mock_send_menu.assert_called_once_with(
            message.chat.id, ANY
        )

@pytest.mark.asyncio
async def test_kushat_command(message):
    """
    Тестируем команду /kushat. Ожидается запрос ввода блюда и установка состояния.
    """
    # Устанавливаем текущий диспетчер
    Dispatcher.set_current(dp)

    # Мокаем хранилище состояния
    dp.storage = MemoryStorage()

    # Устанавливаем фиктивное состояние
    state = FSMContext(storage=dp.storage, chat=message.chat.id, user=message.from_user.id)
    Dispatcher.get_current().current_state = lambda *args, **kwargs: state

    # Вызываем тестируемую команду
    await kushat_command(message)

    # Проверяем вызовы
    message.answer.assert_called_once_with("Введите блюдо:")
    current_state = await dp.storage.get_state(chat=message.chat.id, user=message.from_user.id)
    assert current_state == RecipeStates.waiting_for_recipe_name.state

@pytest.mark.asyncio
async def test_handle_kushat_callback(callback_query):
    """
    Тестируем callback 'kushat'. Ожидается вызов команды /kushat.
    """
    with patch("chosen_recipe.kushat_command") as mock_kushat:
        await handle_kushat_callback(callback_query)
        mock_kushat.assert_awaited_once_with(callback_query.message)

@pytest.mark.asyncio
async def test_first_button_handler(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки first_button.
    Ожидается: бот запросит блюдо и перейдёт в состояние waiting_for_recipe_name.
    """
    callback_query.data = "first_button"
    with patch("chosen_recipe.RecipeStates.waiting_for_recipe_name.set", new_callable=AsyncMock) as mock_set_state:
        await check_button(callback_query)
        callback_query.message.answer.assert_called_once_with("Введите блюдо:")
        mock_set_state.assert_awaited_once()
        callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_button_one_handler(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки button_one.
    Ожидается: бот запросит блюдо и установит состояние waiting_for_recipe_name.
    """
    callback_query.data = "button_one"
    with patch("chosen_recipe.RecipeStates.waiting_for_recipe_name.set", new_callable=AsyncMock) as mock_set_state:
        await button_one_handler(callback_query)
        callback_query.message.answer.assert_called_once_with("Введите блюдо:")
        mock_set_state.assert_awaited_once()
        callback_query.answer.assert_called_once()



@pytest.mark.asyncio
async def test_handle_recipe_accept(callback_query, fsm_context):
    """
    Тест: кнопка 'recipe_accept'.
    Ожидается: "Приятного аппетита!" с клавиатурой и завершение состояния.
    """
    callback_query.data = "recipe_accept"

    # Вызываем тестируемую функцию
    await handle_recipe_accept(callback_query, fsm_context)

    # Проверяем вызов
    callback_query.message.answer.assert_called_once_with(
        "Приятного аппетита!",
        reply_markup=ANY  # Игнорируем точную структуру клавиатуры
    )
    fsm_context.finish.assert_awaited_once()
    callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_recipe_reject(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки, которая отказывается от рецепта.
    Ожидается: бот попытается показать следующий рецепт.
    """
    callback_query.data = "recipe_reject"
    fsm_context.get_data.return_value = {"current_recipe_index": 0}

    with patch("chosen_recipe.show_recipe", new_callable=AsyncMock) as mock_show_recipe:
        await handle_recipe_reject(callback_query, fsm_context)
        mock_show_recipe.assert_awaited_once_with(callback_query.message, fsm_context, recipe_index=1)
        callback_query.answer.assert_called_once()



@pytest.mark.asyncio
async def test_handle_next_recipe_show_next(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки show_next_recipe.
    Ожидается: бот покажет следующий рецепт.
    """
    callback_query.data = "show_next_recipe"
    fsm_context.get_data.return_value = {"current_recipe_index": 0}

    with patch("chosen_recipe.show_recipe", new_callable=AsyncMock) as mock_show_recipe:
        await handle_next_recipe(callback_query, fsm_context)
        mock_show_recipe.assert_awaited_once_with(callback_query.message, fsm_context, recipe_index=1)
        callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_next_recipe_end_view(callback_query, fsm_context):
    """
    Тест: кнопка 'end_recipe_view'.
    Ожидается: "Приятного аппетита!" с клавиатурой и завершение состояния.
    """
    callback_query.data = "end_recipe_view"

    await handle_next_recipe(callback_query, fsm_context)

    callback_query.message.answer.assert_called_once_with(
        "Приятного аппетита!",
        reply_markup=ANY
    )
    fsm_context.finish.assert_awaited_once()
    callback_query.answer.assert_called_once()

@pytest.mark.asyncio
async def test_handle_next_recipe_set_no_recipes_left(callback_query, fsm_context):
    """
    Тестируем handle_next_recipe_set, если рецептов больше нет.
    Ожидается: завершение состояния.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1", "link2"],
        "recipe_titles": ["Рецепт 1", "Рецепт 2"],
        "recipe_image_urls": ["url1", "url2"]
    }
    fsm_context.update_data = AsyncMock()

    await handle_next_recipe_set(callback_query, fsm_context)
    callback_query.message.answer.assert_any_call("Больше рецептов нет.")
    fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_next_recipe_set_overflow(callback_query, fsm_context):
    """
    Тестируем обработчик "Следующие варианты", если индекс превышает количество рецептов.
    Ожидается: завершение состояния.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1"],
        "recipe_titles": ["Рецепт 1"],
        "recipe_image_urls": ["url1"]
    }
    fsm_context.update_data = AsyncMock()

    await handle_next_recipe_set(callback_query, fsm_context)
    fsm_context.update_data.assert_called_once_with(current_recipe_index=3)

@pytest.mark.asyncio
async def test_check_button_sets_state(callback_query):
    """
    Тестируем нажатие кнопки "я хочу стать женщиной...".
    Ожидается: бот попросит ввести блюдо и установит состояние FSM.
    """
    callback_query.data = "first_button"

    Dispatcher.set_current(dp)

    with patch.object(RecipeStates.waiting_for_recipe_name, 'set', new_callable=AsyncMock) as mock_set_state:
        await check_button(callback_query)
        callback_query.message.answer.assert_called_once_with("Введите блюдо:")
        mock_set_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_restaurant_name_handler_no_results(callback_query, fsm_context):
    """
    Тестируем поиск рецептов по названию блюда, если ничего не найдено.
    Ожидается: бот отправит сообщение "Рецепты не найдены".
    """
    fsm_context.get_data.return_value = {}
    callback_query.message.text = "Неизвестное блюдо"

    with patch("chosen_recipe.fetch_reviews", return_value=([], [], [])):
        await recipe_name_handler(callback_query.message, fsm_context)

        callback_query.message.answer.assert_any_call("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
        callback_query.message.answer.assert_any_call("Рецепты не найдены.")

        # Проверяем, что метод answer вызывался ровно два раза
        assert callback_query.message.answer.call_count == 2

        fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_select_handler_invalid_data(callback_query, fsm_context):
    """
    Тестируем выбор рецепта с некорректными данными.
    Ожидается: бот отправит сообщение об ошибке.
    """
    callback_query.data = "select_image_invalid"

    await show_recipe_to_user(callback_query, fsm_context)

    callback_query.answer.assert_called_once_with("Некорректный индекс рецепта.")


def test_fetch_ingredients_from_recipe_no_links():
    """
    Тестируем извлечение ингредиентов при отсутствии ссылок.
    Ожидается: пустой список ингредиентов и None для порций.
    """
    ingredients, portions = fetch_ingredients_from_recipe([])
    assert ingredients == []
    assert portions is None

@patch("chosen_recipe.requests.get")
def test_search_ingredient_online(mock_get):
    """
    Тестируем поиск ссылки на ингредиент в интернете.
    Ожидается: возврат первой найденной ссылки.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '<a href="url?q=https://example.com&sa=U">Example</a>'
    mock_get.return_value = mock_response

    link = search_ingredient_online("ингридиент")
    assert link == "https://example.com"

def test_fetch_reviews_no_results():
    """
    Тестируем fetch_reviews с запросом, который не даёт результатов.
    Ожидается: возврат пустых списков.
    """
    with patch("chosen_recipe.urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_urlopen.return_value = mock_response

        links, titles, images = fetch_reviews("not_a_real_dish")
        assert links == []
        assert titles == []
        assert images == []


def test_search_ingredient_online_no_results():
    """
    Тестируем поиск ингредиентов, если ничего не найдено.
    Ожидается: возврат None.
    """
    with patch("chosen_recipe.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = ""
        result = search_ingredient_online("nonexistent_ingredient")
        assert result is None


def test_fetch_ingredients_from_recipe_partial_data():
    """
    Тестируем fetch_ingredients_from_recipe, если данные о порциях отсутствуют.
    Ожидается: корректное возвращение ингредиентов без порций.
    """
    html_content = """
    <div class="_ingredients_1r0sn_28">
        <div itemprop="recipeIngredient">Ингредиент 1</div>
        <div itemprop="recipeIngredient">Ингредиент 2</div>
    </div>
    """
    with patch("chosen_recipe.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = html_content
        mock_get.return_value = mock_response

        ingredients, portions = fetch_ingredients_from_recipe(["http://test-recipe.com"])
        assert ingredients == ["Ингредиент 1", "Ингредиент 2"]
        assert portions is None

@pytest.mark.asyncio
async def test_recipe_name_handler_no_recipes_found(message, fsm_context):
    """
    Тестируем обработчик recipe_name_handler, если рецепты не найдены.
    Ожидается: сообщение "Рецепты не найдены." и завершение состояния.
    """
    message.text = "Несуществующее блюдо"
    with patch("chosen_recipe.fetch_reviews", return_value=([], [], [])):
        await recipe_name_handler(message, fsm_context)
        message.answer.assert_any_call("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
        message.answer.assert_any_call("Рецепты не найдены.")
        fsm_context.finish.assert_awaited_once()



def test_lemmatize_word():
    """
    Тестируем приведение слова к нормальной форме.
    Ожидается: правильная лемма для входного слова.
    """
    assert lemmatize_word("машины") == "машина"
    assert lemmatize_word("бежал") == "бежать"
    assert lemmatize_word("яблоками") == "яблоко"


def test_lemmatize_text():
    """
    Тестируем лемматизацию текста.
    Ожидается: лемматизированные слова без стоп-слов.
    """
    input_text = "Машины едут по дороге в Москву"
    expected_output = ["машина", "ехать", "дорога", "москва"]
    assert lemmatize_text(input_text) == expected_output

    input_text_with_stopwords = "И машина поехала на дорогу"
    expected_output_with_stopwords = ["машина", "поехать", "дорога"]
    assert lemmatize_text(input_text_with_stopwords) == expected_output_with_stopwords

def test_lemmatize_text_empty():
    """
    Тестируем поведение lemmatize_text с пустым текстом.
    Ожидается: пустой список.
    """
    assert lemmatize_text("") == []
    assert lemmatize_text(" ") == []

def test_lemmatize_text_complex():
    """
    Тестируем лемматизацию сложного текста.
    Ожидается: корректная обработка разных словоформ.
    """
    input_text = "Яблоки падают с деревьев, а машины стоят на месте."
    expected_output = ["яблоко", "падать", "дерево", "машина", "стоять", "место"]
    assert lemmatize_text(input_text) == expected_output



def test_lemmatize_text_only_stopwords():
    """
    Тестируем текст, который состоит только из стоп-слов.
    Ожидается: пустой список.
    """
    input_text = "и с в на для по из а или от без"
    assert lemmatize_text(input_text) == []


@pytest.mark.asyncio
async def test_show_recipe_no_more_recipes(callback_query, fsm_context):
    """
    Тестируем ситуацию, когда больше нет рецептов для показа.
    Ожидается: бот отправит сообщение и завершит состояние.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": [],
        "recipe_titles": [],
        "recipe_image_urls": []
    }

    await show_recipe(callback_query.message, fsm_context, recipe_index=0)
    callback_query.message.answer.assert_called_once_with("Больше рецептов нет.")
    fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_show_recipe_to_user_invalid_index(callback_query, fsm_context):
    """
    Тестируем обработчик select_image с некорректным индексом.
    Ожидается: отправка сообщения об ошибке.
    """
    callback_query.data = "select_image_99"
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1"],
        "recipe_titles": ["Рецепт 1"]
    }

    await show_recipe_to_user(callback_query, fsm_context)
    callback_query.answer.assert_called_once_with("Некорректный индекс рецепта.")

@pytest.mark.asyncio
async def test_show_recipe_partial_data(callback_query, fsm_context):
    """
    Тестируем отображение рецептов, если данные частично заполнены (отсутствуют изображения).
    Ожидается: корректная работа без ошибок.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1", "link2"],
        "recipe_titles": ["Рецепт 1", "Рецепт 2"],
        "recipe_image_urls": [None, None]  # Нет изображений
    }

    await show_recipe(callback_query.message, fsm_context, recipe_index=0)
    callback_query.message.answer.assert_called_once_with("Выберите рецепт:", reply_markup=ANY)

@pytest.mark.asyncio
async def test_show_recipe_to_user_no_ingredients(callback_query, fsm_context):
    """
    Тестируем show_recipe_to_user, если ингредиенты не найдены.
    Ожидается: сообщение об отсутствии ингредиентов.
    """
    callback_query.data = "select_image_0"
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1"],
        "recipe_titles": ["Рецепт 1"]
    }

    with patch("chosen_recipe.fetch_ingredients_from_recipe", return_value=([], None)):
        await show_recipe_to_user(callback_query, fsm_context)

    callback_query.message.answer.assert_called_once_with("Ингредиенты не найдены.")
    fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_show_recipe_index_out_of_range(message, fsm_context):
    """
    Тестируем show_recipe, если индекс больше количества рецептов.
    Ожидается: сообщение "Больше рецептов нет." и завершение состояния.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1", "link2"],
        "recipe_titles": ["Рецепт 1", "Рецепт 2"],
        "recipe_image_urls": ["url1", "url2"]
    }

    await show_recipe(message, fsm_context, recipe_index=3)
    message.answer.assert_called_once_with("Больше рецептов нет.")
    fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_show_recipe_empty_data(message, fsm_context):
    """
    Тестируем show_recipe с пустыми данными.
    Ожидается: сообщение "Больше рецептов нет." и завершение состояния.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": [],
        "recipe_titles": [],
        "recipe_image_urls": []
    }

    await show_recipe(message, fsm_context, recipe_index=0)
    message.answer.assert_called_once_with("Больше рецептов нет.")
    fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_show_recipe_no_images(message, fsm_context):
    """
    Тестируем show_recipe, если изображения отсутствуют.
    Ожидается: корректная работа без отправки изображений.
    """
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1", "link2"],
        "recipe_titles": ["Рецепт 1", "Рецепт 2"],
        "recipe_image_urls": [None, None]
    }

    await show_recipe(message, fsm_context, recipe_index=0)
    message.answer.assert_called_with("Выберите рецепт:", reply_markup=ANY)

@pytest.mark.asyncio
async def test_show_recipe_to_user_empty_ingredients(callback_query, fsm_context):
    """
    Тестируем show_recipe_to_user, если ингредиенты пусты.
    Ожидается: сообщение "Ингредиенты не найдены."
    """
    callback_query.data = "select_image_0"
    fsm_context.get_data.return_value = {
        "recipe_links": ["link1"],
        "recipe_titles": ["Рецепт 1"]
    }

    with patch("chosen_recipe.fetch_ingredients_from_recipe", return_value=([], None)):
        await show_recipe_to_user(callback_query, fsm_context)

    callback_query.message.answer.assert_called_once_with("Ингредиенты не найдены.")
    fsm_context.finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_random_command(message):
    """
    Тестируем команду /random. Ожидается отправка сообщения с клавиатурой.
    """
    with patch("random_recipe.RandomRecipeState.waiting_for_cuisine_type.set", new_callable=AsyncMock) as mock_set_state:
        await random_command(message)
        message.answer.assert_called_once_with(
            "Введите тип кухни (например, итальянская, японская) или выберите 'Без разницы':",
            reply_markup=ANY
        )
        mock_set_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_random_any_cuisine_handler(callback_query, fsm_context):
    """
    Тестируем выбор "Без разницы". Ожидается сообщение о поиске рецептов.
    """
    callback_query.data = "random_any_cuisine"

    with patch("random_recipe.process_random_recipe", new_callable=AsyncMock) as mock_process:
        await random_any_cuisine_handler(callback_query, fsm_context)
        callback_query.message.answer.assert_any_call("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
        mock_process.assert_awaited_once_with(callback_query.message, fsm_context)

@pytest.mark.asyncio
async def test_random_any_cuisine_handler_with_flag(callback_query, fsm_context):
    """
    Тестируем random_any_cuisine_handler, когда в состоянии установлен флаг.
    Ожидается: вызов process_random_recipe с "любой" кухней.
    """
    fsm_context.get_data.return_value = {"flag": True}
    with patch("random_recipe.process_random_recipe", new_callable=AsyncMock) as mock_process:
        await random_any_cuisine_handler(callback_query, fsm_context)
        mock_process.assert_awaited_once_with(callback_query.message, fsm_context)
        callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_random_cuisine_handler(message, fsm_context):
    """
    Тестируем ввод типа кухни. Ожидается сообщение о поиске рецептов.
    """
    message.text = "Итальянская"

    with patch("random_recipe.process_random_recipe", new_callable=AsyncMock) as mock_process:
        await random_cuisine_handler(message, fsm_context)
        message.answer.assert_any_call("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")
        mock_process.assert_awaited_once_with(message, fsm_context)

def test_form_payload():
    """
    Тестируем формирование тела запроса для Yandex GPT.
    """
    request_text = "Предложи рецепт пасты"
    payload = form_payload(request_text)
    payload_json = json.loads(payload)
    assert payload_json["modelUri"] == f"gpt://{FOLDER_ID}/yandexgpt-lite/latest"
    assert payload_json["completionOptions"]["temperature"] == 1
    assert payload_json["completionOptions"]["maxTokens"] == 2000
    assert payload_json["messages"][1]["text"] == request_text

@pytest.mark.asyncio
async def test_process_random_recipe(message, fsm_context):
    """
    Тестируем процесс обработки случайного рецепта.
    """
    fsm_context.get_data.return_value = {"flag": False, "cuisine_type": "итальянская"}

    with patch("random_recipe.extract_event_details", return_value="Блюдо: Паста. Рецепт: Готовьте. Список ингредиентов на 2 порции: макароны 200г, сыр 100г.") as mock_extract, \
         patch("random_recipe.parse_gpt_result", return_value=("Паста", "Готовьте", ["макароны 200г", "сыр 100г"])) as mock_parse, \
         patch("random_recipe.search_ingredient_online", return_value="https://shop.com/macaronis") as mock_search:

        await process_random_recipe(message, fsm_context)
        mock_extract.assert_called_once()
        mock_parse.assert_called_once()
        mock_search.assert_called()
        message.answer.assert_called()

@pytest.mark.asyncio
async def test_process_random_recipe_error(message, fsm_context):
    """
    Тестируем обработку ошибки в process_random_recipe.
    """
    with patch("random_recipe.extract_event_details", side_effect=Exception("Ошибка GPT")):
        await process_random_recipe(message, fsm_context)
        message.answer.assert_called_once_with("Ошибка при запросе: Ошибка GPT")


@pytest.mark.asyncio
async def test_handle_accept_recipe(callback_query, fsm_context):
    """
    Тестируем обработчик принятия рецепта.
    """
    await handle_accept_recipe(callback_query, fsm_context)
    callback_query.message.answer.assert_called_once_with("Приятного аппетита! 🍽")
    fsm_context.finish.assert_awaited_once()
    callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_reject_recipe(callback_query, fsm_context):
    """
    Тестируем обработчик отклонения рецепта.
    """
    with patch("random_recipe.process_random_recipe", new_callable=AsyncMock) as mock_process:
        await handle_reject_recipe(callback_query, fsm_context)
        mock_process.assert_awaited_once_with(callback_query, fsm_context, is_callback=True)

