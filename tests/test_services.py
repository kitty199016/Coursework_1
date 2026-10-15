from datetime import datetime
import json
import pytest
from unittest.mock import patch
import pandas as pd
import os

# Импортируем тестируемые функции и исключения
from src.services import (
    load_transactions_from_xls,
    high_yield_cashback_categories,
    search_for_transfers_to_individuals,
    FileError
)


# ==========================================
# ТЕСТЫ ДЛЯ ФУНКЦИИ load_transactions_from_xls
# ==========================================

def test_load_transactions_from_xls_not_found():
    """Проверка генерации FileNotFoundError, если файла не существует."""
    # Обновлен паттерн match под точный текст исключения из вашего кода
    with pytest.raises(FileNotFoundError, match=r"Предупреждение: Файл не_существующий_файл\.xls не найден\."):
        load_transactions_from_xls("не_существующий_файл.xls")


@patch("pandas.read_excel")
def test_load_transactions_from_xls_success(mock_read_excel, tmp_path):
    """Проверка успешной загрузки данных из Excel."""
    # Создаем временный пустой файл, чтобы os.path.exists вернул True
    fake_file = tmp_path / "operations.xls"
    fake_file.write_text("fake content")

    mock_df = pd.DataFrame({"Дата операции": ["01.01.2021 00:00:00"]})
    mock_read_excel.return_value = mock_df

    result_df = load_transactions_from_xls(str(fake_file))

    mock_read_excel.assert_called_once_with(str(fake_file), engine='xlrd')
    assert isinstance(result_df, pd.DataFrame)
    assert result_df.iloc[0]["Дата операции"] == "01.01.2021 00:00:00"


@patch("pandas.read_excel")
def test_load_transactions_from_xls_corrupted(mock_read_excel, tmp_path):
    """Проверка выброса кастомного FileError при сбое парсинга файла."""
    fake_file = tmp_path / "corrupted.xls"
    fake_file.write_text("corrupted content")

    # Имитируем падение движка xlrd
    mock_read_excel.side_effect = Exception("Разрушенный заголовок файла")

    with pytest.raises(FileError, match="Ошибка при чтении файла"):
        load_transactions_from_xls(str(fake_file))


# ==========================================
# ТЕСТЫ ДЛЯ high_yield_cashback_categories
# ==========================================

@pytest.fixture
def sample_cashback_data():
    """Фикстура, генерирующая DataFrame с тестовыми транзакциями для кэшбэка."""
    return pd.DataFrame([
        # Подходящая транзакция 1 (Май 2021)
        {"Дата операции": "15.05.2021 12:00:00", "Статус": "OK", "Кэшбэк": 100, "Категория": "Супермаркеты",
         "Сумма платежа": -2000},
        # Подходящая транзакция 2 (Май 2021, та же категория для проверки агрегации)
        {"Дата операции": "20.05.2021 15:30:00", "Статус": "OK", "Кэшбэк": 50, "Категория": "Супермаркеты",
         "Сумма платежа": -1000},
        # Подходящая транзакция 3 (Май 2021, другая категория)
        {"Дата операции": "25.05.2021 18:00:00", "Статус": "OK", "Кэшбэк": 300, "Категория": "Рестораны",
         "Сумма платежа": -3000},
        # Не подходит: Другой месяц (Июнь)
        {"Дата операции": "01.06.2021 10:00:00", "Статус": "OK", "Кэшбэк": 100, "Категория": "Супермаркеты",
         "Сумма платежа": -2000},
        # Не подходит: Неуспешный статус операции
        {"Дата операции": "16.05.2021 11:00:00", "Статус": "FAILED", "Кэшбэк": 100, "Категория": "Фастфуд",
         "Сумма платежа": -1000},
        # Не подходит: Это доход (Сумма платежа > 0)
        {"Дата операции": "17.05.2021 09:00:00", "Статус": "OK", "Кэшбэк": 0, "Категория": "Пополнения",
         "Сумма платежа": 50000},
        # Не подходит: Кэшбэк равен NaN/None
        {"Дата операции": "18.05.2021 14:00:00", "Статус": "OK", "Кэшбэк": None, "Категория": "Такси",
         "Сумма платежа": -500}
    ])


def test_high_yield_cashback_categories_success(sample_cashback_data):
    """Проверка правильной фильтрации, суммирования и сортировки кэшбэка."""
    json_str = high_yield_cashback_categories(sample_cashback_data, year=2021, month=5)
    result = json.loads(json_str)

    # Проверяем, что попали только нужные категории
    assert "Супермаркеты" in result
    assert "Рестораны" in result
    assert "Фастфуд" not in result  # Исключен по статусу FAILED
    assert "Пополнения" not in result  # Исключен по положительной сумме

    # Проверяем правильность суммирования трат (берется модуль суммы)
    # Супермаркеты: 2000 + 1000 = 3000
    assert result["Супермаркеты"] == 3000
    # Рестораны: 3000
    assert result["Рестораны"] == 3000


def test_high_yield_cashback_categories_empty():
    """Проверка поведения функции, если за выбранный месяц транзакций нет."""
    empty_df = pd.DataFrame(columns=["Дата операции", "Статус", "Кэшбэк", "Категория", "Сумма платежа"])
    json_str = high_yield_cashback_categories(empty_df, 2023, 1)

    assert json.loads(json_str) == {}


# ==========================================
# ТЕСТЫ ДЛЯ search_for_transfers_to_individuals
# ==========================================

@pytest.fixture
def sample_transfer_data():
    """Фикстура, генерирующая DataFrame для проверки регулярного выражения физических лиц."""
    return pd.DataFrame([
        # Валидный кейс: Категория Переводы и формат "Имя Ф."
        {"Категория": "Переводы", "Описание": "Александр С.", "Сумма платежа": -500},
        {"Категория": "Переводы", "Описание": "Иван Г.", "Сумма платежа": -1000},

        # Невалидный кейс 1: Маленькая буква в имени или инициале
        {"Категория": "Переводы", "Описание": "игорь П.", "Сумма платежа": -300},
        {"Категория": "Переводы", "Описание": "Олег в.", "Сумма платежа": -400},

        # Невалидный кейс 2: Отсутствие точки или лишние буквы в фамилии
        {"Категория": "Переводы", "Описание": "Анна С", "Сумма платежа": -200},
        {"Категория": "Переводы", "Описание": "Мария Смирнова", "Сумма платежа": -150},

        # Невалидный кейс 3: Другая категория, хоть имя и подходит
        {"Категория": "Супермаркеты", "Описание": "Сергей М.", "Сумма платежа": -800},

        # Невалидный кейс 4: Это доходная операция (Сумма платежа > 0)
        {"Категория": "Переводы", "Описание": "Елена Б.", "Сумма платежа": 5000}
    ])


def test_search_for_transfers_to_individuals_regex(sample_transfer_data):
    """Проверка фильтрации переводов физическим лицам по регулярному выражению."""
    result = search_for_transfers_to_individuals(sample_transfer_data)

    # Должно быть найдено только два перевода ("Александр С." и "Иван Г.")
    assert len(result) == 2

    descriptions = [tx["Описание"] for tx in result]
    assert "Александр С." in descriptions
    assert "Иван Г." in descriptions
    assert "игорь П." not in descriptions
    assert "Сергей М." not in descriptions  # Отсечен по категории
    assert "Елена Б." not in descriptions  # Отсечен по положительной сумме


def test_search_for_transfers_to_individuals_empty():
    """Проверка работы функции на пустом наборе данных."""
    empty_df = pd.DataFrame(columns=["Категория", "Описание", "Сумма платежа"])
    result = search_for_transfers_to_individuals(empty_df)

    assert result == []
