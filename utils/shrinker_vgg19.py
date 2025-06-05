# shrinker_vgg19.py

# Программа для обрезки модели VGG19 до N слоев и сохранения её в отдельный файл
# Запуск из корня проекта:$ python utils/shrinker_vgg19.py


import torch
import torchvision.models as models
import torch.nn as nn
import os

# Определим, сколько слоев из features мы хотим оставить.
# Для NST часто используют слои до conv4_2 или conv5_1.
# VGG19 features:
# conv1_1 (0), relu1_1 (1)
# conv1_2 (2), relu1_2 (3)
# pool1   (4)
# conv2_1 (5), relu2_1 (6)
# conv2_2 (7), relu2_2 (8)
# pool2   (9)
# conv3_1 (10), relu3_1 (11) # Твои 11 слоев заканчиваются здесь (индекс 10)
# conv3_2 (12), relu3_2 (13)
# conv3_3 (14), relu3_3 (15)
# conv3_4 (16), relu3_4 (17)
# pool3   (18)
# conv4_1 (19), relu4_1 (20)
# conv4_2 (21), relu4_2 (22) # Часто используется для content loss
# conv4_3 (23), relu4_3 (24)
# conv4_4 (25), relu4_4 (26)
# pool4   (27)
# conv5_1 (28), relu5_1 (29) # Часто используется для style loss (самый глубокий)
# ... и так далее

# Если нужны слои до conv4_2 (индекс 21), то нужно взять 22 слоя: [:22]
# Если нужны слои до relu4_1 (индекс 20), то нужно взять 21 слой: [:21]
# Если нужны слои до conv5_1 (индекс 28), то нужно взять 29 слоев: [:29]
# Установи нужное значение в зависимости от твоих CONTENT_LAYERS и STYLE_LAYERS
NUM_FEATURE_LAYERS_TO_KEEP = 11  # Пример: до conv4_2 (индекс 21)

# Путь к весам полной модели
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_MODEL_PATH = os.path.join(BASE_DIR, '..', 'app', 'models', 'vgg19-dcbb9e9d.pth')

# Путь для сохранения обрезанной модели
TRIMMED_MODEL_FILENAME = f'vgg19_{NUM_FEATURE_LAYERS_TO_KEEP}_layers.pth'
TRIMMED_MODEL_PATH = os.path.join(BASE_DIR, '..', 'app', 'models', TRIMMED_MODEL_FILENAME)


def create_trimmed_vgg19():
    # Загружаем VGG19 со стандартными весами ImageNet, чтобы потом взять из нее часть
    vgg19_full = models.vgg19(weights=models.VGG19_Weights.IMAGENET1K_V1)
    
    # Если ты хочешь использовать свой локальный файл vgg19-dcbb9e9d.pth как источник,
    # то нужно сначала загрузить его state_dict в пустую модель:
    # vgg19_full = models.vgg19(weights=None) # или models.vgg19() до torchvision 0.13
    # vgg19_full.load_state_dict(torch.load(FULL_MODEL_PATH))
    
    vgg19_features = vgg19_full.features

    # Обрезаем нужное количество слоев
    # list(vgg19_features.children())[:NUM_FEATURE_LAYERS_TO_KEEP]
    # создает список из первых NUM_FEATURE_LAYERS_TO_KEEP слоев
    trimmed_features = nn.Sequential(*list(vgg19_features.children())[:NUM_FEATURE_LAYERS_TO_KEEP])

    # Отключаем градиенты (для NST это стандартно, т.к. мы оптимизируем картинку, а не модель)
    for param in trimmed_features.parameters():
        param.requires_grad = False

    # Сохраняем всю модель (архитектуру + веса)
    torch.save(trimmed_features, TRIMMED_MODEL_PATH)
    print(
        f"Trimmed VGG19 (features only, {NUM_FEATURE_LAYERS_TO_KEEP} layers) "
        f"saved to {TRIMMED_MODEL_PATH}"
    )
    print(f"Model size: {os.path.getsize(TRIMMED_MODEL_PATH) / (1024*1024):.2f} MB")


if __name__ == "__main__":
    create_trimmed_vgg19()