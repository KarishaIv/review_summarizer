import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from aiogram import types
from aiogram.types import  CallbackQuery
from aiogram.dispatcher import FSMContext
from aiogram import Dispatcher


from main import (
    dp,
    RecipeStates,
    button_one_handler,
    check_button,
    handle_recipe_accept,
    handle_recipe_reject,
    select_image_handler,
    handle_next_recipe,
    show_recipe,
    recipe_name_handler
)


@pytest.fixture
def callback_query():
    """Фикстура для мокирования callback_query"""
    mock_cb = MagicMock(spec=CallbackQuery)
    mock_cb.message = MagicMock(spec=types.Message)
    mock_cb.message.chat.id = 123456789
    mock_cb.message.answer = AsyncMock()
    mock_cb.message.edit_text = AsyncMock()
    mock_cb.answer = AsyncMock()
    mock_cb.from_user = MagicMock(id=12345, is_bot=False, first_name="TestUser")
    return mock_cb


@pytest.fixture
def fsm_context():
    """Фикстура для мокирования контекста FSM."""
    fsm = MagicMock(spec=FSMContext)
    fsm.set_state = AsyncMock()
    fsm.finish = AsyncMock()
    fsm.update_data = AsyncMock()
    fsm.get_data = AsyncMock(return_value={})
    return fsm


@pytest.mark.asyncio
async def test_first_button_handler(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки first_button.
    Ожидается: бот запросит блюдо и перейдёт в состояние waiting_for_recipe_name.
    """
    callback_query.data = "first_button"
    with patch("main.RecipeStates.waiting_for_recipe_name.set", new_callable=AsyncMock) as mock_set_state:
        await check_button(callback_query)
        callback_query.message.answer.assert_called_once_with("Введите блюдо:")
        mock_set_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_button_one_handler(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки button_one.
    Ожидается: бот запросит блюдо и установит состояние waiting_for_recipe_name.
    """
    callback_query.data = "button_one"
    with patch("main.RecipeStates.waiting_for_recipe_name.set", new_callable=AsyncMock) as mock_set_state:
        await button_one_handler(callback_query)
        callback_query.message.answer.assert_called_once_with("Введите блюдо:")
        mock_set_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_recipe_accept(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки, которая подтверждает выбор рецепта.
    Ожидается: бот скажет "Приятного аппетита!" и завершит состояние.
    """
    callback_query.data = "recipe_accept"

    await handle_recipe_accept(callback_query, fsm_context)

    callback_query.message.answer.assert_called_once_with("Приятного аппетита!")
    fsm_context.finish.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_recipe_reject(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки, которая отказывается от рецепта.
    Ожидается: бот попытается показать следующий рецепт.
    """
    callback_query.data = "recipe_reject"
    with patch("main.show_recipe", new_callable=AsyncMock) as mock_show_recipe:
        fsm_context.get_data.return_value = {"current_recipe_index": 0}

        await handle_recipe_reject(callback_query, fsm_context)
        mock_show_recipe.assert_awaited_once_with(callback_query.message, fsm_context, recipe_index=1)


@pytest.mark.asyncio
async def test_handle_next_recipe_show_next(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки show_next_recipe.
    Ожидается: бот покажет следующий рецепт.
    """
    callback_query.data = "show_next_recipe"
    fsm_context.get_data.return_value = {"current_recipe_index": 0}

    with patch("main.show_recipe", new_callable=AsyncMock) as mock_show_recipe:
        await handle_next_recipe(callback_query, fsm_context)
        mock_show_recipe.assert_awaited_once_with(callback_query.message, fsm_context, recipe_index=1)


@pytest.mark.asyncio
async def test_handle_next_recipe_end_view(callback_query, fsm_context):
    """
    Тестируем нажатие кнопки end_recipe_view.
    Ожидается: бот пожелает приятного аппетита и завершит состояние.
    """
    callback_query.data = "end_recipe_view"

    await handle_next_recipe(callback_query, fsm_context)
    callback_query.message.answer.assert_called_once_with("Приятного аппетита!")
    fsm_context.finish.assert_awaited_once()

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

    with patch("main.fetch_reviews", return_value=([], [], [])):
        await recipe_name_handler(callback_query.message, fsm_context)

        callback_query.message.answer.assert_any_call("Ищу рецепты и ингредиенты, это может занять немного времени...🫦")

        callback_query.message.answer.assert_any_call("Рецепты не найдены.")

        # Проверяем, что метод answer вызывался ровно два раза
        assert callback_query.message.answer.call_count == 2

        fsm_context.finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_select_image_handler_invalid_data(callback_query, fsm_context):
    """
    Тестируем выбор рецепта с некорректными данными.
    Ожидается: бот отправит сообщение об ошибке.
    """
    callback_query.data = "select_image_invalid"

    await select_image_handler(callback_query, fsm_context)

    callback_query.answer.assert_called_once_with("Некорректный индекс рецепта.")

