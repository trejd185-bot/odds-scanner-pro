import json, os, time, random, cloudscraper, requests
from bs4 import BeautifulSoup

TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")
URL = "https://www.betexplorer.com/dropping-odds/"
HISTORY_FILE = "history.json"
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
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    try:
        resp = scraper.get(URL)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            for row in soup.select('.table-main__tr'):
                try:
                    link = row.select_one('.table-main__tt a')
                    if not link: continue
                    url = link['href']
                    name = link.text.strip()
                    drop = abs(float(row.select_one('.table-main__drop').text.replace('%', '')))
                    odd = row.select('.table-main__odds')[-1].text.strip()
                    
                    if drop >= MIN_DROP and url not in history:
                        icon = "🎮" if "esports" in url else "⚽"
                        msg = f"🚨 <b>BETEXPLORER: {drop}%</b>\n\n{icon} <b>{name}</b>\n🔻 Падение: {drop}%\n💰 КФ: {odd}\n🔗 <a href='https://www.betexplorer.com{url}'>Link</a>"
                        send_telegram(msg)
                        new_history.append(url)
                        time.sleep(2)
                except: continue
    except Exception as e: print(e)
    save_history(new_history)

if __name__ == "__main__": run()
