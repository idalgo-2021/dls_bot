import asyncio
import functools
import io
import logging
import time
from aiogram import Bot, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from PIL import Image

from app.cyclegan_engine import CycleGANEngine
from app.handlers.common import cmd_start

from .utils import format_duration


logger = logging.getLogger(__name__)
router = Router()


# FSM for CycleGAN
class CycleGANStates(StatesGroup):
    choosing_style = State()
    uploading_photo = State()


@router.message(Command("cyclegan"))
async def cmd_cyclegan_start(
    message: Message, state: FSMContext, cyclegan_engine: CycleGANEngine
):
    await state.clear()

    available_styles = cyclegan_engine.get_available_styles()
    if not available_styles:
        await message.answer(
            "К сожалению, сейчас нет доступных стилей CycleGAN. Попробуйте позже."
        )
        return

    builder = InlineKeyboardBuilder()
    for style_code, display_name in available_styles.items():
        builder.button(text=display_name, callback_data=f"cyclegan_style_{style_code}")

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cyclegan_cancel"))

    await message.answer(
        "Выберите стиль, который хотите применить:", reply_markup=builder.as_markup()
    )
    await state.set_state(CycleGANStates.choosing_style)


@router.callback_query(
    F.data.startswith("cyclegan_style_"), CycleGANStates.choosing_style
)
async def cq_choose_style(callback: CallbackQuery, state: FSMContext):
    style_code = callback.data.split("_")[-1]
    await state.update_data(chosen_style=style_code)

    await callback.message.edit_text(
        "Отлично! Вы выбрали стиль. Теперь, пожалуйста, отправьте мне фотографию, "
        "которую нужно обработать.",
        reply_markup=get_cancel_cyclegan_keyboard(),
    )
    await state.set_state(CycleGANStates.uploading_photo)
    await callback.answer()


@router.message(F.photo, CycleGANStates.uploading_photo)
async def handle_photo_for_cyclegan(
    message: Message,
    state: FSMContext,
    cyclegan_engine: CycleGANEngine,
    bot: Bot,
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
        "Принял фото. Начинаю творить магию... ✨\nЭто может занять несколько секунд.",
        reply_markup=get_cancel_cyclegan_keyboard(),
    )

    try:
        photo_bio = io.BytesIO()
        await bot.download(message.photo[-1].file_id, destination=photo_bio)
        content_image = Image.open(photo_bio)

        loop = asyncio.get_running_loop()
        start_time = time.monotonic()

        func_to_run = functools.partial(
            cyclegan_engine.stylize, image=content_image, style_name=style_code
        )
        result_image = await loop.run_in_executor(None, func_to_run)

        result_bio = io.BytesIO()
        result_image.save(result_bio, format="JPEG")
        result_bio.seek(0)
        file_to_send = BufferedInputFile(result_bio.read(), filename="result.jpg")

        duration_str = format_duration(start_time)
        final_caption = (
            f"Готово! Ваш шедевр в стиле «{style_code}»\n"
            f"⏱️ Время на стилизацию: {duration_str}\n\n"
            "Для начала нового сеанса введите /start"
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


def get_cancel_cyclegan_keyboard():
    return (
        InlineKeyboardBuilder()
        .button(text="❌ Отмена", callback_data="cyclegan_cancel")
        .as_markup()
    )


async def cancel_cyclegan_operation(
    message_or_callback: Message | CallbackQuery,
    state: FSMContext,
    is_callback: bool = False,
):
    current_state = await state.get_state()
    if current_state is None:
        reply_text = "Нет активной CycleGAN операции для отмены."
        if is_callback:
            await message_or_callback.answer(reply_text, show_alert=True)
        else:
            await message_or_callback.answer(reply_text)
        return

    logger.info(
        f"Cancelling CycleGAN state {current_state} for user {message_or_callback.from_user.id}"
    )
    await state.clear()

    reply_text = "Процесс CycleGAN отменен."
    if is_callback:
        await message_or_callback.message.edit_text(reply_text)
    else:
        await message_or_callback.answer(reply_text)

    await cmd_start(
        message_or_callback.message if is_callback else message_or_callback, state
    )

    if is_callback:
        await message_or_callback.answer()


@router.callback_query(F.data == "cyclegan_cancel", StateFilter(CycleGANStates))
async def cb_cancel_cyclegan(callback: CallbackQuery, state: FSMContext):
    await cancel_cyclegan_operation(callback, state, is_callback=True)


@router.message(Command("cancel"), StateFilter(CycleGANStates))
async def cmd_cancel_cyclegan(message: Message, state: FSMContext):
    await cancel_cyclegan_operation(message, state)


@router.message(CycleGANStates.uploading_photo, ~F.text.in_({"/cancel"}), ~F.photo)
@router.message(CycleGANStates.uploading_photo)
async def incorrect_upload(message: Message):
    await message.answer(
        "Пожалуйста, отправьте именно фотографию, а не текст или другой файл.",
        reply_markup=get_cancel_cyclegan_keyboard(),
    )
