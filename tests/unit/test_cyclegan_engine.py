import pytest
import torch
from unittest import mock
from PIL import Image


from app.cyclegan_engine import CycleGANEngine
from app.architectures.cyclegan_networks import ResnetGenerator


# --- Фикстура для конфига ---
@pytest.fixture
def cyclegan_config(tmp_path):
    class DummyConfig:
        DEVICE_PREFERENCE = "cpu"
        MODELS_DIR = tmp_path
        
        OUTPUT_CHANNELS = 3
        NUM_RESIDUAL_BLOCKS = 9
        IMAGE_SIZE = 256
        styles = {
            "monet": {"display_name": "Monet Style", "model_file": "monet.pth"},
            "vangogh": {"display_name": "Van Gogh Style", "model_file": "vangogh.pth"},
            "no_file": {"display_name": "No File Style"},
            "bad_path": {
                "display_name": "Bad Path Style",
                "model_file": "nonexistent.pth",
            },
        }

    return DummyConfig()


# --- Тест на инициализацию (по аналогии с nst_engine) ---


@mock.patch("app.cyclegan_engine.CycleGANEngine._load_all_models")
@mock.patch("app.cyclegan_engine.CycleGANEngine._determine_device")
def test_init_calls_helpers(
    mock_determine_device, mock_load_all_models, cyclegan_config
):
    """Тестирует, что __init__ вызывает свои зависимости."""
    CycleGANEngine(cyclegan_config)
    mock_determine_device.assert_called_once()
    mock_load_all_models.assert_called_once()


# --- Тесты для _load_all_models ---


@mock.patch("app.cyclegan_engine.torch.load")
@mock.patch("app.cyclegan_engine.ResnetGenerator")
def test_load_all_models_success_and_skip(
    mock_resnet_gen, mock_torch_load, cyclegan_config, tmp_path
):
    """
    Тестирует логику загрузки: успешную, пропуск из-за отсутствия файла
    и пропуск из-за отсутствия пути в конфиге.
    """
    # Создаем фейковые файлы моделей, которые существуют
    (tmp_path / "monet.pth").touch()
    (tmp_path / "vangogh.pth").touch()

    # Создаем экземпляр, обходя __init__
    engine = CycleGANEngine.__new__(CycleGANEngine)
    engine.config = cyclegan_config
    engine.device = torch.device("cpu")
    engine.models = {}

    # Вызываем тестируемый метод
    engine._load_all_models()

    # Проверяем, что загрузились только 2 модели
    assert len(engine.models) == 2
    assert "monet" in engine.models
    assert "vangogh" in engine.models
    assert "no_file" not in engine.models
    assert "bad_path" not in engine.models

    # Проверяем, что флаг установлен
    assert engine._initialized is True
    # Проверяем, что torch.load вызывался дважды
    assert mock_torch_load.call_count == 2


@mock.patch("app.cyclegan_engine.torch.load")
def test_load_all_models_sets_initialized_to_false_if_no_models_loaded(
    mock_torch_load, cyclegan_config
):
    """Тестирует, что _initialized остается False, если ни одна модель не загрузилась."""
    # Не создаем никаких файлов моделей
    engine = CycleGANEngine.__new__(CycleGANEngine)
    engine.config = cyclegan_config
    engine.device = torch.device("cpu")
    engine.models = {}
    engine._initialized = False  # Устанавливаем начальное значение

    engine._load_all_models()

    assert len(engine.models) == 0
    assert engine._initialized is False
    mock_torch_load.assert_not_called()


# --- Тест для get_available_styles ---
def test_get_available_styles(cyclegan_config):
    # Экземпляр, обходя __init__
    engine = CycleGANEngine.__new__(CycleGANEngine)
    engine.config = cyclegan_config
    # Имитация, что загружены только две модели
    engine.models = {"monet": mock.MagicMock(), "vangogh": mock.MagicMock()}

    styles = engine.get_available_styles()

    assert styles == {"monet": "Monet Style", "vangogh": "Van Gogh Style"}
    # Проверяем, что стили без моделей не попали в результат
    assert "no_file" not in styles
    assert "bad_path" not in styles


# --- Тест для `stylize` ---
def test_stylize_success(cyclegan_config):
    """Тестирует успешный процесс стилизации с моком модели."""
    # Создаем "пустой" движок
    engine = CycleGANEngine.__new__(CycleGANEngine)
    engine.config = cyclegan_config
    engine.device = torch.device("cpu")

    # Создаем и добавляем фейковую модель (мок)
    mock_model = mock.MagicMock(spec=ResnetGenerator)
    # Говорим моку, что при вызове он должен вернуть тензор нужной формы
    mock_model.return_value = torch.randn(1, 3, 256, 256)
    engine.models = {"monet": mock_model}

    # Создаем фейковое входное изображение
    dummy_image = Image.new("RGB", (300, 300))

    # Вызываем метод
    result_image = engine.stylize(dummy_image, "monet")

    # Проверяем, что модель была вызвана
    mock_model.assert_called_once()
    # Проверяем, что результат - это объект изображения PIL
    assert isinstance(result_image, Image.Image)
    assert result_image.size == (256, 256)  # Размер после ресайза


def test_stylize_raises_error_for_invalid_style(cyclegan_config):
    """Тестирует, что stylize падает, если стиль не загружен."""
    engine = CycleGANEngine.__new__(CycleGANEngine)
    engine.config = cyclegan_config
    engine.models = {"monet": mock.MagicMock()}  # "vangogh" не загружен

    dummy_image = Image.new("RGB", (300, 300))

    with pytest.raises(ValueError) as excinfo:
        engine.stylize(dummy_image, "vangogh")
    assert "is not a valid or loaded style" in str(excinfo.value)
