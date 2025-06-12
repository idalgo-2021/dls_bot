import asyncio
import logging

from pathlib import Path
import shutil
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
from pydantic import ValidationError

from app.env_settings import Settings

from app.handlers import nst_router, common_router, cyclegan_router

from app.nst_engine import NSTEngine
from app.nst_config import nst_params

from app.cyclegan_engine import CycleGANEngine
from app.cyclegan_config import cyclegan_params

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def cleanup_temp_directory(path: Path) -> None:
    logger.info(f"Cleaning temporary directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    for item in path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
            logger.info(f"Removed temporary item: {item}")
        except Exception as e:
            logger.error(f"Failed to delete {item}: {e}")


async def on_startup(bot: Bot, dispatcher: Dispatcher):
    logger.info("Performing startup cleanup...")
    try:
        cleanup_temp_directory(nst_params.TEMP_IMAGE_DIR)
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)

    bot_info = await bot.get_me()
    logger.info(f"Bot @{bot_info.username} (ID: {bot_info.id}) started.")

    settings: Settings = dispatcher["settings"]

    if settings.BOT_RUN_MODE == "webhook":
        if not settings.WEBHOOK_URL:
            logger.error("WEBHOOK_URL must be set in .env for webhook mode.")
            return
        webhook_url = str(settings.WEBHOOK_URL).rstrip("/") + settings.WEBHOOK_PATH
        logger.info(f"Setting webhook to: {webhook_url}")
        secret = settings.WEBHOOK_SECRET.get_secret_value() if settings.WEBHOOK_SECRET else None
        # params_to_set_webhook = {
        #     "url": webhook_url,
        #     "drop_pending_updates": True,
        #     "secret_token": secret,
        # }
        # if settings.WEBHOOK_CERT_PATH:
        #     from aiogram.types import FSInputFile
        #
        #     try:
        #         cert_file = FSInputFile(settings.WEBHOOK_CERT_PATH)
        #         params_to_set_webhook["certificate"] = cert_file
        #         logger.info((f"Using self-signed certificate: " f"{settings.WEBHOOK_CERT_PATH}"))
        #     except Exception as e:
        #         logger.error(
        #             f"Error preparing certificate file " f"{settings.WEBHOOK_CERT_PATH}: {e}"
        #         )
        #         return
        # try:
        #     await bot.set_webhook(**params_to_set_webhook)
        #     webhook_info = await bot.get_webhook_info()
        #     logger.info(f"Webhook info: {webhook_info}")
        #     if webhook_info.url != webhook_url:
        #         logger.error(
        #             f"Webhook was set to {webhook_info.url}, " f"but expected {webhook_url}"
        #         )
        # except Exception as e:
        #     logger.error(f"Failed to set webhook: {e}", exc_info=True)
        try:
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                secret_token=secret,
                # ...
            )
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)
    ###
    else:
        logger.info("Running in polling mode. Deleting any existing webhook.")
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Failed to delete webhook: {e}", exc_info=True)


async def on_shutdown(bot: Bot, dispatcher: Dispatcher):
    logger.warning("Bot shutting down...")

    settings: Settings = dispatcher["settings"]

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


def create_bot_and_dispatcher(settings: Settings, storage: MemoryStorage) -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=storage)
    dp["settings"] = settings

    # NSTEngine initialization
    dp["nst_engine"] = None
    if nst_params:
        try:
            nst_engine_instance = NSTEngine(nst_params)
            if nst_engine_instance._initialized:
                dp["nst_engine"] = nst_engine_instance
                dp.include_router(nst_router)
                logger.info("NSTEngine initialized and router registered.")
            else:
                logger.warning(
                    "NSTEngine created, but failed to initialize properly. "
                    "NST functionality is disabled."
                )
        except Exception as e:
            logger.critical(f"Critical error during NSTEngine initialization: {e}", exc_info=True)
    else:
        logger.info("NST config not found, NST functionality is disabled.")

    # CycleGAN initialization
    dp["cyclegan_engine"] = None
    if cyclegan_params:
        try:
            cyclegan_engine_instance = CycleGANEngine(cyclegan_params)
            if cyclegan_engine_instance._initialized:
                dp["cyclegan_engine"] = cyclegan_engine_instance
                dp.include_router(cyclegan_router)
                logger.info("CycleGANEngine initialized and router registered.")
            else:
                logger.warning(
                    "CycleGANEngine created, but no models were loaded. "
                    "CycleGAN functionality is disabled."
                )
        except Exception as e:
            logger.critical(
                f"Critical error during CycleGANEngine initialization: {e}", exc_info=True
            )
    else:
        logger.info("CycleGAN config not found, CycleGAN functionality is disabled.")

    # Registering other routers
    dp.include_router(common_router)

    # Registering startup/shutdown hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return bot, dp


async def main():
    # # Checking .env file existence
    # env_path = Path(".env")
    # if not env_path.is_file():
    #     logger.critical(f"The environment file was not found on the path: {env_path.resolve()}")
    #     logger.critical("Please create a file.env based on .env.example and fill it in.")
    #     sys.exit(1)

    storage = MemoryStorage()

    # Load settings and validate environment
    try:
        app_settings = Settings()
    except ValidationError as e:
        logger.critical("Environment validation error. Check yours .the env file.")
        for error in e.errors():
            field = ".".join(map(str, error["loc"])) if error["loc"] else "General"
            logger.critical(f"  - Parameter '{field}': {error['msg']}")
        sys.exit(1)

    bot, dp = create_bot_and_dispatcher(app_settings, storage)

    aiohttp_runner = None

    try:
        if app_settings.BOT_RUN_MODE == "polling":
            logger.info("Starting polling...")
            await dp.start_polling(bot)

        elif app_settings.BOT_RUN_MODE == "webhook":
            if not app_settings.WEBHOOK_URL or not app_settings.WEBHOOK_PORT:
                logger.error(("WEBHOOK_URL and WEBHOOK_PORT must be set for " "webhook mode."))
                return

            app = web.Application()
            secret_val = (
                app_settings.WEBHOOK_SECRET.get_secret_value()
                if app_settings.WEBHOOK_SECRET
                else None
            )
            webhook_requests_handler = SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=secret_val,
            )
            webhook_requests_handler.register(app, path=app_settings.WEBHOOK_PATH)
            setup_application(app, dp, bot=bot)

            aiohttp_runner = web.AppRunner(app)
            await aiohttp_runner.setup()
            site = web.TCPSite(
                aiohttp_runner,
                host="0.0.0.0",
                port=app_settings.WEBHOOK_PORT,
            )
            await site.start()
            logger.info(
                f"Webhook server is running on http://"
                f"0.0.0.0:{app_settings.WEBHOOK_PORT}{app_settings.WEBHOOK_PATH}"
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
        if app_settings.BOT_RUN_MODE == "polling":
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
