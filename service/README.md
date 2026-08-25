# Инсайдер — Telegram Bot

Сервисная версия Инсайдера: тот же движок (STARRI-интервью → маппинг → генерация контента), но через Telegram-бота. Каждый пользователь проходит интервью в личном чате, а данные (Business DNA, истории, артефакты) хранятся изолированно в базе.

Уникальный чат на пользователя = приватность данных. Никто из случайных прохожих не видит чужие истории.

**Ссылка:** https://t.me/the_insider_bot

## Как это работает

```
Telegram ←→ Bot (Python) ←→ AI (polza.ai) ←→ PostgreSQL (Supabase)
```

- **Conversational UI** — Telegram (симпатичный и знакомый)
- **Оркестрация** — `bot/ai/client.py`: state machine этапов интервью (перевод SKILL.md в программный конечный автомат)
- **AI** — DeepSeek V4 Flash через OpenAI-совместимый API polza.ai
- **Хранилище** — PostgreSQL (Supabase), изоляция по `user_id`

## Команды

| Команда | Что делает |
|---------|-----------|
| `/start` | Приветствие, обзор команд |
| `/init` | Настроить Business DNA (контекст компании) |
| `/setup` | Перенастроить Business DNA |
| `/extract` | Провести STARRI-интервью |
| `/map` | Смапить историю на аудиторию и формат |
| `/generate` | Сгенерировать черновик контента |
| `/admin` | Панель администратора (только для admins) |
| `/cancel` | Отменить текущее действие |

## Запуск локально

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить переменные окружения
cp .env.example .env
# заполни BOT_TOKEN, POLZA_API_KEY, DATABASE_URL, ADMIN_TELEGRAM_IDS

# 3. Запустить бота
python -m bot.main
# Миграции БД применяются автоматически при старте
```

## Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `POLZA_API_KEY` | Ключ API polza.ai |
| `POLZA_BASE_URL` | Базовый URL (по умолчанию `https://api.polza.ai/v1`) |
| `AI_MODEL` | Модель (по умолчанию `deepseek-v4-flash`) |
| `DATABASE_URL` | Строка подключения к PostgreSQL (Supabase) |
| `ADMIN_TELEGRAM_IDS` | Список ID админов через запятую |

## Деплой на Railway (бесплатно)

1. Заведите репозиторий на GitHub и запушьте код из `service/`
2. В Railway: **New Project → Deploy from GitHub repo** → выберите репозиторий
3. Добавьте переменные окружения (см. таблицу выше)
4. Railway автоматически соберёт Docker-образ и запустит
5. Telegram-бот работает через long-polling — домен не нужен

## Структура

```
service/
├── bot/
│   ├── main.py          # Entry point, dispatcher
│   ├── handlers.py      # Telegram-обработчики команд и состояний
│   ├── db.py            # Слой доступа к PostgreSQL
│   └── ai/
│       └── client.py    # AI-клиент polza.ai + state machine + промпты
├── db/
│   └── schema.sql       # DDL для Supabase
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Отличия от скилла

| | Скилл | Сервис (бот) |
|---|---|---|
| Где работает | В любом AI-клиенте (Claude Code, Cursor...) | В Telegram |
| Данные | Локальные файлы (my_data/) | PostgreSQL, изолированно по пользователю |
| Идентификация | Файловая система | telegram_id |
| Контекст компании | `business/dna.yaml` в репо | JSONB в таблице users |

Скилл и сервис используют **одинаковую логику** (SKILL.md / protocol.md → `ai/client.py`). Можно использовать оба параллельно: скилл — для внутренней работы тех, у кого есть доступ к репо, сервис — для внешних пользователей.