Отлично! Теперь, имея полный код, я вижу реальную архитектуру проекта. Это не просто «проверка отключений», а **два полноценных парсера-монитора** для сайта `skk65.ru` (вероятно, «Сахалинская Коммунальная Компания»). Обновляю README с учетом деталей кода.

---

```markdown
# switchoff

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MongoDB](https://img.shields.io/badge/MongoDB-✓-green.svg)](https://www.mongodb.com/)
[![Playwright](https://img.shields.io/badge/Playwright-✓-orange.svg)](https://playwright.dev/)

**Автоматизированный мониторинг отключений ЖКХ** (электричество, отопление, горячая вода) с сайта skk65.ru с сохранением в MongoDB, скриншотами и генерацией отчетов.

---

## 📦 Компоненты системы

Проект содержит **два независимых скрипта** для разных подходов к мониторингу:

| Файл | Назначение | Технологии |
|------|------------|-------------|
| `comm_switchoff.py` | **Тяжеловесный монитор** — полный парсинг с детальными страницами и скриншотами | `requests` + `BeautifulSoup` + `Playwright` + `MongoDB` + `GridFS` |
| `utility_monitor.py` | **Легковесный асинхронный монитор** — быстрый парсинг дат и адресов из HTML | `aiohttp` + `asyncio` + `motor` + `MongoDB` |

---

## 🎯 Основные возможности

### ✅ `comm_switchoff.py` (полный мониторинг)

- Парсинг разделов: **отопление** (`/otoplenie`) и **горячая вода** (`/goryachaya-voda`)
- Обход по **ссылкам на детальные страницы** новостей
- Извлечение заголовка, описания и даты события
- **Создание скриншотов** страниц (через Playwright Chromium)
- Сохранение скриншотов в **GridFS** (MongoDB) и локально в папку `screenshots/YYYY-MM-DD_HH-MM/`
- Сохранение всех данных в MongoDB (коллекция `outages`) с **upsert** по `detail_url`
- Генерация единого **Markdown‑отчета** (`skk_combined_report_YYYY-MM-DD.md`)

### ✅ `utility_monitor.py` (быстрый асинхронный монитор)

- Асинхронная загрузка страницы `/otkljucheniya/otoplenie`
- **Регулярные выражения** для поиска дат (типа `30 марта 2026`) и адресов
- Сохранение уникальных отключений в MongoDB с **уникальным ключом** (`outage_key`)
- Генерация **краткого Markdown‑отчета** в папку `~/utility_monitor/data/outages_YYYYMMDD_HHMMSS.md`
- Вывод в консоль последних 5 дат с адресами

---

## 🧰 Требования

Установите зависимости:

```bash
pip install requests beautifulsoup4 pymongo playwright aiohttp motor
playwright install chromium
```

Или создайте `requirements.txt`:

```txt
requests>=2.31.0
beautifulsoup4>=4.12.0
pymongo>=4.5.0
playwright>=1.40.0
aiohttp>=3.9.0
motor>=3.3.0
```

---

## ⚙️ Настройка

### Для `comm_switchoff.py`

Отредактируйте переменные в начале файла:

```python
SAVE_TO_MONGO = True                # сохранять в MongoDB
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "skk_monitoring"
COLLECTION_NAME = "outages"
FOLLOW_LINKS = True                 # переходить по ссылкам детальной страницы
TAKE_SCREENSHOTS = True             # делать скриншоты
SCREENSHOT_WIDTH = 1280
SCREENSHOT_HEIGHT = 900

SOURCES = [                         # список разделов для парсинга
    {"url": "https://skk65.ru/otkljucheniya/otoplenie", "category": "otoplenie"},
    {"url": "https://skk65.ru/goryachaya-voda/", "category": "goryachaya_voda"},
]
```

### Для `utility_monitor.py`

Отредактируйте:

```python
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "utility_monitor"
COLLECTION_NAME = "outages"
DATA_DIR = os.path.expanduser("~/utility_monitor/data")
BASE_URL = "https://skk65.ru/otkljucheniya/otoplenie"
```

---

## 🚀 Запуск

### Простой запуск (вручную)

```bash
# Полный мониторинг со скриншотами
python comm_switchoff.py

# Быстрый асинхронный мониторинг
python utility_monitor.py
```

### Автоматический запуск (Windows)

Файл `run_PythonAutoRun_comm_switchoff.bat` (содержимое предположительное):

```batch
@echo off
cd /d "C:\path\to\switchoff"
python comm_switchoff.py
```

Добавьте этот .bat в **Планировщик задач Windows** для ежедневного/ежечасного запуска.

---

## 📁 Структура выходных данных

```
switchoff/
├── skk_combined_report_YYYY-MM-DD.md          # отчет comm_switchoff.py
├── screenshots/
│   └── YYYY-MM-DD_HH-MM/
│       └── адрес_страницы.png                  # скриншоты
├── ~/utility_monitor/data/
│   └── outages_YYYYMMDD_HHMMSS.md             # отчет utility_monitor.py
└── MongoDB (локально или удаленно)
    ├── skk_monitoring.outages                  # коллекция comm_switchoff
    └── utility_monitor.outages                 # коллекция utility_monitor
```

### Пример данных в MongoDB (comm_switchoff)

```json
{
  "category": "otoplenie",
  "title": "Отключение отопления 15.05.2026 на ул. Ленина",
  "description": "В связи с ремонтными работами...",
  "event_date": ISODate("2026-05-15"),
  "parsed_at": ISODate("2026-05-07 10:00:00"),
  "detail_url": "https://skk65.ru/...",
  "screenshot_gridfs_id": "65f3b2a1..."
}
```

---

## 🔄 Сравнение подходов

| Характеристика | `comm_switchoff.py` | `utility_monitor.py` |
|----------------|----------------------|------------------------|
| **Скорость** | Медленнее (из-за скриншотов) | Очень быстрый (асинхронный) |
| **Детализация** | Полное описание + заголовок | Только даты и адреса |
| **Скриншоты** | ✅ Да (Playwright) | ❌ Нет |
| **Обход ссылок** | ✅ Да | ❌ Нет (только главная страница) |
| **Хранение** | MongoDB + GridFS | MongoDB |
| **Использование** | Для архивации и юрид. значимости | Для быстрого оповещения |

---

## 🐛 Обработка ошибок

- `comm_switchoff.py` не падает, если нет MongoDB — продолжает работать с локальными файлами
- При ошибке Playwright скриншоты отключаются, но парсинг продолжается
- `utility_monitor.py` использует асинхронный тайм-аут 30 секунд

---

## 📝 Формат отчета (Markdown)

Пример вывода `comm_switchoff.py`:

```markdown
# Сводная информация об отключениях СКК
Дата формирования: 07.05.2026 14:30

## [TOOL] Раздел: otoplenie

### Отключение отопления 15.05.2026
**Дата:** 15.05.2026
**Описание:** ул. Советская 10-20, пер. Почтовый 5
**Ссылка:** https://skk65.ru/... 
**Скриншот:** screenshots/2026-05-07_14-30/otkljuchenie_otoplenija_15_05_2026.png
```


## 📬 Контакты

Автор: [@BlackJackBander](https://github.com/BlackJackBander)
