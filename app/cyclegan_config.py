import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = Path(__file__).parent / "configs" / "cyclegan_params.yaml"


class CycleGANConfig:
    def __init__(self, data: dict):
        try:
            self.MODELS_DIR = Path(data["MODELS_DIR"])

            # Device parameters
            self.DEVICE_PREFERENCE = data.get("DEVICE", "auto").lower()

            # Model parameters(depends of architecture)
            self.INPUT_CHANNELS = int(data.get("INPUT_CHANNELS", 3))
            self.OUTPUT_CHANNELS = int(data.get("OUTPUT_CHANNELS", 3))
            self.NUM_RESIDUAL_BLOCKS = int(data.get("NUM_RESIDUAL_BLOCKS", 9))
            self.IMAGE_SIZE = int(data.get("IMAGE_SIZE", 256))

            # Style list
            self.styles = data.get("styles", {})
            if not isinstance(self.styles, dict):
                raise TypeError("'styles' section in config must be a dictionary.")

        except KeyError as e:
            raise KeyError(f"The required key is missing in {CONFIG_FILE_PATH}: {e}")

        # Creating directories, if there are none, during configuration initialization
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)


def load_cyclegan_config(path: Path = CONFIG_FILE_PATH) -> CycleGANConfig:
    if not path.exists():
        raise FileNotFoundError(f"CycleGAN config file not found at {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        return CycleGANConfig(config_data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid CycleGAN config at {path}: {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error loading CycleGAN config file {path}: {e}", exc_info=True
        )
        raise


try:
    cyclegan_params = load_cyclegan_config()
except (FileNotFoundError, ValueError, Exception) as e:
    logger.warning(
        f"Could not load CycleGAN parameters: {e}. "
        "CycleGAN functionality will be disabled."
    )
    cyclegan_params = None
