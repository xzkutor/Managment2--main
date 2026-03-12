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
| `/` | Користувацька сторінка (дані з БД) |
| `/service` | Операційна панель (категорії / маппінги / історія) |
| `/gap` | Розрив асортименту для контент-менеджерів |

---

## API — короткий огляд

Три групи ендпоінтів:

- **DB-first** — `/api/stores`, `/api/categories`, `/api/comparison`, `/api/gap` — основний флоу читання та порівняння. Повний контракт: [docs/api/db_first.md](docs/api/db_first.md).
- **Service/Admin** — синхронізація, скрапінг, маппінги. Докладніше: [docs/api/admin.md](docs/api/admin.md).

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

## Тести

```bash
PYTHONPATH=. pytest -q
```

Докладніше: [docs/testing/testing_strategy.md](docs/testing/testing_strategy.md).

---

## Структура проєкту

```
Managment2--main/
├── app.py              # Flask сервер + init DB
├── pricewatch/         # ядро: core, db, net, services, shops
│   └── net/            # канонічний HTTP-клієнт (pricewatch.net.http_client)
├── migrations/         # Alembic міграції
├── templates/          # HTML-шаблони
├── tests/              # тести
├── docs/               # детальна документація
└── README.md
```

> **Примітка:** `http_client.py` у корені — тимчасовий compatibility shim. Новий код повинен імпортувати з `pricewatch.net.http_client`.

Повна карта: [docs/repository_map.md](docs/repository_map.md).

---

## Технології

- **Backend:** Flask, SQLAlchemy 2.x, SQLite / PostgreSQL
- **Парсинг:** requests, BeautifulSoup4, lxml
- **Порівняння:** rapidfuzz
- **Міграції:** Alembic
- **Frontend:** HTML5, CSS3, JavaScript

---

## Ліцензія

MIT

