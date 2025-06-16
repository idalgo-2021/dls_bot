import asyncio
import functools
import logging
import time
import os
import uuid
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.nst_engine import NSTEngine, NSTModelNotInitializedError
from app.nst_config import nst_params

from .common import cmd_start as common_cmd_start
from .utils import format_duration

logger = logging.getLogger(__name__)
router = Router()


# FSM for NST
class NSTStates(StatesGroup):
    choosing_style_source = State()  # load the style or select the default one
    waiting_for_style_upload = State()  # Waiting for the style image
    waiting_for_content_image = State()  # Waiting for the content image


@router.message(Command("nst"))
async def cmd_nst_start(message: Message, state: FSMContext, nst_engine: NSTEngine):
    await state.clear()

    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 Загрузить свой стиль", callback_data="nst_upload_style")

    default_styles = nst_engine.get_available_styles()
    for filename, display_name in default_styles.items():
        builder.button(text=display_name, callback_data=f"nst_default_style:{filename}")

    builder.adjust(1, 2)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="nst_cancel"))

    await message.answer(
        "🎨 Neural Style Transfer 🎨\n" "Выберите источник для изображения стиля:",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(NSTStates.choosing_style_source)


@router.callback_query(
    F.data == "nst_upload_style", StateFilter(NSTStates.choosing_style_source)
)
async def cb_upload_style(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Хорошо! Теперь отправьте мне картинку для СТИЛЯ.",
        reply_markup=_get_cancel_inline_keyboard(),
    )
    await state.set_state(NSTStates.waiting_for_style_upload)
    await callback.answer()


@router.callback_query(
    F.data.startswith("nst_default_style:"),
    StateFilter(NSTStates.choosing_style_source),
)
async def cb_default_style(callback: CallbackQuery, state: FSMContext):
    style_filename = callback.data.split(":", 1)[1]
    style_image_path = nst_params.DEFAULT_STYLE_IMAGE_DIR / style_filename

    if not style_image_path.exists():
        await callback.message.edit_text(
            "Ошибка: выбранный стиль не найден. Попробуйте снова."
        )
        await state.clear()
        await common_cmd_start(callback.message, state)
        return

    await state.update_data(
        style_image_path=str(style_image_path), style_is_default=True
    )
    await callback.message.edit_text(
        f"Стиль '{style_image_path.stem.capitalize()}' выбран. "
        "Теперь отправьте картинку с КОНТЕНТОМ (обычную).",
        reply_markup=_get_cancel_inline_keyboard(),
    )
    await state.set_state(NSTStates.waiting_for_content_image)
    await callback.answer()


@router.message(NSTStates.waiting_for_style_upload, F.photo)
async def nst_style_image_uploaded(message: Message, state: FSMContext, bot: Bot):
    if not message.photo:
        await message.answer(
            "Пожалуйста, отправьте картинку (не файл).",
            reply_markup=_get_cancel_inline_keyboard(),
        )
        return

    photo_file_id = message.photo[-1].file_id

    # Saving the image to a temporary file
    file_info = await bot.get_file(photo_file_id)
    file_ext = Path(file_info.file_path).suffix or ".jpg"
    temp_style_filename = f"style_{message.from_user.id}_{uuid.uuid4().hex}{file_ext}"
    temp_style_path = nst_params.TEMP_IMAGE_DIR / temp_style_filename

    try:
        await bot.download_file(file_info.file_path, destination=str(temp_style_path))
        logger.info(f"Style image saved to: {temp_style_path}")
    except Exception as e:
        logger.error(f"Error downloading style image: {e}")
        await message.answer(
            "Не удалось загрузить изображение стиля. Попробуйте еще раз или /cancel",
            reply_markup=_get_cancel_inline_keyboard(),
        )
        return

    await state.update_data(
        style_image_path=str(temp_style_path), style_is_default=False
    )
    await state.set_state(NSTStates.waiting_for_content_image)
    await message.answer(
        "Стиль принят! Теперь отправьте картинку с КОНТЕНТОМ (обычную).",
        reply_markup=_get_cancel_inline_keyboard(),
    )


@router.message(
    NSTStates.waiting_for_style_upload, ~Command(commands=["cancel", "start", "help"])
)
async def nst_style_image_invalid_upload(message: Message):
    await message.answer(
        "Это не похоже на картинку. Пожалуйста, отправьте картинку для СТИЛЯ "
        "или используйте /cancel для отмены.",
        reply_markup=_get_cancel_inline_keyboard(),
    )


@router.message(NSTStates.waiting_for_content_image, F.photo)
async def nst_content_image_received(
    message: Message, state: FSMContext, bot: Bot, nst_engine: NSTEngine
):
    # 1. Получаем данные из FSM
    user_data = await state.get_data()
    style_image_path = user_data.get("style_image_path")
    style_is_default = user_data.get("style_is_default", False)

    if not style_image_path:
        logger.error("Style image path not found in state data!")
        await message.answer(
            "Произошла внутренняя ошибка (не найден путь к стилю). Пожалуйста, начните заново /nst."
        )
        await state.clear()
        return

    # 2. Сообщаем пользователю о начале работы
    processing_msg = await message.answer(
        "Контент принят! ✨ Начинаю творить магию... \nЭто может занять некоторое время. ⏳"
    )

    # 3. Объявляем переменные, которые понадобятся в `finally`
    temp_content_path = None

    try:
        # 4. Скачиваем изображение контента
        content_photo_file_id = message.photo[-1].file_id
        file_info = await bot.get_file(content_photo_file_id)
        file_ext = Path(file_info.file_path).suffix or ".jpg"
        temp_content_filename = (
            f"content_{message.from_user.id}_{uuid.uuid4().hex}{file_ext}"
        )
        temp_content_path = nst_params.TEMP_IMAGE_DIR / temp_content_filename

        await bot.download_file(file_info.file_path, destination=str(temp_content_path))
        logger.info(f"Content image saved to: {temp_content_path}")

        # 5. Запускаем "тяжелую" операцию
        loop = asyncio.get_running_loop()
        start_time = time.monotonic()

        func_to_run = functools.partial(
            nst_engine.process_images, style_image_path, str(temp_content_path)
        )
        stylized_image_bytes = await loop.run_in_executor(None, func_to_run)

        # 6. Готовим и отправляем результат
        result_photo = BufferedInputFile(
            stylized_image_bytes, filename="stylized_result.jpg"
        )
        duration_str = format_duration(start_time)  # Используем утилиту
        final_caption = (
            "Готово! Вот ваш стилизованный шедевр. 🖼️\n\n"
            f"⏱️ Время на стилизацию: примерно {duration_str}\n\n"
            "Для начала нового сеанса введите /start"
        )

        await message.answer_photo(result_photo, caption=final_caption)

    except NSTModelNotInitializedError:
        logger.error("NST engine was not initialized when called.")
        await message.answer(
            "Ошибка инициализации сервиса стилизации. Пожалуйста, попробуйте позже."
        )
    except RuntimeError as e:
        logger.error(f"NST Runtime Error: {e}", exc_info=True)
        await message.answer(
            f"К сожалению, во время стилизации произошла ошибка: {e}. "
            "Попробуйте другие изображения."
        )
    except Exception as e:
        logger.error(
            f"Error during NST processing or sending result: {e}", exc_info=True
        )
        await message.answer(
            "Произошла непредвиденная ошибка при обработке. "
            "Пожалуйста, попробуйте позже."
        )
    finally:
        # 7. Очистка ресурсов в любом случае
        if processing_msg:
            try:
                await bot.delete_message(
                    chat_id=processing_msg.chat.id, message_id=processing_msg.message_id
                )
            except Exception:
                pass  # Игнорируем ошибки при удалении сообщения

        # Очищаем временный файл с контентом, если он был создан
        if temp_content_path and Path(temp_content_path).exists():
            try:
                os.remove(temp_content_path)
                logger.info(f"Removed temporary content image: {temp_content_path}")
            except OSError as e:
                logger.error(f"Error removing temporary content image: {e}")

        # Очищаем временный файл со стилем, только если он был загружен пользователем
        if (
            not style_is_default
            and style_image_path
            and Path(style_image_path).exists()
        ):
            try:
                os.remove(style_image_path)
                logger.info(f"Removed temporary style image: {style_image_path}")
            except OSError as e:
                logger.error(f"Error removing temporary style image: {e}")

        await state.clear()


@router.message(
    NSTStates.waiting_for_content_image, ~Command(commands=["cancel", "start", "help"])
)
async def nst_content_image_invalid(message: Message):
    await message.answer(
        "Это не похоже на картинку. Пожалуйста, отправьте картинку для КОНТЕНТА "
        "или используй /cancel для отмены.",
        reply_markup=_get_cancel_inline_keyboard(),
    )


def _get_cancel_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="nst_cancel")]
        ]
    )


@router.message(Command("cancel"), StateFilter(NSTStates))
async def cmd_cancel_nst(message: Message, state: FSMContext):
    await cancel_nst_operation(message, state)


@router.callback_query(F.data == "nst_cancel", StateFilter(NSTStates))
async def cb_cancel_nst(callback: CallbackQuery, state: FSMContext):
    await cancel_nst_operation(callback, state, is_callback=True)


async def cancel_nst_operation(
    message_or_callback: Message | CallbackQuery,
    state: FSMContext,
    is_callback: bool = False,
):
    current_state = await state.get_state()
    if current_state is None:
        reply_text = "Нет активной NST операции для отмены."
        if is_callback:
            await message_or_callback.answer(reply_text, show_alert=True)
        else:
            await message_or_callback.answer(reply_text)
        return

    logger.info(
        f"Cancelling state {current_state} for user {message_or_callback.from_user.id}"
    )

    user_data = await state.get_data()
    style_img_path = user_data.get("style_image_path")
    content_img_path = user_data.get("content_image_path")

    if (
        style_img_path
        and not user_data.get("style_is_default", False)
        and Path(style_img_path).exists()
    ):
        try:
            os.remove(style_img_path)
            logger.info(f"Removed temporary style image: {style_img_path}")
        except OSError as e:
            logger.error(f"Error removing temporary style image {style_img_path}: {e}")

    if content_img_path and Path(content_img_path).exists():
        try:
            os.remove(content_img_path)
            logger.info(f"Removed temporary content image: {content_img_path}")
        except OSError as e:
            logger.error(
                f"Error removing temporary content image {content_img_path}: {e}"
            )

    await state.clear()

    reply_text = "Процесс Neural Style Transfer отменен."
    if is_callback:
        await message_or_callback.message.edit_text(reply_text)
    else:
        await message_or_callback.answer(reply_text)

    await common_cmd_start(
        message_or_callback.message if is_callback else message_or_callback, state
    )

    if is_callback:
        await message_or_callback.answer()
