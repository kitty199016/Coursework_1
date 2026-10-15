from datetime import datetime
import json
import os
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# Импортируем декоратор и функцию.
# Замените 'src.views', если ваш код лежит в другом модуле.
from src.reports import report_to_file, spending_by_category


# ==========================================
# ФИКСТУРЫ ДЛЯ ТЕСТОВЫХ ДАННЫХ
# ==========================================

@pytest.fixture
def sample_transactions():
    """Фикстура, создающая DataFrame с тестовыми транзакциями за разные даты."""
    return pd.DataFrame([
        # Подходит: Категория Продукты, дата внутри 3 месяцев от 15.12.2025
        {"Дата операции": "10.11.2025 14:00:00", "Категория": "Продукты", "Сумма платежа": -1500},
        {"Дата операции": "01.12.2025 09:30:00", "Категория": "Продукты", "Сумма платежа": -500},

        # Не подходит: Другая категория, хоть дата и верная
        {"Дата операции": "20.11.2025 18:00:00", "Категория": "Фаствуд", "Сумма платежа": -300},

        # Не подходит: Дата сильно в прошлом (больше 3 месяцев назад)
        {"Дата операции": "01.07.2025 12:00:00", "Категория": "Продукты", "Сумма платежа": -2000},

        # Не подходит: Дата в будущем относительно выбранной конечной даты
        {"Дата операции": "20.12.2025 10:00:00", "Категория": "Продукты", "Сумма платежа": -1000}
    ])


# ==========================================
# ТЕСТЫ ФУНКЦИИ ФИЛЬТРАЦИИ ОПЕРАЦИЙ
# ==========================================

def test_spending_by_category_filtering(sample_transactions):
    """Проверка корректности фильтрации по категории и временному промежутку в 3 месяца."""
    # Тестируем с фиксированной конечной датой
    result_df = spending_by_category(
        transactions=sample_transactions,
        category="Продукты",
        date="2025.12.15 00:00:00"
    )

    # В выборку должны попасть только первые две транзакции
    assert len(result_df) == 2
    assert (result_df["Категория"] == "Продукты").all()

    # Суммы отфильтрованных трат: -1500 и -500
    amounts = result_df["Сумма платежа"].tolist()
    assert -1500 in amounts
    assert -500 in amounts
    assert -2000 not in amounts  # Старая дата отсечена


def test_spending_by_category_empty(sample_transactions):
    """Проверка работы, если подходящих под категорию транзакций нет."""
    result_df = spending_by_category(
        transactions=sample_transactions,
        category="Авто",
        date="2025.12.15 00:00:00"
    )
    assert result_df.empty


# ==========================================
# ТЕСТЫ ДЕКОРАТОРА REPORT_TO_FILE
# ==========================================

def test_report_to_file_with_custom_name(sample_transactions, tmp_path):
    """Проверяет работу декоратора при явной передаче имени файла в скобках."""
    # Формируем изолированный путь во временной директории pytest
    test_report_file = tmp_path / "custom_output.json"

    # Создаем тестовую функцию локально и оборачиваем её декоратором с именем файла
    @report_to_file(str(test_report_file))
    def custom_test_func(df):
        return df[df["Категория"] == "Продукты"]

    # Запуск функции
    res_df = custom_test_func(sample_transactions)

    # Проверки: файл должен физически создаться
    assert os.path.exists(test_report_file)

    # Читаем записанный JSON и проверяем содержимое
    with open(test_report_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    assert isinstance(json_data, list)
    # Всего 4 транзакции категории "Продукты" в фикстуре (без учета фильтра дат в этой функции)
    assert len(json_data) == 4


def test_report_to_file_default_name(sample_transactions, tmp_path):
    """Проверяет автогенерацию имени файла (вызов @report_to_file без скобок) и корректность структуры."""

    frozen_time = datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    expected_filename = f"report_{frozen_time}.json"

    # Переходим во временную директорию pytest на время теста
    with patch("os.getcwd", return_value=str(tmp_path)), \
            patch("src.views.datetime") as mock_datetime:
        # Замораживаем время ДО того, как применится декоратор
        mock_datetime.now.return_value.strftime.return_value = frozen_time

        # Декорируем функцию динамически внутри патча времени!
        @report_to_file
        def default_test_func(df):
            return df.head(1)

        # Перехватываем сохранение в JSON
        with patch("pandas.DataFrame.to_json") as mock_to_json:
            default_test_func(sample_transactions)

            # Проверяем, что pandas вызвал сохранение со строго зафиксированным именем файла
            mock_to_json.assert_called_once()

            # Извлекаем переданное имя файла из позиционных или именованных аргументов
            called_filename = mock_to_json.call_args[0][0] if mock_to_json.call_args[0] else mock_to_json.call_args[
                1].get("path_or_buf")
            assert called_filename == expected_filename


def test_report_to_file_exception_handling():
    """Проверяет, что декоратор корректно логирует и пробрасывает ошибку при сбое записи."""

    # Передаем заведомо некорректный тип вместо строки или функции, что вызовет сбой у df.to_json
    @report_to_file(filename_or_func=12345)
    def broken_report_func():
        return pd.DataFrame({"col": [1]})

    with pytest.raises(Exception):
        broken_report_func()
