import os
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

SPORTS = {
    '⚽ ФУТБОЛ': "https://www.betexplorer.com/popular-bets/soccer/",
    '🏀 БАСКЕТБОЛ': "https://www.betexplorer.com/popular-bets/basketball/",
    '🏒 ХОККЕЙ': "https://www.betexplorer.com/popular-bets/hockey/",
    '🎾 ТЕННИС': "https://www.betexplorer.com/popular-bets/tennis/"
}

ICONS = {
    '⚽ ФУТБОЛ': '⚽',
    '🏀 БАСКЕТБОЛ': '🏀',
    '🏒 ХОККЕЙ': '🏒',
    '🎾 ТЕННИС': '🎾'
}

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def is_float(text):
    """Проверяет, является ли текст числом (кэфом), например '1.11'"""
    try:
        return "." in text and float(text) > 0
    except:
        return False

def get_teams(match_name):
    """Разделяет строку 'Team A - Team B' на две команды"""
    parts = match_name.split(' - ')
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    return match_name, "Противник"

def run_smart_scanner():
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

        total_matches = 0

        for sport_name, url in SPORTS.items():
            print(f"🌍 {sport_name}...")
            try:
                driver.get(url)
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr"))
                    )
                except:
                    continue

                rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
                if len(rows) < 2: continue

                count = 0
                
                # Проходим по строкам
                for row in rows[1:]:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) < 4: continue
                        
                        # 1. Ссылка и Имя матча
                        link_el = cols[0].find_element(By.TAG_NAME, "a")
                        match_name = link_el.text.strip()
                        link = link_el.get_attribute("href")
                        
                        col1_text = cols[1].text.strip() # Либо Исход ("1"), либо Кэф ("1.11")
                        col2_text = cols[2].text.strip() # Либо Кэф ("1.5"), либо Кэф противника
                        
                        # --- ЛОГИКА ОПРЕДЕЛЕНИЯ ТАБЛИЦЫ ---
                        
                        final_pick = ""
                        final_odd = ""
                        team1, team2 = get_teams(match_name)
                        
                        # СЦЕНАРИЙ А: Таблица "Сломалась" (как на скрине) -> Там кэфы (1.11, 6.85)
                        if is_float(col1_text):
                            odd_home = float(col1_text)
                            try:
                                odd_away = float(col2_text)
                            except:
                                odd_away = 100.0 # Если второй кэф пустой
                            
                            # В популярных ставках обычно грузят на фаворита (меньший кэф)
                            if odd_home < odd_away:
                                final_pick = f"Победа 1 <b>({team1})</b>"
                                final_odd = str(odd_home)
                            else:
                                final_pick = f"Победа 2 <b>({team2})</b>"
                                final_odd = str(odd_away)
                        
                        # СЦЕНАРИЙ Б: Таблица Нормальная -> Там исход ("1", "X", "2")
                        else:
                            pick = col1_text.upper()
                            final_odd = col2_text
                            
                            if pick == '1':
                                final_pick = f"Победа 1 <b>({team1})</b>"
                            elif pick == '2':
                                final_pick = f"Победа 2 <b>({team2})</b>"
                            elif pick == 'X':
                                final_pick = "Ничья <b>(X)</b>"
                            else:
                                final_pick = f"Исход: {pick}"

                        # Отправка
                        icon = ICONS.get(sport_name, '🔥')
                        
                        msg = (
                            f"🔥 <b>ТОП ПРОГРУЗ | {sport_name}</b>\n\n"
                            f"{icon} <b>{match_name}</b>\n"
                            f"✅ Выбор: {final_pick}\n"
                            f"📉 Кэф: <b>{final_odd}</b>\n\n"
                            f"🔗 <a href='{link}'>Открыть матч</a>"
                        )
                        
                        send_telegram(msg)
                        
                        count += 1
                        total_matches += 1
                        
                        if count >= 3: # Топ-3 матча на спорт
                            break
                            
                    except Exception as e:
                        continue

            except Exception as e:
                print(f"Ошибка {sport_name}: {e}")
                continue
        
        if total_matches == 0:
            send_telegram("💤 Популярных матчей сейчас нет.")
        else:
            send_telegram(f"🏁 <b>Сканирование завершено.</b> Найдено: {total_matches}")

    except Exception as e:
        send_telegram(f"❌ Ошибка: {e}")
    
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    run_smart_scanner()
