import os
import sys
from unittest.mock import patch
import pandas as pd
import pytest
import re
from src.services import search_for_transfers_to_individuals

# Добавляем корень проекта в пути поиска Python
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
from datetime import datetime
import pytest
from unittest.mock import patch

# Импортируем из нового сервисного модуля
from src.services import high_yield_cashback_categories


@pytest.fixture
def mock_transactions_list():
    return [
        {"date": datetime(2026, 5, 1), "type": "расход", "category": "Супермаркеты", "amount": 10000.0},
        {"date": datetime(2026, 5, 4), "type": "расход", "category": "Рестораны", "amount": 5000.0},
        {"date": datetime(2026, 5, 10), "type": "расход", "category": "Супермаркеты", "amount": 2000.0},
        {"date": datetime(2026, 5, 15), "type": "расход", "category": "Переводы", "amount": 8000.0},
        {"date": datetime(2026, 6, 1), "type": "расход", "category": "Рестораны", "amount": 3000.0},
    ]


@patch('src.services.load_transactions_from_xls')
def test_high_yield_cashback_categories_from_file(mock_load, mock_transactions_list):
    """Тест анализа кэшбэка при автоматическом чтении из файла в src.services."""
    mock_load.return_value = mock_transactions_list

    # Вызываем функцию без передачи data, чтобы сработал триггер чтения файла
    result_json = high_yield_cashback_categories(data=None, year=2026, month=5)
    data = json.loads(result_json)

    # Проверяем расчеты (5%): Супермаркеты (12000 * 0.05 = 600), Рестораны (5000 * 0.05 = 250)
    assert data["Супермаркеты"] == 600
    assert data["Рестораны"] == 250
    assert "Переводы" not in data

    # Проверка сортировки по убыванию прибыли
    assert list(data.keys()) == ["Супермаркеты", "Рестораны"]


@pytest.fixture
def mock_excel_data():
    """Фикстура, которая имитирует содержимое Excel-файла."""
    return pd.DataFrame(
        [
            {
                "category": "Переводы",
                "description": "Валерий А.",
                "amount": 1500,
            },  # Подходит
            {
                "category": "Супермаркеты",
                "description": "Пятерочка",
                "amount": 450,
            },  # Не та категория
            {
                "category": "Переводы",
                "description": "Сергей З.",
                "amount": 300,
            },  # Подходит
            {
                "category": "Переводы",
                "description": "Оплата ЖКХ",
                "amount": 2800,
            },  # Не имя физлица
            {
                "category": "Переводы",
                "description": "Артем П.",
                "amount": 10000,
            },  # Подходит
            {
                "category": "Переводы",
                "description": "Перевод между своими счетами",
                "amount": 5000,
            },  # Не имя физлица
            {
                "category": "Переводы",
                "description": "Иван Иванович",
                "amount": 100,
            },  # Нет точки и фамилия целиком
            {
                "category": "Переводы",
                "description": "петр С.",
                "amount": 200,
            },  # Имя со строчной буквы
        ]
    )


@patch("pandas.read_excel")
def test_search_transfers_success(mock_read_excel, mock_excel_data):
    """Тест успешного поиска и фильтрации транзакций."""
    # Подменяем возвращаемое значение pd.read_excel нашим фейковым датафреймом
    mock_read_excel.return_value = mock_excel_data

    result = search_for_transfers_to_individuals()

    # Проверяем, что в результате ровно 3 транзакции (Валерий А., Сергей З., Артем П.)
    assert "transactions" in result
    assert len(result["transactions"]) == 3

    # Проверяем конкретные имена в отфильтрованном результате
    descriptions = [tx["description"] for tx in result["transactions"]]
    assert "Валерий А." in descriptions
    assert "Сергей З." in descriptions
    assert "Артем П." in descriptions
    assert "Оплата ЖКХ" not in descriptions


@patch("pandas.read_excel")
def test_search_transfers_file_not_found(mock_read_excel):
    """Тест поведения функции, если файл отсутствует на диске."""
    # Имитируем ошибку отсутствия файла
    mock_read_excel.side_effect = FileNotFoundError()

    result = search_for_transfers_to_individuals()

    assert "error" in result
    assert "не найден" in result["error"]


@patch("pandas.read_excel")
def test_search_transfers_empty_file(mock_read_excel):
    """Тест поведения функции, если Excel файл пустой."""
    # Возвращаем пустой датафрейм
    mock_read_excel.return_value = pd.DataFrame(
        columns=["category", "description", "amount"]
    )

    result = search_for_transfers_to_individuals()

    assert "transactions" in result
    assert len(result["transactions"]) == 0
