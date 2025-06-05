# nst_engine.py

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from PIL import Image
import torchvision.transforms as transforms

from torchvision.models import vgg19

import logging
import io
from pathlib import Path
from app.nst_config import nst_params

logger = logging.getLogger(__name__)


class NSTModelNotInitializedError(Exception):
    pass


class NSTEngine:
    def __init__(self, config):
        self.config = config
        self.device = None
        self.image_size = None
        self.cnn_model = None
        self.cnn_normalization_mean = None
        self.cnn_normalization_std = None
        self._initialized = False

        try:
            self._determine_device_and_image_size()
            self._load_model()
            self._initialized = True
            logger.info(
                f"NSTEngine initialized. Device: {self.device}, Image Size: {self.image_size}"
            )
        except Exception as e:
            logger.critical(f"NSTEngine initialization failed: {e}", exc_info=True)

    def _determine_device_and_image_size(self):
        pref = nst_params.DEVICE_PREFERENCE
        determined_device_str = "cpu"

        if pref == "auto":
            if torch.cuda.is_available():
                determined_device_str = "cuda"
                image_size = nst_params.IMAGE_SIZE_CUDA
            else:
                determined_device_str = "cpu"
                image_size = nst_params.IMAGE_SIZE_CPU
        elif pref == "cuda":
            if torch.cuda.is_available():
                determined_device_str = "cuda"
                image_size = nst_params.IMAGE_SIZE_CUDA
            else:
                logger.warning("CUDA preferred in config but not available. Falling back to CPU.")
                determined_device_str = "cpu"
                image_size = nst_params.IMAGE_SIZE_CPU
        elif pref == "cpu":
            determined_device_str = "cpu"
            image_size = nst_params.IMAGE_SIZE_CPU
        else:
            logger.warning(f"Unknown device preference '{pref}' in config. Falling back to CPU.")
            determined_device_str = "cpu"
            image_size = nst_params.IMAGE_SIZE

        if image_size is None:
            image_size = nst_params.IMAGE_SIZE

        self.device = torch.device(determined_device_str)
        self.image_size = int(image_size)
        # logger.info(f"Determined device: {self.device}, Determined image size: {self.image_size}")

    def _load_model(self):
        model_config_path_str = str(nst_params.MODEL_PATH)
        model_type = str(nst_params.MODEL_TYPE)

        model_path_abs = Path(__file__).resolve().parent / model_config_path_str

        model_loaded_successfully = False
        logger.info(
            "Attempting to load model. Type: '%s', Path: '%s'",
            model_type,
            model_path_abs if model_config_path_str else "N/A",
        )

        if model_type == "shrunk_object":
            if not model_config_path_str:
                logger.error("MODEL_TYPE is 'shrunk_object' but MODEL_PATH is not set.")
            elif model_path_abs.exists():
                try:
                    logger.info(f"Loading SHRUNK VGG19 model OBJECT from: {model_path_abs}")
                    loaded_model_features = torch.load(
                        model_path_abs,
                        map_location=self.device,
                        weights_only=False,
                    )
                    self.cnn_model = loaded_model_features.to(self.device).eval()
                    logger.info(
                        f"Successfully loaded shrunk VGG19 model object from {model_path_abs}"
                    )
                    model_loaded_successfully = True
                except Exception as e:
                    logger.error(
                        f"Failed to load shrunk model object from {model_path_abs}: {e}",
                        exc_info=True,
                    )
            else:
                logger.error(f"MODEL_TYPE is 'shrunk_object' but file {model_path_abs} not found.")

        elif model_type == "full_statedict":
            if not model_config_path_str:
                logger.error("MODEL_TYPE is 'full_statedict' but MODEL_PATH is not set.")
            elif model_path_abs.exists():
                try:
                    logger.info(f"Loading FULL VGG19 weights from state_dict: {model_path_abs}")
                    cnn_model_instance = vgg19(weights=None)
                    state_dict = torch.load(model_path_abs, map_location=self.device)
                    cnn_model_instance.load_state_dict(state_dict)
                    self.cnn_model = cnn_model_instance.features.to(self.device).eval()
                    logger.info(f"Successfully loaded full VGG19 weights from {model_path_abs}")
                    model_loaded_successfully = True
                except Exception as e:
                    logger.error(
                        f"Failed to load weights from {model_path_abs} into full VGG19: {e}",
                        exc_info=True,
                    )
            else:
                logger.error(f"MODEL_TYPE is 'full_statedict' but file {model_path_abs} not found.")

        if not model_loaded_successfully:
            raise RuntimeError(
                "FATAL: Could not load any VGG19 model. "
                f"Specified type: '{model_type}', path: '{model_config_path_str}'. "
                "Check config and file."
            )

        # Нормализация
        self.cnn_normalization_mean = torch.tensor(self.config.NORMALIZATION_MEAN).to(self.device)
        self.cnn_normalization_std = torch.tensor(self.config.NORMALIZATION_STD).to(self.device)

    class ContentLoss(nn.Module):
        def __init__(self, target):
            super().__init__()
            self.target = target.detach()
            self.loss = None

        def forward(self, input_tensor):
            self.loss = F.mse_loss(input_tensor, self.target)
            return input_tensor

    @staticmethod
    def gram_matrix(input_tensor):
        a, b, c, d = input_tensor.size()
        features = input_tensor.view(a * b, c * d)
        G = torch.mm(features, features.t())
        return G.div(a * b * c * d)

    class StyleLoss(nn.Module):
        def __init__(self, target_feature):
            super().__init__()
            self.target = NSTEngine.gram_matrix(target_feature).detach()
            self.loss = None

        def forward(self, input_tensor):
            G = NSTEngine.gram_matrix(input_tensor)
            self.loss = F.mse_loss(G, self.target)
            return input_tensor

    class Normalization(nn.Module):
        def __init__(self, mean, std, device):
            super().__init__()
            self.mean = torch.tensor(mean, device=device).view(-1, 1, 1)
            self.std = torch.tensor(std, device=device).view(-1, 1, 1)

        def forward(self, img):
            return (img - self.mean) / self.std

    def _image_loader(self, image_path_or_bytes):
        if not self._initialized:
            raise NSTModelNotInitializedError("NSTEngine is not initialized. Cannot load image.")
        loader_transform = transforms.Compose(
            [transforms.Resize((self.image_size, self.image_size)), transforms.ToTensor()]
        )
        if isinstance(image_path_or_bytes, (str, Path)):
            image = Image.open(image_path_or_bytes).convert("RGB")
        elif isinstance(image_path_or_bytes, bytes):
            image = Image.open(io.BytesIO(image_path_or_bytes)).convert("RGB")
        else:
            raise ValueError("image_path_or_bytes must be a file path (str/Path) or bytes.")
        image = loader_transform(image).unsqueeze(0)
        return image.to(self.device, torch.float)

    def _tensor_to_pil_image(self, tensor):
        if not self._initialized:
            raise NSTModelNotInitializedError(
                "NSTEngine is not initialized. " "Cannot convert tensor to PIL image."
            )
        image = tensor.cpu().clone()
        image = image.squeeze(0)
        unloader = transforms.ToPILImage()
        image = unloader(image)
        return image

    def _get_style_model_and_losses(self, style_img_tensor, content_img_tensor):
        if not self._initialized:
            raise NSTModelNotInitializedError(
                "NSTEngine is not initialized. Cannot get style model and losses."
            )
        if self.cnn_model is None:
            raise NSTModelNotInitializedError(
                "CNN model (VGG features) is not loaded in NSTEngine."
            )

        normalization = NSTEngine.Normalization(
            self.cnn_normalization_mean.tolist(),
            self.cnn_normalization_std.tolist(),
            self.device,
        ).to(self.device)

        content_losses = []
        style_losses = []
        model = nn.Sequential(normalization).to(self.device)
        i = 0

        content_layers_cfg = self.config.CONTENT_LAYERS
        style_layers_cfg = self.config.STYLE_LAYERS

        for layer in self.cnn_model.children():
            if isinstance(layer, nn.Conv2d):
                i += 1
                name = f"conv_{i}"
            elif isinstance(layer, nn.ReLU):
                name = f"relu_{i}"
                layer = nn.ReLU(inplace=False)
            elif isinstance(layer, nn.MaxPool2d):
                name = f"pool_{i}"
            elif isinstance(layer, nn.BatchNorm2d):
                name = f"bn_{i}"
            else:
                raise RuntimeError(f"Unrecognized layer: {layer.__class__.__name__}")

            model.add_module(name, layer)

            if name in content_layers_cfg:
                target = model(content_img_tensor).detach()
                content_loss = NSTEngine.ContentLoss(target)
                model.add_module(f"content_loss_{i}", content_loss)
                content_losses.append(content_loss)

            if name in style_layers_cfg:
                target_feature = model(style_img_tensor).detach()
                style_loss = NSTEngine.StyleLoss(target_feature)
                model.add_module(f"style_loss_{i}", style_loss)
                style_losses.append(style_loss)

        # Обрезаем модель до последнего слоя потерь
        for i_crop in range(len(model) - 1, -1, -1):
            if isinstance(model[i_crop], NSTEngine.ContentLoss) or isinstance(
                model[i_crop], NSTEngine.StyleLoss
            ):
                break
        model = model[: (i_crop + 1)]
        return model, style_losses, content_losses

    def _get_input_optimizer(self, input_img_tensor):
        if not self._initialized:
            raise NSTModelNotInitializedError("NSTEngine is not initialized. Cannot get optimizer.")
        optimizer = optim.LBFGS([input_img_tensor.requires_grad_()])
        return optimizer

    def _run_style_transfer_core(self, content_img_tensor, style_img_tensor, input_img_tensor):
        if not self._initialized:
            raise NSTModelNotInitializedError(
                "NSTEngine is not initialized. Cannot run style transfer core."
            )
        logger.info("Building the style transfer model..")

        model, style_losses, content_losses = self._get_style_model_and_losses(
            style_img_tensor, content_img_tensor
        )

        input_img_tensor.requires_grad_(True)
        model.requires_grad_(False)

        optimizer = self._get_input_optimizer(input_img_tensor)
        logger.info("Optimizing..")
        run = [0]
        num_steps = self.config.NUM_STEPS
        style_weight = self.config.STYLE_WEIGHT
        content_weight = self.config.CONTENT_WEIGHT

        while run[0] <= num_steps:

            def closure():
                with torch.no_grad():
                    input_img_tensor.clamp_(0, 1)
                optimizer.zero_grad()
                model(input_img_tensor)
                style_score = 0
                content_score = 0
                for sl in style_losses:
                    style_score += sl.loss
                for cl in content_losses:
                    content_score += cl.loss
                style_score *= style_weight
                content_score *= content_weight
                loss = style_score + content_score
                loss.backward()
                run[0] += 1
                if run[0] % 50 == 0:
                    logger.info(
                        f"run {run[0]}: Style Loss : {style_score.item():4f} "
                        f"Content Loss: {content_score.item():4f}"
                    )
                return style_score + content_score

            optimizer.step(closure)

        with torch.no_grad():
            input_img_tensor.clamp_(0, 1)
        return input_img_tensor

    def process_images(self, style_image_path_or_bytes, content_image_path_or_bytes):
        if not self._initialized:
            raise NSTModelNotInitializedError(
                "NSTEngine is not initialized. Call initialize() first or check logs."
            )

        try:
            style_img_tensor = self._image_loader(style_image_path_or_bytes)
            content_img_tensor = self._image_loader(content_image_path_or_bytes)
        except Exception as e:
            logger.error(f"Error loading images for NST: {e}")
            raise

        input_img_tensor = content_img_tensor.clone()

        logger.info(
            f"Starting NST process for style: {style_image_path_or_bytes}, "
            f"content: {content_image_path_or_bytes}"
        )
        output_tensor = self._run_style_transfer_core(
            content_img_tensor, style_img_tensor, input_img_tensor
        )
        logger.info("NST process finished.")

        output_pil_image = self._tensor_to_pil_image(output_tensor)
        img_byte_arr = io.BytesIO()
        output_pil_image.save(img_byte_arr, format="JPEG")
        return img_byte_arr.getvalue()
