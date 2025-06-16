import pytest
import torch
from unittest import mock

from app.nst_engine import NSTEngine
from torchvision.models import vgg19


class DummyConfig:
    # Minimal config for NSTEngine
    DEVICE_PREFERENCE = "cpu"
    IMAGE_SIZE = 64
    IMAGE_SIZE_CPU = 64
    IMAGE_SIZE_CUDA = 128
    MODEL_PATH = "dummy_model.pth"
    MODEL_TYPE = "shrunk_object"
    NORMALIZATION_MEAN = [0.485, 0.456, 0.406]
    NORMALIZATION_STD = [0.229, 0.224, 0.225]
    # DEFAULT_STYLE_IMAGE_DIR = Path("/tmp")
    # CONTENT_LAYERS = ["conv_4"]
    # STYLE_LAYERS = ["conv_1", "conv_2", "conv_3", "conv_4", "conv_5"]
    # NUM_STEPS = 1
    # STYLE_WEIGHT = 1e6
    # CONTENT_WEIGHT = 1


@pytest.fixture
def config(tmp_path):
    cfg = DummyConfig()
    cfg.MODEL_PATH = str(tmp_path / "dummy_model.pth")
    return cfg


@mock.patch("app.nst_engine.NSTEngine._load_model")
@mock.patch("app.nst_engine.NSTEngine._load_default_styles")
@mock.patch("app.nst_engine.NSTEngine._determine_device_and_image_size")
def test_init_completes_successfully(
    mock_determine_device, mock_load_styles, mock_load_model, config
):
    """
    Тестирует, что __init__ успешно завершается, если все его
    внутренние вызовы (хелперы) отработали без ошибок.
    """

    # Назначаем side_effect или return_value.
    # По умолчанию моки просто ничего не делают и возвращают MagicMock.
    # Этого достаточно, чтобы они не выбрасывали исключений.

    # Вызываем конструктор.
    engine = NSTEngine(config)

    # 1. Главная проверка: конструктор дошел до конца и установил флаг.
    assert engine._initialized is True

    # 2. Проверяем, что конструктор действительно вызвал свои зависимости.
    mock_determine_device.assert_called_once()
    mock_load_styles.assert_called_once()
    mock_load_model.assert_called_once()


# --- Тест на неуспешную инициализацию ---
@mock.patch("app.nst_engine.NSTEngine._load_default_styles")
@mock.patch("app.nst_engine.NSTEngine._determine_device_and_image_size")
@mock.patch(
    "app.nst_engine.NSTEngine._load_model", side_effect=RuntimeError("Failed to load")
)
def test_init_fails_if_loader_fails(
    mock_load_model, mock_determine_device, mock_load_styles, config
):
    """
    Тестирует, что __init__ НЕ устанавливает флаг _initialized,
    если один из хелперов вызывает исключение.
    """
    # Ожидаем, что конструктор поймает RuntimeError и не упадет,
    # а просто не завершит инициализацию.
    engine = NSTEngine(config)

    assert engine._initialized is False
    mock_load_model.assert_called_once()


@mock.patch("app.nst_engine.NSTEngine._load_default_styles")
@mock.patch("app.nst_engine.NSTEngine._determine_device_and_image_size")
def test_init_sets_initialized_to_false_if_model_fails(
    mock_determine_device, mock_load_styles, config
):
    """
    Тестирует, что флаг _initialized остается False, если
    _load_model вызывает ошибку, которую ловит конструктор.
    """
    # Модель не создана, поэтому _load_model() вызовет RuntimeError внутри себя.

    # Не ожидаем исключения, просто вызываем конструктор.
    engine = NSTEngine(config)

    # Главная проверка: флаг остался в значении False, потому что
    # конструктор поймал исключение и не дошел до строки `self._initialized = True`
    assert engine._initialized is False


@pytest.fixture
def engine_for_loading(config):
    """Фикстура для создания 'пустого' движка для тестирования отдельных методов."""
    # ИСПРАВЛЕНИЕ: Создаем экземпляр, обходя __init__, но только для тестирования
    # изолированных методов. Это приемлемо здесь.
    engine = NSTEngine.__new__(NSTEngine)
    engine.config = config
    engine.device = torch.device("cpu")
    engine.cnn_model = None
    engine.cnn_normalization_mean = None
    engine.cnn_normalization_std = None
    return engine


def test_load_model_shrunk_object_success(engine_for_loading, tmp_path):
    dummy_model = torch.nn.Sequential(torch.nn.Conv2d(3, 3, 1))
    model_path = tmp_path / "dummy_model.pth"

    torch.save(dummy_model, model_path)
    engine_for_loading.config.MODEL_PATH = str(model_path)

    # Мокаем только логгер(он мешает)
    with mock.patch("app.nst_engine.logger"):
        engine_for_loading._load_model()

    assert isinstance(engine_for_loading.cnn_model, torch.nn.Module)
    assert torch.allclose(
        engine_for_loading.cnn_normalization_mean,
        torch.tensor(engine_for_loading.config.NORMALIZATION_MEAN),
    )


def test_load_model_shrunk_object_missing_file(engine_for_loading):
    engine_for_loading.config.MODEL_PATH = "nonexistent.pth"
    with pytest.raises(RuntimeError) as excinfo:
        engine_for_loading._load_model()
    assert "Could not load any VGG19 model" in str(excinfo.value)


def test_load_model_shrunk_object_no_path(config):
    config.MODEL_PATH = ""
    engine = NSTEngine.__new__(NSTEngine)
    engine.config = config
    engine.device = torch.device("cpu")

    with mock.patch("app.nst_engine.logger"):
        with pytest.raises(RuntimeError) as excinfo:
            engine._load_model()
    assert "Could not load any VGG19 model" in str(excinfo.value)


def test_load_model_full_statedict_success(engine_for_loading, tmp_path):
    engine_for_loading.config.MODEL_TYPE = "full_statedict"

    dummy_model = vgg19(weights=None)
    model_path = tmp_path / "dummy_model_statedict.pth"
    torch.save(dummy_model.state_dict(), model_path)
    engine_for_loading.config.MODEL_PATH = str(model_path)

    with mock.patch("app.nst_engine.logger"):
        engine_for_loading._load_model()

    assert isinstance(engine_for_loading.cnn_model, torch.nn.Sequential)


def test_load_model_full_statedict_missing_file(tmp_path, config):
    config.MODEL_TYPE = "full_statedict"
    config.MODEL_PATH = str(tmp_path / "nonexistent.pth")
    engine = NSTEngine.__new__(NSTEngine)
    engine.config = config
    engine.device = torch.device("cpu")

    with mock.patch("app.nst_engine.logger"):
        with pytest.raises(RuntimeError) as excinfo:
            engine._load_model()
    assert "Could not load any VGG19 model" in str(excinfo.value)


def test_load_model_full_statedict_no_path(config):
    config.MODEL_TYPE = "full_statedict"
    config.MODEL_PATH = ""
    engine = NSTEngine.__new__(NSTEngine)
    engine.config = config
    engine.device = torch.device("cpu")

    with mock.patch("app.nst_engine.logger"):
        with pytest.raises(RuntimeError) as excinfo:
            engine._load_model()
    assert "Could not load any VGG19 model" in str(excinfo.value)


def test_load_model_unknown_type(engine_for_loading):
    """Проверяет поведение при неизвестном типе модели в конфиге."""
    engine_for_loading.config.MODEL_TYPE = "unknown_type"
    with pytest.raises(RuntimeError) as excinfo:
        engine_for_loading._load_model()
    assert "Could not load any VGG19 model" in str(excinfo.value)
