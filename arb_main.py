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

SPORTS = {
    '⚽ Футбол': "https://www.betexplorer.com/popular-bets/soccer/",
    '🏀 Баскетбол': "https://www.betexplorer.com/popular-bets/basketball/",
    '🎾 Теннис': "https://www.betexplorer.com/popular-bets/tennis/",
    '🏒 Хоккей': "https://www.betexplorer.com/popular-bets/hockey/"
}

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def get_readable_pick(match_name, pick_raw):
    """Превращает '1' в 'Real Madrid', '2' в 'Barcelona'"""
    try:
        # Очищаем исход от мусора (иногда там пробелы)
        pick = pick_raw.strip()
        
        # Разделяем название матча "Team A - Team B"
        teams = match_name.split(' - ')
        
        if len(teams) == 2:
            home_team = teams[0].strip()
            away_team = teams[1].strip()
            
            if pick == '1':
                return f"Победа 1: <b>{home_team}</b>"
            elif pick == '2':
                return f"Победа 2: <b>{away_team}</b>"
            elif pick.upper() == 'X':
                return "Результат: <b>Ничья</b>"
        
        # Если не удалось разделить названия или это не 1/X/2
        return f"Исход: <b>{pick}</b>"
    except:
        return f"Исход: {pick_raw}"

def run_fix_scanner():
    # Сообщение о старте (можно убрать потом)
    send_telegram("🚀 <b>Запуск V3 (Фикс имен)...</b>")

    # --- МАКСИМАЛЬНАЯ МАСКИРОВКА ---
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Реалистичный User-Agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    # Отключение флагов автоматизации
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Скрипт для скрытия Selenium
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        total_sent = 0

        for sport_name, url in SPORTS.items():
            print(f"🌍 Иду в {sport_name}...")
            try:
                driver.get(url)
                
                # Ждем таблицу до 15 секунд (лучше, чем просто sleep)
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr"))
                    )
                except:
                    print(f"⚠️ {sport_name}: Таблица не прогрузилась.")
                    continue

                rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
                
                if len(rows) < 2:
                    continue

                count_sport = 0
                
                # Пропускаем шапку [0]
                for row in rows[1:]:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        
                        # Таблица Popular Bets имеет структуру:
                        # 0: Матч | 1: Исход (Pick) | 2: Кэф | 3: Дата
                        
                        if len(cols) < 3: continue
                        
                        match_text = cols[0].text.strip() # Например: "Real - Barca"
                        pick_raw = cols[1].text.strip()   # Например: "1"
                        odd = cols[2].text.strip()        # Например: "2.12"
                        
                        # ВАЖНО: Иногда сайт меняет колонки местами.
                        # Проверка: если в pick_raw число с точкой (например 2.12), значит мы взяли не ту колонку
                        if "." in pick_raw and len(pick_raw) > 2:
                            # Сдвигаем индексы, если верстка поплыла (редкий случай)
                            pick_raw = "1?" # Заглушка
                        
                        readable_pick = get_readable_pick(match_text, pick_raw)
                        
                        # Ссылка
                        try:
                            link = cols[0].find_element(By.TAG_NAME, "a").get_attribute("href")
                        except:
                            link = url

                        msg = (
                            f"🔥 <b>POPULAR {sport_name.upper()}</b>\n\n"
                            f"🏟 <b>{match_text}</b>\n"
                            f"🎯 {readable_pick}\n"
                            f"💰 Кэф: {odd}\n"
                            f"🔗 <a href='{link}'>Открыть матч</a>"
                        )
                        
                        send_telegram(msg)
                        
                        count_sport += 1
                        total_sent += 1
                        
                        # Берем ТОП-3 матча на каждый спорт
                        if count_sport >= 3:
                            break
                            
                    except Exception as e:
                        print(f"Ошибка строки: {e}")
                        continue
                        
            except Exception as e:
                print(f"Ошибка раздела {sport_name}: {e}")
                continue

        if total_sent == 0:
            send_telegram("⚠️ Бот прошел все ссылки, но популярных матчей на сегодня нет (или сайт блокирует).")
        else:
            send_telegram(f"🏁 <b>Готово.</b> Найдено матчей: {total_sent}")

    except Exception as e:
        send_telegram(f"❌ Критическая ошибка: {e}")
    
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    run_fix_scanner()
