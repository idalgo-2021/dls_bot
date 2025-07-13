from pathlib import Path
import torch
import torchvision.transforms as transforms
from PIL import Image

import logging

from app.architectures.cyclegan_networks import ResnetGenerator
import torch.nn as nn
import functools
from app.cyclegan_config import CycleGANConfig


logger = logging.getLogger(__name__)


class CycleGANModelNotInitializedError(Exception):
    pass


class CycleGANEngine:
    def __init__(self, config: CycleGANConfig):
        self.config = config
        self.device = None
        self.models = {}
        self._initialized = False

        try:
            self._determine_device()
            self._load_all_models()  # _initialized will be set in this method
            logger.info(
                f"CycleGANEngine initialization finished. "
                f"Device: {self.device}. Loaded models: {len(self.models)}"
            )
        except Exception as e:
            self._initialized = False
            logger.critical(f"CycleGANEngine initialization failed: {e}", exc_info=True)

    def _determine_device(self):
        pref = self.config.DEVICE_PREFERENCE
        determined_device_str = "cpu"

        if pref == "auto":
            if torch.cuda.is_available():
                determined_device_str = "cuda"
            else:
                determined_device_str = "cpu"
        elif pref == "cuda":
            if torch.cuda.is_available():
                determined_device_str = "cuda"
            else:
                logger.warning(
                    "CUDA preferred in config but not available. Falling back to CPU."
                )
                determined_device_str = "cpu"
        elif pref == "cpu":
            determined_device_str = "cpu"
        else:
            logger.warning(
                f"Unknown device preference '{pref}' in config. Falling back to CPU."
            )
            determined_device_str = "cpu"

        self.device = torch.device(determined_device_str)

    def _load_all_models(self):
        styles = self.config.styles
        if not styles or not isinstance(styles, dict):
            logger.warning(
                "No 'styles' section found in CycleGAN configuration file. "
                "No models will be loaded."
            )
            return

        for style_name, style_info in styles.items():
            model_filename = style_info.get("model_file")
            if not model_filename:
                logger.warning(
                    f"No 'model_file' specified for style '{style_name}'. Skipping."
                )
                continue

            model_path = self.config.MODELS_DIR / Path(model_filename).name

            if not model_path.exists():
                logger.warning(
                    f"Model file not found for style '{style_name}': {model_path}"
                )
                continue

            try:
                netG = ResnetGenerator(
                    input_nc=self.config.INPUT_CHANNELS,
                    output_nc=self.config.OUTPUT_CHANNELS,
                    ngf=64,
                    norm_layer=functools.partial(
                        nn.InstanceNorm2d, affine=False, track_running_stats=False
                    ),
                    use_dropout=False,
                    n_blocks=self.config.NUM_RESIDUAL_BLOCKS,
                )

                netG.load_state_dict(
                    torch.load(
                        model_path,
                        map_location=self.device
                    ),
                    strict=False
                )

                netG.to(self.device).eval()

                self.models[style_name] = netG
                logger.info(
                    f"Successfully loaded CycleGAN model for style: {style_name}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to load model for style '{style_name}' from {model_path}: {e}",
                    exc_info=True,
                )

        if len(self.models) > 0:
            self._initialized = True

    def get_available_styles(self) -> dict:
        return {
            name: info["display_name"]
            for name, info in self.config.styles.items()
            if name in self.models
        }

    def _image_to_tensor(self, image: Image.Image) -> torch.Tensor:
        transform = transforms.Compose(
            [
                transforms.Resize(self.config.IMAGE_SIZE),
                transforms.CenterCrop(self.config.IMAGE_SIZE),
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
            ]
        )
        return transform(image.convert("RGB")).unsqueeze(0).to(self.device)

    def _tensor_to_pil_image(self, tensor: torch.Tensor) -> Image.Image:
        output_image = tensor.detach().squeeze(0).cpu()
        output_image = output_image * 0.5 + 0.5  # Denormalization
        return transforms.ToPILImage()(output_image)

    def stylize(self, image: Image.Image, style_name: str) -> Image.Image:
        if style_name not in self.models:
            raise ValueError(f"Style '{style_name}' is not a valid or loaded style.")

        model = self.models[style_name]
        img_tensor = self._image_to_tensor(image)
        with torch.no_grad():
            output_tensor = model(img_tensor)

        return self._tensor_to_pil_image(output_tensor)
