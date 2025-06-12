from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.full_name}! Я dls_bot.\n"
        "Я могу:\n"
        "- Повторять твои сообщения (эхо)\n"
        "- Помочь тебе со справкой (/help)\n"
        "- Перенести стиль с одной картинки на другую используя алгоритм Гатиса (/nst)"
        "- Стилизовать изображение(фото) под известный стиль (/cyclegan)"
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Это страница справки.\n"
        "/start - начать диалог\n"
        "/help - эта справка\n"
        "/nst - начать процесс Neural Style Transfer(медленный, но универсальный алгоритм)\n"
        "/cyclegan - начать процесс CycleGAN (быстро, но только по заданным стилям)\n"
        "/cancel - отменить текущую операцию (например, загрузку картинок для /nst или /cyclegan)\n"
        "Любое другое сообщение будет повторено (эхо)."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активной операции для отмены.")
        return

    await state.clear()
    await message.answer("Операция отменена.")


@router.message(F.text)
async def echo_handler(message: Message):
    if message.text:
        try:
            await message.answer(f"echo: {message.text}")
        except Exception as e:
            print(f"Error sending echo: {e}")
            await message.answer("Не могу повторить это сообщение.")
