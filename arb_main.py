import os
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

# Новый источник: BetWatch (Раздел Футбол)
URL = "https://www.betwatch.fr/en/moneyway-1x2-football"

# Минимальная сумма (Евро), чтобы прислать уведомление
MIN_MONEY = 5000  # Для теста поставь 1000, потом увеличь до 20000

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL: return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def parse_money(text):
    """Превращает '15 400 €' в число 15400"""
    try:
        # Убираем € и пробелы
        clean = re.sub(r'[^\d]', '', text)
        return int(clean)
    except: return 0

def run_betwatch():
    print("🚀 Запуск Chrome для BetWatch...")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"🌍 Перехожу на {URL}...")
        driver.get(URL)
        
        # Ждем загрузку таблицы (максимум 15 сек)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table"))
            )
            print("✅ Таблица загрузилась!")
        except:
            print("⚠️ Таймаут ожидания таблицы (возможно, сайт тупит)")

        # Ищем строки таблицы
        rows = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr")
        print(f"📊 Найдено строк: {len(rows)}")
        
        found_matches = 0

        for row in rows:
            try:
                # Получаем текст всей строки
                text = row.text
                
                # Ищем сумму ставок (обычно она в конце или посередине с значком €)
                # На BetWatch структура: Время | Матч | 1 | X | 2 | Объем
                
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 5: continue

                # Название матча (обычно 2-я колонка)
                match_name = cols[1].text.strip()
                
                # Ищем самую большую сумму в ячейках 1, X, 2
                # Обычно это колонки с процентами и суммами.
                # BetWatch показывает суммы при наведении, но часто и текстом.
                # Попробуем найти просто максимальное число с € в строке
                
                money_matches = re.findall(r'(\d[\d\s]*)\s?€', text)
                if not money_matches: continue
                
                # Превращаем все найденные суммы в числа и берем максимум
                amounts = [parse_money(m) for m in money_matches]
                max_amount = max(amounts)
                
                if max_amount >= MIN_MONEY:
                    # Форматируем для красоты
                    pretty_sum = "{:,}".format(max_amount).replace(",", " ")
                    
                    msg = (
                        f"💶 <b>BETWATCH MONEY: {pretty_sum} €</b>\n\n"
                        f"⚽ <b>{match_name}</b>\n"
                        f"💰 Общий объем ставок\n"
                        f"🔗 <a href='{URL}'>Перейти на сайт</a>"
                    )
                    
                    send_telegram(msg)
                    found_matches += 1
                    
                    # Ограничитель, чтобы не спамить (максимум 3 матча за запуск)
                    if found_matches >= 3:
                        print("Лимит отправки за раз достигнут.")
                        break
                        
            except Exception as e:
                continue

        if found_matches == 0:
            print("Матчей с такой суммой не найдено (или парсинг не удался).")
            # Тестовое сообщение, чтобы ты знал, что бот смотрел
            send_telegram(f"🔍 Сканер прошел по BetWatch. Найдено строк: {len(rows)}. Крупных ставок пока нет.")

        driver.quit()

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        send_telegram(f"❌ Ошибка BetWatch: {e}")

if __name__ == "__main__":
    run_betwatch()
