from datetime import datetime, timedelta
import json
import urllib.request
import xml.etree.ElementTree as ET
import yfinance as yf
from typing import Literal
from src.services import load_transactions_from_xls, load_config_json
import pandas as pd

PERIOD = Literal["DEFAULT", "W", "M", "Y", "ALL"]

# ==========================================
# ИНТЕГРАЦИЯ С РЕАЛЬНЫМИ ВНЕШНИМИ API
# ==========================================

def fetch_cbr_currency_rates(date_str: str) -> dict:
    """Получает официальные курсы валют от ЦБ РФ на указанную дату."""
    target_date = datetime.strptime(date_str, "%Y.%m.%d %H:%M:%S")
    cbr_date_str = target_date.strftime("%d/%m/%Y")
    url = f"https://cbr.ru/scripts/XML_daily.asp?date_req={cbr_date_str}"

    target_char_codes = load_config_json()["target_char_codes"]
    rates = load_config_json()["rates"]

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        for valute in root.findall('Valute'):
            char_code = valute.find('CharCode').text
            if char_code in target_char_codes:
                value_str = valute.find('Value').text.replace(',', '.')
                nominal = float(valute.find('Nominal').text.replace(',', '.'))
                rate_per_unit = float(value_str) / nominal
                rates[char_code] = round(rate_per_unit, 2)
        return rates
    except Exception as e:
        print(f"Ошибка API ЦБ РФ ({e}). Использованы базовые значения.")
        return {"USD": 92.50, "EUR": 100.15, "CNY": 12.80}


def fetch_real_stock_prices() -> dict:
    """Получает рыночную стоимость акций из S&P 500 в реальном времени."""
    tickers = load_config_json()["tickers"]
    stock_prices = {}
    try:
        data = yf.download(tickers, period="1d", progress=False)
        for ticker in tickers:
            last_price = data['Close'][ticker].iloc[-1]
            stock_prices[ticker] = round(float(last_price), 2)
        return stock_prices
    except Exception as e:
        print(f"Ошибка API Yahoo Finance ({e}). Использованы базовые значения.")
        return {"AAPL": 175.2, "MSFT": 420.5, "NVDA": 875.0, "AMZN": 180.1}


# ==========================================
# ВЫЧИСЛЕНИЕ ДИАПАЗОНОВ С УЧЕТОМ УСЛОВИЯ
# ==========================================

def get_date_range(date_str: str, period: PERIOD = "DEFAULT"):
    target_date = datetime.strptime(date_str, '%Y.%m.%d %H:%M:%S')

    if period == "DEFAULT":
        # По умолчанию: с начала месяца, на который выпадает дата, по саму дату
        start_date = datetime(target_date.year, target_date.month, 1)
        end_date = target_date
    elif period == "W":
        start_date = target_date - timedelta(days=target_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "M":
        start_date = datetime(target_date.year, target_date.month, 1)
        if target_date.month == 12:
            end_date = datetime(target_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
    elif period == "Y":
        start_date = datetime(target_date.year, 1, 1)
        end_date = datetime(target_date.year, 12, 31)
    elif period == "ALL":
        start_date = datetime.min
        end_date = target_date
    else:
        raise ValueError(f"Неизвестный период: {period}")

    return start_date, end_date

def get_greeting() -> str:
    """Возвращает приветсвие в зависимости от времени суток"""
    current_hour = datetime.now().hour

    if 0 <= current_hour < 6:
        return "Доброй ночи"
    elif 6 <= current_hour < 12:
        return "Доброе утро"
    elif 12 <= current_hour < 18:
        return "Добрый день"
    else:
        return "Добрый вечер"


# ==========================================
# ГЛАВНАЯ ФУНКЦИЯ ОБРАБОТКИ
# ==========================================

def process_financial_data(date_str: str, period: PERIOD = "DEFAULT", file_path: str = "data/operations.xls") -> str:
    try:
        start_date, end_date = get_date_range(date_str, period)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Загружаем "живые" транзакции напрямую из Excel-файла
    transactions = load_transactions_from_xls(file_path)
    # Фильтрация транзачкций
    filtered_tx = [
        tx for _, tx in transactions.iterrows()
        if isinstance(tx["Дата платежа"], str) and start_date <= datetime.strptime(tx["Дата платежа"],
                                                                                   "%d.%m.%Y") <= end_date
    ]
    #Cards
    cards = {}
    for transact in filtered_tx:
        if pd.notna(transact.get("Номер карты")):
            card_num = transact.get("Номер карты")
            if transact.get("Статус") == "OK":
                if (amount := int(transact.get("Сумма платежа"))) < 0:
                    if card_num in cards:
                        cards[card_num]["total_spent"] += abs(amount)
                        if pd.notna(transact.get("Кэшбэк")):
                            cards[card_num]["cashback"] += int(transact.get("Кэшбэк"))
                    else:
                        if pd.notna(transact.get("Кэшбэк")):
                            cashback = int(transact.get("Кэшбэк"))
                        else:
                            cashback = 0
                        cards[card_num] = {"total_spent": abs(amount),
                                           "cashback": cashback}
    cards_out = [{
        "last_digits":cards,
        "total_spent": val["total_spent"],
        "cashback": val["cashback"]} for cards, val in cards.items()]

    #Топ 5 транзакций
    top_transactions_raw = sorted(filtered_tx, key=lambda x: abs(x.get("Сумма платежа")), reverse=True)
    top_transactions = []
    for idx, value in enumerate(top_transactions_raw):
        if idx < 5:
            top_transactions.append({
                "date": value.get("Дата платежа"),
                "amount": value.get("Сумма платежа"),
                "category": value.get("Категория"),
                "description": value.get("Описание")
            })
    # Живые котировки
    live_currency_rates = fetch_cbr_currency_rates(date_str)
    live_stock_prices = fetch_real_stock_prices()

    response_data = {
        "greeting": get_greeting(),
        "cards": [cards_out],
        "top_transactions": top_transactions,
        "currency_rates": live_currency_rates,
        "stock_prices": live_stock_prices
    }

    return json.dumps(response_data, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    # Демонстрационный запуск
    json_result = process_financial_data("2021.05.25 00:00:00", "M")
    print(json_result)
