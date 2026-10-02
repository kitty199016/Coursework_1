import os
import sys

# Добавляем корень проекта в пути поиска Python
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from datetime import datetime
import pytest
from unittest.mock import patch

# Импортируем функции
from src.views import process_financial_data, get_date_range


# ==========================================
# ФИКСТУРЫ
# ==========================================

@pytest.fixture
def test_date():
    return "2026-05-15"


@pytest.fixture
def mock_transactions_list():
    """Возвращает фиксированный список транзакций, имитирующий файл."""
    return [
        {"date": datetime(2026, 5, 1), "type": "расход", "category": "Супермаркеты", "amount": 1000.4},
        {"date": datetime(2026, 5, 10), "type": "расход", "category": "Рестораны", "amount": 500.1},
        {"date": datetime(2026, 5, 12), "type": "расход", "category": "Наличные", "amount": 2000.0},
        {"date": datetime(2026, 5, 15), "type": "расход", "category": "Переводы", "amount": 3000.0},
        {"date": datetime(2026, 5, 15), "type": "поступление", "category": "Зарплата", "amount": 50000.0},
        {"date": datetime(2026, 5, 20), "type": "расход", "category": "Транспорт", "amount": 300.0}
    ]


# ==========================================
# ТЕСТЫ ДЛЯ get_date_range
# ==========================================

@pytest.mark.parametrize("period, expected_start, expected_end", [
    ("DEFAULT", datetime(2026, 5, 1), datetime(2026, 5, 15)),
    ("W", datetime(2026, 5, 11), datetime(2026, 5, 17)),
    ("M", datetime(2026, 5, 1), datetime(2026, 5, 31)),
    ("Y", datetime(2026, 1, 1), datetime(2026, 12, 31)),
    ("ALL", datetime.min, datetime(2026, 5, 15))
])
def test_get_date_range_valid(test_date, period, expected_start, expected_end):
    start, end = get_date_range(test_date, period)
    assert start == expected_start
    assert end == expected_end


def test_get_date_range_invalid(test_date):
    with pytest.raises(ValueError, match="Неизвестный период"):
        get_date_range(test_date, "UNKNOWN_PERIOD")


# ==========================================
# ТЕСТЫ ГЛАВНОЙ ФУНКЦИИ
# ==========================================

@patch('src.views.load_transactions_from_xls')
@patch('src.views.fetch_cbr_currency_rates')
@patch('src.views.fetch_real_stock_prices')
def test_process_financial_data_with_xls(mock_stocks, mock_currency, mock_load, mock_transactions_list, test_date):
    """Тест парсинга данных и правильности математических расчетов."""
    mock_load.return_value = mock_transactions_list
    mock_currency.return_value = {"USD": 90.0, "EUR": 98.0, "CNY": 12.5}
    mock_stocks.return_value = {"AAPL": 170.0, "MSFT": 400.0}

    response_json = process_financial_data(test_date, "DEFAULT")
    data = json.loads(response_json)

    # 1. Проверка округления до целых и подсчета сумм
    assert data["Расходы"]["Общая сумма"] == 6500
    assert data["Поступления"]["Общая сумма"] == 50000

    # 2. Проверка основных разделов расходов
    assert data["Расходы"]["Основные"]["Супермаркеты"] == 1000
    assert data["Расходы"]["Основные"]["Рестораны"] == 500

    # 3. Проверка блоков Переводы/Наличные и их сортировки
    transfers = data["Расходы"]["Переводы и наличные"]
    assert transfers["Переводы"] == 3000
    assert transfers["Наличные"] == 2000
    assert list(transfers.keys()) == ["Переводы", "Наличные"]

    # 4. Проверка интеграции с API-моками
    assert data["Курс валют"]["USD"] == 90.0
    assert data["Стоимость акций S&P 500"]["AAPL"] == 170.0


@patch('src.views.load_transactions_from_xls')
@patch('src.views.fetch_cbr_currency_rates')
@patch('src.views.fetch_real_stock_prices')
def test_top_7_categories_and_others(mock_stocks, mock_currency, mock_load, test_date):
    """Проверка лимита в 7 категорий и группировки остальных в 'Остальное'."""
    mock_currency.return_value = {"USD": 90.0}
    mock_stocks.return_value = {"AAPL": 170.0}

    # Имитируем 9 разных категорий расходов (каждая по 100 рублей)
    mock_load.return_value = [
        {"date": datetime(2026, 5, 15), "type": "расход", "category": f"Категория_{i}", "amount": 100.0}
        for i in range(1, 10)
    ]

    response_json = process_financial_data(test_date, "M")
    data = json.loads(response_json)
    main_expenses = data["Расходы"]["Основные"]

    # Должно быть ровно 7 уникальных категорий + 1 категория "Остальное"
    assert len(main_expenses) == 8
    assert "Остальное" in main_expenses
    assert main_expenses["Остальное"] == 200
