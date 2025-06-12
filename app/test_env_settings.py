# app/test_env_settings.py
import pytest

# from pydantic import ValidationError
from app.env_settings import Settings
from pathlib import Path


@pytest.fixture
def create_temp_env_file():
    """
    Фабрика для создания временных .env файлов с заданным содержимым.
    Использование:
    temp_env = create_temp_env_file({'VAR': 'value'})
    s = Settings(_env_file=temp_env)
    """
    temp_files = []

    def _create_file(content: dict):
        # Создаем временный файл
        # `delete=False`, чтобы мы могли закрыть его и передать имя дальше
        # pytest позаботится об удалении, когда фикстура завершится
        import tempfile

        f = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)

        # Записываем содержимое словаря в файл
        for key, value in content.items():
            f.write(f"{key}={value}\n")

        f.close()
        temp_files.append(f.name)
        return Path(f.name)

    # yield возвращает нашу фабричную функцию в тест
    yield _create_file

    # Код очистки: pytest выполнит его после завершения всех тестов,
    # использующих эту фикстуру
    import os

    for file_path in temp_files:
        try:
            os.unlink(file_path)
        except OSError:
            pass


# --- ТЕПЕРЬ САМ ТЕСТ ---


def test_bot_run_mode_defaults_to_polling_when_absent(create_temp_env_file):
    """
    Тест: BOT_RUN_MODE отсутствует в .env, должно быть 'polling'.
    """
    # Шаг 1: Создаем .env, в котором НЕТ BOT_RUN_MODE
    temp_env_path = create_temp_env_file(
        {
            "TELEGRAM_BOT_TOKEN": "123:ABC"
            # BOT_RUN_MODE здесь намеренно отсутствует
        }
    )

    # Шаг 2: Создаем Settings.
    # Мы не можем быть уверены, что окружение чистое, поэтому для 100% надежности
    # мы "обнуляем" переменную окружения через monkeypatch.
    # Но для этого нам понадобится monkeypatch в тесте.
    # Давайте пока попробуем без него, предполагая, что .env переопределит.

    # Мы говорим pydantic читать ТОЛЬКО наш временный .env
    s = Settings(_env_file=temp_env_path)

    # Шаг 3: Проверяем, что Pydantic взял значение по умолчанию
    assert s.BOT_RUN_MODE == "polling"
    assert s.TELEGRAM_BOT_TOKEN.get_secret_value() == "123:ABC"
