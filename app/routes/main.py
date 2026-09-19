from flask import Blueprint, render_template, request, redirect, url_for, session
from database import users_collection, transactions_collection, budgets_collection
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from ml.expense_classifier import categorize_expense
from ml.spending_predictor import predict_monthly_spending
from ml.financial_insights import generate_financial_insights

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("home.html")


@main_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        user_data = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password)
        }

        users_collection.insert_one(user_data)

        return redirect(url_for("main.home"))

    return render_template("register.html")




@main_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = users_collection.find_one({"email": email})

        if user and check_password_hash(user["password"], password):

            session["user_id"] = str(user["_id"])
            session["user_name"] = user["name"]

            return redirect(url_for("main.home"))

        return "Invalid email or password"

    return render_template("login.html")


@main_bp.route("/transactions", methods=["GET", "POST"])
def transactions():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if request.method == "POST":

        transaction_type = request.form.get("type")
        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get("description")
        date = request.form.get("date")

        if transaction_type == "expense":
            category = categorize_expense(description)

        transaction_data = {
            "user_id": session["user_id"],
            "type": transaction_type,
            "amount": float(amount),
            "category": category,
            "description": description,
            "date": date
        }

        transactions_collection.insert_one(transaction_data)

        return redirect(url_for("main.transactions"))

    user_transactions = transactions_collection.find(
        {"user_id": session["user_id"]}
    ).sort("date", -1)

    return render_template(
        "transactions.html",
        transactions=user_transactions
    )

@main_bp.route("/transactions/delete/<transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    transactions_collection.delete_one({
        "_id": ObjectId(transaction_id),
        "user_id": session["user_id"]
    })

    return redirect(url_for("main.transactions"))

@main_bp.route("/transactions/edit/<transaction_id>", methods=["GET", "POST"])
def edit_transaction(transaction_id):

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    transaction = transactions_collection.find_one({
        "_id": ObjectId(transaction_id),
        "user_id": session["user_id"]
    })

    if not transaction:
        return "Transaction not found"

    if request.method == "POST":

        transaction_type = request.form.get("type")
        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get("description")
        date = request.form.get("date")

        transactions_collection.update_one(
            {
                "_id": ObjectId(transaction_id),
                "user_id": session["user_id"]
            },
            {
                "$set": {
                    "type": transaction_type,
                    "amount": float(amount),
                    "category": category,
                    "description": description,
                    "date": date
                }
            }
        )

        return redirect(url_for("main.transactions"))

    return render_template(
        "edit_transaction.html",
        transaction=transaction
    )

@main_bp.route("/budgets", methods=["GET", "POST"])
def budgets():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if request.method == "POST":

        category = request.form.get("category")
        amount = request.form.get("amount")

        budget_data = {
            "user_id": session["user_id"],
            "category": category,
            "amount": float(amount)
        }

        budgets_collection.insert_one(budget_data)

        return redirect(url_for("main.budgets"))

    budgets = list(
        budgets_collection.find(
            {"user_id": session["user_id"]}
        )
    )

    return render_template(
        "budgets.html",
        budgets=budgets
    )

@main_bp.route("/dashboard")
def dashboard():

    # Make sure the user is logged in
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user_id = session["user_id"]

    # Get this user's transactions
    user_transactions = list(
        transactions_collection.find({"user_id": user_id})
    )
        # Predict monthly spending
    predicted_spending = predict_monthly_spending(user_transactions)
    # Get this user's budgets
    user_budgets = list(
        budgets_collection.find({"user_id": user_id})
    )
            # Generate financial insights
    financial_insights = generate_financial_insights(
        user_transactions,
        user_budgets
    )
    # Calculate spending for each budget category
    budget_overview = []

    for budget in user_budgets:

        category = budget["category"]
        budget_amount = budget["amount"]

        spent = sum(
            transaction["amount"]
            for transaction in user_transactions
            if transaction["type"] == "expense"
            and transaction["category"].lower() == category.lower()
        )

        remaining = budget_amount - spent

        if budget_amount > 0:
            percentage = (spent / budget_amount) * 100
        else:
            percentage = 0

        budget_overview.append({
            "category": category,
            "budget": budget_amount,
            "spent": spent,
            "remaining": remaining,
            "percentage": percentage
        })
    # Calculate spending by category
    category_spending = {}

    for transaction in user_transactions:

        if transaction["type"] == "expense":

            category = transaction["category"]
            amount = transaction["amount"]

            if category in category_spending:
                category_spending[category] += amount
            else:
                category_spending[category] = amount
   

    # Calculate income and expenses
    total_income = sum(
        transaction["amount"]
        for transaction in user_transactions
        if transaction["type"] == "income"
    )

    total_expenses = sum(
        transaction["amount"]
        for transaction in user_transactions
        if transaction["type"] == "expense"
    )

    # Calculate balance
    balance = total_income - total_expenses

       # Get recent transactions
    recent_transactions = list(
        transactions_collection.find(
            {"user_id": user_id}
        ).sort("_id", -1).limit(5)
    )

    return render_template(
        "dashboard.html",
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        transactions=recent_transactions,
        budget_overview=budget_overview,
        category_spending=category_spending,
        predicted_spending=predicted_spending,
        financial_insights=financial_insights
    )


@main_bp.route("/api/transactions")
def api_transactions():

    if "user_id" not in session:
        return {"error": "User not logged in"}, 401

    user_transactions = list(
        transactions_collection.find(
            {"user_id": session["user_id"]},
            {
                "_id": 0,
                "user_id": 0
            }
        )
    )

    return {
        "transactions": user_transactions
    }
@main_bp.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("main.home"))