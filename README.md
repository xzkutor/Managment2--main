# Порівняння товарів за посиланнями

Веб-застосунок для парсингу товарів з декількох сайтів та їх порівняння.

> Детальна технічна документація знаходиться у [`docs/`](docs/index.md).

## Можливості

✅ Вставити посилання на декілька сайтів  
✅ Автоматичний парсинг товарів  
✅ Порівняння товарів за назвою та артикулом  
✅ Групування схожих товарів  
✅ Вивід у таблиці з колонками: Артикул, Назва, Модель  
✅ Зручний інтерфейс  
✅ Доменно-орієнтована евристика збігу для хокейного інвентарю

---

## Документація

| Розділ | Файл |
|---|---|
| Майстер-індекс документації | [docs/index.md](docs/index.md) |
| Архітектура | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Структура репозиторію | [docs/repository_map.md](docs/repository_map.md) |
| DB-first API | [docs/api/db_first.md](docs/api/db_first.md) |
| Admin/Service API | [docs/api/admin.md](docs/api/admin.md) |
| Порівняння та евристика збігу | [docs/domain/comparison_and_matching.md](docs/domain/comparison_and_matching.md) |
| Gap-review workflow | [docs/domain/gap_review.md](docs/domain/gap_review.md) |
| Sync lifecycle та БД | [docs/operations/sync_lifecycle.md](docs/operations/sync_lifecycle.md) |
| Стратегія тестування | [docs/testing/testing_strategy.md](docs/testing/testing_strategy.md) |

---

## Встановлення

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
pip install -r requirements.txt
```

---

## Запуск застосунку

```bash
python app.py
```

Доступно на http://localhost:5000.

---

## UI-сторінки

| Шлях | Призначення |
|---|---|
| `/` | Порівняння асортименту: авто-пропозиції, кандидати, тільки-в-референсі, тільки-в-цільовому |
| `/matches` | Перегляд збережених підтверджених маппінгів товарів |
| `/service` | Операційна панель (категорії / маппінги / історія) |
| `/gap` | Розрив асортименту для контент-менеджерів |

---

## API — короткий огляд

Три групи ендпоінтів:

- **DB-first** — `/api/stores`, `/api/stores/<id>/categories`, `/api/comparison`, `/api/gap` — основний флоу читання та порівняння. Повний контракт: [docs/api/db_first.md](docs/api/db_first.md).
- **Service/Admin** — синхронізація, скрапінг, маппінги. Докладніше: [docs/api/admin.md](docs/api/admin.md).
- **Internal/Admin (adapter runtime)** — `/api/adapters`, `/api/adapters/<name>/categories` — тільки для операційного/адмін-introspection адаптерів. Не є частиною канонічного DB-first API. Нормальні UI-флоу не залежать від цих ендпоінтів.

---

## База даних та міграції

ORM: SQLAlchemy 2.x. За замовчуванням SQLite (`sqlite:///pricewatch.db`).
PostgreSQL підтримується як альтернативний backend (ADR-0006).

**Alembic є канонічним шляхом керування схемою для не-тестових середовищ.**

```bash
# SQLite (за замовчуванням, без змінних оточення):
PYTHONPATH=. alembic upgrade head

# PostgreSQL:
export DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname
PYTHONPATH=. alembic upgrade head
```

Перевірка роботи з PostgreSQL: `tests/verify_postgres.py` (інструкції всередині файлу).

Докладніше: [docs/operations/sync_lifecycle.md](docs/operations/sync_lifecycle.md).

---

## Валідація запитів (Pydantic)

Активні write-ендпоінти (`/api/comparison`, `/api/gap`, `/api/gap/status` та ін.)
використовують Pydantic для валідації тіла запиту на HTTP-рівні.

При помилці валідації відповідь:

```json
{
  "error": "validation_error",
  "message": "Request body is invalid.",
  "details": [{"field": "...", "message": "..."}]
}
```

HTTP-статус: `422` для помилок Pydantic, `400` для не-JSON контенту.

Деталі у [CONTRIBUTING.md](CONTRIBUTING.md) розділ "Boundary validation".

---

## Виробнича топологія процесів (Production Runtime Topology)

Для виробничого середовища веб, планувальник і воркер запускаються як **окремі процеси**:

| Процес | Команда | Призначення |
|---|---|---|
| **Web** | `gunicorn app:app` | Обслуговує HTTP API та UI. Flask dev server — тільки для локальної розробки |
| **Scheduler** | `python -m pricewatch.scrape.run_scheduler` | Виявляє задачі, ставить у чергу ScrapeRun, керує ретраями |
| **Worker** | `python -m pricewatch.scrape.run_worker` | Забирає ScrapeRun із черги та виконує раннери |

### Змінні оточення для тонкого налаштування

| Змінна | За замовчуванням | Опис |
|---|---|---|
| `APP_ENV` | `development` | Режим середовища. `production` або `prod` — вимикає вбудований autostart планувальника |
| `SCHEDULER_ENABLED` | `true` | Вмикає/вимикає планувальник |
| `SCHEDULER_AUTOSTART` | `true` | Дозволяє автозапуск вбудованого планувальника у dev-режимі |
| `SCHEDULER_TICK_SECONDS` | `30` | Інтервал між тіками планувальника (секунди) |
| `WORKER_ENABLED` | `true` | Вмикає/вимикає воркер |
| `WORKER_POLL_INTERVAL_SEC` | `5` | Інтервал опитування черги воркером (секунди) |

### Локальна розробка

```bash
# Звичайний запуск Flask dev server (вбудований планувальник запускається автоматично, якщо APP_ENV != production)
python app.py

# Або явно увімкнути планувальник
SCHEDULER_ENABLED=true SCHEDULER_AUTOSTART=true python app.py

# Статус планувальника та черги
curl http://localhost:5000/api/scrape-status
```

---

## Frontend розробка (Vue 3 + Vite SPA)

Фронтенд побудований на Vue 3 + Vite 5 + TypeScript як єдиний SPA. Flask обслуговує
`templates/spa.html` для всіх UI-маршрутів; Vue Router керує клієнтською навігацією.

### Встановлення залежностей

```bash
cd frontend
npm install
```

### Режим розробки (Vite dev server)

```bash
# У одному терміналі — Flask backend
python app.py

# В іншому терміналі — Vite dev server (hot-reload)
cd frontend && npm run dev
```

У Flask конфігурації встановіть:
```
VITE_USE_DEV_SERVER=True
VITE_DEV_SERVER_URL=http://localhost:5173
```

Тоді `{{ vite_asset_tags('src/main.ts') }}` у `spa.html` буде підключати assets безпосередньо з Vite.

### Production build

```bash
cd frontend && npm run build
# Артефакти записуються у static/dist/
```

Flask читає `static/dist/.vite/manifest.json` і автоматично підставляє правильні хеш-іменовані asset-URL через `vite_asset_tags('src/main.ts')`.

### Запуск frontend-тестів

```bash
cd frontend && npm test
```

### Виробниче середовище (Production)

```bash
# Web
gunicorn app:app --bind 0.0.0.0:5000 --workers 2

# Scheduler (окремий процес)
APP_ENV=production python -m pricewatch.scrape.run_scheduler

# Worker (окремий процес, можна запустити кілька)
APP_ENV=production python -m pricewatch.scrape.run_worker
```

> **Важливо:** у виробничому середовищі (`APP_ENV=production`) вбудований autostart планувальника з `app.py` завжди заблокований, навіть якщо `SCHEDULER_AUTOSTART=true`. Це запобігає випадковому запуску планувальника всередині web-процесу.

---

## Тести

```bash
# Python/pytest
PYTHONPATH=. pytest -q

# Frontend (Vitest)
cd frontend && npm test
```

Докладніше: [docs/testing/testing_strategy.md](docs/testing/testing_strategy.md).

---

## Структура проєкту

```
Managment2--main/
├── app.py              # Фабрика застосунку (create_app) + точка запуску WSGI/dev
├── pricewatch/         # Основний пакет
│   ├── core/           # Спільні примітиви, нормалізація, реєстр адаптерів
│   ├── db/             # ORM-моделі, репозиторії, DB-абстракції
│   ├── net/            # Канонічний HTTP-клієнт (pricewatch.net.http_client)
│   ├── services/       # Use-cases: синхронізація, маппінги, порівняння, gap
│   ├── shops/          # Адаптери для кожного магазину
│   └── web/            # Flask Blueprints — весь HTTP-шар (маршрути, серіалізатори)
├── frontend/           # Vue 3 + Vite 5 + TypeScript SPA
│   ├── src/
│   │   ├── main.ts     # Єдина точка входу SPA
│   │   ├── router/     # Vue Router (routes.ts + index.ts)
│   │   ├── layouts/    # AppShellLayout (header + RouterView)
│   │   ├── pages/      # Компоненти сторінок + composables + api (per-page)
│   │   ├── components/ # Спільні Vue-компоненти (AppShellHeader, BaseButton, …)
│   │   ├── composables/# Спільні composables (useAsyncState, …)
│   │   ├── api/        # Спільний HTTP-клієнт та адаптери API
│   │   ├── types/      # Фронтенд DTO-типи
│   │   └── test/       # Vitest unit/component тести (включно з test/router/)
│   └── vite.config.ts
├── static/
│   ├── css/            # Спільний CSS (common.css)
│   └── dist/           # Vite build output (генерується автоматично)
├── migrations/         # Alembic міграції
├── templates/          # spa.html — єдиний SPA-шаблон Flask
├── tests/              # Python/pytest тести
├── docs/               # Детальна документація
└── README.md
```


Повна карта: [docs/repository_map.md](docs/repository_map.md).

---

## Технології

- **Backend:** Flask, SQLAlchemy 2.x, SQLite / PostgreSQL
- **Парсинг:** requests, BeautifulSoup4, lxml
- **Порівняння:** rapidfuzz
- **Міграції:** Alembic
- **Frontend:** Vue 3, Vite 5, TypeScript
- **Frontend-тести:** Vitest, @vue/test-utils

---

## Ліцензія

MIT

