import os
import json
import time
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- НАСТРОЙКИ ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")

# Ссылка на падающие коэффициенты (фильтр: за последние 24 часа)
URL = "https://www.betexplorer.com/dropping-odds/"

# Минимальный процент падения (15 = 15%)
MIN_DROP = 15.0

# Файл истории (чтобы не спамить одним и тем же)
HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(data):
    try:
        # Храним только последние 300 матчей
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data[-300:], f)
    except:
        pass

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def get_sport_icon(link):
    if "soccer" in link: return "⚽"
    if "basketball" in link: return "🏀"
    if "tennis" in link: return "🎾"
    if "hockey" in link: return "🏒"
    if "volleyball" in link: return "🏐"
    if "handball" in link: return "🤾"
    return "🚨"

def run_drop_scanner():
    print(f"🚀 Запуск поиска прогрузов > {MIN_DROP}%...")

    # Настройки "Невидимки"
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Загружаем историю
        history = load_history()
        new_history = history.copy()
        found_count = 0

        print(f"🌍 Иду на {URL}...")
        driver.get(URL)
        
        # Ждем таблицу
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr"))
            )
        except:
            print("⚠️ Таблица не прогрузилась.")
            driver.quit()
            return

        rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
        print(f"📊 Найдено строк: {len(rows)}")

        for row in rows:
            try:
                # Ищем процент падения (класс .table-main__drop)
                try:
                    drop_element = row.find_element(By.CLASS_NAME, "table-main__drop")
                    drop_text = drop_element.text.strip().replace('%', '')
                    drop_val = float(drop_text)
                except:
                    continue # Если в строке нет процента, пропускаем

                # Мы берем модуль числа (так как падение пишут с минусом, например -20.5)
                drop_val = abs(drop_val)

                # Фильтр: Ищем только падение больше MIN_DROP (15%)
                if drop_val < MIN_DROP:
                    continue

                # Извлекаем данные матча
                cols = row.find_elements(By.TAG_NAME, "td")
                
                # Ссылка и Название
                link_el = cols[0].find_element(By.TAG_NAME, "a")
                match_name = link_el.text.strip()
                link = link_el.get_attribute("href")
                
                # Проверка истории (чтобы не слать повторно)
                if link in history:
                    continue

                # Текущий кэф (обычно последняя колонка с классом odds)
                # Или просто берем текст из ячейки кэфа
                try:
                    odds_el = row.find_element(By.CLASS_NAME, "table-main__odds")
                    current_odd = odds_el.text.strip()
                except:
                    current_odd = "N/A"

                # На кого грузят? (Обычно выделено жирным или цветом, но упростим)
                # Определяем вид спорта по ссылке
                icon = get_sport_icon(link)

                msg = (
                    f"📉 <b>СИЛЬНОЕ ПАДЕНИЕ | {drop_val}%</b>\n\n"
                    f"{icon} <b>{match_name}</b>\n"
                    f"🔻 Прогруз: <b>{drop_val}%</b>\n"
                    f"💰 Текущий Кэф: <b>{current_odd}</b>\n\n"
                    f"🔗 <a href='{link}'>Открыть матч</a>"
                )
                
                send_telegram(msg)
                
                new_history.append(link)
                found_count += 1
                
                # Пауза 1 сек, чтобы телеграм не блочил
                time.sleep(1)

            except Exception as e:
                continue

        # Сохраняем обновленную историю
        if found_count > 0:
            print(f"✅ Найдено новых прогрузов: {found_count}")
            # Сохраняем файл истории в систему
            save_history(new_history)
        else:
            print("💤 Новых прогрузов >15% пока нет.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        send_telegram(f"❌ Ошибка бота: {e}")
    
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    run_drop_scanner()
