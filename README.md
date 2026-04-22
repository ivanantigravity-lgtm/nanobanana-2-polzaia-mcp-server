# Nano Banana 2 Polza MCP Server

`mcp-name: io.github.ivanantigravity-lgtm/nanobanana-2-polzaia-mcp-server`

MCP-сервер для генерации и редактирования изображений через `Polza` с моделями семейства Google Nano Banana:

- `google/gemini-3.1-flash-image-preview` — Nano Banana 2, модель по умолчанию
- `google/gemini-3-pro-image-preview` — для сложных композиций и максимального качества
- `google/gemini-2.5-flash-image` — для быстрых черновиков

Сервер отдаёт изображения настоящими MCP image content-блоками и параллельно — структурированный JSON с метаданными и подсказками по воспроизводимости.

## Инструменты MCP

- `generate_image` — генерация и редактирование. Поддерживает до трёх референсов для conditioning, выбор модели, aspect ratio, разрешение и прочие параметры.
- `fetch_generation` — докачка уже запущенной генерации по `gen_...` id. Нужен, когда MCP-клиент отвалился по таймауту, а генерация на стороне Polza успешно завершилась. Позволяет не перегенерировать (и не оплачивать повторно).
- `upload_file` — загрузка файлов в Polza Storage.
- `show_output_stats` — статистика локальной выходной директории.
- `maintenance` — обслуживание кэша, квот и БД.

## Что нужно пользователю

- `Claude Code` или любой другой MCP-клиент
- `uv`
- `Python 3.11+`
- `POLZA_AI_API_KEY` (токен аккаунта Polza)

## Быстрая установка за 2 минуты

Для `Claude Code` / `VS Code`:

1. Установите `uv` (`brew install uv` на macOS).
2. В корне проекта создайте файл `.mcp.json`.
3. Вставьте конфиг и подставьте свой Polza-ключ.

```json
{
  "mcpServers": {
    "nanobanana-polza": {
      "command": "uvx",
      "args": ["nanobanana-2-polzaia-mcp-server@latest"],
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/Users/yourname/Documents/nanobanana"
      }
    }
  }
}
```

Перезапустите Claude Code / VS Code.

## Восстановление после таймаута

MCP-клиенты (в том числе Claude Code) обычно имеют собственный таймаут на один tool call порядка 60 секунд. Nano Banana 2 укладывается в это окно не всегда, и клиент может вернуть `The read operation timed out` ещё до того, как Polza успела отдать результат. Сервер Polza в этот момент доводит генерацию до конца и сохраняет её под `gen_...` id.

Если такое случилось:

1. Посмотрите `gen_...` id в веб-интерфейсе Polza (раздел генераций).
2. Вызовите `fetch_generation` с этим id — сервер опросит статус и сохранит файл локально.

```
fetch_generation(media_id="gen_2158267363095220225",
                 output_path="/abs/path/to/slide_3.png")
```

Параметр `output_path` принимает как конкретный файл, так и директорию. При отсутствии параметра файл сохраняется в `IMAGE_OUTPUT_DIR`.

## Локальная разработка

```bash
git clone https://github.com/ivanantigravity-lgtm/nanobanana-2-polzaia-mcp-server.git
cd nanobanana-2-polzaia-mcp-server
uv sync
cp .env.example .env
```

Минимум в `.env`:

```env
POLZA_AI_API_KEY=your_polza_api_key
POLZA_BASE_URL=https://polza.ai/api
IMAGE_OUTPUT_DIR=/absolute/path/to/output
```

Запуск:

```bash
uv run python -m nanobanana_2_polzaia_mcp_server.server
```

## Claude Code / VS Code (варианты конфига)

Установленный через PyPI пакет — рекомендуемый вариант:

```json
{
  "mcpServers": {
    "nanobanana-polza": {
      "command": "uvx",
      "args": ["nanobanana-2-polzaia-mcp-server@latest"],
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/Users/demo/Documents/nanobanana"
      }
    }
  }
}
```

Запуск из исходников:

```json
{
  "mcpServers": {
    "nanobanana-polza-local": {
      "command": "uv",
      "args": ["run", "python", "-m", "nanobanana_2_polzaia_mcp_server.server"],
      "cwd": "/absolute/path/to/nanobanana-2-polzaia-mcp-server",
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/absolute/path/to/output"
      }
    }
  }
}
```

## Claude Desktop

На macOS добавьте сервер в файл:

`~/Library/Application Support/Claude/claude_desktop_config.json`

Пример:

```json
{
  "mcpServers": {
    "nanobanana-polza": {
      "command": "uvx",
      "args": ["nanobanana-2-polzaia-mcp-server@latest"],
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/Users/demo/Documents/nanobanana"
      }
    }
  }
}
```

## Переменные окружения

| Переменная | Обязательно | Описание |
|---|---|---|
| `POLZA_AI_API_KEY` | да | Токен доступа к Polza API |
| `POLZA_BASE_URL` | нет | База API, по умолчанию `https://polza.ai/api` |
| `IMAGE_OUTPUT_DIR` | нет | Директория для сохранённых файлов, по умолчанию `~/nanobanana-images` |
| `POLZA_POLL_INTERVAL_SECONDS` | нет | Интервал поллинга статуса, по умолчанию `2` |
| `POLZA_POLL_TIMEOUT_SECONDS` | нет | Таймаут ожидания генерации, по умолчанию `120` |
| `POLZA_EXTERNAL_USER_ID` | нет | Передаётся в Polza как `user` для антифрода |
| `RETURN_FULL_IMAGE` | нет | Возвращать полное изображение в MCP-ответе вместо thumbnail |
| `NANOBANANA_MODEL` | нет | Дефолтный tier: `auto`, `nb2`, `pro`, `flash` |

## Публикация новой версии

```bash
# 1. bump версии в pyproject.toml и nanobanana_2_polzaia_mcp_server/__init__.py
# 2. обновить CHANGELOG.md
# 3. прогнать быстрый smoke-test
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall nanobanana_2_polzaia_mcp_server
uv build

# 4. публикация на PyPI
uv publish --token "$UV_PUBLISH_TOKEN"

# 5. публикация метаданных в MCP Registry
brew install mcp-publisher   # один раз
mcp-publisher login
mcp-publisher publish
```

MCP Registry хранит только метаданные, сам пакет должен лежать на PyPI.

## Используемые эндпоинты Polza

- `POST /v1/media` — запуск генерации
- `GET /v1/media/{id}` — статус и результат (используется для `fetch_generation` и поллинга)
- `POST /v1/storage/upload` — загрузка референса
- `GET /v1/storage/files/{id}` — метаданные файла
- `DELETE /v1/storage/files/{id}` — удаление файла

## Лицензия

MIT. См. файл `LICENSE`.
