# Порівняння товарів за посиланнями

Веб-застосунок для парсингу товарів з декількох сайтів та їх порівняння.

## Можливості

✅ Вставити посилання на декілька сайтів  
✅ Автоматичний парсинг товарів  
✅ Порівняння товарів за назвою та артикулом  
✅ Групування схожих товарів  
✅ Вивід у таблиці з колонками: Артикул, Назва, Модель  
✅ Зручний інтерфейс  
✅ Доменно-орієнтована евристика збігу для хокейного інвентарю

*Поточна архітектура:* логіка парсингу винесена в плагіни (адаптери) для кожного магазину, які автоматично підхоплюються реєстром та вибираються за доменом URL. Референсним сайтом є `prohockey.com.ua`. Евристика збігу товарів реалізована в `pricewatch/core/normalize.py`.

---

## Документація

| Розділ | Файл |
|---|---|
| Архітектура | [docs/architecture/overview.md](docs/architecture/overview.md) |
| DB-first API (порівняння, gap) | [docs/api/db_first.md](docs/api/db_first.md) |
| Admin/Service API | [docs/api/admin.md](docs/api/admin.md) |
| Legacy/Debug API | [docs/api/internal_legacy.md](docs/api/internal_legacy.md) |
| Порівняння та евристика збігу | [docs/domain/comparison_and_matching.md](docs/domain/comparison_and_matching.md) |
| Gap-review workflow | [docs/domain/gap_review.md](docs/domain/gap_review.md) |
| Доменні інваріанти | [docs/domain/domain_invariants.md](docs/domain/domain_invariants.md) |
| Sync lifecycle та БД | [docs/operations/sync_lifecycle.md](docs/operations/sync_lifecycle.md) |
| Адаптерний контракт | [docs/integrations/adapter_contract.md](docs/integrations/adapter_contract.md) |
| Стратегія тестування | [docs/testing/testing_strategy.md](docs/testing/testing_strategy.md) |

---

## Встановлення

### 1. Встановіть Python 3.7+
https://www.python.org/downloads/

### 2. Відкрийте термінал у папці проєкту

```bash
cd Managment2--main
```

### 3. Створіть та активуйте віртуальне оточення

```bash
python -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows
```

### 4. Встановіть залежності

```bash
pip install -r requirements.txt
```

### Корисні поради

- Рекомендовано оновити `pip` перед встановленням:
  ```bash
  python -m pip install --upgrade pip
  ```
- Завжди використовуйте `python -m pip` для роботи з тим самим інтерпретатором.
- Активація в PowerShell може вимагати:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
  venv\Scripts\Activate.ps1
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
| `/` | Користувацька сторінка. Дані читаються лише з БД. |
| `/service` | Операційна панель (Категорії / Мапінги / Історія). |
| `/gap` | Розрив асортименту для контент-менеджерів. |

Докладніше: [docs/architecture/overview.md](docs/architecture/overview.md).

---

## API — короткий огляд

### DB-first (основний флоу)

| Метод | Шлях | Опис |
|---|---|---|
| `GET` | `/api/stores` | Список магазинів |
| `GET` | `/api/stores/<id>/categories` | Категорії магазину |
| `GET` | `/api/categories/<id>/products` | Товари категорії |
| `GET` | `/api/categories/<id>/mapped-target-categories` | Замаплені цільові категорії |
| `POST` | `/api/comparison` | Порівняння за маппінгами |
| `POST` | `/api/comparison/confirm-match` | Підтвердити мепінг товарів |
| `POST` | `/api/gap` | Gap-товари для review |
| `POST` | `/api/gap/status` | Зберегти статус gap-товару |

### Service / admin

| Метод | Шлях | Опис |
|---|---|---|
| `POST` | `/api/admin/stores/sync` | Синхронізація registry → БД |
| `POST` | `/api/stores/<id>/categories/sync` | Скрапити категорії |
| `POST` | `/api/categories/<id>/products/sync` | Скрапити товари |
| `GET` | `/api/category-mappings` | Список маппінгів |
| `POST` | `/api/category-mappings` | Створити маппінг |
| `PUT` | `/api/category-mappings/<id>` | Змінити метадані маппінгу |
| `DELETE` | `/api/category-mappings/<id>` | Видалити маппінг |
| `POST` | `/api/category-mappings/auto-link` | Авто-маппінг за назвою |
| `GET` | `/api/scrape-runs` | Історія запусків |
| `GET` | `/api/scrape-status` | Поточний статус (полінг) |

Повний JSON-контракт: [docs/api/db_first.md](docs/api/db_first.md), [docs/api/admin.md](docs/api/admin.md).

---

## База даних та міграції

- ORM: SQLAlchemy 2.x, SQLite за замовчуванням (`sqlite:///pricewatch.db`).
- Конфігурація через `DATABASE_URL`, `DB_DEBUG_SQL`, `DB_SKIP_CREATE_ALL`.

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

Конкретний файл:
```bash
PYTHONPATH=. pytest tests/test_normalize_hockey.py -q
```

Докладніше: [docs/testing/testing_strategy.md](docs/testing/testing_strategy.md).

---

## Структура проєкту

```
Managment2--main/
├── app.py                          # Flask сервер + init DB
├── parser.py                       # сумісний фасад
├── http_client.py                  # HTTP клієнт/обгортка
├── pricewatch/
│   ├── core/                       # ядро парсингу/нормалізації
│   ├── db/
│   │   ├── models.py               # SQLAlchemy моделі (+ GapItemStatus)
│   │   └── repositories/
│   │       ├── gap_repository.py   # gap статуси
│   │       └── ...
│   ├── services/
│   │   ├── comparison_service.py   # ComparisonService
│   │   ├── gap_service.py          # GapService
│   │   └── ...
│   └── shops/                      # адаптери магазинів
├── migrations/
│   └── versions/
│       ├── 095e10abb6f9_initial_schema.py
│       └── a1b2c3d4e5f6_add_gap_item_statuses.py
├── templates/
│   ├── index.html                  # /
│   ├── service.html                # /service
│   └── gap.html                    # /gap
├── tests/
│   ├── test_normalize_hockey.py    # 93 unit-тести евристики
│   ├── test_gap.py                 # 12 тестів /gap
│   └── ...
├── examples/db_usage.py
├── docs/                           # детальна документація
└── README.md
```

---

## Технології

- **Backend:** Flask, SQLAlchemy 2.x, SQLite / PostgreSQL
- **Парсинг:** requests, BeautifulSoup4, lxml
- **Порівняння:** difflib
- **Міграції:** Alembic
- **Frontend:** HTML5, CSS3, JavaScript

---

## Усунення неполадок

### `ModuleNotFoundError`
Переконайтесь, що активовано оточення і встановлено залежності:
```bash
pip install -r requirements.txt
```

### Порт 5000 зайнятий
Змініть порт у `app.py`: `app.run(debug=True, port=8000)`.

### Сайт не парситься
1. Перевірте правильність URL.
2. Перевірте з'єднання з інтернетом.
3. Деякі сайти блокують парсинг — спробуйте інший URL.

---

## Ліцензія

MIT

