# Порівняння товарів за посиланнями

Веб-застосунок для парсингу товарів з декількох сайтів та їх порівняння.

## Можливості

✅ Вставити посилання на декілька сайтів  
✅ Автоматичний парсинг товарів  
✅ Порівняння товарів за назвою та артикулом  
✅ Групування схожих товарів  
✅ Вивід у таблиці з колонками: Артикул, Назва, Модель  
✅ Зручний інтерфейс  
✅ Доменно-орієнтована евристика збігу для хокейного інвентарю (жорсткі відхилення за типом продукту, спортивним контекстом, воротарським признаком; штрафи/бонуси за кривизну, посадку ковзанів, гнучкість, ручність)

*Поточна архітектура:* логіка парсингу винесена в плагіни (адаптери) для кожного магазину, які автоматично підхоплюються реєстром та вибираються за доменом URL. Референсним сайтом є `prohockey.com.ua`, всі інші URL порівнюються з його каталогом. Евристика збігу товарів реалізована в `pricewatch/core/normalize.py` і підтримує 21 тип продукту, 3 спортивних контексти (хокей / інлайн / флорбол), воротарський сегмент, кривизну ключки, посадку ковзанів та ін.

## Встановлення

### 1. Встановіть Python 3.7+
https://www.python.org/downloads/

### 2. Відкрийте термінал у папці проєкту

```bash
cd C:\Users\user\Desktop\"Managment2--main
```

### 3. Створіть віртуальне оточення

```bash
python -m venv venv
```

### 4. Активуйте віртуальне оточення

**У Windows:**
```bash
venv\Scripts\activate
```

**У macOS/Linux:**
```bash
source venv/bin/activate
```

### 5. Встановіть залежності

```bash
pip install -r requirements.txt
```

### Корисні поради

- Рекомендовано оновити `pip` перед встановленням залежностей:
```powershell
python -m pip install --upgrade pip
```
- Завжди використовуйте `python -m pip` щоб впевнено працювати з тим самим інтерпретатором:
```powershell
python -m pip install -r requirements.txt
```
- Активація в PowerShell може вимагати дозволу виконання скриптів:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
venv\Scripts\Activate.ps1
```
- Скрипт парсеру також доступний окремо: щоб запустити CLI-скрейпер без веб-інтерфейсу:
```powershell
python parser.py
```
- CORS вже додано у `app.py` (через `flask-cors`), тому фронтенд має працювати при запуску `python app.py`.

## Запуск застосунку

```bash
python app.py
```

Доступно на http://localhost:5000. Головна сторінка тепер читає ТІЛЬКИ БД (жодного прямого скрапінгу) й дозволяє обрати reference/target магазини, категорії та переглянути товари. Для запуску синхронізацій, редагування мапінгів і перегляду історії використовуйте `/service`.

## Адмінський UI

- `/` — користувацька сторінка. Всі дані зчитуються з `stores/categories/products` таблиць. Якщо записи застарілі, користувач бачить підказку перейти на сервісну панель.
- `/service` — операційна панель з трьома вкладками: Категорії (синхронізація та запуск скрапу), Мапінги (CRUD для category_mappings) та Історія (таблиця scrape_runs з пагінацією та REST-полінгом `/api/scrape-status`).
- `/gap` — сторінка перегляду **асортиментного розриву** для контент-менеджерів. Показує товари цільового магазину, яких немає у reference-асортименті. Детальніше — у розділі **«Сторінка розриву асортименту (`/gap`)»** нижче.

---

## Сторінка розриву асортименту (`/gap`)

Сторінка `/gap` призначена для контент-менеджерів і дозволяє переглядати та опрацьовувати **gap-товари** — товари цільового магазину, які:
- не входять у підтверджені мепінги (`ProductMapping`)
- не з'являються у жодному списку кандидатів

### Сценарій використання

1. Оберіть **цільовий магазин** (не reference).
2. Оберіть **reference-категорію**.
3. Завантажуються замаплені цільові категорії — всі відмічені за замовчуванням.
4. Якщо маппінгів немає — завантаження заблоковане з підказкою перейти на `/service`.
5. Встановіть фільтри (пошук, «лише в наявності», статуси) та натисніть **«Показати розрив»**.
6. Результати згруповані за цільовою категорією із summary-картками.

### Статуси gap-товарів

| Статус | Зберігається в БД | Значення |
|---|---|---|
| `new` | ❌ (неявний) | Не опрацьовано |
| `in_progress` | ✅ | Контент-менеджер взяв у роботу |
| `done` | ✅ | Опрацьовано |

- **За замовчуванням** видимі: `new` + `in_progress`. Статус `done` прихований, але **завжди рахується у summary**.
- Кнопки дій: **«Взяти в роботу»** (`new` → `in_progress`), **«Позначити опрацьованим»** (`in_progress` → `done`).

### API для сторінки `/gap`

#### `POST /api/gap`

Повертає згруповані gap-товари для обраного контексту.

**Запит:**
```json
{
  "target_store_id": 2,
  "reference_category_id": 10,
  "target_category_ids": [21, 22],
  "search": "bauer",
  "only_available": true,
  "statuses": ["new", "in_progress"]
}
```

- `target_store_id` — **обов'язковий**.
- `reference_category_id` — **обов'язковий**.
- `target_category_ids` — **обов'язковий**, непорожній список. Кожен id мусить бути у маппінгах для `reference_category_id`, інакше `400`.
- `search` — фільтрація за підрядком у назві (регістро-незалежна).
- `only_available` — якщо `true`, показуються тільки товари з `is_available=true`.
- `statuses` — список видимих статусів. За замовчуванням `["new", "in_progress"]`. Статус `done` завжди рахується у `summary.done` незалежно від цього фільтру.

**Відповідь:**
```json
{
  "reference_category": {"id": 10, "name": "Ключки"},
  "target_store": {"id": 2, "name": "HockeyShop"},
  "selected_target_categories": [
    {"target_category_id": 21, "target_category_name": "Ключки Senior"}
  ],
  "summary": {"total": 37, "new": 21, "in_progress": 9, "done": 7},
  "groups": [
    {
      "target_category": {"id": 21, "name": "Ключки Senior"},
      "count": 12,
      "items": [
        {
          "target_product": {
            "id": 501, "name": "Bauer Vapor X5 Pro Grip Stick Senior",
            "price": 8999, "currency": "UAH",
            "product_url": "https://...", "is_available": true
          },
          "status": "new"
        }
      ]
    }
  ]
}
```

**Помилки (400):**
- `target_store_id` не вказано.
- `reference_category_id` не вказано або не знайдено.
- `target_category_ids` порожній або містить id, не замаплений до `reference_category_id`.

#### `POST /api/gap/status`

Зберігає статус опрацювання gap-товару.

**Запит:**
```json
{
  "reference_category_id": 10,
  "target_product_id": 501,
  "status": "in_progress"
}
```

Допустимі значення `status`: `"in_progress"`, `"done"`. Статус `"new"` **не приймається** (він неявний — відсутність рядка в БД).

**Відповідь:**
```json
{
  "success": true,
  "item": {
    "reference_category_id": 10,
    "target_product_id": 501,
    "status": "in_progress",
    "updated_at": "2026-03-08T10:00:00"
  }
}
```

### Таблиця БД: `gap_item_statuses`

| Колонка | Тип | Опис |
|---|---|---|
| `id` | INTEGER PK | Авто-інкремент |
| `reference_category_id` | INTEGER FK→categories | Reference-категорія |
| `target_product_id` | INTEGER FK→products | Target-товар |
| `status` | VARCHAR(50) | `in_progress` або `done` |
| `created_at` | DATETIME | Час створення |
| `updated_at` | DATETIME | Час останнього оновлення |

Унікальний обмеження: `(reference_category_id, target_product_id)`.  
Міграція: `migrations/versions/a1b2c3d4e5f6_add_gap_item_statuses.py`.



### Класифікація API-ендпоінтів

#### DB-first (основний флоу)

| Метод | Шлях | Опис |
|---|---|---|
| `GET` | `/api/stores` | Список магазинів з БД. **Тільки читання.** |
| `GET` | `/api/stores/<id>/categories` | Категорії магазину з БД. |
| `GET` | `/api/categories/<id>/products` | Товари категорії з БД. |
| `GET` | `/api/categories/<id>/mapped-target-categories` | Замаплені цільові категорії для обраної reference-категорії. Підтримує `?target_store_id=<id>` для фільтрації за магазином. |
| `POST` | `/api/comparison` | Порівняння за маппінгами (дані з БД). Детальний формат нижче. |
| `POST` | `/api/comparison/confirm-match` | Підтвердити мепінг товарів — зберегти `ProductMapping` у БД. |
| `POST` | `/api/gap` | Отримати згруповані gap-товари (target-only) для review. |
| `POST` | `/api/gap/status` | Зберегти статус опрацювання gap-товару (`in_progress` / `done`). |

#### Service / admin

| Метод | Шлях | Опис |
|---|---|---|
| `POST` | `/api/admin/stores/sync` | Синхронізує registry → БД. |
| `POST` | `/api/stores/<id>/categories/sync` | Скрапить категорії і зберігає в БД. |
| `POST` | `/api/categories/<id>/products/sync` | Скрапить товари категорії і зберігає в БД. |
| `GET` | `/api/category-mappings` | Список маппінгів категорій. |
| `POST` | `/api/category-mappings` | Створити маппінг. Пара категорій незмінна після створення. |
| `PUT` | `/api/category-mappings/<id>` | Змінити лише метадані (`match_type`, `confidence`). |
| `DELETE` | `/api/category-mappings/<id>` | Видалити маппінг. |
| `POST` | `/api/category-mappings/auto-link` | Авто-маппінг за точним `normalized_name`. |
| `GET` | `/api/scrape-runs` | Історія запусків. |
| `GET` | `/api/scrape-runs/<id>` | Деталі конкретного запуску. |
| `GET` | `/api/scrape-status` | Поточні/останні запуски (полінг для service page). |

#### Legacy / internal / debug

| Метод | Шлях | Опис |
|---|---|---|
| `GET` | `/api/reference-products` | Живий скрапінг reference-адаптера по категорії. |
| `POST` | `/api/check` | Живий скрапінг довільних URL. Debug. |
| `POST` | `/api/parse-example` | Розбір HTML-фрагменту таблиці. Debug. |

---

## Mapping-driven порівняння

Порівняння категорій побудоване навколо **`category_mappings`** — таблиці зв'язків між reference і target категоріями.

### Ключові правила

- Порівняння **дозволено лише для замаплених пар** категорій.  
  Якщо маппінгів немає — кнопка «Порівняти» заблокована, API повертає `400`.
- Маппінги підтримують **many-to-many**:  
  одна reference-категорія може мати кілька target-категорій (у різних магазинах).
- **Підтверджені мепінги товарів (`ProductMapping`)** зберігаються у БД. Кандидати — **runtime only**, не персистуються.
- Дані порівняння читаються **виключно з БД** — без живого скрапінгу.

### Сценарій використання

1. Синхронізуйте категорії на `/service` → вкладка «Категорії».
2. Створіть маппінги вручну або через «⚡ Авто-маппінг за назвою».
3. Відкрийте `/` → оберіть reference-магазин і (опційно) цільовий магазин.
4. Оберіть reference-категорію — замаплені цільові категорії з'являться автоматично (всі відмічені за замовчуванням).
5. Зніміть зайві галочки або залиште всі → натисніть «Порівняти категорії».
6. У результатах:
   - ✅ **Підтверджені збіги** — збережені `ProductMapping` + авто-high-confidence.
   - 🔎 **Групи кандидатів** — товари без підтвердженого мепінгу, але з кандидатами.
   - 📋 **Тільки в референсі** — без підходящих кандидатів.
   - 📦 **Тільки в цільовому** — не фігурують ні в підтверджених, ні в кандидатах.

---

### `GET /api/categories/<reference_category_id>/mapped-target-categories`

**Query параметри:**
- `target_store_id` (опційний) — фільтр за цільовим магазином.

**Відповідь:**
```json
{
  "reference_category": {"id": 1, "name": "Ковзани", "store_id": 1, "store_name": "RefShop", "is_reference": true},
  "target_store": {"id": 2, "name": "HockeyShop", "is_reference": false},
  "mapped_target_categories": [
    {
      "target_category_id": 11,
      "target_category_name": "Ключки Senior",
      "target_store_id": 2,
      "target_store_name": "HockeyShop",
      "match_type": "exact",
      "confidence": 1.0,
      "mapping_id": 5
    }
  ]
}
```

---

### `POST /api/comparison`

**Запит:**
```json
{
  "reference_category_id": 1,
  "target_category_ids": [5, 6],
  "target_store_id": 2
}
```

Поля:
- `reference_category_id` — **обов'язковий**.
- `target_category_ids` — рекомендований: список id замаплених target-категорій. **Кожен id мусить бути в маппінгах**, інакше `400`.
- `target_category_id` — legacy fallback (один id). Ігнорується, якщо передано `target_category_ids`.
- `target_store_id` — опційний фільтр при авто-підборі target-категорій (коли `target_category_ids` не передано).

**Відповідь:**
```json
{
  "reference_category": {"id": 1, "name": "Ковзани", "store_name": "RefShop", "is_reference": true},
  "target_store": {"id": 2, "name": "HockeyShop", "is_reference": false},
  "selected_target_categories": [
    {"target_category_id": 5, "target_category_name": "Ковзани", "match_type": "exact", "confidence": 1.0}
  ],
  "summary": {
    "confirmed_matches": 8,
    "candidate_groups": 2,
    "reference_only": 2,
    "target_only": 1
  },
  "confirmed_matches": [
    {
      "reference_product": {"id": 10, "name": "Bauer Vapor X5 SR", "price": 4500},
      "target_product": {"id": 20, "name": "Bauer Vapor X5 Senior", "price": 4800},
      "target_category": {"id": 5, "name": "Ковзани", "store_name": "HockeyShop"},
      "score_percent": 97,
      "score_details": {
        "fuzzy_base": 87.0, "token_bonus": 10.0,
        "shared_tokens": ["VAPOR", "X5"], "shared_series": ["VAPOR"],
        "domain_bonus": 16.0, "product_type": "SKATES",
        "sport_context": "ICE_HOCKEY", "total_score": 113.0
      },
      "match_source": "confirmed",
      "is_confirmed": true
    }
  ],
  "candidate_groups": [
    {
      "reference_product": {"id": 11, "name": "CCM Tacks AS-V SR"},
      "candidates": [
        {
          "target_product": {"id": 21, "name": "CCM Tacks AS-V Senior"},
          "target_category": {"id": 5, "name": "Ковзани"},
          "score_percent": 78,
          "score_details": {"fuzzy_base": 75.0, "token_bonus": 4.0},
          "match_type": "heuristic",
          "can_accept": true,
          "disabled_reason": null
        }
      ]
    }
  ],
  "reference_only": [
    {"reference_product": {"id": 12, "name": "Bauer Supreme M4 SR"}}
  ],
  "target_only": [
    {
      "target_product": {"id": 22, "name": "True Catalyst 9 Senior"},
      "target_category": {"id": 5, "name": "Ковзани"}
    }
  ]
}
```

**Поля `confirmed_matches`:**
- `is_confirmed: true` — збережений `ProductMapping` у БД.
- `is_confirmed: false` — авто-high-confidence (≥ 85%) від евристики, але ще не підтверджений.
- `match_source`: `"confirmed"` | `"heuristic_high_confidence"` | `"heuristic"`.

**Поля кандидата:**
- `score_percent` — відсоток від 0 до 100 для відображення в UI.
- `score_details` — детальна розбивка балів для tooltip.
- `can_accept: false` + `disabled_reason: "already_confirmed_elsewhere"` — target-товар вже використаний у підтвердженому мепінгу іншого reference-товару.

---

### `POST /api/comparison/confirm-match`

Підтвердити кандидата — зберегти в таблицю `product_mappings`.

**Запит:**
```json
{
  "reference_product_id": 10,
  "target_product_id": 20,
  "match_status": "confirmed",
  "confidence": 0.97
}
```

**Відповідь:** `{"product_mapping": {...}}`

Після підтвердження наступне порівняння покаже цей збіг у блоці `confirmed_matches` з `is_confirmed: true`.

---

### `POST /api/category-mappings/auto-link`

Автоматично створює маппінги між категоріями за точним збігом `normalized_name`.

**Запит:**
```json
{
  "reference_store_id": 1,
  "target_store_id": 2
}
```

**Відповідь:**
```json
{
  "created": [{"reference_category_id": 1, "target_category_id": 5, "match_type": "exact", "confidence": 1.0}],
  "skipped_existing": [],
  "summary": {"created": 3, "skipped_existing": 1, "skipped_no_norm": 0}
}
```

- Не дублює існуючі маппінги.
- Використовує `match_type = "exact"`, `confidence = 1.0`.
- Нечіткий (fuzzy) авто-маппінг **не входить** у поточний скоуп.

---

### Евристика збігу товарів

Евристика (`heuristic_match` у `pricewatch/core/normalize.py`) побудована на доменних словниках, детермінованих екстракторах і багаторівневій системі жорстких відхилень / штрафів / бонусів.

#### Порядок оцінювання пари товарів (`_pair_score`)

| # | Крок | Дія |
|---|---|---|
| 1 | **Hard brand block** | Обидва бренди відомі та різні → `-1e9` (збіг неможливий) |
| 2 | **Sport context conflict** | ICE_HOCKEY ↔ INLINE_HOCKEY ↔ FLOORBALL → `-1e9` |
| 3 | **Goalie conflict** | Один товар воротарський, інший — ні → `-1e9` |
| 4 | **Product type conflict** | Несумісні типи (STICK ↔ SKATES, GLOVES ↔ HELMET тощо) → `-1e9` |
| 5 | **Accessory conflict** | Аксесуар проти основного спорядження → `-1e9` |
| 6 | **Fuzzy base** | `fuzz.token_set_ratio` (0–100) |
| 7 | **Token bonus** | Числові токени (X5, FT6, P28…) `+10`, алфавітні серії `+4` |
| 8 | **Штрафи** | flex `-40`, hand `-60`, level `-25`, curve `-20`, skate fit `-30`, size `-15` |
| 9 | **Бонуси** | product_type `+5`, sport_context `+3`, goalie `+4`, series `+8`, curve `+6`, hand `+5`, flex `+4`, skate_fit `+6` |
| 10 | **Price modifier** | ±3/5 балів (ніколи не блокує збіг) |

#### Доменні словники

**Типи продуктів (`PRODUCT_TYPE_KEYWORDS`)** — 21 тип:

| Гравець | Воротар |
|---|---|
| STICK, SKATES, GLOVES | GOALIE_STICK, GOALIE_SKATES, GOALIE_GLOVE, GOALIE_BLOCKER |
| SHIN_GUARDS, ELBOW_PADS, SHOULDER_PADS | GOALIE_PADS, GOALIE_CHEST, GOALIE_PANTS, GOALIE_HELMET |
| HELMET, PANTS, NECK_GUARD, JOCK_JILL, WRIST_GUARD | — |
| BAG, ACCESSORY | — |

- Класифікація `ACCESSORY` / `BAG` застосовується **лише** якщо присутній контекстний аксесуарний токен (laces/tape/bag/баул тощо) **і** відсутній токен основного спорядження (stick/skat/glove тощо).
- Воротарські модифікатори (goalie / воротар / вратар) автоматично перетворюють STICK→GOALIE_STICK, SKATES→GOALIE_SKATES і т.д.

**Серії та моделі (`MODEL_SERIES` + `_COMPOUND_SERIES`):**

| Одиночні | Складені (нормалізуються в токен) |
|---|---|
| VAPOR, SUPREME, NEXUS, HYPERLITE, MACH, SHADOW | SUPERTACKS (Super Tacks) |
| JETSPEED, TACKS, RIBCOR, CATALYST, HZRDUS | FT6PRO, FT4PRO, M5PRO, M50PRO |
| MISSION, TOUR, PRODIGY, ELITE, VIZION, GSX | X5PRO, X4PRO, 3XPRO, 3SPRO |
| GRIPTAC, POWERFLY | ASV (AS-V), FLYTI (Fly-Ti) |

**Кривизна (`CURVE_TOKENS`):** P28, P29, P88, P90TM, P92, P30, P31, P40, P46.

**Посадка ковзанів (`SKATE_FIT_TOKENS`):** FIT1, FIT2, FIT3, D, EE (wide→EE, regular→D).

**Спортивний контекст:** ICE_HOCKEY / INLINE_HOCKEY / FLOORBALL.

#### Екстрактори

| Функція | Повертає |
|---|---|
| `_extract_product_type(title)` | Канонічний тип або `None` |
| `_extract_sport_context(title)` | `ICE_HOCKEY` / `INLINE_HOCKEY` / `FLOORBALL` / `None` |
| `_extract_goalie_flag(title)` | `bool` |
| `_extract_curve(title)` | `P28`, `P92`, `P90TM`… або `None` |
| `_extract_skate_fit(title)` | `FIT1`/`FIT2`/`FIT3`/`D`/`EE` або `None` |
| `_extract_numeric_size_tokens(title)` | `tuple` числових розмірів |
| `_extract_accessory_flag(title)` | `bool` |

#### Поля `_prep` (на кожен товар)

Крім стандартних полів (`_title`, `_norm`, `_brand`, `_level`, `_tokens`, `_flex`, `_hand`, `_price_uah`, `_url`), тепер додаються:
`_product_type`, `_sport_context`, `_goalie`, `_curve`, `_skate_fit`, `_size_tokens`, `_accessory_flag`.

#### `score_details` — повна структура

```json
{
  "fuzzy_base": 87.0,
  "token_bonus": 20.0,
  "shared_tokens": ["FT6PRO", "JETSPEED", "P28"],
  "shared_series": ["JETSPEED"],
  "domain_bonus": 26.0,
  "product_type": "STICK",
  "sport_context": "ICE_HOCKEY",
  "brand_conflict": "BAUER vs CCM",
  "product_type_conflict": "STICK vs SKATES",
  "sport_context_conflict": "ICE_HOCKEY vs INLINE_HOCKEY",
  "goalie_conflict": "goalie=True vs goalie=False",
  "accessory_conflict": "accessory=True vs accessory=False",
  "level_conflict": "SR vs JR",
  "flex_conflict": "77 vs 102",
  "hand_conflict": "L vs R",
  "curve_conflict": "P28 vs P92",
  "skate_fit_conflict": "FIT1 vs FIT3",
  "size_conflict": "['9.5'] vs ['10.0']",
  "price_mod": 3.0,
  "price_ratio": 0.94,
  "total_score": 113.0
}
```

#### Пороги

| Константа | Значення | Роль |
|---|---|---|
| `MIN_CANDIDATE_SCORE` | 65 | Мінімум для потрапляння у кандидати |
| `HIGH_CONFIDENCE_SCORE` | 85 | Авто-підтвердження у `confirmed_matches` |
| `MIN_GAP` | 6 | Мінімальний розрив між 1-м і 2-м кандидатом |


**Помилки (400):**
- `reference_category_id` не знайдено або не є reference store
- `target_category_id` вказано, але пара не існує в `category_mappings`
- `target_category_id` не вказано і маппінгів немає ("Для цієї категорії ще не створено меппінг")

### `GET /api/categories/<id>/mapped-target-categories`

Повертає список target-категорій, замаплених до обраної reference-категорії:

```json
{
  "reference_category_id": 1,
  "mapped_target_categories": [
    {
      "target_category_id": 5,
      "name": "Ковзани",
      "normalized_name": "kovzany",
      "store_id": 2,
      "store_name": "TargetShop",
      "match_type": "exact",
      "confidence": 1.0,
      "mapping_id": 3
    }
  ]
}
```

Використовується головною сторінкою для фільтрації target-категорій після вибору reference-категорії.

### `POST /api/category-mappings/auto-link`

Автоматично створює `category_mappings` на основі **точного збігу `normalized_name`** між reference і target категоріями:

**Запит:**
```json
{"reference_store_id": 1, "target_store_id": 2}
```

**Відповідь:**
```json
{
  "created": [
    {
      "reference_category_id": 1, "reference_category_name": "Ковзани",
      "target_category_id": 5, "target_category_name": "Ковзани",
      "match_type": "exact", "confidence": 1.0
    }
  ],
  "skipped_existing": [
    {"reference_category_id": 2, "target_category_id": 7}
  ],
  "summary": {"created": 1, "skipped_existing": 1, "skipped_no_norm": 0}
}
```

- **Не створює дублікатів** — якщо маппінг вже існує, пара потрапляє в `skipped_existing`.
- `skipped_no_norm` — кількість reference-категорій без `normalized_name`.
- Кнопка **«⚡ Авто-маппінг за назвою»** на `/service` → «Мапінги» виконує цей запит.

### Сортування матчів у відповіді `/api/comparison`

| `match_source` | Значення |
|---|---|
| `stored` | Збережений `ProductMapping` (підтверджено вручну або через confirm-match). |
| `heuristic` | Підібрано евристичним алгоритмом на основі нормалізованої назви. |

Stored matches мають пріоритет — продукти, покриті `ProductMapping`, не потрапляють до heuristic-matching.

## База даних та міграції

- ORM: SQLAlchemy 2.x, SQLite за замовчуванням (`sqlite:///pricewatch.db`), легка міграція на PostgreSQL через `DATABASE_URL`.
- Ініціалізація: при старті створюються таблиці, крім випадків `FLASK_ENV=production` або `DB_SKIP_CREATE_ALL=1`.
- Налаштування через ENV/Flask config:
  - `DATABASE_URL` — рядок підключення (наприклад, `postgresql+psycopg2://user:pass@host/db` або in-memory для тестів `sqlite+pysqlite:///:memory:`).
  - `DB_DEBUG_SQL` — `1/true` вмикає SQL echo.
  - `DB_SKIP_CREATE_ALL` — пропускає автосоздання таблиць.
  - `FLASK_ENV=production` — також пропускає автосоздання таблиць.

### Alembic

```bash
export DATABASE_URL=sqlite:///pricewatch.db   # або свій URL
PYTHONPATH=. alembic upgrade head
```

Щоб створити нову міграцію після змін у `pricewatch/db/models.py`:

```bash
PYTHONPATH=. alembic revision --autogenerate -m "short description"
```

Далі застосуйте `PYTHONPATH=. alembic upgrade head`.

### Приклад сценарію

`examples/db_usage.py` показує: створення магазинів, запуск scrape_run, upsert категорій/товарів, запис історії цін і створення маппінгів. Запуск:

```bash
python examples/db_usage.py
```

## Тести

Запуск всіх тестів з кореня проєкту (рекомендується):

```bash
PYTHONPATH=. pytest -q
```

Показати детальний звіт по тестах:

```bash
PYTHONPATH=. pytest
```

Запустити конкретний файл або набір тестів:

```bash
PYTHONPATH=. pytest pricewatch/tests/test_hockeyworld_pagination.py -q
# або
PYTHONPATH=. pytest tests/test_check.py -q
```

Запуск тестів у певних папках:

```bash
PYTHONPATH=. pytest pricewatch/tests tests
```

Зупинитись при першій помилці:

```bash
PYTHONPATH=. pytest -x
```

Паралельний запуск (потрібен pytest-xdist):

```bash
pip install pytest-xdist
PYTHONPATH=. pytest -n auto
```

Очищення кешу тестів (папки з кешем можуть з'являтись у `tests/` або `pricewatch/tests`):

```bash
rm -rf tests/.cache
rm -rf pricewatch/tests/.cache
```

Поради:

- Важливо запускати тести з кореня проєкту і вказувати `PYTHONPATH=.` — це забезпечує коректний імпорт локального пакету `pricewatch` і модулів з `tests`.
- Перед запуском тестів активуйте віртуальне оточення та переконайтесь, що залежності встановлені:

```bash
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

- Якщо тестові скрипти імпортують локальні утиліти (наприклад `test_utils`), переконайтесь, що ви запускаєте pytest з кореня проекту або додайте `sys.path` в тестових скриптах для сумісності.

## Як користуватися

1. **Запустіть застосунок** і відкрийте http://localhost:5000 у браузері.
2. **Головна сторінка (`/`)** — вибір reference-магазину, категорії та target-магазину.  
   Всі дані (магазини, категорії, товари) читаються **виключно з БД**. Жодного живого скрапінгу на головній сторінці не відбувається.
3. **Якщо БД порожня або застаріла**, скористайтеся сервісною панеллю:
   - Перейдіть на `/service`.
   - Вкладка **«Категорії»** — оберіть магазин → натисніть «Sync categories» для оновлення категорій з сайту, потім «Sync products» для оновлення товарів.
   - Вкладка **«Мапінги»** — CRUD для `category_mappings` (зв'язок ref-категорії ↔ target-категорії).
   - Вкладка **«Історія»** — таблиця `scrape_runs` з автооновленням статусу поточних запусків.
4. **Порівняння товарів** — після наповнення БД, на головній сторінці оберіть reference-категорію та target-категорію. Результат будується з даних у БД через `POST /api/comparison`.

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
│   │       ├── gap_repository.py   # get/upsert/bulk gap statuses
│   │       └── ...
│   ├── services/
│   │   ├── comparison_service.py   # ComparisonService (target_only логіка)
│   │   ├── gap_service.py          # GapService (build_gap_view, set_gap_item_status)
│   │   └── ...
│   └── shops/                      # адаптери магазинів
├── migrations/
│   └── versions/
│       ├── 095e10abb6f9_initial_schema.py
│       └── a1b2c3d4e5f6_add_gap_item_statuses.py
├── templates/
│   ├── index.html                  # / — порівняння
│   ├── service.html                # /service — операційна панель
│   └── gap.html                    # /gap — розрив асортименту
├── tests/
│   ├── test_normalize_hockey.py    # 93 unit-тести для evristики normalize.py (без DB)
│   ├── test_gap.py                 # 12 тестів для /gap
│   └── ...
├── examples/db_usage.py            # приклад роботи з БД
└── README.md
```

## Технології

- **Backend:** Flask, BeautifulSoup4 (Python)
- **Frontend:** HTML5, CSS3, JavaScript
- **Парсинг:** requests, lxml, beautifulsoup4
- **Порівняння:** difflib, python-levenshtein


## Усунення неполадок

### Помилка "ModuleNotFoundError"
Переконайтесь, що активовано віртуальне оточення і встановлено залежності:
```bash
pip install -r requirements.txt
```

### Порт 5000 зайнятий
Якщо порт зайнятий, змініть порт у `app.py`:

In `app.py` change the run call to use a different port, for example: app.run(debug=True, port=8000) (change 5000 to 8000).

### Сайт не парситься
Деякі сайти можуть блокувати парсинг. У такому випадку:
1. Перевірте, чи URL правильний
2. Перевірте підключення до інтернету
3. Спробуйте інший URL

## Примітки щодо парсингу

- Для більшості магазинів використовується загальний механізм із селекторами.
- Для специфічних сайтів доступні власні адаптери.
- Реєстр адаптерів створюється один раз під час запуску застосунку і повторно використовується.
- `parser.py` збережено як фасад для сумісності імпортів.

## Ліцензія

MIT

## Контакт

Якщо у вас є питання — відкрийте issue.

## Product DTO контракт (важно)

При синхронізації товарів сервис предпочитает явні значення з DTO по наступному правилу:

- `price` (числове значення) — переважне поле; якщо присутнє і валідне, використовується напряму.
- `price_raw` — використовується як запасний варіант, коли `price` не задане; розпізнавання витягує числову частину і валюту.
- `currency` — якщо вказана явно в DTO, має пріоритет над розпізнаною з `price_raw`.
- `source_url` — надається перевага для атрибута джерела; legacy-поля (`source_site`, `url`) використовуються лише як fallback.

Сервис підтримує і словникові об'єкти, і об'єктні DTO (SimpleNamespace-совместимі).


## Правила валидації маппінгів

Backend на етапі створення маппінга (`POST /api/category-mappings`) виконує доменні перевірки:

- `reference_category_id` повинен належати категорії в reference store (store.is_reference == True).
- `target_category_id` не повинен належати reference store.
- reference і target категорії не повинні належати одному і тому ж магазині.

При редагуванні маппінга (`PUT /api/category-mappings/<id>`) пара категорій незмінна — дозволено змінювати лише метадані (наприклад `match_type`, `confidence`).
