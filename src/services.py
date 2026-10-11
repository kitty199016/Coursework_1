from datetime import datetime
import json
import os
import pandas as pd
import re

class FileError(Exception):
    """Custom File error class"""

def load_transactions_from_xls(file_path: str = "data/operations.xls") -> pd.DataFrame:
    """Загружает транзакции из Excel-файла (.xls) с помощью xlrd."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Предупреждение: Файл {file_path} не найден.")

    try:
        df = pd.read_excel(file_path, engine='xlrd')
        return df
    except Exception as e:
        raise FileError(f"Ошибка при чтении файла {file_path}: {e}")

def high_yield_cashback_categories(data: pd.DataFrame | None = None, year: int = None, month: int = None,
                                   file_path: str = "data/operations.xls") -> str:
    """
    Анализирует, какие категории были наиболее выгодными для выбора повышенного кешбэка (5%).
    Если параметр data равен None, данные автоматически считываются из указанного Excel-файла.

    :param data: Данные с транзакциями (список словарей). Если None, загружаются из файла.
    :param year: Год, за который проводится анализ.
    :param month: Месяц, за который проводится анализ.
    :param file_path: Путь к файлу Excel, если данные берутся из него.
    :return: JSON-строка со стоимостью потенциального кэшбэка по категориям.
    """
    # Если данные не переданы в аргумент, загружаем их из файла .xls
    if data is None:
        data = load_transactions_from_xls(file_path)

    cashback_rate = 0.05  # Повышенный кэшбэк 5%
    category_spending = {}

    for tx in data:
        tx_date = tx.get("Дата операции")
        tx_cashback = tx.get("Кэшбэк")
        # Фильтруем только расходы за нужный год и месяц
        if (
                tx.get("Статус") == "OK"
                and isinstance(tx_date, datetime)
                and tx_date.year == year
                and tx_date.month == month
                and tx_cashback is not None
        ):
            category = tx.get("Категория")
            #Вычисляем процент от суммы
            if (amount := int(tx.get("Сумма платежа"))) < 0:
                #Вычислить процент от платежа
                cashback_percent = round((tx_cashback * 100)/amount)
                if category in category_spending:
                    old_value = category_spending[category]["summ"]
                    category_spending[category]["summ"] = old_value + amount
                else:
                    category_spending[category] = {"perc": cashback_percent, "summ": amount}
    # Считаем 5% кэшбэка, сортируем по убыванию выгоды
    potential_cashback = {
        category: spending["summ"]
        for category, spending in sorted(category_spending.items(), key=lambda x: x["perc"], reverse=True)
    }

    return json.dumps(potential_cashback, ensure_ascii=False, indent=4)


def search_for_transfers_to_individuals(data: pd.DataFrame | None = None, file_path: str = "data/operations.xls") -> list[dict]:
    """Возвращает JSON со всеми транзакциями, которые относятся к переводам

    физлицам из файла data/operation.xls. Категория такой транзакции — Переводы,
    а в описании есть имя и первая буква фамилии с точкой.
    """
    if data is None:
        data = load_transactions_from_xls(file_path)
    # Регулярное выражение для поиска "Имя Ф."
    pattern = re.compile(r"^[А-ЯЁ][а-яё]+\s[А-ЯЁ]\.$")
    result = []
    # Проходим по строкам датафрейма
    for tx in data:
        # Приводим к строке и убираем лишние пробелы по краям
        category = tx.get("Категория")
        if (amount := int(tx.get("Сумма платежа"))) < 0:
            # Проверяем условия фильтрации
            description = tx.get("Описание")
            if category == "Переводы" and pattern.match(description):
                # Конвертируем строку датафрейма в обычный словарь Python
                transaction_dict = tx.to_dict()
                result.append(transaction_dict)

    return result
