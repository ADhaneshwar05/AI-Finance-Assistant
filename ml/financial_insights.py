def generate_financial_insights(transactions, budgets):

    insights = []

    total_expenses = sum(
        transaction["amount"]
        for transaction in transactions
        if transaction["type"] == "expense"
    )

    if total_expenses == 0:
        insights.append("No expense data available yet.")
        return insights

    # Check budget usage
    for budget in budgets:

        category = budget["category"]
        budget_amount = budget["amount"]

        spent = sum(
            transaction["amount"]
            for transaction in transactions
            if transaction["type"] == "expense"
            and transaction["category"].lower() == category.lower()
        )

        if budget_amount > 0:

            percentage = (spent / budget_amount) * 100

            if percentage >= 100:
                insights.append(
                    f"You have exceeded your {category} budget."
                )

            elif percentage >= 80:
                insights.append(
                    f"You have used {percentage:.0f}% of your {category} budget."
                )

    # Identify highest spending category
    category_totals = {}

    for transaction in transactions:

        if transaction["type"] == "expense":

            category = transaction["category"]
            amount = transaction["amount"]

            category_totals[category] = (
                category_totals.get(category, 0) + amount
            )

    if category_totals:

        highest_category = max(
            category_totals,
            key=category_totals.get
        )

        highest_amount = category_totals[highest_category]

        insights.append(
            f"Your highest spending category is {highest_category} "
            f"with ₹{highest_amount:.2f} spent."
        )

    return insights