import os
import time
import requests
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

# Ссылки (Футбол, Баскетбол, Теннис, Хоккей)
SPORTS = {
    'ФУТБОЛ': "https://www.betexplorer.com/popular-bets/soccer/",
    'ТЕННИС': "https://www.betexplorer.com/popular-bets/tennis/",
    'БАСКЕТБОЛ': "https://www.betexplorer.com/popular-bets/basketball/",
    'ХОККЕЙ': "https://www.betexplorer.com/popular-bets/hockey/"
}

# Словарь иконок
ICONS = {
    'ФУТБОЛ': '⚽',
    'ТЕННИС': '🎾',
    'БАСКЕТБОЛ': '🏀',
    'ХОККЕЙ': '🏒'
}

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def format_pick(match_name, pick_raw):
    """Красиво оформляет исход: '1' -> 'Победа 1 (Real Madrid)'"""
    try:
        pick = pick_raw.strip().upper()
        
        # Разделяем команды по тире
        teams = match_name.split(' - ')
        
        # Если удалось разделить названия команд
        if len(teams) >= 2:
            home_team = teams[0].strip()
            away_team = teams[1].strip()
            
            if pick == '1':
                return f"Победа 1 <b>({home_team})</b>"
            elif pick == '2':
                return f"Победа 2 <b>({away_team})</b>"
            elif pick == 'X':
                return "Ничья <b>(X)</b>"
        
        # Если это не 1/X/2 или не удалось разделить имена
        return f"Исход: <b>{pick}</b>"
    except:
        return f"Исход: <b>{pick_raw}</b>"

def run_beautiful_scanner():
    # Сообщение о старте (можно убрать, если мешает)
    # send_telegram("🚀 <b>Сканер запущен...</b>")

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

        total_found = 0

        for sport_name, url in SPORTS.items():
            print(f"🌍 {sport_name}...")
            try:
                driver.get(url)
                
                # Ждем таблицу
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr"))
                    )
                except:
                    continue

                rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
                if len(rows) < 2: continue

                count = 0
                
                # Проходим по строкам (пропуская шапку)
                for row in rows[1:]:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) < 4: continue
                        
                        # 1. Берем название матча ИЗ ССЫЛКИ (чтобы не прилипло время)
                        # В ячейке [0] есть тег <a> с названием команд
                        link_element = cols[0].find_element(By.TAG_NAME, "a")
                        match_name = link_element.text.strip() # Чистое имя без времени
                        link = link_element.get_attribute("href")
                        
                        # 2. Исход (1, X, 2)
                        pick_raw = cols[1].text.strip()
                        
                        # 3. Коэффициент
                        odd = cols[2].text.strip()
                        
                        # Формируем красивый текст ставки
                        beautiful_pick = format_pick(match_name, pick_raw)
                        
                        # Иконка спорта
                        icon = ICONS.get(sport_name, '🏆')

                        msg = (
                            f"🔥 <b>ТОП ПРОГРУЗ | {sport_name}</b>\n\n"
                            f"{icon} <b>{match_name}</b>\n"
                            f"🎯 Выбор: {beautiful_pick}\n"
                            f"📉 Кэф: <b>{odd}</b>\n\n"
                            f"🔗 <a href='{link}'>Открыть матч</a>"
                        )
                        
                        send_telegram(msg)
                        
                        count += 1
                        total_found += 1
                        
                        # Лимит: 3 лучших матча на каждый спорт
                        if count >= 3:
                            break
                            
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"Ошибка {sport_name}: {e}")
                continue

        if total_found > 0:
            send_telegram(f"🏁 <b>Сканирование завершено.</b> Найдено матчей: {total_found}")
        else:
            send_telegram("💤 Популярных матчей (прогрузов) сейчас нет.")

    except Exception as e:
        send_telegram(f"❌ Ошибка бота: {e}")
    
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    run_beautiful_scanner()
