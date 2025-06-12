FROM python:3.13-slim

# Устанавливаем рабочую директорию в контейнере
WORKDIR /usr/src/app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY ./app ./app/ 

# Копируем прочие необходимые файлы
COPY ./static ./static 
# COPY ./utils ./utils 

# Указываем команду для запуска приложения
# Запускаем python с указанием модуля. Python сам найдет app.bot.
# Текущая рабочая директория (/usr/src/app) будет добавлена в sys.path,
# поэтому Python найдет пакет app.
CMD ["python", "-m", "app.bot"]

# Порт для вебхуков (WEBHOOK_PORT).
# Этот EXPOSE больше для документации и для `docker run -P`.
EXPOSE 8443