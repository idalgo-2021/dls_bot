import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Message
from aiogram.fsm.context import FSMContext
from app.handlers.common import cmd_cancel, cmd_start


@pytest.mark.asyncio
async def test_cmd_start_clears_state_and_sends_greeting():
    # Arrange
    user = User(
        id=123,
        is_bot=False,
        first_name="Ivan",
        last_name="Ivanov",
        username="ivan",
        language_code="ru",
    )
    message = MagicMock(spec=Message)
    message.from_user = user
    message.answer = AsyncMock()
    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()

    # Act
    await cmd_start(message, state)

    # Assert
    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once()
    sent_text = message.answer.call_args[0][0]
    assert "Привет, Ivan Ivanov! Я — dls_bot 🤖" in sent_text
    assert "команда /nst" in sent_text
    assert "команда /cyclegan" in sent_text
    assert "/help" in sent_text
    assert "/cancel" in sent_text
    assert "echo-режим" in sent_text


@pytest.mark.asyncio
async def test_cmd_cancel_when_no_state():
    # Arrange
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    state = MagicMock(spec=FSMContext)
    state.get_state = AsyncMock(return_value=None)
    state.clear = AsyncMock()

    # Act
    await cmd_cancel(message, state)  # Импортируем cmd_cancel

    # Assert
    state.get_state.assert_awaited_once()
    state.clear.assert_not_awaited()  # Проверяем, что clear НЕ был вызван
    message.answer.assert_awaited_once_with("Нет активной операции для отмены.")
