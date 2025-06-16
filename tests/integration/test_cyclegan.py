import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, PhotoSize, Chat
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from PIL import Image

import app.handlers.cyclegan as cyclegan
from app.handlers.cyclegan import CycleGANStates


@pytest.fixture
def fake_user():
    return User(id=123, is_bot=False, first_name="Test", username="testuser")


@pytest.fixture
def fake_chat():
    return Chat(id=456, type="private")


@pytest.fixture
def fake_message(fake_user, fake_chat):
    msg = MagicMock(spec=Message)
    msg.from_user = fake_user
    msg.chat = fake_chat
    msg.photo = [
        PhotoSize(file_id="photo_id", width=100, height=100, file_unique_id="unique")
    ]
    msg.answer = AsyncMock()
    msg.answer_photo = AsyncMock()
    return msg


@pytest.fixture
def fake_callback(fake_user, fake_chat):
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = fake_user
    cb.message = MagicMock(spec=Message)
    cb.message.chat = fake_chat
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


@pytest.fixture
def fake_state():
    state = AsyncMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.get_data = AsyncMock(return_value={})
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    return state


@pytest.fixture
def fake_bot():
    bot = AsyncMock(spec=Bot)
    bot.download = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot


@pytest.fixture
def fake_cyclegan_engine():
    """Фикстура для мока движка CycleGAN."""
    engine = MagicMock()
    engine.get_available_styles.return_value = {
        "monet": "Monet Style",
        "vangogh": "Van Gogh Style",
    }
    engine.stylize.return_value = Image.new("RGB", (256, 256))
    return engine


@pytest.mark.asyncio
async def test_cmd_cyclegan_start_success(
    fake_message, fake_state, fake_cyclegan_engine
):
    """Тест успешного запуска флоу /cyclegan."""
    await cyclegan.cmd_cyclegan_start(fake_message, fake_state, fake_cyclegan_engine)

    fake_state.clear.assert_awaited_once()
    fake_cyclegan_engine.get_available_styles.assert_called_once()

    call_args, call_kwargs = fake_message.answer.call_args
    assert "Выберите стиль, который хотите применить:" in call_args[0]
    assert "reply_markup" in call_kwargs

    fake_state.set_state.assert_awaited_once_with(CycleGANStates.choosing_style)


@pytest.mark.asyncio
async def test_cmd_cyclegan_start_no_styles(
    fake_message, fake_state, fake_cyclegan_engine
):
    """Тест запуска /cyclegan, когда нет доступных стилей."""
    fake_cyclegan_engine.get_available_styles.return_value = (
        {}
    )  # Имитируем пустой ответ

    await cyclegan.cmd_cyclegan_start(fake_message, fake_state, fake_cyclegan_engine)

    fake_message.answer.assert_awaited_once_with(
        "К сожалению, сейчас нет доступных стилей CycleGAN. Попробуйте позже."
    )
    fake_state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_cq_choose_style(fake_callback, fake_state):
    """Тест выбора стиля по кнопке."""
    fake_callback.data = "cyclegan_style_monet"

    await cyclegan.cq_choose_style(fake_callback, fake_state)

    fake_state.update_data.assert_awaited_once_with(chosen_style="monet")
    fake_callback.message.edit_text.assert_awaited_once()
    call_args, _ = fake_callback.message.edit_text.call_args
    assert "Отлично! Вы выбрали стиль." in call_args[0]

    fake_state.set_state.assert_awaited_once_with(CycleGANStates.uploading_photo)
    fake_callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_photo_for_cyclegan_success(
    fake_message, fake_state, fake_cyclegan_engine, fake_bot
):
    """Тест успешной обработки фото."""
    fake_state.get_data.return_value = {"chosen_style": "monet"}

    processing_message_mock = MagicMock(spec=Message)
    processing_message_mock.delete = AsyncMock()
    fake_message.answer.return_value = processing_message_mock

    # --- ИСПРАВЛЕНИЕ: Имитируем скачивание файла ---
    # Создаем "фейковое" изображение в байтах
    fake_image_bytes = io.BytesIO()
    Image.new("RGB", (10, 10)).save(fake_image_bytes, format="JPEG")
    fake_image_bytes.seek(0)

    # Создаем функцию-имитатор для bot.download
    # Она будет записывать байты в переданный ей объект destination
    async def mock_download(file_id, destination):
        destination.write(fake_image_bytes.read())

    # Назначаем эту функцию нашему моку
    fake_bot.download.side_effect = mock_download
    # ---------------------------------------------

    with patch("app.handlers.cyclegan.asyncio.get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_run_in_executor = AsyncMock(return_value=Image.new("RGB", (256, 256)))
        mock_loop.run_in_executor = mock_run_in_executor
        mock_get_loop.return_value = mock_loop

        with patch("app.handlers.cyclegan.format_duration", return_value="5 сек"):
            await cyclegan.handle_photo_for_cyclegan(
                fake_message, fake_state, fake_cyclegan_engine, fake_bot
            )

    # Теперь все проверки должны пройти, так как выполнение дойдет до
    # конца try блока
    fake_bot.download.assert_awaited_once()
    mock_run_in_executor.assert_awaited_once()

    func_to_run = mock_run_in_executor.call_args[0][1]
    assert func_to_run.func == fake_cyclegan_engine.stylize
    assert func_to_run.keywords["style_name"] == "monet"

    fake_message.answer_photo.assert_awaited_once()
    processing_message_mock.delete.assert_awaited_once()
    fake_state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_photo_for_cyclegan_no_style_in_state(
    fake_message, 
    fake_state, 
    fake_cyclegan_engine,
    fake_bot
):
    """Тест, когда в состоянии FSM не оказалось выбранного стиля."""
    fake_state.get_data.return_value = {}  # Нет chosen_style
    
    # 2. Передаем fake_bot в вызов хендлера
    await cyclegan.handle_photo_for_cyclegan(
        fake_message, fake_state, fake_cyclegan_engine, fake_bot
    )

    # Остальные проверки остаются без изменений
    fake_message.answer.assert_awaited_once()
    call_args, _ = fake_message.answer.call_args
    assert "ошибка, стиль не был выбран" in call_args[0]
    fake_state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_incorrect_upload(fake_message):
    """Тест отправки текста вместо фото."""
    await cyclegan.incorrect_upload(fake_message)

    fake_message.answer.assert_awaited_once()
    call_args, _ = fake_message.answer.call_args
    assert "Пожалуйста, отправьте именно фотографию" in call_args[0]


@pytest.mark.asyncio
async def test_cancel_operation_by_command(fake_message, fake_state):
    """Тест отмены операции командой /cancel."""
    fake_state.get_state.return_value = CycleGANStates.uploading_photo

    with patch("app.handlers.cyclegan.cmd_start", new=AsyncMock()) as mock_cmd_start:
        await cyclegan.cmd_cancel_cyclegan(fake_message, fake_state)

        # Проверяем, что состояние очищено
        fake_state.clear.assert_awaited_once()
        # Проверяем, что отправлен ответ об отмене
        fake_message.answer.assert_awaited_once_with("Процесс CycleGAN отменен.")
        # Проверяем, что в конце вызывается cmd_start для возврата в начало
        mock_cmd_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_operation_by_callback(fake_callback, fake_state):
    """Тест отмены операции кнопкой."""
    fake_state.get_state.return_value = CycleGANStates.choosing_style

    with patch("app.handlers.cyclegan.cmd_start", new=AsyncMock()) as mock_cmd_start:
        await cyclegan.cb_cancel_cyclegan(fake_callback, fake_state)

        fake_state.clear.assert_awaited_once()
        fake_callback.message.edit_text.assert_awaited_once_with(
            "Процесс CycleGAN отменен."
        )
        mock_cmd_start.assert_awaited_once()
        fake_callback.answer.assert_awaited_once()
