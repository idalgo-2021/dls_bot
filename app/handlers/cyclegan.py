import asyncio
import functools
import io
import logging
import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image

from app.cyclegan_engine import CycleGANEngine

logger = logging.getLogger(__name__)
router = Router()


# FSM for CycleGAN
class CycleGANStates(StatesGroup):
    choosing_style = State()
    uploading_photo = State()


@router.message(Command("cyclegan"))
async def cmd_cyclegan_start(message: Message, state: FSMContext, cyclegan_engine: CycleGANEngine):
    await state.clear()
    available_styles = cyclegan_engine.get_available_styles()

    if not available_styles:
        await message.answer("К сожалению, сейчас нет доступных стилей CycleGAN. Попробуйте позже.")
        return

    builder = InlineKeyboardBuilder()
    for style_code, display_name in available_styles.items():
        builder.button(text=display_name, callback_data=f"cyclegan_style_{style_code}")

    builder.adjust(1)  # Располагаем кнопки по одной в ряд

    await message.answer(
        "Выберите стиль, который хотите применить:", reply_markup=builder.as_markup()
    )
    await state.set_state(CycleGANStates.choosing_style)


@router.callback_query(F.data.startswith("cyclegan_style_"), CycleGANStates.choosing_style)
async def cq_choose_style(callback: CallbackQuery, state: FSMContext):
    style_code = callback.data.split("_")[-1]
    await state.update_data(chosen_style=style_code)

    await callback.message.edit_text(
        "Отлично! Вы выбрали стиль. Теперь, пожалуйста, отправьте мне фотографию, "
        "которую нужно обработать."
    )
    await state.set_state(CycleGANStates.uploading_photo)
    await callback.answer()


@router.message(F.photo, CycleGANStates.uploading_photo)
async def handle_photo_for_cyclegan(
    message: Message, state: FSMContext, cyclegan_engine: CycleGANEngine
):
    user_data = await state.get_data()
    style_code = user_data.get("chosen_style")

    if not style_code:
        await message.answer(
            "Произошла ошибка, стиль не был выбран. Пожалуйста, начните заново с команды /cyclegan."
        )
        await state.clear()
        return

    processing_msg = await message.answer(
        "Принял фото. Начинаю творить магию... ✨\nЭто может занять несколько секунд."
    )

    photo_bio = io.BytesIO()
    await message.bot.download(message.photo[-1].file_id, destination=photo_bio)
    content_image = Image.open(photo_bio)

    start_time = time.monotonic()

    try:
        # result_image = cyclegan_engine.stylize(content_image, style_code)
        loop = asyncio.get_running_loop()
        func_to_run = functools.partial(
            cyclegan_engine.stylize, image=content_image, style_name=style_code
        )
        result_image = await loop.run_in_executor(None, func_to_run)

        # Сохраняем результат в байтовый буфер для отправки
        result_bio = io.BytesIO()
        result_image.save(result_bio, format="JPEG")
        result_bio.seek(0)

        # Оборачиваем в BufferedInputFile для отправки
        file_to_send = BufferedInputFile(result_bio.read(), filename="result.jpg")

        end_time = time.monotonic()
        duration_seconds_total = int(end_time - start_time)
        minutes = duration_seconds_total // 60
        seconds = duration_seconds_total % 60
        if minutes > 0:
            duration_str = f"{minutes} мин. {seconds} сек."
        else:
            duration_str = f"{seconds} сек."

        final_caption = (
            f"Готово! Ваш шедевр в стиле «{style_code}» "
            f"⏱️ Время на стилизацию: примерно {duration_str}"
        )
        await message.answer_photo(photo=file_to_send, caption=final_caption)

    except Exception as e:
        print(f"Error during CycleGAN stylization: {e}")
        await message.answer(
            "Ой, что-то пошло не так во время обработки. Попробуйте другое фото или начните заново."
        )
    finally:
        await processing_msg.delete()
        await state.clear()


@router.message(CycleGANStates.uploading_photo)
async def incorrect_upload(message: Message):
    await message.answer("Пожалуйста, отправьте именно фотографию, а не текст или другой файл.")
