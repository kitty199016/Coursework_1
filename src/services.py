from datetime import datetime
import json
import os
import pandas as pd
import re



def load_transactions_from_xls(file_path: str = "data/operations.xls") -> list:
    """Загружает транзакции из Excel-файла (.xls) с помощью xlrd."""
    if not os.path.exists(file_path):
        print(f"Предупреждение: Файл {file_path} не найден.")
        return []

    try:
        df = pd.read_excel(file_path, engine='xlrd')
        df.columns = [str(col).strip().lower() for col in df.columns]

        col_mapping = {
            'дата': 'date', 'date': 'date',
            'тип': 'type', 'type': 'type',
            'категория': 'category', 'category': 'category',
            'сумма': 'amount', 'amount': 'amount'
        }
        df = df.rename(columns=col_mapping)

        required_cols = ['date', 'type', 'category', 'amount']
        df = df[[col for col in required_cols if col in df.columns]]

        df['date'] = pd.to_datetime(df['date'])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['type'] = df['type'].astype(str).str.strip().str.lower()
        df['category'] = df['category'].astype(str).str.strip()

        type_map = {'расход': 'расход', 'expense': 'расход', 'поступление': 'поступление', 'income': 'поступление'}
        df['type'] = df['type'].map(type_map).fillna('расход')

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

def high_yield_cashback_categories(data: list = None, year: int = None, month: int = None,
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
        tx_date = tx.get("date")

        # Фильтруем только расходы за нужный год и месяц
        if (
                tx.get("type") == "расход"
                and isinstance(tx_date, datetime)
                and tx_date.year == year
                and tx_date.month == month
        ):
            category = tx.get("category")

            # Пропускаем переводы и наличные, так как за них кэшбэк не начисляется
            if category in ["Наличные", "Переводы", "Остальное"]:
                continue

            amount = tx.get("amount", 0)
            category_spending[category] = category_spending.get(category, 0) + amount

    # Считаем 5% кэшбэка, округляем до целых и сортируем по убыванию выгоды
    potential_cashback = {
        category: round(spending * cashback_rate)
        for category, spending in sorted(category_spending.items(), key=lambda x: x[1], reverse=True)
    }

    return json.dumps(potential_cashback, ensure_ascii=False, indent=4)


def search_for_transfers_to_individuals() -> dict:
    """Возвращает JSON со всеми транзакциями, которые относятся к переводам

    физлицам из файла data/operation.xls. Категория такой транзакции — Переводы,
    а в описании есть имя и первая буква фамилии с точкой.
    """
    file_path = "data/operation.xls"

    try:
        # Читаем файл Excel. Если данные на определенном листе,
        # можно добавить sheet_name='Имя_листа'
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        return {"error": f"Файл {file_path} не найден."}
    except Exception as e:
        return {"error": f"Ошибка при чтении файла: {str(e)}"}

    # Регулярное выражение для поиска "Имя Ф."
    pattern = re.compile(r"^[А-ЯЁ][а-яё]+\s[А-ЯЁ]\.$")

    filtered_transactions = []

    # Проходим по строкам датафрейма
    # (Предполагается, что колонки называются 'category' и 'description')
    for _, row in df.iterrows():
        # Приводим к строке и убираем лишние пробелы по краям
        category = str(row.get("category", "")).strip()
        description = str(row.get("description", "")).strip()

        # Проверяем условия фильтрации
        if category == "Переводы" and pattern.match(description):
            # Конвертируем строку датафрейма в обычный словарь Python
            transaction_dict = row.to_dict()
            filtered_transactions.append(transaction_dict)

    return {"transactions": filtered_transactions}
