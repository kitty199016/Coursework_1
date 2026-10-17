
from src.services import high_yield_cashback_categories, load_transactions_from_xls
from src.services import search_for_transfers_to_individuals
from src.views import process_financial_data
from src.reports import  spending_by_category

if __name__ == "__main__":
    date = "2021.05.25 00:00:00"
    general_func = process_financial_data(date, "M")
    print(general_func)

    data = load_transactions_from_xls()

    spending_category = spending_by_category(data, "Супермаркеты", date)
    print(spending_category)

    cashbacks = high_yield_cashback_categories(data, 2021, 5)
    print(cashbacks)

    search_transfer = search_for_transfers_to_individuals(data)
    print(search_transfer)


