import os
import json
import time
import requests
from datetime import datetime, timedelta
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
BETS_FILE = "bets.json"

# Ссылки
SPORTS = {
    'ФУТБОЛ': "https://www.betexplorer.com/popular-bets/soccer/",
    'ТЕННИС': "https://www.betexplorer.com/popular-bets/tennis/",
    'БАСКЕТБОЛ': "https://www.betexplorer.com/popular-bets/basketball/",
    'ХОККЕЙ': "https://www.betexplorer.com/popular-bets/hockey/"
}

ICONS = {
    'ФУТБОЛ': '⚽',
    'ТЕННИС': '🎾',
    'БАСКЕТБОЛ': '🏀',
    'ХОККЕЙ': '🏒'
}

# Работаем 10 минут, потом рестарт (чтобы GitHub не убил процесс)
WORK_DURATION_MINUTES = 10 

# --- БАЗА ДАННЫХ ---
def load_bets():
    if os.path.exists(BETS_FILE):
        try:
            with open(BETS_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def save_bets(data):
    try:
        with open(BETS_FILE, 'w') as f: json.dump(data, f, indent=4)
    except: pass

# --- TELEGRAM ---
def send_telegram(text, reply_to=None):
    if not TG_TOKEN or not TG_CHANNEL: return None
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        'chat_id': TG_CHANNEL, 
        'text': text, 
        'parse_mode': 'HTML', 
        'disable_web_page_preview': True
    }
    if reply_to: payload['reply_to_message_id'] = reply_to
    
    try:
        r = requests.post(url, json=payload)
        resp = r.json()
        if resp.get('ok'): return resp['result']['message_id']
    except Exception as e: print(f"TG Err: {e}")
    return None

# --- ОБРАБОТКА ВРЕМЕНИ (МСК) ---
def convert_to_msk(date_str):
    """
    Превращает '14.10. 18:00' (Европа) в '14.10 20:00' (МСК)
    Добавляем +2 часа (разница CET и МСК, грубо).
    """
    try:
        # Убираем лишние точки если есть
        clean_str = date_str.strip()
        
        # Добавляем текущий год для парсинга
        current_year = datetime.now().year
        dt = datetime.strptime(f"{clean_str}.{current_year}", "%d.%m. %H:%M.%Y")
        
        # Добавляем 2 часа (BetExplorer обычно в CET, МСК = CET+2)
        dt_msk = dt + timedelta(hours=2)
        
        return dt_msk.strftime("%d.%m %H:%M (МСК)")
    except:
        # Если не получилось распарсить, возвращаем как есть
        return date_str

# --- ОБРАБОТКА НАЗВАНИЙ ---
def get_team_names(match_name):
    parts = match_name.split(' - ')
    if len(parts) >= 2: return parts[0].strip(), parts[1].strip()
    return match_name, "Соперник"

def format_pick(match_name, pick_raw):
    p = pick_raw.upper().strip()
    t1, t2 = get_team_names(match_name)
    
    if p == '1': return f"Победа 1 <b>({t1})</b>"
    if p == '2': return f"Победа 2 <b>({t2})</b>"
    if p == 'X': return "Ничья <b>(X)</b>"
    return f"Исход: <b>{p}</b>"

# --- ЛОГИКА СКАНЕРА ---
def scan_popular(driver, bets):
    print("🔥 Сканирую рынки...")
    existing_urls = [b['url'] for b in bets]
    updated = False
    
    for sport_name, url in SPORTS.items():
        try:
            driver.get(url)
            try:
                # Ждем таблицу
                WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr")))
            except: continue

            rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
            if len(rows) < 2: continue
            
            count = 0
            # Пропускаем шапку [0]
            for row in rows[1:]:
                try:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    # Структура: [0]Матч, [1]Исход, [2]Кэф, [3]Дата
                    if len(cols) < 4: continue
                    
                    # 1. Ссылка и Название
                    try:
                        link_el = cols[0].find_element(By.TAG_NAME, "a")
                        match_name = link_el.text.strip()
                        link = link_el.get_attribute("href")
                    except: continue

                    if link in existing_urls: continue
                    
                    # 2. Данные (берем textContent, так надежнее)
                    pick_raw = cols[1].get_attribute("textContent").strip()
                    odd = cols[2].get_attribute("textContent").strip()
                    date_raw = cols[3].get_attribute("textContent").strip()
                    
                    # Проверка на пустые данные (чтобы не было пустых сообщений)
                    if not pick_raw or not odd: continue
                    # Если в поле исхода попала дата или кэф (защита от сдвига)
                    if "." in pick_raw and len(pick_raw) > 3: continue 

                    # Форматирование
                    pretty_pick = format_pick(match_name, pick_raw)
                    pretty_time = convert_to_msk(date_raw)
                    icon = ICONS.get(sport_name, '🏆')
                    
                    msg = (
                        f"🔥 <b>ТОП ПРОГРУЗ | {sport_name}</b>\n\n"
                        f"{icon} <b>{match_name}</b>\n"
                        f"🕒 Начало: <b>{pretty_time}</b>\n"
                        f"🎯 {pretty_pick}\n"
                        f"💰 Кэф: <b>{odd}</b>\n"
                        f"🔗 <a href='{link}'>Открыть матч</a>"
                    )
                    
                    msg_id = send_telegram(msg)
                    if msg_id:
                        bets.append({
                            'url': link,
                            'msg_id': msg_id,
                            'pick': pick_raw,
                            'status': 'pending',
                            'timestamp': time.time()
                        })
                        updated = True
                        existing_urls.append(link)
                        time.sleep(1)
                        
                    count += 1
                    if count >= 3: break # Лимит 3 матча на спорт
                except Exception as e:
                    # print(f"Row error: {e}") 
                    continue
        except: continue
        
    return updated

def check_results(driver, bets):
    print("🏁 Проверка результатов...")
    updated = False
    
    for bet in bets:
        if bet['status'] != 'pending': continue
        
        url = bet['url']
        pick = bet['pick']
        msg_id = bet['msg_id']
        
        try:
            driver.get(url)
            try:
                WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, "js-score")))
                score_text = driver.find_element(By.ID, "js-score").text.strip()
                status_text = driver.find_element(By.ID, "match-status-caption").text.strip()
            except: continue 

            if "Finished" in status_text or "After" in status_text or "AET" in status_text:
                parts = score_text.split(':')
                if len(parts) == 2:
                    try:
                        s1, s2 = int(parts[0]), int(parts[1])
                        result = "LOSE"
                        if pick == '1' and s1 > s2: result = "WIN"
                        elif pick == '2' and s2 > s1: result = "WIN"
                        elif pick == 'X' and s1 == s2: result = "WIN"
                        
                        icon = "✅" if result == "WIN" else "❌"
                        # Переводим WIN/LOSE на русский
                        res_ru = "ЗАХОД" if result == "WIN" else "МИНУС"
                        
                        reply = f"{icon} <b>{res_ru}</b>\nСчет: <b>{score_text}</b>"
                        
                        send_telegram(reply, reply_to=msg_id)
                        
                        bet['status'] = 'finished'
                        bet['result'] = result
                        updated = True
                        time.sleep(1)
                    except: continue
        except: continue
            
    return updated

# --- ЗАПУСК ЦИКЛА ---
def run_eternal_loop():
    print("🚀 Бот запущен (Fix: Время МСК + Колонки)")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    bets = load_bets()
    start_time = time.time()
    
    try:
        while True:
            # Таймер работы (чтобы GitHub не убил процесс жестко)
            elapsed_min = (time.time() - start_time) / 60
            if elapsed_min >= WORK_DURATION_MINUTES:
                print("⏰ Время вышло. Перезагрузка...")
                break
            
            has_updates = False
            
            # 1. Проверяем результаты
            if check_results(driver, bets): has_updates = True
            
            # 2. Ищем новые ставки
            if scan_popular(driver, bets): has_updates = True
            
            if has_updates:
                save_bets(bets)
            
            # Спим 3 минуты
            print("💤 Сплю 3 минуты...")
            time.sleep(180)
            
    except Exception as e:
        print(f"Loop Error: {e}")
        save_bets(bets)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    run_eternal_loop()
