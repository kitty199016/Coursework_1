from datetime import datetime
import json
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# Импортируем тестируемые функции напрямую из правильного модуля src.views
from src.views import (
    get_date_range,
    get_greeting,
    fetch_cbr_currency_rates,
    fetch_real_stock_prices,
    process_financial_data
)


# Функция-помощник для вычисления ожидаемого приветствия по текущему времени
def get_expected_greeting() -> str:
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
# ТЕСТЫ ДЛЯ ВЫЧИСЛЕНИЯ ДИАПАЗОНОВ ДАТ
# ==========================================

@pytest.mark.parametrize(
    "date_str, period, expected_start, expected_end",
    [
        ("2021.05.25 00:00:00", "DEFAULT", datetime(2021, 5, 1), datetime(2021, 5, 25)),
        ("2021.05.25 00:00:00", "W", datetime(2021, 5, 24), datetime(2021, 5, 30)),
        ("2021.05.25 00:00:00", "M", datetime(2021, 5, 1), datetime(2021, 5, 31)),
        ("2021.12.10 00:00:00", "M", datetime(2021, 12, 1), datetime(2021, 12, 31)),
        ("2021.05.25 00:00:00", "Y", datetime(2021, 1, 1), datetime(2021, 12, 31)),
        ("2021.05.25 00:00:00", "ALL", datetime.min, datetime(2021, 5, 25)),
    ]
)
def test_get_date_range_valid(date_str, period, expected_start, expected_end):
    start, end = get_date_range(date_str, period)
    assert start == expected_start
    assert end == expected_end


def test_get_date_range_invalid_period():
    with pytest.raises(ValueError, match="Неизвестный период: INVALID"):
        get_date_range("2021.05.25 00:00:00", "INVALID")


# ==========================================
# ТЕСТ ПРИВЕТСТВИЯ ПО ТЕКУЩЕМУ ВРЕМЕНИ
# ==========================================

def test_get_greeting_current_time():
    """Тестирует приветствие на основе текущего системного времени."""
    assert get_greeting() == get_expected_greeting()


# ==========================================
# ТЕСТЫ ДЛЯ ВНЕШНИХ API (MOCKING)
# ==========================================

@patch("urllib.request.urlopen")
def test_fetch_cbr_currency_rates_success(mock_urlopen):
    xml_response = b"""<?xml version="1.0" encoding="windows-1251"?>
    <ValCurs Date="25.05.2021" name="Foreign Currency Market">
        <Valute ID="R01235"><CharCode>USD</CharCode><Nominal>1</Nominal><Value>73,5021</Value></Valute>
        <Valute ID="R01239"><CharCode>EUR</CharCode><Nominal>1</Nominal><Value>89,3012</Value></Valute>
        <Valute ID="R01375"><CharCode>CNY</CharCode><Nominal>10</Nominal><Value>114,2035</Value></Valute>
    </ValCurs>"""

    mock_context = MagicMock()
    mock_context.read.return_value = xml_response
    mock_urlopen.return_value.__enter__.return_value = mock_context

    rates = fetch_cbr_currency_rates("2021.05.25 00:00:00")
    assert rates["USD"] == 73.50
    assert rates["EUR"] == 89.30
    assert rates["CNY"] == 11.42


@patch("urllib.request.urlopen")
def test_fetch_cbr_currency_rates_fallback(mock_urlopen):
    mock_urlopen.side_effect = Exception("Сетевой сбой")
    rates = fetch_cbr_currency_rates("2021.05.25 00:00:00")
    assert rates == {"USD": 92.50, "EUR": 100.15, "CNY": 12.80}


@patch("yfinance.download")
def test_fetch_real_stock_prices_success(mock_download):
    mock_df = pd.DataFrame(
        [[175.2, 420.5, 875.0, 180.1]],
        columns=pd.MultiIndex.from_tuples([('Close', 'AAPL'), ('Close', 'MSFT'), ('Close', 'NVDA'), ('Close', 'AMZN')])
    )
    mock_download.return_value = mock_df

    prices = fetch_real_stock_prices()
    assert prices["AAPL"] == 175.20
    assert prices["MSFT"] == 420.50


# ==========================================
# ТЕСТ ИНТЕГРАЦИИ ГЛАВНОЙ ФУНКЦИИ
# ==========================================

@patch("src.views.load_transactions_from_xls")
@patch("src.views.fetch_cbr_currency_rates")
@patch("src.views.fetch_real_stock_prices")
def test_process_financial_data(mock_stocks, mock_currency, mock_load_xls):
    """Тест интеграционной функции с динамической сверкой времени."""

    # Задаем стабильные ответы для внешних API
    mock_currency.return_value = {"USD": 100.0, "EUR": 110.0, "CNY": 13.0}
    mock_stocks.return_value = {"AAPL": 200.0, "MSFT": 400.0}

    # Подготавливаем тестовые данные (одна транзакция траты, одна дохода, одна отмененная)
    mock_data = [
        {"Дата платежа": "20.05.2021", "Номер карты": "*1111", "Статус": "OK", "Сумма платежа": -5000, "Кэшбэк": 100,
         "Категория": "Супермаркеты", "Описание": "Ашан"},
        {"Дата платежа": "21.05.2021", "Номер карты": "*1111", "Статус": "OK", "Сумма платежа": 10000, "Кэшбэк": 0,
         "Категория": "Пополнения", "Описание": "Зарплата"},
        {"Дата платежа": "22.05.2021", "Номер карты": "*1111", "Статус": "FAILED", "Сумма платежа": -2000, "Кэшбэк": 0,
         "Категория": "Одежда", "Описание": "Zara"}
    ]

    mock_df = MagicMock()
    mock_df.iterrows.return_value = [(i, pd.Series(item)) for i, item in enumerate(mock_data)]
    mock_load_xls.return_value = mock_df

    # Запускаем функцию обработки
    result_json = process_financial_data("2021.05.25 00:00:00", "M", "fake_path.xls")
    result = json.loads(result_json)

    # 1. Проверяем greeting на соответствие реальному текущему времени компьютера
    assert result["greeting"] == get_expected_greeting()

    # 2. Проверяем валюту
    assert result["currency_rates"]["USD"] == 100.0

    # 3. Проверяем карты с учетом вложенной структуры списков в вашем исходном коде: [ [ {..} ] ]
    assert "cards" in result
    assert len(result["cards"]) == 1

    inner_cards_list = result["cards"][0]
    assert len(inner_cards_list) == 1

    target_card = inner_cards_list[0]
    assert target_card["last_digits"] == "*1111"
    assert target_card["total_spent"] == 5000
    assert target_card["cashback"] == 100

    # 4. Проверяем топ-транзакции (сортируются по модулю суммы платежа)
    assert len(result["top_transactions"]) == 3
    assert result["top_transactions"][0]["description"] == "Зарплата"


def test_process_financial_data_error_flow():
    result_json = process_financial_data("2021.05.25 00:00:00", "INVALID")
    result = json.loads(result_json)
    assert "error" in result
