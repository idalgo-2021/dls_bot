import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User, PhotoSize
from aiogram.fsm.context import FSMContext

from aiogram import Bot

import app.handlers.nst as nst


@pytest.fixture
def fake_user():
    return User(id=123, is_bot=False, first_name="Test")


@pytest.fixture
def fake_message(fake_user):
    msg = MagicMock(spec=Message)
    msg.from_user = fake_user
    msg.photo = [
        PhotoSize(
            file_id="photo_id",
            width=100,
            height=100,
            file_unique_id="unique",
            file_size=1234,
        )
    ]
    msg.answer = AsyncMock()
    msg.answer_photo = AsyncMock()
    return msg


@pytest.fixture
def fake_callback(fake_user):
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = fake_user
    cb.data = "nst_upload_style"
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


@pytest.fixture
def fake_state():
    state = AsyncMock(spec=FSMContext)
    state.get_data = AsyncMock(return_value={})
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    return state


@pytest.fixture
def fake_bot():
    bot = AsyncMock(spec=Bot)
    bot.get_file = AsyncMock(return_value=MagicMock(file_path="test.jpg"))
    bot.download_file = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot


@pytest.fixture
def fake_nst_engine():
    engine = MagicMock()
    engine.get_available_styles.return_value = {"starry.jpg": "Starry Night"}
    engine.process_images.return_value = b"imagebytes"
    return engine


@pytest.fixture
def patch_nst_params(tmp_path, monkeypatch):
    class DummyParams:
        DEFAULT_STYLE_IMAGE_DIR = tmp_path
        TEMP_IMAGE_DIR = tmp_path

    monkeypatch.setattr(nst, "nst_params", DummyParams())


@pytest.mark.asyncio
async def test_cmd_nst_start(
    fake_message, fake_state, fake_nst_engine, patch_nst_params
):
    await nst.cmd_nst_start(fake_message, fake_state, fake_nst_engine)
    fake_message.answer.assert_called()
    fake_state.set_state.assert_called_with(nst.NSTStates.choosing_style_source)


@pytest.mark.asyncio
async def test_cb_upload_style(fake_callback, fake_state):
    await nst.cb_upload_style(fake_callback, fake_state)
    fake_callback.message.edit_text.assert_called()
    fake_state.set_state.assert_called_with(nst.NSTStates.waiting_for_style_upload)
    fake_callback.answer.assert_called()


@pytest.mark.asyncio
async def test_cb_default_style_success(
    fake_callback, fake_state, patch_nst_params, tmp_path
):
    # Setup style file
    style_file = tmp_path / "starry.jpg"
    style_file.write_bytes(b"123")
    fake_callback.data = "nst_default_style:starry.jpg"
    await nst.cb_default_style(fake_callback, fake_state)
    fake_callback.message.edit_text.assert_called()
    fake_state.update_data.assert_called()
    fake_state.set_state.assert_called_with(nst.NSTStates.waiting_for_content_image)
    fake_callback.answer.assert_called()


@pytest.mark.asyncio
async def test_cb_default_style_not_found(fake_callback, fake_state, patch_nst_params):
    fake_callback.data = "nst_default_style:missing.jpg"
    fake_callback.message = AsyncMock()
    fake_callback.message.edit_text = AsyncMock()
    with patch("app.handlers.nst.common_cmd_start", new=AsyncMock()):
        await nst.cb_default_style(fake_callback, fake_state)
    fake_callback.message.edit_text.assert_called()
    fake_state.clear.assert_called()


@pytest.mark.asyncio
async def test_nst_style_image_uploaded_success(
    fake_message, fake_state, fake_bot, patch_nst_params, tmp_path
):
    await nst.nst_style_image_uploaded(fake_message, fake_state, fake_bot)
    fake_bot.download_file.assert_called()
    fake_state.update_data.assert_called()
    fake_state.set_state.assert_called_with(nst.NSTStates.waiting_for_content_image)
    fake_message.answer.assert_called()


@pytest.mark.asyncio
async def test_nst_style_image_uploaded_no_photo(fake_message, fake_state, fake_bot):
    fake_message.photo = []
    await nst.nst_style_image_uploaded(fake_message, fake_state, fake_bot)
    fake_message.answer.assert_called()


@pytest.mark.asyncio
async def test_nst_style_image_invalid_upload(fake_message):
    await nst.nst_style_image_invalid_upload(fake_message)
    fake_message.answer.assert_called()


@pytest.mark.asyncio
async def test_nst_content_image_received_success(
    fake_message, fake_state, fake_bot, fake_nst_engine, patch_nst_params, tmp_path
):
    # Setup FSM state
    style_file = tmp_path / "starry.jpg"
    style_file.write_bytes(b"123")
    fake_state.get_data = AsyncMock(
        return_value={"style_image_path": str(style_file), "style_is_default": True}
    )
    with patch("app.handlers.nst.format_duration", return_value="1 сек"):
        await nst.nst_content_image_received(
            fake_message, fake_state, fake_bot, fake_nst_engine
        )
    fake_message.answer_photo.assert_called()
    fake_state.clear.assert_called()


@pytest.mark.asyncio
async def test_nst_content_image_received_no_style_path(
    fake_message, fake_state, fake_bot, fake_nst_engine
):
    fake_state.get_data = AsyncMock(return_value={})
    await nst.nst_content_image_received(
        fake_message, fake_state, fake_bot, fake_nst_engine
    )
    fake_message.answer.assert_called()
    fake_state.clear.assert_called()


@pytest.mark.asyncio
async def test_nst_content_image_invalid(fake_message):
    await nst.nst_content_image_invalid(fake_message)
    fake_message.answer.assert_called()


@pytest.mark.asyncio
async def test_cmd_cancel_nst(fake_message, fake_state):
    with patch("app.handlers.nst.cancel_nst_operation", new=AsyncMock()):
        await nst.cmd_cancel_nst(fake_message, fake_state)
        nst.cancel_nst_operation.assert_awaited()


@pytest.mark.asyncio
async def test_cb_cancel_nst(fake_callback, fake_state):
    with patch("app.handlers.nst.cancel_nst_operation", new=AsyncMock()):
        await nst.cb_cancel_nst(fake_callback, fake_state)
        nst.cancel_nst_operation.assert_awaited()


@pytest.mark.asyncio
async def test_cancel_nst_operation_message(fake_message, fake_state):
    fake_state.get_state = AsyncMock(return_value="some_state")
    fake_state.get_data = AsyncMock(return_value={})
    fake_state.clear = AsyncMock()
    with patch("app.handlers.nst.common_cmd_start", new=AsyncMock()):
        await nst.cancel_nst_operation(fake_message, fake_state)
    fake_message.answer.assert_called()


@pytest.mark.asyncio
async def test_cancel_nst_operation_callback(fake_callback, fake_state):
    fake_state.get_state = AsyncMock(return_value="some_state")
    fake_state.get_data = AsyncMock(return_value={})
    fake_state.clear = AsyncMock()
    fake_callback.message.edit_text = AsyncMock()
    with patch("app.handlers.nst.common_cmd_start", new=AsyncMock()):
        await nst.cancel_nst_operation(fake_callback, fake_state, is_callback=True)
    fake_callback.message.edit_text.assert_called()
    fake_callback.answer.assert_called()
