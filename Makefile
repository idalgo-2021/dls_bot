IMAGE_NAME ?= my_dls_bot

TAG ?= latest
CONTAINER_NAME = dls_bot_container
ENV_FILE = .env

.PHONY: help build run run-webhook logs stop clean lint test requirements

help:
	@echo "Доступные команды для управления проектом dls_bot:"
	@echo "  make build            - Собрать Docker-образ (тег: $(TAG))"
	@echo "  make run              - Запустить Docker-контейнер в режиме polling (использует $(ENV_FILE))"
	@echo "  make run-webhook      - Запустить Docker-контейнер в режиме webhook (использует $(ENV_FILE), требует настройки порта и туннеля)"
	@echo "  make logs             - Показать логи запущенного контейнера $(CONTAINER_NAME)"
	@echo "  make stop             - Остановить Docker-контейнер $(CONTAINER_NAME)"
	@echo "  make clean            - Удалить остановленный контейнер $(CONTAINER_NAME) и опционально образ"
	@echo "  make clean-image      - Удалить Docker-образ $(IMAGE_NAME):$(TAG)"
	@echo "  make lint             - Запустить линтер (например, flake8 или ruff)"
	@echo "  make format           - Отформатировать код (например, black или ruff format)"
	@echo "  make test             - Запустить тесты (например, pytest)"
	@echo "  make requirements     - Сгенерировать requirements.txt из текущего venv (если используется)"
	@echo "  make shell            - Запустить shell внутри нового контейнера для отладки"
	@echo ""
	@echo "Переменные, которые можно переопределить при вызове:"
	@echo "  make build TAG=v1.0.0"
	@echo "  make run ENV_FILE=.env.production"

# --- Docker команды ---
build:
	@echo "Сборка Docker-образа $(IMAGE_NAME):$(TAG)..."
	docker build -t $(IMAGE_NAME):$(TAG) .
#	docker build --load -t $(IMAGE_NAME):$(TAG) .

run:
	@echo "Запуск контейнера $(CONTAINER_NAME) из образа $(IMAGE_NAME):$(TAG) с $(ENV_FILE)..."
	@echo "Убедитесь, что BOT_RUN_MODE=polling в $(ENV_FILE) или закомментировано"
	docker run --rm --name $(CONTAINER_NAME) --env-file $(ENV_FILE) $(IMAGE_NAME):$(TAG)

run-webhook:
	@echo "Запуск контейнера $(CONTAINER_NAME) из образа $(IMAGE_NAME):$(TAG) в режиме webhook с $(ENV_FILE)..."
	@echo "Убедитесь, что BOT_RUN_MODE=webhook и WEBHOOK_URL настроены в $(ENV_FILE)"
	@echo "Не забудьте пробросить порт (например, -p 8443:8443) и запустить ngrok или аналог!"
	docker run --rm --name $(CONTAINER_NAME) -p 3000:3000 --env-file $(ENV_FILE) $(IMAGE_NAME):$(TAG)
	# Замените 8443:8443 на ваш актуальный проброс портов, если он отличается

logs:
	@echo "Логи контейнера $(CONTAINER_NAME)..."
	docker logs -f $(CONTAINER_NAME)

stop:
	@echo "Остановка контейнера $(CONTAINER_NAME)..."
	docker stop $(CONTAINER_NAME) || true # || true чтобы не было ошибки, если контейнер уже остановлен

clean: stop
	@echo "Удаление остановленного контейнера $(CONTAINER_NAME)..."
	docker rm $(CONTAINER_NAME) || true # || true чтобы не было ошибки, если контейнера нет

clean-image:
	@echo "Удаление Docker-образа $(IMAGE_NAME):$(TAG)..."
	docker rmi $(IMAGE_NAME):$(TAG) || true

shell:
	@echo "Запуск интерактивной сессии в новом контейнере из образа $(IMAGE_NAME):$(TAG)..."
	docker run --rm -it --env-file $(ENV_FILE) --entrypoint /bin/bash $(IMAGE_NAME):$(TAG)


# --- Python/Проектные команды (предполагают наличие venv и установленных dev-зависимостей) ---
lint:
	@echo "Запуск линтера..."
	flake8 ./app
#	flake8 --config=.flake8 ./app

format:
	@echo "Форматирование кода..."
	black ./app

test:
	@echo "Запуск тестов..."
	pytest

requirements:
	@echo "Генерация requirements.txt"
	pip freeze > requirements.txt