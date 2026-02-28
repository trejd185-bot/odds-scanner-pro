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
BETS_FILE = "bets.json"

# URL для падающих кэфов
URL_DROPS = "https://www.betexplorer.com/dropping-odds/"
# URL для денег (Oddsalert Moneyway)
URL_MONEY = "https://www.oddsalert.com/moneyway"

MIN_DROP = 15.0  # Падение > 15%
MIN_MONEY = 5000 # Сумма > 5000 евро (для теста)

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
    payload = {'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if reply_to: payload['reply_to_message_id'] = reply_to
    try:
        r = requests.post(url, json=payload)
        resp = r.json()
        if resp.get('ok'): return resp['result']['message_id']
    except Exception as e: print(f"TG Err: {e}")
    return None

# --- СКАНЕР ДЕНЕГ (Oddsalert) ---
def scan_moneyway(driver, bets):
    print("💶 Сканирую Oddsalert Moneyway...")
    updated = False
    existing_urls = [b.get('url', '') for b in bets]
    
    try:
        driver.get(URL_MONEY)
        time.sleep(10) # Ждем прогрузки
        
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        print(f"Moneyway строк: {len(rows)}")
        
        for row in rows:
            try:
                text = row.text
                if "€" not in text: continue
                
                # Ищем сумму (например 10K €)
                money_match = re.search(r'(\d+[K\d\.,]*)\s?€', text)
                if not money_match: continue
                
                money_raw = money_match.group(1)
                
                # Парсим число
                try:
                    clean = money_raw.replace('K', '000').replace('.', '').replace(',', '')
                    amount = int(clean)
                except: continue
                
                if amount < MIN_MONEY: continue
                
                # Ссылка на матч
                try:
                    link_el = row.find_element(By.TAG_NAME, "a")
                    link = link_el.get_attribute("href")
                    match_name = link_el.text.strip()
                except: continue
                
                if link in existing_urls: continue
                
                # Формируем сообщение
                pretty_sum = "{:,}".format(amount).replace(",", " ")
                msg = (
                    f"💶 <b>BIG MONEY: {pretty_sum} €</b>\n"
                    f"⚽ <b>{match_name}</b>\n"
                    f"🔗 <a href='{link}'>Link</a>"
                )
                
                msg_id = send_telegram(msg)
                if msg_id:
                    bets.append({
                        'url': link,
                        'msg_id': msg_id,
                        'type': 'money',
                        'status': 'pending',
                        'timestamp': time.time()
                    })
                    updated = True
                    existing_urls.append(link)
                    time.sleep(1)
                    
            except: continue
            
    except Exception as e:
        print(f"Moneyway Error: {e}")
        
    return updated

# --- СКАНЕР ПАДЕНИЙ (BetExplorer) ---
def scan_drops(driver, bets):
    print("📉 Сканирую BetExplorer Drops...")
    updated = False
    existing_urls = [b.get('url', '') for b in bets]
    
    try:
        driver.get(URL_DROPS)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-main tr")))
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
        
        for row in rows:
            try:
                try:
                    drop_el = row.find_element(By.CLASS_NAME, "table-main__drop")
                    drop_val = float(drop_el.text.strip().replace('%', ''))
                except: continue
                
                if abs(drop_val) < MIN_DROP: continue
                
                cols = row.find_elements(By.TAG_NAME, "td")
                link_el = cols[0].find_element(By.TAG_NAME, "a")
                link = link_el.get_attribute("href")
                match_name = link_el.text.strip()
                
                if link in existing_urls: continue
                
                msg = (
                    f"📉 <b>DROP {abs(drop_val)}%</b>\n"
                    f"⚽ <b>{match_name}</b>\n"
                    f"🔗 <a href='{link}'>Link</a>"
                )
                
                msg_id = send_telegram(msg)
                if msg_id:
                    bets.append({
                        'url': link,
                        'msg_id': msg_id,
                        'type': 'drop',
                        'status': 'pending',
                        'timestamp': time.time()
                    })
                    updated = True
                    existing_urls.append(link)
                    time.sleep(1)
            except: continue
    except Exception as e:
        print(f"Drop Error: {e}")
        
    return updated

# --- ПРОВЕРКА РЕЗУЛЬТАТОВ ---
def check_results(driver, bets):
    print("🏁 Проверка результатов...")
    updated = False
    now = time.time()
    
    for bet in bets:
        # Проверяем только 'pending' матчи
        if bet.get('status') != 'pending': continue
        
        # Если прошло меньше 2 часов (7200 сек) с момента отправки, скорее всего матч еще идет
        # Но для теста проверим всё
        # if (now - bet['timestamp']) < 3600: continue
        
        url = bet['url']
        msg_id = bet['msg_id']
        
        try:
            driver.get(url)
            # Ждем прогрузки счета
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "js-score")))
                score_text = driver.find_element(By.ID, "js-score").text.strip()
                status_text = driver.find_element(By.ID, "match-status-caption").text.strip()
            except: continue # Еще не начался или ошибка
            
            # Если матч завершен
            if "Finished" in status_text or "After" in status_text:
                reply_text = f"🏁 <b>МАТЧ ЗАВЕРШЕН</b>\nСчет: <b>{score_text}</b>"
                send_telegram(reply_text, reply_to=msg_id)
                
                bet['status'] = 'finished'
                updated = True
                time.sleep(1)
                
        except: continue
        
    return updated

def run_all():
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
        
        # 1. Сначала Moneyway
        if scan_moneyway(driver, bets): save_bets(bets)
        
        # 2. Потом Drops
        if scan_drops(driver, bets): save_bets(bets)
        
        # 3. Потом Проверка результатов
        if check_results(driver, bets): save_bets(bets)

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    run_all()
