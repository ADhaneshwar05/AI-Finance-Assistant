from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from database import (
    users_collection,
    transactions_collection,
    budgets_collection
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from bson.objectid import ObjectId

from ml.expense_classifier import categorize_expense
from ml.spending_predictor import predict_monthly_spending
from ml.financial_insights import generate_financial_insights


main_bp = Blueprint("main", __name__)


# ============================================================
# HOME
# ============================================================

@main_bp.route("/")
def home():

    return render_template("home.html")


# ============================================================
# REGISTER
# ============================================================

@main_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Basic validation
        if not name or not name.strip():
            return "Name is required"

        if not email or not email.strip():
            return "Email is required"

        if not password:
            return "Password is required"

        # Check whether email already exists
        existing_user = users_collection.find_one({
            "email": email
        })

        if existing_user:
            return "Email already registered"

        user_data = {
            "name": name.strip(),
            "email": email.strip(),
            "password": generate_password_hash(password)
        }

        users_collection.insert_one(user_data)

        return redirect(url_for("main.login"))

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@main_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = users_collection.find_one({
            "email": email
        })

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = str(user["_id"])
            session["user_name"] = user["name"]

            return redirect(url_for("main.home"))

        return "Invalid email or password"

    return render_template("login.html")


# ============================================================
# TRANSACTIONS
# ============================================================

@main_bp.route("/transactions", methods=["GET", "POST"])
def transactions():

    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if request.method == "POST":

        transaction_type = request.form.get("type")
        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get("description")
        date = request.form.get("date")

        # ----------------------------------------------------
        # Validate amount
        # ----------------------------------------------------

        try:

            amount_value = float(amount)

        except (TypeError, ValueError):

            return "Amount must be a valid number"

        if amount_value <= 0:

            return "Amount must be greater than 0"

        # ----------------------------------------------------
        # Validate description
        # ----------------------------------------------------

        if not description or not description.strip():

            return "Description is required"

        description = description.strip()

        # ----------------------------------------------------
        # Validate transaction type
        # ----------------------------------------------------

        if transaction_type not in ["income", "expense"]:

            return "Invalid transaction type"

        # ----------------------------------------------------
        # Automatically categorize expenses
        # ----------------------------------------------------

        if transaction_type == "expense":

            category = categorize_expense(description)

        # ----------------------------------------------------
        # Create transaction
        # ----------------------------------------------------

        transaction_data = {

            "user_id": session["user_id"],

            "type": transaction_type,

            "amount": amount_value,

            "category": category,

            "description": description,

            "date": date
        }

        transactions_collection.insert_one(
            transaction_data
        )

        # ====================================================
        # BUDGET WARNING
        # ====================================================

        if transaction_type == "expense":

            # Find budget for the transaction category
            user_budgets = budgets_collection.find({
                "user_id": session["user_id"]
            })

            for budget in user_budgets:

                budget_category = str(
                    budget.get("category", "")
                ).strip().lower()

                transaction_category = str(
                    category
                ).strip().lower()

                # Check matching category
                if budget_category == transaction_category:

                    budget_amount = float(
                        budget.get("amount", 0)
                    )

                    if budget_amount <= 0:
                        continue

                    # Calculate total spending for this category
                    category_transactions = transactions_collection.find({
                        "user_id": session["user_id"],
                        "type": "expense",
                        "category": category
                    })

                    category_spending = sum(
                        float(transaction.get("amount", 0))
                        for transaction in category_transactions
                    )

                    # Calculate percentage used
                    percentage = (
                        category_spending /
                        budget_amount
                    ) * 100

                    # ------------------------------------------------
                    # Budget exceeded
                    # ------------------------------------------------

                    if percentage >= 100:

                        flash(
                            f"Budget exceeded for {category}. "
                            f"You have spent ₹{category_spending:.2f} "
                            f"against a budget of ₹{budget_amount:.2f}.",
                            "danger"
                        )

                    # ------------------------------------------------
                    # Budget approaching limit
                    # ------------------------------------------------

                    elif percentage >= 80:

                        flash(
                            f"Budget approaching limit for {category}. "
                            f"You have used {percentage:.1f}% "
                            f"of your budget.",
                            "warning"
                        )

                    break

        return redirect(
            url_for("main.transactions")
        )

    # ========================================================
    # SEARCH / FILTER TRANSACTIONS
    # ========================================================

    search = request.args.get(
        "search",
        ""
    ).strip()

    query = {
        "user_id": session["user_id"]
    }

    if search:

        query["$or"] = [

            {
                "description": {
                    "$regex": search,
                    "$options": "i"
                }
            },

            {
                "category": {
                    "$regex": search,
                    "$options": "i"
                }
            }
        ]

    user_transactions = transactions_collection.find(
        query
    ).sort("date", -1)

    return render_template(
        "transactions.html",
        transactions=user_transactions,
        search=search
    )


# ============================================================
# DELETE TRANSACTION
# ============================================================

@main_bp.route(
    "/transactions/delete/<transaction_id>",
    methods=["POST"]
)
def delete_transaction(transaction_id):

    if "user_id" not in session:

        return redirect(
            url_for("main.login")
        )

    transactions_collection.delete_one({

        "_id": ObjectId(transaction_id),

        "user_id": session["user_id"]

    })

    return redirect(
        url_for("main.transactions")
    )


# ============================================================
# EDIT TRANSACTION
# ============================================================

@main_bp.route(
    "/transactions/edit/<transaction_id>",
    methods=["GET", "POST"]
)
def edit_transaction(transaction_id):

    if "user_id" not in session:

        return redirect(
            url_for("main.login")
        )

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

        # ----------------------------------------------------
        # Validate amount
        # ----------------------------------------------------

        try:

            amount_value = float(amount)

        except (TypeError, ValueError):

            return "Amount must be a valid number"

        if amount_value <= 0:

            return "Amount must be greater than 0"

        # ----------------------------------------------------
        # Validate description
        # ----------------------------------------------------

        if not description or not description.strip():

            return "Description is required"

        description = description.strip()

        # ----------------------------------------------------
        # Validate transaction type
        # ----------------------------------------------------

        if transaction_type not in ["income", "expense"]:

            return "Invalid transaction type"

        # ----------------------------------------------------
        # Re-categorize edited expense
        # ----------------------------------------------------

        if transaction_type == "expense":

            category = categorize_expense(
                description
            )

        # ----------------------------------------------------
        # Update transaction
        # ----------------------------------------------------

        transactions_collection.update_one(

            {
                "_id": ObjectId(transaction_id),

                "user_id": session["user_id"]
            },

            {
                "$set": {

                    "type": transaction_type,

                    "amount": amount_value,

                    "category": category,

                    "description": description,

                    "date": date
                }
            }
        )

        return redirect(
            url_for("main.transactions")
        )

    return render_template(
        "edit_transaction.html",
        transaction=transaction
    )


# ============================================================
# BUDGETS
# ============================================================

@main_bp.route(
    "/budgets",
    methods=["GET", "POST"]
)
def budgets():

    if "user_id" not in session:

        return redirect(
            url_for("main.login")
        )

    if request.method == "POST":

        category = request.form.get(
            "category"
        )

        amount = request.form.get(
            "amount"
        )

        # Validate category
        if not category or not category.strip():

            return "Category is required"

        # Validate amount
        try:

            amount_value = float(amount)

        except (TypeError, ValueError):

            return "Budget amount must be a valid number"

        if amount_value <= 0:

            return "Budget amount must be greater than 0"

        budget_data = {

            "user_id": session["user_id"],

            "category": category.strip(),

            "amount": amount_value
        }

        budgets_collection.insert_one(
            budget_data
        )

        return redirect(
            url_for("main.budgets")
        )

    budgets = list(
        budgets_collection.find({
            "user_id": session["user_id"]
        })
    )

    return render_template(
        "budgets.html",
        budgets=budgets
    )


# ============================================================
# DASHBOARD
# ============================================================

@main_bp.route("/dashboard")
def dashboard():

    # User must be logged in
    if "user_id" not in session:

        return redirect(
            url_for("main.login")
        )

    user_id = session["user_id"]

    # --------------------------------------------------------
    # Get user's transactions
    # --------------------------------------------------------

    user_transactions = list(
        transactions_collection.find({
            "user_id": user_id
        })
    )

    # --------------------------------------------------------
    # Predict monthly spending
    # --------------------------------------------------------

    predicted_spending = predict_monthly_spending(
        user_transactions
    )

    # --------------------------------------------------------
    # Get user's budgets
    # --------------------------------------------------------

    user_budgets = list(
        budgets_collection.find({
            "user_id": user_id
        })
    )

    # --------------------------------------------------------
    # Generate financial insights
    # --------------------------------------------------------

    financial_insights = generate_financial_insights(
        user_transactions,
        user_budgets
    )

    # --------------------------------------------------------
    # Calculate budget overview
    # --------------------------------------------------------

    budget_overview = []

    for budget in user_budgets:

        category = budget["category"]

        budget_amount = float(
            budget["amount"]
        )

        spent = sum(

            float(transaction["amount"])

            for transaction in user_transactions

            if transaction["type"] == "expense"

            and transaction["category"].lower()
            == category.lower()
        )

        remaining = (
            budget_amount - spent
        )

        if budget_amount > 0:

            percentage = (
                spent /
                budget_amount
            ) * 100

        else:

            percentage = 0

        # ----------------------------------------------------
        # Budget status
        # ----------------------------------------------------

        if percentage >= 100:

            status = "Budget Exceeded"

        elif percentage >= 80:

            status = "Approaching Limit"

        else:

            status = "Within Budget"

        budget_overview.append({

            "category": category,

            "budget": budget_amount,

            "spent": spent,

            "remaining": remaining,

            "percentage": percentage,

            "status": status
        })

    # --------------------------------------------------------
    # Calculate spending by category
    # --------------------------------------------------------

    category_spending = {}

    for transaction in user_transactions:

        if transaction["type"] == "expense":

            category = transaction["category"]

            amount = float(
                transaction["amount"]
            )

            if category in category_spending:

                category_spending[category] += amount

            else:

                category_spending[category] = amount
        # --------------------------------------------------------
    # Calculate monthly spending
    # --------------------------------------------------------

    monthly_spending = {}

    for transaction in user_transactions:

        if transaction["type"] == "expense":

            transaction_date = str(
                transaction.get("date", "")
            )

            month_key = transaction_date[:7]

            if len(month_key) == 7:

                amount = float(
                    transaction["amount"]
                )

                if month_key in monthly_spending:

                    monthly_spending[month_key] += amount

                else:

                    monthly_spending[month_key] = amount
    # --------------------------------------------------------
    # Calculate total income
    # --------------------------------------------------------

    total_income = sum(

        float(transaction["amount"])

        for transaction in user_transactions

        if transaction["type"] == "income"
    )

    # --------------------------------------------------------
    # Calculate total expenses
    # --------------------------------------------------------

    total_expenses = sum(

        float(transaction["amount"])

        for transaction in user_transactions

        if transaction["type"] == "expense"
    )

    # --------------------------------------------------------
    # Calculate balance
    # --------------------------------------------------------

    balance = (
        total_income -
        total_expenses
    )

    # --------------------------------------------------------
    # Recent transactions
    # --------------------------------------------------------

    recent_transactions = list(

        transactions_collection.find({
            "user_id": user_id
        })

        .sort("_id", -1)

        .limit(5)
    )

    # --------------------------------------------------------
    # Render dashboard
    # --------------------------------------------------------

    return render_template(

        "dashboard.html",

        total_income=total_income,

        total_expenses=total_expenses,

        balance=balance,

        transactions=recent_transactions,

        budget_overview=budget_overview,

        category_spending=category_spending,

        predicted_spending=predicted_spending,

        financial_insights=financial_insights,

        monthly_spending=monthly_spending
    )
    


# ============================================================
# API - GET TRANSACTIONS
# ============================================================

@main_bp.route("/api/transactions")
def api_transactions():

    if "user_id" not in session:
        return {
            "error": "User not logged in"
        }, 401

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


@main_bp.route("/predict-category", methods=["POST"])
def predict_category_api():

    data = request.get_json()

    if not data:
        return {
            "error": "JSON data is required"
        }, 400

    description = data.get("description")

    if not description or not description.strip():
        return {
            "error": "Description is required"
        }, 400

    category = categorize_expense(description)

    return {
        "description": description,
        "predicted_category": category
    }, 200

# ============================================================
# API - UPDATE TRANSACTION
# ============================================================

@main_bp.route("/transactions/<transaction_id>", methods=["PUT"])
def api_update_transaction(transaction_id):

    if "user_id" not in session:
        return {
            "error": "User not logged in"
        }, 401

    data = request.get_json()

    if not data:
        return {
            "error": "Request body is required"
        }, 400

    transaction = transactions_collection.find_one({
        "_id": ObjectId(transaction_id),
        "user_id": session["user_id"]
    })

    if not transaction:
        return {
            "error": "Transaction not found"
        }, 404

    transaction_type = data.get("type", transaction["type"])
    amount = data.get("amount", transaction["amount"])
    category = data.get("category", transaction["category"])
    description = data.get(
        "description",
        transaction["description"]
    )
    date = data.get("date", transaction["date"])

    if amount is None or float(amount) <= 0:
        return {
            "error": "Amount must be greater than 0"
        }, 400

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

    return {
        "message": "Transaction updated successfully"
    }, 200
    # ============================================================
# API - DELETE TRANSACTION
# ============================================================

@main_bp.route("/transactions/<transaction_id>", methods=["DELETE"])
def api_delete_transaction(transaction_id):

    if "user_id" not in session:
        return {
            "error": "User not logged in"
        }, 401

    result = transactions_collection.delete_one({
        "_id": ObjectId(transaction_id),
        "user_id": session["user_id"]
    })

    if result.deleted_count == 0:
        return {
            "error": "Transaction not found"
        }, 404

    return {
        "message": "Transaction deleted successfully"
    }, 200
    # ============================================================
# API - FINANCIAL INSIGHTS
# ============================================================

@main_bp.route("/insights", methods=["GET"])
def api_insights():

    if "user_id" not in session:
        return {
            "error": "User not logged in"
        }, 401

    user_id = session["user_id"]

    user_transactions = list(
        transactions_collection.find({
            "user_id": user_id
        })
    )

    user_budgets = list(
        budgets_collection.find({
            "user_id": user_id
        })
    )

    insights = generate_financial_insights(
        user_transactions,
        user_budgets
    )

    return {
        "insights": insights
    }, 200
@main_bp.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("main.home"))