import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = Path(__file__).parent / "configs" / "nst_params.yaml"


class NSTConfig:
    def __init__(self, data: dict):
        try:
            self.TEMP_IMAGE_DIR = Path(data["TEMP_IMAGE_DIR"])
            self.DEFAULT_STYLE_IMAGE_DIR = Path(data["DEFAULT_STYLE_IMAGE_DIR"])

            # Model parameters
            self.MODEL_PATH = data["MODEL_PATH"]
            self.MODEL_TYPE = data.get("MODEL_TYPE", "shrunk_object").lower()

            # Device parameters
            self.DEVICE_PREFERENCE = data.get("DEVICE", "auto").lower()

            # Model and image parameters
            self.IMAGE_SIZE = int(data.get("IMAGE_SIZE", 256))
            self.IMAGE_SIZE_CPU = int(data.get("IMAGE_SIZE_CPU", self.IMAGE_SIZE))
            self.IMAGE_SIZE_CUDA = int(data.get("IMAGE_SIZE_CUDA", self.IMAGE_SIZE))

            # Normalization for VGG19 (ImageNet)
            self.NORMALIZATION_MEAN = data.get("NORMALIZATION_MEAN", [0.485, 0.456, 0.406])
            self.NORMALIZATION_STD = data.get("NORMALIZATION_STD", [0.229, 0.224, 0.225])

            # Layers
            self.CONTENT_LAYERS = data.get("CONTENT_LAYERS", ["conv_4"])
            self.STYLE_LAYERS = data.get(
                "STYLE_LAYERS", ["conv_1", "conv_2", "conv_3", "conv_4", "conv_5"]
            )

            # Optimization parameters
            self.NUM_STEPS = int(data.get("NUM_STEPS", 200))
            self.STYLE_WEIGHT = float(data.get("STYLE_WEIGHT", 1000000))
            self.CONTENT_WEIGHT = float(data.get("CONTENT_WEIGHT", 1))
        except KeyError as e:
            raise KeyError(f"The required key is missing in {CONFIG_FILE_PATH}: {e}")

        # Creating directories, if there are none, during configuration initialization
        self.TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_STYLE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def load_nst_config(path: Path = CONFIG_FILE_PATH) -> NSTConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        return NSTConfig(config_data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid NST config at {path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading config file {path}: {e}", exc_info=True)
        raise


try:
    nst_params = load_nst_config()
except (FileNotFoundError, ValueError, Exception) as e:
    logger.warning(f"Could not load NST parameters: {e}. NST functionality will be disabled.")
    nst_params = None
