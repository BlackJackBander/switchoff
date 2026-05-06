#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utility Outages Monitor - skk65.ru"""

import asyncio
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import os
import re

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "utility_monitor"
COLLECTION_NAME = "outages"
DATA_DIR = os.path.expanduser("~/utility_monitor/data")
BASE_URL = "https://skk65.ru/otkljucheniya/otoplenie"

async def fetch_page(session, url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with session.get(url, headers=headers, timeout=30) as response:
        if response.status == 200:
            return await response.text()
    return None

def parse_outages(html):
    """Парсинг: ищем строки вида '30 марта 2026 ... адреса'"""
    outages = []
    months = {'марта':'03','мар':'03','апреля':'04','апр':'04','мая':'05','июня':'06',
              'июля':'07','августа':'08','сентября':'09','октября':'10','ноября':'11',
              'декабря':'12','января':'01','февраля':'02'}
    
    date_pattern = re.compile(r'(\d{1,2})\s+(марта|мар|апреля|апр|мая|июня|июля|августа|сентября|октября|ноября|декабря|января|февраля)\s+(\d{4})', re.IGNORECASE)
    
    for line in html.split('\n'):
        line = line.strip()
        if not line or len(line) < 20:
            continue
        
        match = date_pattern.search(line)
        if match:
            day = match.group(1)
            month = months.get(match.group(2).lower(), '01')
            year = match.group(3)
            date_str = f"{day}.{month}.{year}"
            
            # Извлекаем адреса после даты
            after_date = line[match.end():].strip()
            addresses = [a.strip() for a in after_date.split(';') if a.strip() and len(a.strip()) > 5]
            
            if addresses:
                outages.append({'date': date_str, 'addresses': addresses, 'parsed_at': datetime.now().isoformat()})
    
    return outages

async def save_to_mongodb(outages, collection):
    saved = 0
    for outage in outages:
        key = f"{outage['date']}_{hash(tuple(sorted(outage['addresses'])))}"
        if not await collection.find_one({"outage_key": key}):
            await collection.insert_one({
                "outage_key": key, "date": outage['date'], "addresses": outage['addresses'],
                "address_count": len(outage['addresses']), "parsed_at": outage['parsed_at'], "created_at": datetime.now()
            })
            saved += 1
    return saved

def generate_markdown(outages, output_file):
    md = ["# 🔧 Отчёт по отключениям коммунальных услуг",
          f"**Сформировано:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
          f"**Источник:** [skk65.ru]({BASE_URL})", "\n---\n"]
    
    by_date = {}
    for o in outages:
        by_date.setdefault(o['date'], []).extend(o['addresses'])
    
    sorted_dates = sorted(by_date.keys(), reverse=True)
    total = sum(len(a) for a in by_date.values())
    
    md.extend(["## 📊 Статистика",
               f"- **Дней с отключениями:** {len(sorted_dates)}",
               f"- **Всего адресов:** {total}", "\n---\n", "## 📅 По датам"])
    
    for date in sorted_dates[:10]:
        addrs = by_date[date]
        md.append(f"\n### {date} ({len(addrs)} адресов)")
        for addr in addrs[:10]:
            md.append(f"- {addr}")
        if len(addrs) > 10:
            md.append(f"- ... и ещё {len(addrs) - 10}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

async def main():
    print("=" * 60)
    print("UTILITY OUTAGES MONITOR")
    print("=" * 60)
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    await collection.create_index("outage_key", unique=True)
    
    async with aiohttp.ClientSession() as session:
        print("📥 Загрузка...")
        html = await fetch_page(session, BASE_URL)
        if not html:
            print("❌ Ошибка загрузки")
            return
        
        print("🔍 Парсинг...")
        outages = parse_outages(html)
        print(f"✅ Найдено: {len(outages)}")
        
        print("💾 MongoDB...")
        saved = await save_to_mongodb(outages, collection)
        print(f"✅ Добавлено: {saved}")
        
        print("📝 Отчёт...")
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(DATA_DIR, f"outages_{ts}.md")
        generate_markdown(outages, output_file)
        print(f"✅ {output_file}")
        
        # Вывод в чат
        print("\n" + "=" * 60)
        print("📋 ПОСЛЕДНИЕ ОТКЛЮЧЕНИЯ")
        print("=" * 60)
        
        by_date = {}
        for o in outages:
            by_date.setdefault(o['date'], []).extend(o['addresses'])
        
        for date in sorted(by_date.keys(), reverse=True)[:5]:
            addrs = by_date[date]
            print(f"\n📅 {date} ({len(addrs)} адресов):")
            for addr in addrs[:5]:
                print(f"  • {addr}")
            if len(addrs) > 5:
                print(f"  ... +{len(addrs) - 5}")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    asyncio.run(main())
