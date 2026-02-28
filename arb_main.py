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
URL = "https://www.arbworld.net/en/moneyway"

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL:
        print("❌ ОШИБКА: Нет токена/канала!")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML'})
    except Exception as e:
        print(f"Ошибка ТГ: {e}")

def run_selenium():
    print("🚀 Запуск Chrome (Selenium)...")
    
    # Настройка браузера для GitHub Actions
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Без графики
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") # Скрываем, что мы робот
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    try:
        # Установка драйвера
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"🌍 Перехожу на {URL}...")
        driver.get(URL)
        
        # Ждем 10 секунд, чтобы сайт прогрузился и прошла проверка Cloudflare
        time.sleep(10)
        
        # Получаем заголовок страницы для проверки
        title = driver.title
        print(f"Заголовок сайта: {title}")
        
        # Ищем таблицу
        rows = driver.find_elements(By.CSS_SELECTOR, "table.items tr")
        print(f"📊 Найдено строк: {len(rows)}")
        
        if "Just a moment" in title or len(rows) == 0:
            print("⛔ Попали на капчу Cloudflare или сайт не прогрузился.")
            # Делаем скриншот для отладки (в логах его не увидеть, но сам факт полезен)
            send_telegram(f"⚠️ Arbworld блокирует доступ (Title: {title}). Попробуй перезапуск.")
        else:
            # Если строки найдены - пробуем взять первый матч
            try:
                first_row = rows[1].text
                send_telegram(f"✅ УСПЕХ! Selenium пробил защиту.\nПервая строка данных:\n{first_row[:100]}...")
            except:
                send_telegram("✅ Сайт открылся, но таблица странная.")

        driver.quit()

    except Exception as e:
        print(f"❌ Ошибка Selenium: {e}")
        send_telegram(f"❌ Ошибка бота: {e}")

if __name__ == "__main__":
    run_selenium()
