# YouTube -> Discord via GitHub Actions

Автоматически проверяет YouTube RSS-ленты и отправляет уведомления о новых видео в Discord через webhook.

## Как работает

- Запускается каждые 10 минут через GitHub Actions `schedule`
- Поддерживает **несколько YouTube-каналов** одновременно
- Получает последнее видео из RSS-ленды каждого канала
- Отправляет embed-уведомление в Discord, если найдено новое видео
- Сохраняет состояние в `state.json` с датой и временем последней проверки
- Поддерживает **force-posting** любого видео по запросу

## Файлы

| Файл | Описание |
|------|----------|
| `youtube_to_discord.py` | Основной скрипт |
| `.github/workflows/youtube-discord.yml` | GitHub Actions workflow |
| `requirements.txt` | Python-зависимости |
| `state.json` | Состояние (создаётся автоматически) |

## Формат state.json

```json
{
  "channels": {
    "UCxxxxxxxxxxxxxxxx": {
      "video_id": "dQw4w9WgXcQ",
      "updated_at": "2026-06-08T15:41:04Z"
    },
    "UCyyyyyyyyyyyyyyyyyy": {
      "video_id": "xxxxxxxxxxx",
      "updated_at": "2026-06-08T14:00:00Z"
    }
  },
  "last_checked": "2026-06-08T15:41:04Z",
  "last_updated": "2026-06-08T15:41:04Z"
}
```

## Настройка

### 1. GitHub Secrets

Перейди в `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

| Секрет | Обязателен | Описание |
|--------|------------|----------|
| `DISCORD_WEBHOOK_URL` | Да | URL Discord webhook |
| `YOUTUBE_CHANNEL_IDS` | Да | ID каналов через запятую (например, `UCxxxxx,UCyyyyy`) |
| `DISCORD_ROLE_ID` | Нет | ID роли для пинга при новом видео |
| `BOT_NAME` | Нет | Имя webhook-бота |
| `BOT_AVATAR_URL` | Нет | URL аватара webhook-бота |

### 2. Первый запуск

Запусти workflow вручную через `Actions` -> `YouTube to Discord` -> `Run workflow` (поле оставить пустым).

Первый запуск **не отправляет** сообщение в Discord — он только сохраняет текущее последнее видео каждого канала в `state.json` как точку отсчёта. Все последующие новые видео будут вызывать уведомления.

### 3. Force-post

Чтобы принудительно отправить последнее видео конкретного канала:

1. Перейди в `Actions` -> `YouTube to Discord` -> `Run workflow`
2. В поле `Channel ID to force-post` введи ID канала
3. Нажми `Run workflow`

## Как найти YouTube Channel ID

1. Открой канал на YouTube
2. Перейди в `О канале` -> нажми `Поделиться` -> `Скопировать ID канала`
3. Либо посмотри в URL: `youtube.com/channel/UCxxxxxxxx` — это и есть ID

## Требования

- Python 3.11+
- `requests` (устанавливается автоматически из `requirements.txt`)
