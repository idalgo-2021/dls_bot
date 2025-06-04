import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from app.env_settings import settings
from app.handlers import nst_router, common_router
from app.nst_engine import NSTEngine
from app.nst_config import nst_params


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    bot_info = await bot.get_me()
    logger.info(f"Bot @{bot_info.username} (ID: {bot_info.id}) started.")

    if settings.BOT_RUN_MODE == "webhook":
        if not settings.WEBHOOK_URL:
            logger.error("WEBHOOK_URL must be set in .env for webhook mode.")
            return
        webhook_url = str(settings.WEBHOOK_URL).rstrip("/") + settings.WEBHOOK_PATH
        logger.info(f"Setting webhook to: {webhook_url}")
        secret = settings.WEBHOOK_SECRET.get_secret_value() if settings.WEBHOOK_SECRET else None
        params_to_set_webhook = {
            "url": webhook_url,
            "drop_pending_updates": True,
            "secret_token": secret,
        }
        if settings.WEBHOOK_CERT_PATH:
            from aiogram.types import FSInputFile

            try:
                cert_file = FSInputFile(settings.WEBHOOK_CERT_PATH)
                params_to_set_webhook["certificate"] = cert_file
                logger.info((f"Using self-signed certificate: " f"{settings.WEBHOOK_CERT_PATH}"))
            except Exception as e:
                logger.error(
                    f"Error preparing certificate file " f"{settings.WEBHOOK_CERT_PATH}: {e}"
                )
                return
        try:
            await bot.set_webhook(**params_to_set_webhook)
            webhook_info = await bot.get_webhook_info()
            logger.info(f"Webhook info: {webhook_info}")
            if webhook_info.url != webhook_url:
                logger.error(
                    f"Webhook was set to {webhook_info.url}, " f"but expected {webhook_url}"
                )
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)
    else:
        logger.info("Running in polling mode. Deleting any existing webhook.")
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Failed to delete webhook: {e}", exc_info=True)


async def on_shutdown(bot: Bot, dispatcher: Dispatcher):
    logger.warning("Bot shutting down...")

    if settings.BOT_RUN_MODE == "webhook":
        logger.info("Deleting webhook...")
        try:
            await bot.delete_webhook()
        except Exception as e:
            logger.error(f"Failed to delete webhook on shutdown: {e}", exc_info=True)

    if dispatcher and dispatcher.storage:
        logger.info("Closing FSM storage...")
        await dispatcher.storage.close()
        if hasattr(dispatcher.storage, "wait_closed"):
            await dispatcher.storage.wait_closed()

    if bot and bot.session:
        logger.info("Closing bot session...")
        await bot.session.close()

    logger.info("Bot stopped.")


async def main():
    storage = MemoryStorage()
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=storage, bot=bot)

    # Регистрация роутеров
    # for router_item in all_routers:
    #     dp.include_router(router_item)
    dp.include_router(nst_router)
    dp.include_router(common_router)

    # Регистрация startup/shutdown хуков
    # on_startup получит bot от Dispatcher'а
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Инициализация NST движка
    try:
        nst_engine_instance = NSTEngine(nst_params)
        dp["nst_engine"] = nst_engine_instance
        logger.info("NSTEngine instance created and added to Dispatcher.")
    except Exception as e:
        logger.critical(
            f"Failed to initialize NSTEngine: {e}. NST functionality will be unavailable.",
            exc_info=True,
        )
        dp["nst_engine"] = None

    aiohttp_runner = None
    try:
        if settings.BOT_RUN_MODE == "polling":
            logger.info("Starting polling...")
            await dp.start_polling(bot)

        elif settings.BOT_RUN_MODE == "webhook":
            if not settings.WEBHOOK_URL or not settings.WEBHOOK_PORT:
                logger.error(("WEBHOOK_URL and WEBHOOK_PORT must be set for " "webhook mode."))
                return

            app = web.Application()
            secret_val = (
                settings.WEBHOOK_SECRET.get_secret_value() if settings.WEBHOOK_SECRET else None
            )
            webhook_requests_handler = SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=secret_val,
            )
            webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
            setup_application(app, dp, bot=bot)

            aiohttp_runner = web.AppRunner(app)
            await aiohttp_runner.setup()
            site = web.TCPSite(
                aiohttp_runner,
                host="0.0.0.0",
                port=settings.WEBHOOK_PORT,
            )
            await site.start()
            logger.info(
                f"Webhook server is running on http://"
                f"0.0.0.0:{settings.WEBHOOK_PORT}{settings.WEBHOOK_PATH}"
            )
            await asyncio.Event().wait()
    except asyncio.exceptions.CancelledError:
        logger.info("Main loop was cancelled. Proceeding with shutdown.")
    except (KeyboardInterrupt, SystemExit) as e:
        logger.info(f"Bot execution stopped by {type(e).__name__}.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in main: {e}", exc_info=True)
    finally:
        logger.info("Starting cleanup procedures in main finally...")
        if settings.BOT_RUN_MODE == "polling":
            if dp.storage and hasattr(dp.storage, "closed"):
                is_storage_closed = getattr(dp.storage, "closed", True)
                if not is_storage_closed:
                    logger.warning(
                        (
                            (
                                "FSM Storage (polling) might not have been "
                                "closed by on_shutdown. Closing now."
                            )
                        )
                    )
                    await dp.storage.close()
                    if hasattr(dp.storage, "wait_closed"):
                        await dp.storage.wait_closed()
        elif aiohttp_runner:
            logger.info("Cleaning up aiohttp runner.")
            await aiohttp_runner.cleanup()

        logger.info("Main finally cleanup finished.")


if __name__ == "__main__":
    asyncio.run(main())
