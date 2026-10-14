import logging
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Any
import pandas as pd

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def report_to_file(filename_or_func: Optional[Any] = None) -> Callable:
    """
    Декоратор для функций-отчетов. Записывает результат работы (DataFrame) в файл.
    Может вызываться как @report_to_file, так и @report_to_file(filename="my_report.json").
    """
    # Если передан аргумент, проверяем, является ли он функцией (вызов без скобок)
    is_func = callable(filename_or_func)

    # Определяем имя файла по умолчанию или берем переданное
    if is_func or filename_or_func is None:
        # Формат по умолчанию: report_ГГГГММДД_ЧЧММСС.json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        custom_filename = f"report_{timestamp}.json"
    else:
        custom_filename = filename_or_func

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> pd.DataFrame:
            logger.info(f"Запуск генерации отчета в функции {func.__name__}...")

            # Получаем результат работы функции (это должен быть DataFrame)
            df_result = func(*args, **kwargs)

            try:
                # Сохраняем в JSON
                df_result.to_json(custom_filename, orient="records", force_ascii=False, indent=4)
                logger.info(f"Отчет успешно сохранен в файл: {custom_filename}")
            except Exception as e:
                logger.error(f"Ошибка при записи отчета в файл {custom_filename}: {e}")
                raise e

            return df_result

        return wrapper

    # Если декоратор вызван без скобок @report_to_file
    if is_func:
        return decorator(filename_or_func)

    # Если декоратор вызван со скобками @report_to_file("name.json")
    return decorator

@report_to_file
def spending_by_category(transactions: pd.DataFrame,
                         category: str,
                         date: str | None = None) -> pd.DataFrame:
    # 1. Определяем конечную дату (если None, берем текущую)
    end_date = pd.to_datetime(date) if date else pd.Timestamp.now()

    # 2. Вычисляем начальную дату (минус 3 месяца)
    start_date = end_date - pd.DateOffset(months=3)

    # 3. Делаем копию, чтобы не изменять исходный датафрейм, и приводим даты
    df = transactions.copy()
    df['date'] = pd.to_datetime(df['date'])

    # 4. Фильтруем по категории и временному промежутку
    filtered_df = df[
        (df['category'] == category) &
        (df['date'] >= start_date) &
        (df['date'] <= end_date)
        ]

    return filtered_df
