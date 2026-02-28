import os
import json
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
BETS_FILE = "bets.json"
URL_DROPS = "https://www.betexplorer.com/dropping-odds/"
MIN_DROP = 15.0  # Процент падения

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
def load_bets():
    if os.path.exists(BETS_FILE):
        try:
            with open(BETS_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def save_bets(data):
    try:
        # Очистка: удаляем матчи, которые завершились более 24 часов назад (чтобы файл не пух)
        # Но для простоты пока просто перезаписываем
        with open(BETS_FILE, 'w') as f: json.dump(data, f, indent=4)
    except: pass

# --- ТЕЛЕГРАМ ---
def send_telegram(text, reply_to=None):
    if not TG_TOKEN or not TG_CHANNEL: return None
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        'chat_id': TG_CHANNEL, 
        'text': text, 
        'parse_mode': 'HTML', 
        'disable_web_page_preview': True
    }
    if reply_to:
        payload['reply_to_message_id'] = reply_to
        
    try:
        r = requests.post(url, json=payload)
        response = r.json()
        if response.get('ok'):
            return response['result']['message_id'] # Возвращаем ID сообщения
    except Exception as e:
        print(f"Ошибка ТГ: {e}")
    return None

# --- ЧАСТЬ 1: ПРОВЕРКА РЕЗУЛЬТАТОВ ---
def check_results(driver, bets):
    print("🕵️‍♂️ Проверка результатов...")
    updated = False
    
    # Проходим по всем матчам со статусом 'pending'
    for bet in bets:
        if bet['status'] != 'pending': continue
        
        url = bet['url']
        pick = bet['pick'] # '1', 'X', '2'
        msg_id = bet['msg_id']
        
        try:
            driver.get(url)
            # Ищем статус матча (Finished, FT, After Pen)
            # На BetExplorer счет обычно в id="js-score" или class="list-details__item__score"
            try:
                # Ждем немного
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "js-score")))
                score_text = driver.find_element(By.ID, "js-score").text.strip() # Пример: "2:1"
                status_text = driver.find_element(By.ID, "match-status-caption").text.strip() # Пример: "Finished"
            except:
                continue # Матч еще не загрузился или не начался

            # Если матч не закончен - пропускаем
            if "Finished" not in status_text and "After" not in status_text and "AET" not in status_text:
                continue

            # Парсим счет "2:1"
            parts = score_text.split(':')
            if len(parts) != 2: continue
            
            score_home = int(parts[0])
            score_away = int(parts[1])
            
            # Определяем результат
            result = "LOSE"
            if pick == '1' and score_home > score_away: result = "WIN"
            elif pick == '2' and score_away > score_home: result = "WIN"
            elif pick == 'X' and score_home == score_away: result = "WIN"
            
            # Формируем ответ
            if result == "WIN":
                reply_text = f"✅ <b>ЗАХОД!</b>\nСчет: <b>{score_text}</b>"
            else:
                reply_text = f"❌ <b>МИНУС</b>\nСчет: <b>{score_text}</b>"
                
            print(f"Матч завершен: {url} -> {result}")
            send_telegram(reply_text, reply_to=msg_id)
            
            # Обновляем статус в базе
            bet['status'] = 'finished'
            bet['result'] = result
            updated = True
            time.sleep(2)
            
        except Exception as e:
            print(f"Ошибка проверки {url}: {e}")
            continue
            
    return updated

# --- ЧАСТЬ 2: ПОИСК НОВЫХ ---
def scan_new_drops(driver, bets):
    print("🔍 Поиск новых прогрузов...")
    updated = False
    existing_urls = [b['url'] for b in bets]
    
    try:
        driver.get(URL_DROPS)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr")))
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
        
        for row in rows:
            try:
                # Ищем % падения
                try:
                    drop_el = row.find_element(By.CLASS_NAME, "table-main__drop")
                    drop_val = float(drop_el.text.strip().replace('%', ''))
                except: continue
                
                if abs(drop_val) < MIN_DROP: continue
                
                # Данные
                cols = row.find_elements(By.TAG_NAME, "td")
                link_el = cols[0].find_element(By.TAG_NAME, "a")
                match_name = link_el.text.strip()
                link = link_el.get_attribute("href")
                
                if link in existing_urls: continue
                
                # Определяем, на кого упал кэф.
                # На BetExplorer Dropping Odds падающий кэф выделен цветом или классом.
                # Но для простоты: смотрим колонки. 
                # 4-я колонка = 1, 5-я = X, 6-я = 2.
                # Где есть класс "k-green" или подобное? Сложно.
                # УПРОЩЕНИЕ: Если кэф на фаворита < 2.0, считаем что грузят на него.
                # Или просто пишем "Прогруз" и ждем результата.
                
                # Для теста будем считать: если drop > 0 (нет минуса), то это ошибка парсинга.
                # BetExplorer пишет падение как "-20%".
                
                # ПОПЫТКА ОПРЕДЕЛИТЬ ИСХОД (1, X, 2)
                # Мы не знаем точно, на кого падение из общей таблицы.
                # Пусть бот пишет "Следим за матчем" и потом дает счет.
                # НО чтобы сказать WIN/LOSE, нам нужно знать ставку.
                # ДАВАЙТЕ ПОКА СТАВИТЬ НА '1' (Хозяев), если падение там визуально.
                # ЛАЙФХАК: Для MVP мы будем просто писать счет матча по итогу, без WIN/LOSE,
                # если не можем определить исход.
                # Но давай попробуем найти исход.
                
                pick = "?"
                odds = row.find_elements(By.CLASS_NAME, "table-main__odds")
                # Это сложно без глубокого анализа DOM.
                # Давай сделаем так: Бот просто будет сообщать РЕЗУЛЬТАТ матча.
                
                msg = (
                    f"📉 <b>DROP {abs(drop_val)}%</b>\n"
                    f"⚽ <b>{match_name}</b>\n"
                    f"🔗 <a href='{link}'>Link</a>"
                )
                
                # Отправляем
                msg_id = send_telegram(msg)
                
                if msg_id:
                    # Сохраняем в базу (по умолчанию ставим pick='?', просто мониторим счет)
                    bets.append({
                        'url': link,
                        'msg_id': msg_id,
                        'pick': '?', 
                        'status': 'pending',
                        'timestamp': time.time()
                    })
                    updated = True
                    existing_urls.append(link)
                    time.sleep(1)
                    
            except: continue
            
    except Exception as e:
        print(f"Ошибка сканера: {e}")
        
    return updated

def run_bot():
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    bets = load_bets()
    driver = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 1. Сначала проверяем результаты старых матчей
        if check_results(driver, bets):
            save_bets(bets)
            
        # 2. Потом ищем новые
        if scan_new_drops(driver, bets):
            save_bets(bets)
            
    except Exception as e:
        print(f"CRASH: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    run_bot()
