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

# Новый источник: Oddstake (Раздел Moneyway)
URL = "https://www.oddstake.com/moneyway.html"

# Минимальная сумма (объем) в евро
MIN_MONEY = 1000  # Для теста - 1000. Потом поставь 10000 или выше.

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def parse_money(text):
    """Превращает '10.5K €' или '10,500' в число"""
    try:
        # Убираем всё лишнее
        clean = text.upper().replace("€", "").replace("EUR", "").strip()
        
        # Если есть K (тысячи), например 10K
        if "K" in clean:
            clean = clean.replace("K", "")
            return int(float(clean) * 1000)
            
        # Если просто число с запятой или точкой
        clean = re.sub(r'[^\d]', '', clean)
        return int(clean)
    except:
        return 0

def run_oddstake():
    print("🚀 Запуск сканера Oddstake...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Маскируемся под обычный ПК
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"🌍 Иду на {URL}...")
        driver.get(URL)
        time.sleep(10) # Ждем прогрузки
        
        # Проверяем заголовок, чтобы убедиться, что сайт открылся
        print(f"Заголовок: {driver.title}")

        # Ищем таблицу (на Oddstake она обычно имеет id="moneyway_table" или просто большая таблица)
        rows = driver.find_elements(By.CSS_SELECTOR, "tr")
        print(f"📊 Найдено строк: {len(rows)}")
        
        if len(rows) < 5:
            send_telegram("⚠️ Oddstake открылся, но таблица пустая.")
            driver.quit()
            return

        matches_found = 0

        for row in rows:
            try:
                text = row.text
                # Ищем значок €
                if "€" not in text: continue
                
                # Разбиваем строку на части
                # Пример строки: "20:00 Real Madrid vs Barcelona 100K € ..."
                
                # Ищем все денежные суммы в строке
                # Регулярка ищет числа, за которыми (сразу или через пробел) стоит €
                money_list = re.findall(r'(\d+[K\d\.,]*)\s?€', text)
                
                if not money_list: continue
                
                # Превращаем в числа и берем максимум
                amounts = [parse_money(m) for m in money_list]
                max_amount = max(amounts)
                
                if max_amount >= MIN_MONEY:
                    # Пытаемся вытащить название матча
                    # Обычно это текст в начале строки
                    parts = text.split("€")[0] # Берем всё до первого значка евро
                    match_name = parts[-50:] # Берем последние 50 символов перед деньгами (там название)
                    
                    # Чистим название от мусора
                    match_name = re.sub(r'\d{2}:\d{2}', '', match_name).strip() # Убираем время
                    
                    # Форматируем сумму
                    pretty_sum = "{:,}".format(max_amount).replace(",", " ")
                    
                    msg = (
                        f"💶 <b>ODDSTAKE MONEY: {pretty_sum} €</b>\n\n"
                        f"⚽ <b>{match_name}</b>\n"
                        f"🔗 <a href='{URL}'>Открыть сайт</a>"
                    )
                    
                    print(f"Нашел: {match_name} - {pretty_sum}")
                    send_telegram(msg)
                    matches_found += 1
                    
                    if matches_found >= 3:
                        break # Не спамим больше 3 за раз
                        
            except Exception as e:
                continue

        if matches_found == 0:
            print("Матчи не найдены.")
            # Раскомментируй строку ниже, если хочешь видеть отчет каждый раз
            # send_telegram(f"✅ Oddstake проверен. Строк: {len(rows)}. Крупных денег нет.")

        driver.quit()

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        send_telegram(f"❌ Ошибка Oddstake: {e}")

if __name__ == "__main__":
    run_oddstake()
