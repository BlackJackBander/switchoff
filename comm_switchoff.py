import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pymongo import MongoClient
from gridfs import GridFS
import time
import re
import os

# --- НАСТРОЙКИ ---
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SAVE_TO_MONGO = True 
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "skk_monitoring"
COLLECTION_NAME = "outages"
FOLLOW_LINKS = True
TAKE_SCREENSHOTS = True
SCREENSHOT_WIDTH = 1280
SCREENSHOT_HEIGHT = 900

# Список разделов для парсинга
SOURCES = [
    {"url": "https://skk65.ru/otkljucheniya/otoplenie", "category": "otoplenie"},
    {"url": "https://skk65.ru/goryachaya-voda/", "category": "goryachaya_voda"}
]
# -----------------

browser = None

def init_browser():
    global browser
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        return pw, browser
    except Exception as e:
        print(f"      [WARN] Не удалось инициализировать браузер: {e}")
        return None, None

def close_browser(pw):
    global browser
    if browser:
        browser.close()
    if pw:
        pw.stop()

def take_screenshot(url, folder_path, screenshot_id, width=1280, height=900):
    global browser
    if browser is None:
        return None
    
    try:
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(0.5)
        
        safe_name = re.sub(r'[^\w\-]', '_', screenshot_id[:50])
        filename = f"{safe_name}.png"
        filepath = os.path.join(folder_path, filename)
        
        page.screenshot(path=filepath, full_page=False)
        page.close()
        
        return filepath
    except Exception as e:
        print(f"      [WARN] Ошибка создания скриншота: {e}")
        return None

def parse_detail_page(url, headers):
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        entry_title = soup.find('h1', class_='entry-title')
        entry_content = soup.find('div', class_='entry-content')
        
        title = entry_title.get_text(strip=True) if entry_title else ""
        
        if entry_content:
            for br in entry_content.find_all('br'):
                br.replace_with('\n')
            content = entry_content.get_text(separator=' ', strip=True)
        else:
            content = ""
        
        return title, content
    except Exception as e:
        print(f"      [WARN] Ошибка загрузки детальной страницы: {e}")
        return "", ""

def parse_date_from_title(title):
    pattern = r'(\d{2}\.\d{2}\.\d{4})'
    match = re.search(pattern, title)
    if match:
        try:
            return datetime.strptime(match.group(1), '%d.%m.%Y')
        except:
            pass
    return datetime.now()

def slugify(text):
    text = re.sub(r'[^\w\s\-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text[:60]

def parse_skk_outages():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    db_collection = None
    fs = None
    save_to_mongo = SAVE_TO_MONGO
    
    if save_to_mongo:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            client.server_info() 
            db = client[DB_NAME]
            db_collection = db[COLLECTION_NAME]
            fs = GridFS(db)
            print("[MongoDB] Подключено.")
        except Exception as e:
            print(f"[ERROR] Ошибка подключения к MongoDB: {e}")
            save_to_mongo = False

    run_datetime = datetime.now()
    run_folder_name = run_datetime.strftime("%Y-%m-%d_%H-%M")
    screenshots_base_path = os.path.join("screenshots", run_folder_name)
    os.makedirs(screenshots_base_path, exist_ok=True)
    print(f"[FOLDER] Папка для скриншотов: {screenshots_base_path}")

    pw = None
    take_screenshots = TAKE_SCREENSHOTS
    if take_screenshots:
        pw, browser = init_browser()
        if browser is None:
            print("[WARN] Скриншоты отключены из-за ошибки браузера")
            take_screenshots = False

    current_date_str = run_datetime.strftime("%Y-%m-%d")
    filename = f"skk_combined_report_{current_date_str}.md"
    all_outages = []

    print(f"[FILE] Файл отчета: {filename}")

    with open(filename, 'w', encoding='utf-8') as md_file:
        md_file.write(f"# Сводная информация об отключениях СКК\n")
        md_file.write(f"Дата формирования: {run_datetime.strftime('%d.%m.%Y %H:%M')}\n\n")

        for source in SOURCES:
            url = source["url"]
            category = source["category"]

            print(f"\n[PARSE] Обработка раздела: {category}")
            print(f"   URL: {url}")
            md_file.write(f"## [TOOL] Раздел: {category}\n\n")
            
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                containers = soup.find_all('div', class_='pt-cv-ifield')
                
                if not containers:
                    print(f"   [EMPTY] Событий в разделе '{category}' не обнаружено.")
                    md_file.write("Актуальных событий не найдено.\n\n")
                    continue

                print(f"   [FIND] Найдено контейнеров: {len(containers)}")

                for idx, container in enumerate(containers, 1):
                    title_elem = container.find('h4', class_='pt-cv-title')
                    link_tag = title_elem.find('a') if title_elem else None
                    
                    if not link_tag:
                        continue
                    
                    detail_url = link_tag.get('href', "")
                    card_title = link_tag.get_text(strip=True)
                    
                    detail_title = card_title
                    description = ""
                    screenshot_path = None
                    screenshot_gridfs_id = None
                    event_date_obj = parse_date_from_title(card_title)
                    
                    if FOLLOW_LINKS and detail_url:
                        print(f"   [LOAD] [{idx}/{len(containers)}] Загрузка: {card_title[:40]}...")
                        time.sleep(0.3)
                        detail_title, description = parse_detail_page(detail_url, headers)
                        if not detail_title:
                            detail_title = card_title
                        if not description:
                            desc_elem = container.find('div', class_='pt-cv-content')
                            if desc_elem:
                                for br in desc_elem.find_all('br'):
                                    br.replace_with(' ')
                                description = desc_elem.get_text(separator=' ', strip=True)
                    else:
                        desc_elem = container.find('div', class_='pt-cv-content')
                        if desc_elem:
                            for br in desc_elem.find_all('br'):
                                br.replace_with(' ')
                            description = desc_elem.get_text(separator=' ', strip=True)
                    
                    if take_screenshots and detail_url:
                        screenshot_id = slugify(card_title)
                        print(f"   [SCREEN] Создание скриншота...")
                        screenshot_path = take_screenshot(
                            detail_url, 
                            screenshots_base_path, 
                            screenshot_id,
                            SCREENSHOT_WIDTH,
                            SCREENSHOT_HEIGHT
                        )
                        
                        if screenshot_path and save_to_mongo and fs is not None:
                            try:
                                with open(screenshot_path, 'rb') as f:
                                    screenshot_data = f.read()
                                
                                gridfs_filename = f"{screenshot_id}.png"
                                screenshot_gridfs_id = fs.put(
                                    screenshot_data,
                                    filename=gridfs_filename,
                                    content_type='image/png',
                                    metadata={
                                        "source_url": detail_url,
                                        "title": card_title,
                                        "category": category,
                                        "created_at": datetime.now()
                                    }
                                )
                                print(f"   [DB] Скриншот сохранен в GridFS: {screenshot_gridfs_id}")
                            except Exception as grid_err:
                                print(f"      [WARN] Ошибка сохранения в GridFS: {grid_err}")
                                screenshot_gridfs_id = None
                    
                    outage_data = {
                        "category": category,
                        "title": detail_title,
                        "description": description,
                        "event_date": event_date_obj,
                        "parsed_at": run_datetime,
                        "source_url": url,
                        "detail_url": detail_url,
                        "screenshot_path": screenshot_path,
                        "screenshot_gridfs_id": str(screenshot_gridfs_id) if screenshot_gridfs_id else None
                    }
                    
                    all_outages.append(outage_data)
                    
                    print(f"      [OK] {detail_title[:50]}...")
                    
                    md_file.write(f"### {detail_title}\n\n")
                    md_file.write(f"**Дата:** {event_date_obj.strftime('%d.%m.%Y')}\n\n")
                    md_file.write(f"**Описание:**\n{description}\n\n")
                    md_file.write(f"**Ссылка:** {detail_url}\n\n")
                    if screenshot_path:
                        md_file.write(f"**Скриншот:** {screenshot_path}\n\n")
                    md_file.write("---\n\n")
                    
                    if save_to_mongo and db_collection is not None:
                        try:
                            db_collection.update_one(
                                {"detail_url": detail_url},
                                {"$set": outage_data},
                                upsert=True
                            )
                        except Exception as db_err:
                            print(f"      [WARN] Ошибка записи в MongoDB: {db_err}")

            except requests.RequestException as req_err:
                print(f"   [ERROR] Ошибка запроса: {req_err}")
                md_file.write(f"[WARN] Ошибка при загрузке данных раздела '{category}': {req_err}\n\n")
            except Exception as inner_e:
                print(f"   [ERROR] Ошибка при парсинге {category}: {inner_e}")
                import traceback
                traceback.print_exc()
                md_file.write(f"[WARN] Ошибка при парсинге '{category}': {inner_e}\n\n")

    close_browser(pw)

    print(f"\n[DONE] Обработка завершена. Найдено событий: {len(all_outages)}")
    print(f"[FILE] Результат сохранен в '{filename}'")
    print(f"[FOLDER] Скриншоты: {screenshots_base_path}")
    if save_to_mongo:
        print("[DB] Данные сохранены в MongoDB")

if __name__ == "__main__":
    parse_skk_outages()
