import os
import time
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- НАСТРОЙКИ ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHANNEL = os.environ.get("TG_CHANNEL")

# Источник: BetWatch
URL = "https://www.betwatch.fr/en/moneyway-1x2-football"

# Минимальная сумма (объем рынка) в евро
MIN_MONEY = 1000  # Поставь пока 1000 для теста, потом подними до 20000

# Файл истории (чтобы не спамить одним и тем же)
HISTORY_FILE = "history_money.txt"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return f.read().splitlines()
    return []

def save_history(match_name):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{match_name}\n")

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def parse_money(text):
    """Ищет числа перед знаком €"""
    # Находит все варианты: 10 000€, 10000 €, 5.5K €
    try:
        # Удаляем всё кроме цифр и значка евро
        clean_text = text.replace(" ", "")
        if "€" in clean_text:
            # Вытаскиваем число перед евро
            matches = re.findall(r'(\d+)€', clean_text)
            if matches:
                # Берем самое большое число в строке (там может быть несколько)
                return max([int(m) for m in matches])
    except:
        pass
    return 0

def run_scanner():
    print("🚀 Запуск 'Всеядного' сканера...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"🌍 Иду на {URL}...")
        driver.get(URL)
        
        # Ждем 20 секунд (на всякий случай, если интернет медленный)
        time.sleep(20)
        
        # Берем ВСЕ строки на сайте (тег <tr>), не глядя на классы
        rows = driver.find_elements(By.TAG_NAME, "tr")
        print(f"📊 Всего строк (TR) на сайте: {len(rows)}")
        
        if len(rows) < 5:
            # Если строк мало, значит сайт не прогрузил таблицу
            body_text = driver.find_element(By.TAG_NAME, "body").text[:200]
            send_telegram(f"⚠️ Таблица пустая. Текст на сайте:\n{body_text}")
            driver.quit()
            return

        history = load_history()
        matches_found = 0

        for row in rows:
            text = row.text
            
            # Если в строке нет значка евро, пропускаем
            if "€" not in text:
                continue

            # Пытаемся найти сумму
            money = parse_money(text)
            
            if money >= MIN_MONEY:
                # Пытаемся найти название матча (обычно там есть время типа 20:00 или : )
                # Или просто берем первые слова строки
                lines = text.split('\n')
                match_name = lines[0] if len(lines) > 0 else "Unknown Match"
                
                # Проверка на дубликат
                if match_name in history:
                    continue
                
                # Форматируем сумму
                pretty_sum = "{:,}".format(money).replace(",", " ")
                
                msg = (
                    f"💶 <b>MONEY DETECTED: {pretty_sum} €</b>\n\n"
                    f"⚽ <b>{match_name}</b>\n"
                    f"🔗 <a href='{URL}'>Смотреть BetWatch</a>"
                )
                
                send_telegram(msg)
                save_history(match_name)
                matches_found += 1
                
                # Лимит 3 сообщения за раз
                if matches_found >= 3:
                    print("Лимит сообщений.")
                    break

        if matches_found == 0:
            print("Матчи с деньгами не найдены (или уже были отправлены).")
            # Можно раскомментировать для теста:
            # send_telegram(f"🔍 Сканер жив. Проверил {len(rows)} строк. Новых денег >{MIN_MONEY}€ нет.")

        driver.quit()

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        send_telegram(f"❌ Ошибка скрипта: {e}")

if __name__ == "__main__":
    run_scanner()
