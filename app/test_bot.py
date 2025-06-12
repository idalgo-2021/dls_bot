import asyncio

# import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.bot as bot_module


@pytest.mark.asyncio
@patch("app.bot.settings")
@patch("app.bot.NSTEngine")
@patch("app.bot.nst_params")
@patch("app.bot.CycleGANEngine")
@patch("app.bot.cyclegan_params")
@patch("app.bot.nst_router")
@patch("app.bot.cyclegan_router")
@patch("app.bot.common_router")
@patch("app.bot.MemoryStorage")
@patch("app.bot.Bot")
@patch("app.bot.Dispatcher")
async def test_main_polling_mode(
    mock_dispatcher,
    mock_bot,
    mock_memorystorage,
    mock_common_router,
    mock_cyclegan_router,
    mock_nst_router,
    mock_cyclegan_params,
    mock_CycleGANEngine,
    mock_nst_params,
    mock_NSTEngine,
    mock_settings,
):
    # Setup mocks
    mock_settings.BOT_RUN_MODE = "polling"
    mock_settings.TELEGRAM_BOT_TOKEN.get_secret_value.return_value = "token"
    mock_dispatcher_instance = MagicMock()
    mock_dispatcher.return_value = mock_dispatcher_instance
    mock_bot_instance = MagicMock()
    mock_bot.return_value = mock_bot_instance
    mock_memorystorage.return_value = MagicMock()

    # NSTEngine
    mock_nst_params.__bool__.return_value = True
    mock_nst_engine_instance = MagicMock()
    mock_nst_engine_instance._initialized = True
    mock_NSTEngine.return_value = mock_nst_engine_instance

    # CycleGANEngine
    mock_cyclegan_params.__bool__.return_value = True
    mock_cyclegan_engine_instance = MagicMock()
    mock_cyclegan_engine_instance._initialized = True
    mock_CycleGANEngine.return_value = mock_cyclegan_engine_instance

    # Patch start_polling to avoid running forever
    mock_dispatcher_instance.start_polling = AsyncMock()

    await bot_module.main()

    # Check that polling was started
    mock_dispatcher_instance.start_polling.assert_awaited_with(mock_bot_instance)
    # Routers included
    mock_dispatcher_instance.include_router.assert_any_call(mock_nst_router)
    mock_dispatcher_instance.include_router.assert_any_call(mock_cyclegan_router)
    mock_dispatcher_instance.include_router.assert_any_call(mock_common_router)

    # Engines set
    # assert mock_dispatcher_instance.__setitem__.call_args_list[0][0][0] == "nst_engine"
    # assert mock_dispatcher_instance.__setitem__.call_args_list[1][0][0] == "cyclegan_engine"
    # Получаем список всех ключей, которые были установлены в dp
    set_keys = [call[0][0] for call in mock_dispatcher_instance.__setitem__.call_args_list]
    # Проверяем, что оба нужных ключа присутствуют в списке
    assert "nst_engine" in set_keys
    assert "cyclegan_engine" in set_keys


@pytest.mark.asyncio
@patch("app.bot.settings")
@patch("app.bot.NSTEngine")
@patch("app.bot.nst_params")
@patch("app.bot.CycleGANEngine")
@patch("app.bot.cyclegan_params")
@patch("app.bot.nst_router")
@patch("app.bot.cyclegan_router")
@patch("app.bot.common_router")
@patch("app.bot.MemoryStorage")
@patch("app.bot.Bot")
@patch("app.bot.Dispatcher")
@patch("app.bot.web")
@patch("app.bot.SimpleRequestHandler")
@patch("app.bot.setup_application")
async def test_main_webhook_mode(
    mock_setup_application,
    mock_SimpleRequestHandler,
    mock_web,
    mock_dispatcher,
    mock_bot,
    mock_memorystorage,
    mock_common_router,
    mock_cyclegan_router,
    mock_nst_router,
    mock_cyclegan_params,
    mock_CycleGANEngine,
    mock_nst_params,
    mock_NSTEngine,
    mock_settings,
):
    # Setup mocks
    mock_settings.BOT_RUN_MODE = "webhook"
    mock_settings.TELEGRAM_BOT_TOKEN.get_secret_value.return_value = "token"
    mock_settings.WEBHOOK_URL = "https://example.com"
    mock_settings.WEBHOOK_PORT = 8443
    mock_settings.WEBHOOK_PATH = "/webhook"
    mock_settings.WEBHOOK_SECRET = None

    mock_dispatcher_instance = MagicMock()
    mock_dispatcher.return_value = mock_dispatcher_instance
    mock_bot_instance = MagicMock()
    mock_bot.return_value = mock_bot_instance
    mock_memorystorage.return_value = MagicMock()

    # NSTEngine
    mock_nst_params.__bool__.return_value = True
    mock_nst_engine_instance = MagicMock()
    # mock_nst_engine_instance._initialized = True
    mock_NSTEngine.return_value = mock_nst_engine_instance

    # CycleGANEngine
    mock_cyclegan_params.__bool__.return_value = True
    mock_cyclegan_engine_instance = MagicMock()
    # mock_cyclegan_engine_instance._initialized = True
    mock_CycleGANEngine.return_value = mock_cyclegan_engine_instance

    # aiohttp mocks
    mock_app = MagicMock()
    mock_web.Application.return_value = mock_app

    mock_runner = MagicMock()

    mock_runner.setup = AsyncMock()
    mock_runner.cleanup = AsyncMock()

    mock_web.AppRunner.return_value = mock_runner
    mock_site = MagicMock()

    # Указываем, что его метод start - это AsyncMock
    mock_site.start = AsyncMock()

    mock_web.TCPSite.return_value = mock_site

    # Patch asyncio.Event().wait to avoid blocking forever
    with patch("asyncio.Event") as mock_event_cls:
        mock_event = MagicMock()
        mock_event.wait = AsyncMock(side_effect=asyncio.CancelledError)
        mock_event_cls.return_value = mock_event

        await bot_module.main()

    # Webhook server started
    mock_web.AppRunner.assert_called_with(mock_app)
    mock_web.TCPSite.assert_called_with(
        mock_runner, host="0.0.0.0", port=mock_settings.WEBHOOK_PORT
    )
    mock_site.start.assert_awaited()
    mock_SimpleRequestHandler.return_value.register.assert_called_with(
        mock_app, path=mock_settings.WEBHOOK_PATH
    )
    mock_setup_application.assert_called_with(
        mock_app, mock_dispatcher_instance, bot=mock_bot_instance
    )
    # Routers included
    mock_dispatcher_instance.include_router.assert_any_call(mock_nst_router)
    mock_dispatcher_instance.include_router.assert_any_call(mock_cyclegan_router)
    mock_dispatcher_instance.include_router.assert_any_call(mock_common_router)


@pytest.mark.asyncio
@patch("app.bot.settings")
@patch("app.bot.NSTEngine")
@patch("app.bot.nst_params")
@patch("app.bot.CycleGANEngine")
@patch("app.bot.cyclegan_params")
@patch("app.bot.nst_router")
@patch("app.bot.cyclegan_router")
@patch("app.bot.common_router")
@patch("app.bot.MemoryStorage")
@patch("app.bot.Bot")
@patch("app.bot.Dispatcher")
async def test_main_nst_engine_init_failure(
    mock_dispatcher,
    mock_bot,
    mock_memorystorage,
    mock_common_router,
    mock_cyclegan_router,
    mock_nst_router,
    mock_cyclegan_params,
    mock_CycleGANEngine,
    mock_nst_params,
    mock_NSTEngine,
    mock_settings,
):
    # Setup mocks
    mock_settings.BOT_RUN_MODE = "polling"
    mock_settings.TELEGRAM_BOT_TOKEN.get_secret_value.return_value = "token"
    mock_dispatcher_instance = MagicMock()
    mock_dispatcher.return_value = mock_dispatcher_instance
    mock_bot_instance = MagicMock()
    mock_bot.return_value = mock_bot_instance
    mock_memorystorage.return_value = MagicMock()

    # NSTEngine fails to initialize
    mock_nst_params.__bool__.return_value = True
    mock_nst_engine_instance = MagicMock()
    mock_nst_engine_instance._initialized = False
    mock_NSTEngine.return_value = mock_nst_engine_instance

    # CycleGANEngine
    mock_cyclegan_params.__bool__.return_value = False

    # Patch start_polling to avoid running forever
    mock_dispatcher_instance.start_polling = AsyncMock()

    await bot_module.main()

    # NST router should not be included
    calls = [call[0][0] for call in mock_dispatcher_instance.include_router.call_args_list]
    assert mock_nst_router not in calls
    # Common router should be included
    assert mock_common_router in calls


@pytest.mark.asyncio
@patch("app.bot.settings")
@patch("app.bot.NSTEngine")
@patch("app.bot.nst_params")
@patch("app.bot.CycleGANEngine")
@patch("app.bot.cyclegan_params")
@patch("app.bot.nst_router")
@patch("app.bot.cyclegan_router")
@patch("app.bot.common_router")
@patch("app.bot.MemoryStorage")
@patch("app.bot.Bot")
@patch("app.bot.Dispatcher")
async def test_main_cyclegan_engine_init_failure(
    mock_dispatcher,
    mock_bot,
    mock_memorystorage,
    mock_common_router,
    mock_cyclegan_router,
    mock_nst_router,
    mock_cyclegan_params,
    mock_CycleGANEngine,
    mock_nst_params,
    mock_NSTEngine,
    mock_settings,
):
    # Setup mocks
    mock_settings.BOT_RUN_MODE = "polling"
    mock_settings.TELEGRAM_BOT_TOKEN.get_secret_value.return_value = "token"
    mock_dispatcher_instance = MagicMock()
    mock_dispatcher.return_value = mock_dispatcher_instance
    mock_bot_instance = MagicMock()
    mock_bot.return_value = mock_bot_instance
    mock_memorystorage.return_value = MagicMock()

    # NSTEngine
    mock_nst_params.__bool__.return_value = False

    # CycleGANEngine fails to initialize
    mock_cyclegan_params.__bool__.return_value = True
    mock_cyclegan_engine_instance = MagicMock()
    mock_cyclegan_engine_instance._initialized = False
    mock_CycleGANEngine.return_value = mock_cyclegan_engine_instance

    # Patch start_polling to avoid running forever
    mock_dispatcher_instance.start_polling = AsyncMock()

    await bot_module.main()

    # CycleGAN router should not be included
    calls = [call[0][0] for call in mock_dispatcher_instance.include_router.call_args_list]
    assert mock_cyclegan_router not in calls
    # Common router should be included
    assert mock_common_router in calls
