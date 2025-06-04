# Используем официальный образ Python
FROM python:3.13-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /usr/src/app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
# COPY . . # Этот вариант тоже рабочий при наличии хорошего .dockerignore
# Более явное копирование:
COPY ./app ./app/ 

# Если у тебя есть другие файлы в корне проекта, которые нужны приложению
# (например, если бы env_settings.py был в корне, а не в app/), их нужно скопировать отдельно:
# COPY env_settings.py .

# Указываем команду для запуска приложения
# Запускаем python с указанием модуля. Python сам найдет app.bot.
# Текущая рабочая директория (/usr/src/app) будет добавлена в sys.path,
# поэтому Python найдет пакет app.
CMD ["python", "-m", "app.bot"]

# Порт для вебхуков (WEBHOOK_PORT).
# В твоем env_settings.py по умолчанию 8443.
# Этот EXPOSE больше для документации и для `docker run -P`.
EXPOSE 8443