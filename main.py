import json
import os
import cloudscraper
from bs4 import BeautifulSoup
import requests
import time
import re

# --- НАСТРОЙКИ ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")

URL = "https://www.arbworld.net/en/moneyway"
HISTORY_FILE = "money_history.json"

# Минимальная сумма в ЕВРО, чтобы пришло уведомление
MIN_MONEY = 20000  # Например, 20 000 евро

def send_telegram(text):
    if not TG_TOKEN or not TG_CHANNEL:
        print("❌ ОШИБКА: Нет токена или канала!")
        return
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        'chat_id': TG_CHANNEL,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print(f"Ошибка Телеграм: {r.text}")
    except Exception as e:
        print(f"Сбой отправки: {e}")

def parse_money(text):
    """Превращает '€ 105,400' в число 105400"""
    try:
        # Убираем все лишнее, оставляем только цифры
        clean = re.sub(r'[^\d]', '', text)
        return int(clean)
    except:
        return 0

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def save_history(data):
    try:
        with open(HISTORY_FILE, 'w') as f: json.dump(data[-200:], f)
    except: pass

def run_scanner():
    print(f"💰 Запуск сканера Moneyway... Порог: {MIN_MONEY}€")
    
    # 1. Загрузка истории
    history = load_history()
    new_history = history.copy()
    
    # 2. Настройка скрапера (маскируемся под Firefox)
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'firefox', 'platform': 'windows', 'mobile': False}
    )

    try:
        response = scraper.get(URL)
        if response.status_code != 200:
            print(f"⛔ Сайт не открылся, код: {response.status_code}")
            # Если 403 - значит Cloudflare забанил. Ничего не поделаешь, пробуем позже.
            return

        soup = BeautifulSoup(response.text, 'lxml')
        
        # Ищем таблицу Moneyway
        rows = soup.select('table.items tr')
        print(f"Найдено строк: {len(rows)}")

        for row in rows:
            try:
                # Пропускаем заголовки
                if not row.find('td'): continue
                
                cols = row.find_all('td')
                if len(cols) < 8: continue

                # Извлекаем данные
                match_name = cols[2].get_text(strip=True)
                link_tag = cols[2].find('a')
                match_url = link_tag['href'] if link_tag else match_name
                
                # Колонки с деньгами (обычно 1, X, 2 находятся в col 5, 6, 7)
                # Но на Arbworld Moneyway структура может быть сложной.
                # Ищем ячейки, где есть знак евро €
                
                money_found = False
                best_sum = 0
                outcome = ""
                
                # Перебираем ячейки 1, X, 2 (индексы могут меняться, ищем по смыслу)
                # Обычно это 5 (1), 6 (X), 7 (2)
                outcomes_names = ["П1 (Dom)", "X (Draw)", "П2 (Away)"]
                target_cols = [cols[5], cols[6], cols[7]]

                for i, col in enumerate(target_cols):
                    text = col.get_text(strip=True)
                    money = parse_money(text)
                    
                    if money > best_sum:
                        best_sum = money
                        outcome = outcomes_names[i]

                # ПРОВЕРКИ
                if best_sum < MIN_MONEY: continue
                if match_url in history: continue # Уже отправляли

                # ОТПРАВКА
                # Превращаем число обратно в красивый вид: 100000 -> 100,000
                pretty_sum = "{:,}".format(best_sum).replace(",", " ")
                
                msg = (
                    f"💶 <b>BIG MONEY: {pretty_sum} €</b>\n\n"
                    f"⚽ <b>{match_name}</b>\n"
                    f"🎯 Прогруз на: <b>{outcome}</b>\n"
                    f"🔗 <a href='https://www.arbworld.net{match_url}'>Открыть Moneyway</a>"
                )
                
                print(f"Отправляю: {match_name} ({pretty_sum}€)")
                send_telegram(msg)
                
                new_history.append(match_url)
                money_found = True
                time.sleep(2)

            except Exception as e:
                continue

        if not money_found:
            print("Нет матчей с такими суммами.")

    except Exception as e:
        print(f"Критическая ошибка: {e}")

    save_history(new_history)

if __name__ == "__main__":
    # ТЕСТОВАЯ ПРОВЕРКА ПРИ ЗАПУСКЕ
    # Если ты это видишь в логах, но не в телеге - проблема в токене/ID
    print("Проверка связи...")
    run_scanner()
