# Порівняння товарів за посиланнями

Веб-застосунок для парсингу товарів з декількох сайтів та їх порівняння.

## Можливості

✅ Вставити посилання на декілька сайтів  
✅ Автоматичний парсинг товарів  
✅ Порівняння товарів за назвою та артикулом  
✅ Групування схожих товарів  
✅ Вивід у таблиці з колонками: Артикул, Назва, Модель  
✅ Зручний інтерфейс  

*Поточна архітектура:* логіка парсингу винесена в плагіни (адаптери) для кожного магазину, які автоматично підхоплюються реєстром та вибираються за доменом URL. Референсним сайтом є `prohockey.com.ua`, всі інші URL порівнюються з його каталогом.

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

Застосунок буде доступний за адресою http://localhost:5000

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

1. **Відкрийте браузер** і перейдіть на http://localhost:5000
2. **Виберіть категорію** з випадаючого списку (sticks-sr, skates-sr і т.п.).
   - Парсер намагається знайти відповідну сторінку цієї категорії як на prohockey.com.ua,
     так і на перевірюваних зовнішніх сайтах. Якщо посилання не містить
     категорії, скрипт обітеться до головної сторінки і спробує виявити потрібний
     розділ за ключовим словом.
   - Вказаний фільтр також використовується для відсіювання товарів: із результатів
     будуть утримані тільки ті позиції, де назва або посилання містять ключову
     фразу. Якщо не вказано, всі знайдені позиції перевіряться.
3. **Введіть посилання на інші магазини** у полі вводу (можна кілька URL).
4. Якщо потрібно, натисніть **"Додати ще посилання"**.
5. **Натисніть кнопку "Перевірити відсутні"**.
6. **Почекайте**, поки скрипт виконає запити; поруч з формою зʼявиться статистика та
   таблиця результатів. Таблиця містить товари, яких **немає на prohockey.com.ua**,
   з колонками ціна/валюта, джерело, посилання та статус.

## Структура проєкту

### API

* `GET /api/categories` — повертає масив slug-ів категорій із референсного сайту.  
* `POST /api/check` — перевіряє відсутні товари на `prohockey.com.ua` для наданих URL.  
* `POST /api/scrape` — повертає `501` (залишено як заглушку).  

### Плагінна архітектура

- `pricewatch/core` — ядро: пагінація, витяг даних, нормалізація, порівняння.  
- `pricewatch/shops/<shop>/adapter.py` — адаптер конкретного магазину.  
- `pricewatch/core/plugin_loader.py` — автодискавері адаптерів.  
- `pricewatch/core/registry.py` — реєстр плагінів, вибір адаптера за URL.  
- `pricewatch/core/generic_adapter.py` — fallback-парсер для невідомих доменів.  

TODO: замінити CSS-селектори в адаптерах на YAML-шаблони (`pricewatch/shops/<shop>/templates/*.yaml`)

```
Managment2--main/
│
├── app.py                          # Основний Flask сервер
├── parser.py                       # Сумісний фасад (реекспорт API)
├── http_client.py                  # HTTP клієнт/обгортка
├── pricewatch/
│   ├── core/
│   │   ├── models.py               # ProductItem, ParsedPrice
│   │   ├── normalize.py            # Нормалізація та порівняння
│   │   ├── extract.py              # Витяг з HTML/JSON
│   │   ├── pagination.py           # Пагінація
│   │   ├── plugin_base.py          # BaseShopAdapter
│   │   ├── plugin_loader.py        # discover_adapters()
│   │   ├── registry.py             # ShopRegistry
│   │   ├── reference_service.py    # Побудова каталогу референса
│   │   └── generic_adapter.py      # Fallback-адаптер
│   └── shops/
│       ├── prohockey/adapter.py    # Референсний адаптер
│       ├── hockeyshans/adapter.py
│       ├── hockeyshop/adapter.py
│       └── hockeyworld/adapter.py
├── templates/
│   └── index.html                  # Фронтенд
└── README.md
```

## Технології

- **Backend:** Flask, BeautifulSoup4 (Python)
- **Frontend:** HTML5, CSS3, JavaScript
- **Парсинг:** requests, lxml, beautifulsoup4
- **Порівняння:** difflib, python-levenshtein

## Приклади посилань для парсингу

- https://example.com/shop
- shop.example.com/products
- https://goods.example.com/catalog
- example.com/items

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
