# Bitrix Task Bot

Проект для создания и отслеживания задач в Bitrix24 через телеграм бота. Асинхронная реализация бота включает использование Telegram, базы данных, BitrixAPI, Webhook и связанный с этим код.

## Структура проекта

### Конфигурационные файлы
Все конфигурационные файлы хранятся в `./storage`.

### Миграции
Миграции находятся в папке `./migrations`. Обязательно создайте базу данных через миграции.

### Исходный код
Весь исходный код расположен в папке `./src`.

#### Админ панель (`./src/admin/`)
Админ панель создана с использованием библиотеки [SQLAdmin](https://github.com/aminalaee/sqladmin). Состоит из:
- model_view
- auth

#### Bitrix API (`./src/bitrix/`)
API Bitrix включает модели API и синхронизацию данных с базой данных.

#### Бот (`./src/bot/`)
Структура бота написана на [Aiogram](https://github.com/aiogram/aiogram).

#### Классы (`./src/classes/`)
Состоит из базовых, абстрактных классов, dataclasses, class_const и моделей:
- Logger
- NotifyManager

#### База данных (`./src/db/`)
Код для работы с базой данных на [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy). Миграции выполнены с использованием [Alembic](https://github.com/sqlalchemy/alembic).

#### FastAPI (`./src/fast_api/`)
REST API, написанный на [FastAPI](https://github.com/tiangolo/fastapi), используется для Webhook Bitrix и Telegram.

#### Статические данные (`./src/static/`)
Статичные данные проекта, такие как кнопки и сообщения в боте, а также строки исключения комментариев с Bitrix.

#### Утилиты (`./src/utils/`)
Состоит из шаблонов и TaskReport для отправки статистики по задачам.

#### Конфигурации (`./src/configuration.py`)
Все конфигурации загружаются через этот файл.

#### Точка входа (`./src/main.py`)
Точка входа в приложение.

## Используемые технологии
- [Aiogram](https://github.com/aiogram/aiogram): для создания Telegram-бота.
- [SQLAdmin](https://github.com/aminalaee/sqladmin): для создания административной панели.
- [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy): для работы с базой данных.
- [Alembic](https://github.com/sqlalchemy/alembic): для выполнения миграций базы данных.
- [FastAPI](https://github.com/tiangolo/fastapi): для создания REST API и обработки Webhook.
