# shrinker_vgg19.py
#
# Утилита для обрезки модели VGG19 до N слоев и сохранения её в отдельный файл
#
# Полная модель скачивается из Интернета, а затем обрезается. Однако, доступен 
# вариант  обрезки уже скачанной полной модели, если она 
# находится в локальном каталоге(см.закомментированные строки с FULL_MODEL_PATH).
#
# Обрезанная модель сохраняется в: TRIMMED_MODEL_PATH
#
# Запуск из корня проекта:$ python utils/shrinker_vgg19.py
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 

import torch
import torchvision.models as models
import torch.nn as nn
import os

# Число слоев для обрезки.
# Перед изменением, рекомендуется ознакомиться со структурой VGG19.
NUM_FEATURE_LAYERS_TO_KEEP = 11

# Базовый каталог
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Путь к весам полной модели, расположенной локально(н-р VGG19 м.б. скачана из Интернета)
# FULL_MODEL_PATH = os.path.join(BASE_DIR, '..', 'app', 'models', 'nst', 'vgg19-dcbb9e9d.pth')

# Путь для сохранения обрезанной модели
TRIMMED_MODEL_FILENAME = f'vgg19_{NUM_FEATURE_LAYERS_TO_KEEP}_layers.pth'
TRIMMED_MODEL_PATH = os.path.join(BASE_DIR, '..', 'app', 'models', 'nst', TRIMMED_MODEL_FILENAME)


def create_trimmed_vgg19():
    # Загрузка VGG19 из локального каталога FULL_MODEL_PATH(если модель скачана)
    # vgg19_full = models.vgg19()
    # vgg19_full.load_state_dict(torch.load(FULL_MODEL_PATH))

    # Загрузка VGG19 из Интернета(со стандартными весами ImageNet)
    vgg19_full = models.vgg19(weights=models.VGG19_Weights.IMAGENET1K_V1)
    vgg19_features = vgg19_full.features

    # Обрезка нужного количество слоев
    trimmed_features = nn.Sequential(*list(vgg19_features.children())[:NUM_FEATURE_LAYERS_TO_KEEP])

    # Отключаем градиенты (для NST это стандартно, т.к. мы оптимизируем картинку, а не модель)
    for param in trimmed_features.parameters():
        param.requires_grad = False

    # Некритичные опции
    # # Переводим модель в режим оценки (evaluation mode)
    # trimmed_features.eval()
    # # Перемещаем модель на GPU, если доступно
    # torch.save(trimmed_features.cpu(), TRIMMED_MODEL_PATH)

    # Сохраняем всю модель (архитектуру + веса)
    torch.save(trimmed_features, TRIMMED_MODEL_PATH)
    print(
        f"Trimmed VGG19 (features only, {NUM_FEATURE_LAYERS_TO_KEEP} layers) "
        f"saved to {TRIMMED_MODEL_PATH}"
    )
    print(f"Model size: {os.path.getsize(TRIMMED_MODEL_PATH) / (1024*1024):.2f} MB")


if __name__ == "__main__":
    create_trimmed_vgg19()