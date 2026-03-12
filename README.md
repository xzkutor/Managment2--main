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
| Legacy/Debug API | [docs/api/internal_legacy.md](docs/api/internal_legacy.md) |
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
- **Legacy/Debug** — внутрішні та відладочні ендпоінти. Докладніше: [docs/api/internal_legacy.md](docs/api/internal_legacy.md).

---

## База даних та міграції

ORM: SQLAlchemy 2.x, SQLite за замовчуванням (`sqlite:///pricewatch.db`).

```bash
export DATABASE_URL=sqlite:///pricewatch.db
PYTHONPATH=. alembic upgrade head
```

Докладніше: [docs/operations/sync_lifecycle.md](docs/operations/sync_lifecycle.md).

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
├── pricewatch/         # ядро: core, db, services, shops
├── migrations/         # Alembic міграції
├── templates/          # HTML-шаблони
├── tests/              # тести
├── docs/               # детальна документація
└── README.md
```

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

