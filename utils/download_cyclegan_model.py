# download_cyclegan_model.py
#
# Утилита для загрузки предобученных стилевых моделей с сайта
# URL=http://efrosgans.eecs.berkeley.edu/cyclegan/pretrained_models
#
# Доступные модели - см. в AVAILABLE_MODELS
# Модели скачиваются в каталог - TARGET_DIR
#
# Запуск из корня проекта:$ python utils/download_cyclegan_model.py <имя_модели>"
# Пример: $ python utils/download_cyclegan_model.py style_monet
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import requests
from pathlib import Path
import sys
from tqdm import tqdm

BASE_URL = "http://efrosgans.eecs.berkeley.edu/cyclegan/pretrained_models"
TARGET_DIR = Path(__file__).parent.parent / "app" / "models" / "cyclegan"

AVAILABLE_MODELS = [
    "apple2orange", "orange2apple", "summer2winter_yosemite", "winter2summer_yosemite",
    "horse2zebra", "zebra2horse", "monet2photo", "style_monet", "style_cezanne",
    "style_ukiyoe", "style_vangogh", "sat2map", "map2sat", "cityscapes_photo2label",
    "cityscapes_label2photo", "facades_photo2label", "facades_label2photo",
    "iphone2dslr_flower"
]


def download_model(model_name: str):
    if model_name not in AVAILABLE_MODELS:
        print(f"Ошибка: модель '{model_name}' не найдена в списке доступных.")
        print("Пожалуйста, выберите одну из следующих моделей:")
        print(" ".join(AVAILABLE_MODELS))
        return

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{model_name}.pth"
 
    target_path = TARGET_DIR / f"{model_name}.pth"

    print(f"Скачивание модели '{model_name}'...")
    print(f"Источник: {url}")
    print(f"Сохранение в: {target_path}")

    try:
        response = requests.get(url, stream=True)
        # Проверка на ошибки HTTP (4xx, 5xx)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        
        with open(target_path, 'wb') as f, tqdm(
            desc=model_name,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                size = f.write(chunk)
                bar.update(size)

        print(f"Модель '{model_name}' успешно скачана.")

    except requests.RequestException as e:
        print(f"Ошибка при скачивании: {e}")
        if target_path.exists():
            # Удаляем неполный файл
            target_path.unlink()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python utils/download_models.py <madel name>")
        sys.exit(1)
    
    model_to_download = sys.argv[1]
    download_model(model_to_download)