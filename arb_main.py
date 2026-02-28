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

# Ссылки на популярные ставки (где много денег)
SPORTS = {
    '⚽ Футбол': "https://www.betexplorer.com/popular-bets/soccer/",
    '🏀 Баскетбол': "https://www.betexplorer.com/popular-bets/basketball/",
    '🎾 Теннис': "https://www.betexplorer.com/popular-bets/tennis/",
    '🏒 Хоккей': "https://www.betexplorer.com/popular-bets/hockey/"
}

def send_telegram(text):
    print(f"📤 TG: {text}")
    if not TG_TOKEN or not TG_CHANNEL:
        print("❌ НЕТ ТОКЕНА")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                      json={'chat_id': TG_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
    except Exception as e: print(f"Err TG: {e}")

def run_debug_scanner():
    # 1. ПРОВЕРКА СВЯЗИ
    send_telegram("🚀 <b>Запуск сканера...</b>\nПроверяю все виды спорта.")

    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        total_found = 0

        for sport_name, url in SPORTS.items():
            print(f"🌍 Иду в {sport_name}...")
            try:
                driver.get(url)
                time.sleep(5) # Ждем загрузку
                
                # Ищем таблицу
                rows = driver.find_elements(By.CSS_SELECTOR, "table.table-main tr")
                print(f"{sport_name}: Найдено строк {len(rows)}")
                
                if len(rows) < 2:
                    continue

                sport_count = 0
                # Проходим по строкам (пропуская заголовок)
                for row in rows[1:]:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        # Обычно 4 или 5 колонок
                        if len(cols) < 3: continue
                        
                        match_text = cols[0].text.strip() # Название
                        pick = cols[1].text.strip()       # Исход
                        odd = cols[2].text.strip()        # Кэф
                        
                        # Ссылка
                        try:
                            link = cols[0].find_element(By.TAG_NAME, "a").get_attribute("href")
                        except:
                            link = url

                        # Формируем сообщение
                        msg = (
                            f"🔥 <b>POPULAR {sport_name}</b>\n"
                            f"🏟 <b>{match_text}</b>\n"
                            f"👉 Ставка на: <b>{pick}</b>\n"
                            f"💰 Кэф: {odd}\n"
                            f"🔗 <a href='{link}'>Открыть</a>"
                        )
                        
                        send_telegram(msg)
                        sport_count += 1
                        total_found += 1
                        
                        # Лимит 2 матча на спорт (для теста)
                        if sport_count >= 2:
                            break
                    except:
                        continue
                        
            except Exception as e:
                print(f"Ошибка в {sport_name}: {e}")
                continue

        if total_found == 0:
            send_telegram("⚠️ Сканер прошел все ссылки, но популярных матчей сейчас нет (таблицы пустые).")
        else:
            send_telegram(f"🏁 <b>Сканирование завершено.</b> Найдено матчей: {total_found}")

    except Exception as e:
        send_telegram(f"❌ <b>Критическая ошибка бота:</b>\n{str(e)}")
    
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    run_debug_scanner()
