from datetime import datetime, timedelta
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
import pandas as pd
import yfinance as yf


# ==========================================
# ЧТЕНИЕ ДАННЫХ ИЗ EXCEL (.XLS)
# ==========================================

def load_transactions_from_xls(file_path: str = "data/operations.xls") -> list:
    """
    Загружает транзакции из Excel-файла (.xls).
    Ожидает колонки: 'Дата', 'Тип', 'Категория', 'Сумма'.
    """
    if not os.path.exists(file_path):
        print(f"Предупреждение: Файл {file_path} не найден. Используются пустые данные.")
        return []

    try:
        # Читаем .xls с помощью pandas (движок xlrd)
        df = pd.read_excel(file_path, engine='xlrd')

        # Приводим названия колонок к единому регистру и удаляем лишние пробелы
        df.columns = [str(col).strip().lower() for col in df.columns]

        # Маппинг колонок (поддерживает как русские, так и английские названия)
        col_mapping = {
            'дата': 'date', 'date': 'date',
            'тип': 'type', 'type': 'type',
            'категория': 'category', 'category': 'category',
            'сумма': 'amount', 'amount': 'amount'
        }
        df = df.rename(columns=col_mapping)

        # Фильтруем только нужные колонки
        required_cols = ['date', 'type', 'category', 'amount']
        df = df[[col for col in required_cols if col in df.columns]]

        # Приведение типов данных
        df['date'] = pd.to_datetime(df['date'])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['type'] = df['type'].astype(str).str.strip().str.lower()
        df['category'] = df['category'].astype(str).str.strip()

        # Приведение значений типа ('расход' / 'поступление') к стандарту
        type_map = {'расход': 'расход', 'expense': 'расход', 'поступление': 'поступление', 'income': 'поступление'}
        df['type'] = df['type'].map(type_map).fillna('расход')

        # Превращаем DataFrame в список словарей для обработки нашей логикой
        transactions = []
        for _, row in df.iterrows():
            transactions.append({
                "date": row['date'].to_pydatetime(),
                "type": row['type'],
                "category": row['category'],
                "amount": float(row['amount'])
            })
        return transactions
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        return []


# ==========================================
# ИНТЕГРАЦИЯ С РЕАЛЬНЫМИ ВНЕШНИМИ API
# ==========================================

def fetch_cbr_currency_rates(date_str: str) -> dict:
    """Получает официальные курсы валют от ЦБ РФ на указанную дату."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d")
    cbr_date_str = target_date.strftime("%d/%m/%Y")
    url = f"https://cbr.ru{cbr_date_str}"

    target_char_codes = {"USD", "EUR", "CNY"}
    rates = {"USD": 0.0, "EUR": 0.0, "CNY": 0.0}

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
    tickers = ["AAPL", "MSFT", "NVDA", "AMZN"]
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

def get_date_range(date_str: str, period: str = "DEFAULT"):
    target_date = datetime.strptime(date_str, "%Y-%m-%d")

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


# ==========================================
# ГЛАВНАЯ ФУНКЦИЯ ОБРАБОТКИ
# ==========================================

def process_financial_data(date_str: str, period: str = "DEFAULT", file_path: str = "data/operations.xls") -> str:
    try:
        start_date, end_date = get_date_range(date_str, period)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

    # Загружаем "живые" транзакции напрямую из Excel-файла
    transactions = load_transactions_from_xls(file_path)

    # Фильтрация транзакций
    filtered_tx = [tx for tx in transactions if start_date <= tx["date"] <= end_date]

    expenses_main = {}
    expenses_transfers = {"Наличные": 0, "Переводы": 0}
    incomes_main = {}
    total_expenses, total_incomes = 0, 0

    for tx in filtered_tx:
        amount = tx["amount"]
        category = tx["category"]

        if tx["type"] == "расход":
            total_expenses += amount
            if category in ["Наличные", "Переводы"]:
                expenses_transfers[category] += amount
            else:
                expenses_main[category] = expenses_main.get(category, 0) + amount
        elif tx["type"] == "поступление":
            total_incomes += amount
            incomes_main[category] = incomes_main.get(category, 0) + amount

    # Обработка основных расходов (Топ-7 + Остальное)
    sorted_exp_main = sorted(expenses_main.items(), key=lambda x: x[1], reverse=True)
    top_7_exp = sorted_exp_main[:7]
    others_exp = sorted_exp_main[7:]

    formatted_exp_main = {cat: round(amt) for cat, amt in top_7_exp}
    if others_exp:
        formatted_exp_main["Остальное"] = round(sum(amt for _, amt in others_exp))

    # Обработка переводов и наличных
    sorted_transfers = sorted(expenses_transfers.items(), key=lambda x: x[1], reverse=True)
    formatted_transfers = {cat: round(amt) for cat, amt in sorted_transfers}

    # Обработка поступлений
    sorted_inc_main = sorted(incomes_main.items(), key=lambda x: x[1], reverse=True)
    formatted_inc_main = {cat: round(amt) for cat, amt in sorted_inc_main}

    # Живые котировки
    live_currency_rates = fetch_cbr_currency_rates(date_str)
    live_stock_prices = fetch_real_stock_prices()

    response_data = {
        "Расходы": {
            "Общая сумма": round(total_expenses),
            "Основные": formatted_exp_main,
            "Переводы и наличные": formatted_transfers
        },
        "Поступления": {
            "Общая сумма": round(total_incomes),
            "Основные": formatted_inc_main
        },
        "Курс валют": live_currency_rates,
        "Стоимость акций S&P 500": live_stock_prices
    }

    return json.dumps(response_data, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    # Демонстрационный запуск
    json_result = process_financial_data("2026-05-15", "M")
    print(json_result)
