from collections import defaultdict


def predict_monthly_spending(transactions):

    monthly_expenses = defaultdict(float)

    for transaction in transactions:

        if transaction["type"] == "expense":

            month = transaction["date"][:7]

            monthly_expenses[month] += transaction["amount"]

    if not monthly_expenses:
        return 0

    average_monthly_spending = (
        sum(monthly_expenses.values())
        / len(monthly_expenses)
    )

    return round(average_monthly_spending, 2)