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

# Список видов спорта для сканирования
SPORTS = {
    'soccer': '⚽ Футбол',
    'basketball': '🏀 Баскетбол',
    'tennis': '🎾 Теннис',
    'hockey': '🏒 Хоккей',
    'handball': '🤾 Гандбол',
    'volleyball': '🏐 Волейбол',
    'baseball': '⚾ Бейсбол'
}

BASE_URL = "https://www.betexplorer.com/popular-bets/"

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def get_selection_name(match_name, pick):
    """Определяет название команды по исходу (1, X, 2)"""
    try:
        # Обычно название: "Team A - Team B"
        teams = match_name.split(' - ')
        
        if len(teams) < 2:
            # Если разделитель другой или теннис (имя фамилия)
            if pick == '1': return "Победа 1 (Дома/Фаворит)"
            if pick == '2': return "Победа 2 (Гости)"
            if pick == 'X': return "Ничья"
            return pick

        home_team = teams[0].strip()
        away_team = teams[1].strip()

        if pick == '1':
            return f"Победа 1: <b>{home_team}</b>"
        elif pick == '2':
            return f"Победа 2: <b>{away_team}</b>"
        elif pick == 'X':
            return "Результат: <b>Ничья</b>"
        else:
            return f"Исход: {pick}"
    except:
        return f"Исход: {pick}"

def run_multisport_scanner():
    print("🚀 Запуск Multi-Sport сканера...")
    
    # --- НАСТРОЙКИ STEALTH (Те же, что сработали) ---
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # --- ЦИКЛ ПО ВСЕМ ВИДАМ СПОРТА ---
        for sport_key, sport_name in SPORTS.items():
            url = f"{BASE_URL}{sport_key}/"
            print(f"🌍 Сканирую {sport_name} ({url})...")
            
            try:
                driver.get(url)
                time.sleep(5) # Пауза между переходами
                
                rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
                
                if len(rows) < 2:
                    print(f"⚠️ {sport_name}: Таблица пустая или нет популярных ставок.")
                    continue

                count = 0
                # Пропускаем шапку таблицы [0]
                for row in rows[1:]:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) < 4: continue
                        
                        # Парсим данные
                        match_name = cols[0].text.strip() # Названия команд
                        pick = cols[1].text.strip()       # 1, X или 2
                        odd = cols[2].text.strip()        # Коэффициент
                        
                        # Убираем время из названия матча (если оно там приклеилось)
                        # Обычно BetExplorer пишет время в span, selenium берет всё текстом
                        # Просто берем, как есть, обычно читаемо
                        
                        selection_text = get_selection_name(match_name, pick)
                        
                        # Ссылка
                        try:
                            link = cols[0].find_element(By.TAG_NAME, "a").get_attribute("href")
                        except:
                            link = url

                        msg = (
                            f"🔥 <b>TOP {sport_name.upper()}</b>\n\n"
                            f"⚔️ {match_name}\n"
                            f"🎯 {selection_text}\n"
                            f"💰 Кэф: <b>{odd}</b>\n"
                            f"📊 <i>Высокий объем ставок</i>\n"
                            f"🔗 <a href='{link}'>Открыть матч</a>"
                        )
                        
                        send_telegram(msg)
                        count += 1
                        
                        # Берем только ТОП-3 самых популярных матча на каждый спорт
                        if count >= 3:
                            break
                            
                    except Exception as inner_e:
                        continue
                
                print(f"✅ {sport_name}: отправлено {count} матчей.")
                
            except Exception as e:
                print(f"Ошибка при сканировании {sport_name}: {e}")
                continue

        driver.quit()

    except Exception as e:
        print(f"❌ Критическая ошибка драйвера: {e}")
        send_telegram(f"❌ Ошибка бота: {e}")

if __name__ == "__main__":
    run_multisport_scanner()
