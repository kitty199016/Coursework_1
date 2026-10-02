import pytest
import pandas as pd
from src.reports import spending_by_category


@pytest.fixture
def sample_transactions():
    # Создаем списки отдельно, чтобы избежать проблем с генерацией словаря
    dates_list = [
        "2026-10-01",
        "2026-09-15",
        "2026-07-05",
        "2026-06-30",
        "2026-10-05",
        "2026-09-01",
    ]
    categories_list = [
        "Супермаркеты",
        "Супермаркеты",
        "Супермаркеты",
        "Супермаркеты",
        "Супермаркеты",
        "Транспорт",
    ]
    amounts_list = [100, 200, 300, 400, 500, 600]

    data = {
        "date": dates_list,
        "category": categories_list,
        "amount": amounts_list,
    }
    return pd.DataFrame(data)


def test_spending_by_category_with_date(sample_transactions):
    """Тест: базовая фильтрация с переданной датой"""
    result = spending_by_category(
        sample_transactions, category="Супермаркеты", date="2026-10-02"
    )

    assert len(result) == 3
    assert all(result["category"] == "Супермаркеты")
    assert set(result["amount"]) == {100, 200, 300}


def test_spending_by_category_no_date(sample_transactions):
    """Тест: работа без передачи даты (берется текущая)"""
    current_date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
    sample_transactions.loc[0, "date"] = current_date_str

    result = spending_by_category(sample_transactions, category="Супермаркеты")

    assert len(result) >= 1
    assert current_date_str in result["date"].dt.strftime("%Y-%m-%d").values


def test_spending_by_category_empty_result(sample_transactions):
    """Тест: категория есть, но транзакции вне диапазона дат"""
    result = spending_by_category(
        sample_transactions, category="Супермаркеты", date="2025-01-01"
    )

    assert result.empty


def test_spending_by_category_unknown_category(sample_transactions):
    """Тест: передана несуществующая категория"""
    result = spending_by_category(
        sample_transactions, category="Фастфуд", date="2026-10-02"
    )

    assert result.empty


def test_spending_by_category_keeps_original_df(sample_transactions):
    """Тест: функция не изменяет исходный датафрейм (не мутирует его)"""
    original_copy = sample_transactions.copy()

    spending_by_category(
        sample_transactions, category="Супермаркеты", date="2026-10-02"
    )

    # Проверяем, что исходный df остался абсолютно идентичным оригиналу
    pd.testing.assert_frame_equal(sample_transactions, original_copy)
