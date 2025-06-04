import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.nst_config import nst_params

import os
import uuid
from pathlib import Path

# from app.nst_engine import perform_style_transfer

from .common import cmd_start as common_cmd_start

from app.nst_engine import NSTEngine, NSTModelNotInitializedError

logger = logging.getLogger(__name__)
router = Router()


# Определяем состояния FSM
class NSTStates(StatesGroup):
    choosing_style_source = State()  # загрузить стиль или выбрать дефолтный
    waiting_for_style_upload = State()  # Ожидание загрузки картинки стиля
    waiting_for_content_image = State()  # Ожидание картинки контента


def get_default_styles_buttons():
    buttons = []
    styles_found = []
    for item in nst_params.DEFAULT_STYLE_IMAGE_DIR.iterdir():
        if item.is_file() and item.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            styles_found.append(item)

    if not styles_found:
        return []

    for style_file in styles_found:
        button_text = style_file.stem.replace("_", " ").capitalize()
        from aiogram.types import InlineKeyboardButton

        buttons.append(
            InlineKeyboardButton(
                text=button_text, callback_data=f"nst_default_style:{style_file.name}"
            )
        )
    return buttons


@router.message(Command("nst"))
async def cmd_nst_start(message: Message, state: FSMContext):
    await state.clear()

    # Создаем основной билдер
    final_builder = InlineKeyboardBuilder()

    # 1. Добавляем кнопку "Загрузить свой стиль"
    final_builder.button(text="🎨 Загрузить свой стиль", callback_data="nst_upload_style")
    # Эта кнопка будет в первом ряду, одна.
    # Если нужны еще кнопки в этом ряду, добавляем их до adjust/row.

    # 2. Получаем кнопки для дефолтных стилей
    default_style_buttons = get_default_styles_buttons()

    if default_style_buttons:
        # Добавляем дефолтные стили.
        # .add() добавляет их в текущий ряд, если он не завершен, или в новый.
        # .adjust() потом распределит их.
        for btn in default_style_buttons:
            final_builder.add(btn)  # Добавляем каждую кнопку

        # Распределяем кнопки:
        # Первая кнопка ("Загрузить свой") будет в своем ряду.
        # Остальные (дефолтные стили) по 2 в ряду.
        # Количество кнопок для дефолтных стилей = len(default_style_buttons)
        # Общее количество кнопок = 1 + len(default_style_buttons)
        # Мы хотим: 1 кнопка в первом ряду, затем по 2 кнопки в последующих рядах для остальных
        adjust_params = [1]  # Первая кнопка в своем ряду
        if default_style_buttons:
            adjust_params.extend([2] * (len(default_style_buttons) // 2))
            if len(default_style_buttons) % 2 == 1:
                # Если нечетное кол-во дефолтных, последняя будет одна
                adjust_params.append(1)
        final_builder.adjust(*adjust_params)

        await message.answer(
            "🎨 Neural Style Transfer 🎨\n" "Выберите источник для изображения стиля:",
            reply_markup=final_builder.as_markup(),
        )
    else:  # Если нет дефолтных стилей, только опция загрузки
        # final_builder уже содержит кнопку "Загрузить свой стиль"
        # и .adjust() по умолчанию разместит ее одну в ряду.
        final_builder.adjust(1)  # Явно указываем, что одна кнопка в ряду
        await message.answer(
            "🎨 Neural Style Transfer 🎨\n" "Пожалуйста, загрузите изображение для СТИЛЯ.",
            reply_markup=final_builder.as_markup(),
        )

    await state.set_state(NSTStates.choosing_style_source)


@router.callback_query(F.data == "nst_upload_style", StateFilter(NSTStates.choosing_style_source))
async def cb_upload_style(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Хорошо! Теперь отправь мне картинку для СТИЛЯ.")
    await state.set_state(NSTStates.waiting_for_style_upload)
    await callback.answer()


@router.callback_query(
    F.data.startswith("nst_default_style:"), StateFilter(NSTStates.choosing_style_source)
)
async def cb_default_style(callback: CallbackQuery, state: FSMContext):
    style_filename = callback.data.split(":", 1)[1]
    style_image_path = nst_params.DEFAULT_STYLE_IMAGE_DIR / style_filename

    if not style_image_path.exists():
        await callback.message.edit_text("Ошибка: выбранный стиль не найден. Попробуйте снова.")
        await state.clear()
        await common_cmd_start(callback.message, state)
        return

    await state.update_data(style_image_path=str(style_image_path), style_is_default=True)
    await callback.message.edit_text(
        f"Стиль '{style_image_path.stem.capitalize()}' выбран. "
        "Теперь отправь картинку с КОНТЕНТОМ (обычную)."
    )
    await state.set_state(NSTStates.waiting_for_content_image)
    await callback.answer()


# Отмена на любом этапе NST
@router.message(Command("cancel"), StateFilter(NSTStates))
async def cmd_cancel_nst(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активной NST операции для отмены.")
        return

    logger.info(f"Cancelling state {current_state} for user {message.from_user.id}")

    # Удаление временных файлов, если они были созданы
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
            logger.error(f"Error removing temporary content image {content_img_path}: {e}")

    await state.clear()
    await message.answer("Процесс Neural Style Transfer отменен.")
    # Можно вернуть пользователя к главному меню или приветствию
    await common_cmd_start(message, state)


@router.message(NSTStates.waiting_for_style_upload, F.photo)
async def nst_style_image_uploaded(message: Message, state: FSMContext, bot: Bot):
    if not message.photo:
        await message.answer("Пожалуйста, отправь картинку (не файл).")
        return

    photo_file_id = message.photo[-1].file_id

    # Сохраняем картинку во временный файл
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
            "Не удалось загрузить изображение стиля. Попробуйте еще раз или /cancel"
        )
        return

    await state.update_data(style_image_path=str(temp_style_path), style_is_default=False)
    await state.set_state(NSTStates.waiting_for_content_image)
    await message.answer("Стиль принят! Теперь отправь картинку с КОНТЕНТОМ (обычную).")


@router.message(NSTStates.waiting_for_style_upload)  # Если не фото и не /cancel
async def nst_style_image_invalid_upload(message: Message):
    await message.answer(
        "Это не похоже на картинку. Пожалуйста, отправь картинку для СТИЛЯ "
        "или используй /cancel для отмены."
    )


# @router.message(NSTStates.waiting_for_content_image, F.photo)
# async def nst_content_image_received(message: Message, state: FSMContext, bot: Bot):
@router.message(NSTStates.waiting_for_content_image, F.photo)
async def nst_content_image_received(
    message: Message, state: FSMContext, bot: Bot, nst_engine: NSTEngine
):

    if not message.photo:
        await message.answer("Пожалуйста, отправь картинку (не файл).")
        return

    content_photo_file_id = message.photo[-1].file_id

    # Сохраняем контент-картинку во временный файл
    file_info = await bot.get_file(content_photo_file_id)
    file_ext = Path(file_info.file_path).suffix or ".jpg"
    temp_content_filename = f"content_{message.from_user.id}_{uuid.uuid4().hex}{file_ext}"
    temp_content_path = nst_params.TEMP_IMAGE_DIR / temp_content_filename

    try:
        await bot.download_file(file_info.file_path, destination=str(temp_content_path))
        logger.info(f"Content image saved to: {temp_content_path}")
    except Exception as e:
        logger.error(f"Error downloading content image: {e}")
        await message.answer(
            "Не удалось загрузить изображение контента. Попробуйте еще раз или /cancel"
        )
        return

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

    processing_msg = await message.answer(
        "Контент принят! ✨ Начинаю магию стилизации... Это может занять некоторое время. ⏳"
    )

    # Получаем nst_engine из dispatcher data
    # nst_engine: NSTEngine = Dispatcher.get_current().get("nst_engine")
    # Если не через аргумент функции
    # if not nst_engine or not nst_engine._initialized:
    #     logger.error("NST engine not available or not initialized.")
    if not nst_engine:
        logger.error("NST engine not available in dispatcher.")
        await message.answer("Сервис стилизации временно недоступен. Пожалуйста, попробуйте позже.")
        await state.clear()
        return

    loop = asyncio.get_event_loop()
    try:
        # Запускаем NST(perform_style_transfer) в асинхронном режиме
        # perform_style_transfer сама по себе уже не async, а обычная функция#
        stylized_image_bytes = await loop.run_in_executor(
            None,  # Использует ThreadPoolExecutor по умолчанию
            # perform_style_transfer,  # Функция для запуска
            nst_engine.process_images,
            style_image_path,  # Первый позиционный аргумент для perform_style_transfer
            str(temp_content_path),  # Второй позиционный аргумент
            # Если у perform_style_transfer есть еще параметры, передаем их дальше
            # , num_steps=50 # например
        )

        result_photo = BufferedInputFile(stylized_image_bytes, filename="stylized_result.jpg")
        await message.answer_photo(result_photo, caption="Готово! Вот ваш стилизованный шедевр. 🖼️")
    except NSTModelNotInitializedError:
        logger.error("NST engine was not initialized when called.")
        await message.answer(
            "Ошибка инициализации сервиса стилизации. Пожалуйста, попробуйте позже."
        )
    except RuntimeError as e:
        logger.error(f"NST Runtime Error: {e}", exc_info=True)
        await message.answer(
            f"К сожалению, во время стилизации произошла ошибка: {e}. "
            "Попробуйте другие изображения или /cancel."
        )
    except Exception as e:
        logger.error(f"Error during NST processing or sending result: {e}", exc_info=True)
        await message.answer(
            "Произошла непредвиденная ошибка при обработке. "
            "Пожалуйста, попробуйте позже или /cancel."
        )
    finally:
        # Удаляем временные файлы
        if Path(temp_content_path).exists():
            try:
                os.remove(temp_content_path)
                logger.info(f"Removed temporary content image: {temp_content_path}")
            except OSError as e:
                logger.error(f"Error removing temporary content image {temp_content_path}: {e}")

        if (
            not style_is_default and Path(style_image_path).exists()
        ):  # Удаляем стиль, только если он был загружен пользователем
            try:
                os.remove(style_image_path)
                logger.info(f"Removed temporary style image: {style_image_path}")
            except OSError as e:
                logger.error(f"Error removing temporary style image {style_image_path}: {e}")

        try:  # Удаляем сообщение "Обработка..."
            await bot.delete_message(
                chat_id=processing_msg.chat.id, message_id=processing_msg.message_id
            )
        except Exception:
            pass  # Не критично, если не удалилось

        await state.clear()


@router.message(NSTStates.waiting_for_content_image)  # Если не фото и не /cancel
async def nst_content_image_invalid(message: Message):
    await message.answer(
        "Это не похоже на картинку. Пожалуйста, отправь картинку для КОНТЕНТА "
        "или используй /cancel для отмены."
    )
