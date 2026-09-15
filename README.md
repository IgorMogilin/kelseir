<div align="center">

# 🎵 Kelseir

**Асинхронный Telegram-бот для скачивания аудио с YouTube**

Принимает ссылку → скачивает в фоне через worker → загружает в S3 → отдаёт готовый файл

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://aiogram.dev)
[![Taskiq](https://img.shields.io/badge/Taskiq-Redis-4A90E2?style=flat-square)](https://taskiq-python.github.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Документация](https://github.com/IgorMogilin/kelseir/wiki) ·
[Issues](https://github.com/IgorMogilin/kelseir/issues) ·
[Projects](https://github.com/IgorMogilin/kelseir/projects) ·
[Wiki](https://github.com/IgorMogilin/kelseir/wiki)

</div>

---

## ⚡ Как это работает

```mermaid
flowchart LR
    U([👤 Пользователь]) -->|ссылка| B[🤖 Bot]
    B -->|задача| Q[(📬 Очередь)]
    Q -->|задача| W[⚙️ Worker]
    W -->|аудио| Y[📺 YouTube]
    W -->|файл| S[(☁️ S3)]
    W -->|готово| B
    B -->|🎵 аудио| U
```

**Ключевое:** скачивание не блокирует бота. Тяжёлые операции — в отдельном worker-процессе, связь через Redis-очередь.

---

## 🚀 Быстрый старт

### Требования
Python 3.11+ · Docker · uv

### Запуск

```bash
# 1. Клонировать
git clone https://github.com/IgorMogilin/kelseir.git
cd kelseir

# 2. Поднять инфраструктуру (Redis, PostgreSQL, MinIO)
docker-compose up -d

# 3. Настроить окружение
cp .env.example .env
# → заполнить BOT_TOKEN, REDIS_URL, PG_URL, S3_*

# 4. Установить зависимости
uv sync

# 5. Применить миграции
alembic upgrade head

# 6. Запустить бота
python main.py

# 7. Запустить воркер (в отдельном терминале)
taskiq worker worker:broker
```

📖 **Подробная инструкция** — в [Wiki → Настройка окружения](https://github.com/IgorMogilin/kelseir/wiki/Development-Setup)

---

## 🧱 Стек

| Слой | Технология |
|------|------------|
| Язык | Python 3.11+ |
| Telegram | Aiogram 3 |
| Очередь | Taskiq + Redis |
| БД | PostgreSQL 15 + SQLAlchemy 2.0 |
| Скачивание | yt-dlp + ffmpeg |
| Хранилище | S3-совместимое (MinIO / AWS) |
| Конфиг | pydantic-settings |
| Логи | loguru |

---

## 📚 Документация

Вся подробная документация — в **[Wiki](https://github.com/IgorMogilin/kelseir/wiki)**:

| | Раздел | О чём |
|---|--------|-------|
| 🏗 | [Архитектура](https://github.com/IgorMogilin/kelseir/wiki/Architecture) | Схема сервиса, жизненный цикл задачи |
| ⚙️ | [Конфигурация](https://github.com/IgorMogilin/kelseir/wiki/Configuration) | Переменные окружения, Redis DB |
| 🛠 | [Настройка окружения](https://github.com/IgorMogilin/kelseir/wiki/Development-Setup) | Локальный запуск с нуля |
| 🤖 | [Bot Gateway](https://github.com/IgorMogilin/kelseir/wiki/Bot-Gateway) | Aiogram, FSM, Rate Limiter |
| ⚙️ | [Worker Service](https://github.com/IgorMogilin/kelseir/wiki/Worker-Service) | Taskiq, yt-dlp, S3, кэш |
| 🚢 | [Деплой](https://github.com/IgorMogilin/kelseir/wiki/Deployment) | Развёртывание на сервере |
| 🧪 | [Тестирование](https://github.com/IgorMogilin/kelseir/wiki/Testing) | Тесты, линтеры, CI |

---

## 📁 Структура проекта

```
kelseir/
├── bot/          # Bot Gateway (Aiogram 3)
├── worker/       # Worker Service (Taskiq)
├── core/         # Общая логика (конфиг, логгер, БД, S3)
├── docs/         # Документация и схемы
├── tests/        # Тесты
├── main.py       # Точка входа бота
├── pyproject.toml
└── docker-compose.yml
```

---

## 🎯 Статус

**Веха:** `v0.1.0 — MVP` 🚧 в разработке

Прогресс и задачи — на [канбан-доске](https://github.com/IgorMogilin/kelseir/projects).

---

<div align="center">

<sub>Сделано с ❤️ для тех, кто любит музыку</sub>

</div>
