# Telegram Style Transfer Bot

🎓 **Итоговый проект 1 курса (весна 2025) Deep Learning School МФТИ**

* [Deep Learning School](https://dls.samcs.ru)
* [Course page on stepic.org](https://stepik.org/course/230362/info)

Telegram-бот представляет собой сервис стилизации изображений: он принимает два изображения — основное и стиль — и возвращает изображение с применённым стилем.

---


## Возможности

* ✅ Поддержка **polling** и **webhook** режимов
* ✅ Возможность запуска в **Docker-контейнере**
* ✅ Возможность работы с **ngrok**, **DevTunnels** или **реверс-прокси(nginx)**
* ✅ Без подключения к базе данных и внешним сервисам
* ✅ Использование `.env` файла для конфигурации
* ✅ Асинхронная обработка запросов

## Технологии

* **Язык**: Python
* **Фреймворк**: [aiogram](https://github.com/aiogram/aiogram)
* **HTTP-сервер**: aiohttp
* **Сборка контейнера**: GitHub Actions + GHCR



## Стилизация изображений

### Алгоритм Гатиса(Neural Style Transfer)

* **Ссылка на статью в arxiv.org:** [A Neural Algorithm of Artistic Style](https://arxiv.org/abs/1508.06576)
* **Статья со сквозным примером и ноутбуком**: [Neural Transfer Using PyTorch](https://docs.pytorch.org/tutorials/advanced/neural_style_tutorial.html)

### Какой-то другой алгоритм или подход(д.б. ГАНы)




## Запуск

Бот может быть запущен в Docker. В зависимости от настроек `.env`, может работать в режиме polling или webhook.

Или вручную:

```bash
docker build -t tg-style-bot .
docker run --env-file .env -p 8443:8443 tg-style-bot
```

## Webhook режим

Поддерживается работа:

* через **ngrok**
* через **DevTunnels**
* через **реверс-прокси** (например, nginx)

> ⚠️ При использовании реверс-прокси необходимо пробросить `WEBHOOK_PATH` в настройках nginx.
> 📄 Также может потребоваться передать путь к `.pem`-сертификату через `WEBHOOK_CERT_PATH` при регистрации webhook'а.

## 📁 Конфигурация

Конфигурация задаётся через `.env` файл. Пример — в [.env.example](./.env.example).

Некоторые важные переменные:

* `TELEGRAM_BOT_TOKEN` — токен бота
* `BOT_RUN_MODE` — режим запуска (`polling` или `webhook`)
* `WEBHOOK_URL`, `WEBHOOK_PORT`, `WEBHOOK_PATH`, `WEBHOOK_SECRET`
* `WEBHOOK_CERT_PATH` — нужен при прямом доступе к Telegram API без прокси

## CI/CD

* Используется **GitHub Actions**
* Образ собирается и публикуется в **GHCR**
* Локальные цели (lint, format) — через `Makefile`

## Примечания

* Проект находится в стадии разработки.
* Основной функционал (стилизация изображений) будет реализован позже.
* Пока не требует базы данных или внешних API.

---


Пример:

```markdown
![GitHub Actions](https://github.com/username/repo/actions/workflows/deploy.yml/badge.svg)
![Docker Image Size](https://img.shields.io/docker/image-size/username/image/latest)
```

