import pandas as pd


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
