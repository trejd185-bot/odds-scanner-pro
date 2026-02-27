import json, os, time, random, cloudscraper, requests
from bs4 import BeautifulSoup

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
URL = "https://www.arbworld.net/en/dropping-odds"
HISTORY_FILE = "arb_history.json"
MIN_DROP = 10.0

def save_history(data):
    try:
        with open(HISTORY_FILE, 'w') as f: json.dump(data[-200:], f)
    except: pass

def send_telegram(text):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                  json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})

def run():
    try:
        with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    except: history = []
    
    new_history = history.copy()
    scraper = cloudscraper.create_scraper(browser={'browser': 'firefox', 'platform': 'windows', 'mobile': False})
    
    try:
        resp = scraper.get(URL)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            table = soup.find('table', class_='items')
            if table:
                for row in table.find_all('tr'):
                    try:
                        cols = row.find_all('td')
                        if len(cols) < 8: continue
                        name = cols[2].get_text(strip=True)
                        link = cols[2].find('a')['href'] if cols[2].find('a') else name
                        
                        best_drop, old_k, new_k = 0, 0, 0
                        for col in [cols[5], cols[6], cols[7]]: # 1, X, 2 columns
                            parts = col.get_text(" ", strip=True).split()
                            if len(parts) >= 2:
                                s, c = float(parts[0]), float(parts[1])
                                if s > c:
                                    drop = ((s - c) / s) * 100
                                    if drop > best_drop: best_drop, old_k, new_k = drop, s, c
                        
                        if best_drop >= MIN_DROP and link not in history:
                            msg = f"🌍 <b>ARBWORLD: {best_drop:.1f}%</b>\n\n⚽ <b>{name}</b>\n📉 {old_k} ➔ {new_k}\n🔗 <a href='https://www.arbworld.net{link}'>Link</a>"
                            send_telegram(msg)
                            new_history.append(link)
                            time.sleep(2)
                    except: continue
    except Exception as e: print(e)
    save_history(new_history)

if __name__ == "__main__": run()
