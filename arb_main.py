import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- НАСТРОЙКИ ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")

# Источник: BetExplorer Popular Bets (Самые прогруженные матчи мира)
URL = "https://www.betexplorer.com/popular-bets/soccer/"

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def run_stealth_scanner():
    print("🚀 Запуск STEALTH режима...")
    
    # --- НАСТРОЙКИ НЕВИДИМКИ ---
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 1. Подделываем User-Agent под обычный Windows
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    
    # 2. ОТКЛЮЧАЕМ флаги автоматизации (самое важное!)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Дополнительная маскировка через JS
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"🌍 Иду на {URL}...")
        driver.get(URL)
        time.sleep(10) # Ждем прогрузки
        
        # Ищем таблицу популярных ставок
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
        print(f"📊 Найдено строк: {len(rows)}")
        
        if len(rows) < 3:
            send_telegram("⚠️ BetExplorer открылся, но таблица пустая. Защита сработала.")
            driver.quit()
            return

        matches_found = 0

        # Пропускаем заголовок таблицы [0]
        for row in rows[1:]:
            try:
                # Извлекаем данные
                # Структура: Матч | Ставка | Кэф | Дата
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 4: continue
                
                match_name = cols[0].text.strip()
                pick = cols[1].text.strip() # На кого грузят (1, X, 2)
                odd = cols[2].text.strip()  # Кэф
                
                # Ссылка на матч
                link_el = cols[0].find_element(By.TAG_NAME, "a")
                link = link_el.get_attribute("href")
                
                msg = (
                    f"🔥 <b>POPULAR BET (High Volume)</b>\n\n"
                    f"⚽ <b>{match_name}</b>\n"
                    f"🎯 Грузят на: <b>{pick}</b>\n"
                    f"💰 Кэф: {odd}\n"
                    f"🔗 <a href='{link}'>Открыть матч</a>"
                )
                
                send_telegram(msg)
                matches_found += 1
                
                if matches_found >= 5: # Шлем топ-5 самых популярных
                    break
                    
            except Exception as e:
                continue
        
        if matches_found == 0:
            send_telegram("✅ Сайт открылся, но популярных матчей на сегодня нет.")

        driver.quit()

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        send_telegram(f"❌ Ошибка бота: {e}")

if __name__ == "__main__":
    run_stealth_scanner()
