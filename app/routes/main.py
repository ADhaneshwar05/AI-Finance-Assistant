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

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        if not name or not name.strip():
            return "Name is required"

        if not email or not email.strip():
            return "Email is required"

        if not password:
            return "Password is required"

        name = name.strip()
        email = email.strip().lower()

        # ----------------------------------------------------
        # Check duplicate email
        # ----------------------------------------------------

        existing_user = users_collection.find_one({
            "email": email
        })

        if existing_user:
            return "Email already registered"

        # ----------------------------------------------------
        # Create user
        # ----------------------------------------------------

        user_data = {
            "name": name,
            "email": email,
            "password": generate_password_hash(password)
        }

        users_collection.insert_one(user_data)

        return redirect(
            url_for("main.login")
        )

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@main_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not email.strip():
            return "Email is required"

        if not password:
            return "Password is required"

        email = email.strip().lower()

        user = users_collection.find_one({
            "email": email
        })

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = str(
                user["_id"]
            )

            session["user_name"] = user["name"]

            return redirect(
                url_for("main.home")
            )

        return "Invalid email or password"

    return render_template("login.html")


# ============================================================
# TRANSACTIONS
# ============================================================

@main_bp.route(
    "/transactions",
    methods=["GET", "POST"]
)
def transactions():

    # User must be logged in
    if "user_id" not in session:

        return redirect(
            url_for("main.login")
        )

    # ========================================================
    # ADD TRANSACTION
    # ========================================================

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

        if transaction_type not in [
            "income",
            "expense"
        ]:

            return "Invalid transaction type"

        # ----------------------------------------------------
        # Validate date
        # ----------------------------------------------------

        if not date or not date.strip():

            return "Date is required"

        # ----------------------------------------------------
        # ML prediction for expenses
        # ----------------------------------------------------

        predicted_category = None

        if transaction_type == "expense":

            predicted_category = categorize_expense(description)

            # Preserve a manually selected category.
            if not category or not category.strip():

                category = predicted_category

            else:

                category = category.strip()

        else:

            # Income transactions do not require
            # ML expense prediction.

            if not category or not category.strip():

                category = "Other"

            else:

                category = category.strip()

        # ====================================================
        # CREATE TRANSACTION
        # ====================================================

        transaction_data = {

            "user_id": session["user_id"],

            "type": transaction_type,

            "amount": amount_value,

            "category": category,

            "predicted_category": predicted_category,

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

                # ------------------------------------------------
                # Matching budget category
                # ------------------------------------------------

                if budget_category == transaction_category:

                    budget_amount = float(
                        budget.get("amount", 0)
                    )

                    if budget_amount <= 0:
                        continue

                    # ------------------------------------------------
                    # Calculate total category spending
                    # ------------------------------------------------

                    category_transactions = (
                        transactions_collection.find({

                            "user_id": session["user_id"],

                            "type": "expense",

                            "category": category

                        })
                    )

                    category_spending = sum(

                        float(
                            transaction.get(
                                "amount",
                                0
                            )
                        )

                        for transaction
                        in category_transactions

                    )

                    percentage = (
                        category_spending /
                        budget_amount
                    ) * 100

                    # ------------------------------------------------
                    # Budget exceeded
                    # ------------------------------------------------

                    if percentage >= 100:

                        flash(

                            f"Budget exceeded for "
                            f"{category}. "

                            f"You have spent "
                            f"₹{category_spending:.2f} "

                            f"against a budget of "
                            f"₹{budget_amount:.2f}.",

                            "danger"
                        )

                    # ------------------------------------------------
                    # Budget approaching
                    # ------------------------------------------------

                    elif percentage >= 80:

                        flash(

                            f"Budget approaching limit "
                            f"for {category}. "

                            f"You have used "
                            f"{percentage:.1f}% "
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

    user_transactions = (
        transactions_collection.find(
            query
        ).sort(
            "date",
            -1
        )
    )

    return render_template(

        "transactions.html",

        transactions=user_transactions,

        search=search

    )


# ============================================================
# DELETE TRANSACTION - WEB
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

    try:

        object_id = ObjectId(
            transaction_id
        )

    except Exception:

        return "Invalid transaction ID"

    transactions_collection.delete_one({

        "_id": object_id,

        "user_id": session["user_id"]

    })

    return redirect(
        url_for("main.transactions")
    )


# ============================================================
# EDIT TRANSACTION - WEB
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

    try:

        object_id = ObjectId(
            transaction_id
        )

    except Exception:

        return "Invalid transaction ID"

    transaction = transactions_collection.find_one({

        "_id": object_id,

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
        # Validate type
        # ----------------------------------------------------

        if transaction_type not in [
            "income",
            "expense"
        ]:

            return "Invalid transaction type"

        # ----------------------------------------------------
        # Validate date
        # ----------------------------------------------------

        if not date or not date.strip():

            return "Date is required"

        # ----------------------------------------------------
        # Re-predict expense category
        # ----------------------------------------------------

        predicted_category = None

        if transaction_type == "expense":

            predicted_category = categorize_expense(
                description
            )

            # Preserve user's correction
            if category and category.strip():

                category = category.strip()

            else:

                category = predicted_category

        else:

            if not category or not category.strip():

                category = "Other"

            else:

                category = category.strip()

        # ----------------------------------------------------
        # Update transaction
        # ----------------------------------------------------

        transactions_collection.update_one(

            {
                "_id": object_id,

                "user_id": session["user_id"]
            },

            {
                "$set": {

                    "type": transaction_type,

                    "amount": amount_value,

                    "category": category,

                    "predicted_category":
                        predicted_category,

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

        # ----------------------------------------------------
        # Validate category
        # ----------------------------------------------------

        if not category or not category.strip():

            return "Category is required"

        category = category.strip()

        # ----------------------------------------------------
        # Validate amount
        # ----------------------------------------------------

        try:

            amount_value = float(amount)

        except (TypeError, ValueError):

            return (
                "Budget amount must be "
                "a valid number"
            )

        if amount_value <= 0:

            return (
                "Budget amount must be "
                "greater than 0"
            )

        # ----------------------------------------------------
        # Create budget
        # ----------------------------------------------------

        budget_data = {

            "user_id": session["user_id"],

            "category": category,

            "amount": amount_value

        }

        budgets_collection.insert_one(
            budget_data
        )

        return redirect(
            url_for("main.budgets")
        )

    budgets_data = list(

        budgets_collection.find({

            "user_id": session["user_id"]

        })

    )

    return render_template(

        "budgets.html",

        budgets=budgets_data

    )


# ============================================================
# DASHBOARD
# ============================================================

@main_bp.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("main.login")
        )

    user_id = session["user_id"]

    # ========================================================
    # USER TRANSACTIONS
    # ========================================================

    user_transactions = list(

        transactions_collection.find({

            "user_id": user_id

        })

    )

    # ========================================================
    # PREDICT MONTHLY SPENDING
    # ========================================================

    predicted_spending = (
        predict_monthly_spending(
            user_transactions
        )
    )

    monthly_spending = {}

    for transaction in user_transactions:

        if transaction.get("type") == "expense":

            month = transaction.get("date", "")[:7]

            monthly_spending[month] = (
                monthly_spending.get(month, 0) +
                float(transaction.get("amount", 0))
            )

    # ========================================================
    # USER BUDGETS
    # ========================================================

    user_budgets = list(

        budgets_collection.find({

            "user_id": user_id

        })

    )

    # ========================================================
    # FINANCIAL INSIGHTS
    # ========================================================

    financial_insights = (
        generate_financial_insights(

            user_transactions,

            user_budgets

        )
    )

    # ========================================================
    # BUDGET OVERVIEW
    # ========================================================

    budget_overview = []

    for budget in user_budgets:

        category = budget.get(
            "category",
            "Other"
        )

        budget_amount = float(
            budget.get(
                "amount",
                0
            )
        )

        spent = sum(

            float(
                transaction.get(
                    "amount",
                    0
                )
            )

            for transaction
            in user_transactions

            if transaction.get(
                "type"
            ) == "expense"

            and str(
                transaction.get(
                    "category",
                    ""
                )
            ).lower()
            == str(category).lower()

        )

        remaining = (
            budget_amount -
            spent
        )

        if budget_amount > 0:

            percentage = (
                spent /
                budget_amount
            ) * 100

        else:

            percentage = 0

        # ----------------------------------------------------
        # Status
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

    # ========================================================
    # SPENDING BY CATEGORY
    # ========================================================

    category_spending = {}

    for transaction in user_transactions:

        if transaction.get(
            "type"
        ) == "expense":

            category = transaction.get(
                "category",
                "Other"
            )

            amount = float(
                transaction.get(
                    "amount",
                    0
                )
            )

            if category in category_spending:

                category_spending[
                    category
                ] += amount

            else:

                category_spending[
                    category
                ] = amount

    # ========================================================
    # TOTAL INCOME
    # ========================================================

    total_income = sum(

        float(
            transaction.get(
                "amount",
                0
            )
        )

        for transaction
        in user_transactions

        if transaction.get(
            "type"
        ) == "income"

    )

    # ========================================================
    # TOTAL EXPENSES
    # ========================================================

    total_expenses = sum(

        float(
            transaction.get(
                "amount",
                0
            )
        )

        for transaction
        in user_transactions

        if transaction.get(
            "type"
        ) == "expense"

    )

    # ========================================================
    # BALANCE
    # ========================================================

    balance = (
        total_income -
        total_expenses
    )

    # ========================================================
    # RECENT TRANSACTIONS
    # ========================================================

    recent_transactions = list(

        transactions_collection.find({

            "user_id": user_id

        })

        .sort(
            "_id",
            -1
        )

        .limit(5)

    )

    # ========================================================
    # DASHBOARD
    # ========================================================

    return render_template(

        "dashboard.html",

        total_income=total_income,

        total_expenses=total_expenses,

        balance=balance,

        transactions=recent_transactions,

        budget_overview=budget_overview,

        category_spending=category_spending,

        monthly_spending=monthly_spending,

        predicted_spending=predicted_spending,

        financial_insights=financial_insights

    )


# ============================================================
# API - GET TRANSACTIONS
# ============================================================

@main_bp.route(
    "/api/transactions",
    methods=["GET"]
)
def api_transactions():

    if "user_id" not in session:

        return {
            "error": "User not logged in"
        }, 401

    user_transactions = list(

        transactions_collection.find(

            {
                "user_id":
                    session["user_id"]
            },

            {
                "_id": 0,
                "user_id": 0
            }

        )

    )

    return {

        "transactions":
            user_transactions

    }, 200


# ============================================================
# API - PREDICT CATEGORY
# ============================================================

@main_bp.route(
    "/predict-category",
    methods=["POST"]
)
def predict_category_api():

    if "user_id" not in session:

        return {
            "error": "User not logged in"
        }, 401

    data = request.get_json(
        silent=True
    )

    if not data:

        return {
            "error":
                "JSON data is required"
        }, 400

    description = data.get(
        "description"
    )

    if (
        not description
        or not str(description).strip()
    ):

        return {
            "error":
                "Description is required"
        }, 400

    description = str(
        description
    ).strip()

    category = categorize_expense(
        description
    )

    return {

        "description":
            description,

        "predicted_category":
            category

    }, 200


# ============================================================
# API - UPDATE TRANSACTION
#
# Exact SRS endpoint:
# PUT /transactions/{id}
#
# /api/transactions/{id} is also kept for compatibility.
# ============================================================

@main_bp.route(
    "/transactions/<transaction_id>",
    methods=["PUT"]
)
@main_bp.route(
    "/api/transactions/<transaction_id>",
    methods=["PUT"]
)
def api_update_transaction(
    transaction_id
):

    if "user_id" not in session:

        return {
            "error":
                "User not logged in"
        }, 401

    try:

        object_id = ObjectId(
            transaction_id
        )

    except Exception:

        return {
            "error":
                "Invalid transaction ID"
        }, 400

    data = request.get_json(
        silent=True
    )

    if not data:

        return {
            "error":
                "Request body is required"
        }, 400

    transaction = (
        transactions_collection.find_one({

            "_id": object_id,

            "user_id":
                session["user_id"]

        })
    )

    if not transaction:

        return {
            "error":
                "Transaction not found"
        }, 404

    transaction_type = data.get(
        "type",
        transaction.get(
            "type"
        )
    )

    amount = data.get(
        "amount",
        transaction.get(
            "amount"
        )
    )

    category = data.get(
        "category",
        transaction.get(
            "category",
            "Other"
        )
    )

    description = data.get(
        "description",
        transaction.get(
            "description",
            ""
        )
    )

    date = data.get(
        "date",
        transaction.get(
            "date",
            ""
        )
    )

    # --------------------------------------------------------
    # Validate type
    # --------------------------------------------------------

    if transaction_type not in [
        "income",
        "expense"
    ]:

        return {
            "error":
                "Invalid transaction type"
        }, 400

    # --------------------------------------------------------
    # Validate amount
    # --------------------------------------------------------

    try:

        amount_value = float(
            amount
        )

    except (
        TypeError,
        ValueError
    ):

        return {
            "error":
                "Amount must be a valid number"
        }, 400

    if amount_value <= 0:

        return {
            "error":
                "Amount must be greater than 0"
        }, 400

    # --------------------------------------------------------
    # Validate description
    # --------------------------------------------------------

    if (
        not description
        or not str(description).strip()
    ):

        return {
            "error":
                "Description is required"
        }, 400

    description = str(
        description
    ).strip()

    # --------------------------------------------------------
    # Validate date
    # --------------------------------------------------------

    if (
        not date
        or not str(date).strip()
    ):

        return {
            "error":
                "Date is required"
        }, 400

    # --------------------------------------------------------
    # Expense prediction
    # --------------------------------------------------------

    predicted_category = None

    if transaction_type == "expense":

        predicted_category = (
            categorize_expense(
                description
            )
        )

        # User correction is preserved
        if (
            category
            and str(category).strip()
        ):

            category = str(
                category
            ).strip()

        else:

            category = predicted_category

    else:

        if (
            not category
            or not str(category).strip()
        ):

            category = "Other"

        else:

            category = str(
                category
            ).strip()

    # ========================================================
    # UPDATE
    # ========================================================

    transactions_collection.update_one(

        {

            "_id": object_id,

            "user_id":
                session["user_id"]

        },

        {

            "$set": {

                "type":
                    transaction_type,

                "amount":
                    amount_value,

                "category":
                    category,

                "predicted_category":
                    predicted_category,

                "description":
                    description,

                "date":
                    date

            }

        }

    )

    return {

        "message":
            "Transaction updated successfully"

    }, 200


# ============================================================
# API - DELETE TRANSACTION
#
# Exact SRS endpoint:
# DELETE /transactions/{id}
#
# /api/transactions/{id} is also kept for compatibility.
# ============================================================

@main_bp.route(
    "/transactions/<transaction_id>",
    methods=["DELETE"]
)
@main_bp.route(
    "/api/transactions/<transaction_id>",
    methods=["DELETE"]
)
def api_delete_transaction(
    transaction_id
):

    if "user_id" not in session:

        return {
            "error":
                "User not logged in"
        }, 401

    try:

        object_id = ObjectId(
            transaction_id
        )

    except Exception:

        return {
            "error":
                "Invalid transaction ID"
        }, 400

    result = transactions_collection.delete_one({

        "_id": object_id,

        "user_id":
            session["user_id"]

    })

    if result.deleted_count == 0:

        return {
            "error":
                "Transaction not found"
        }, 404

    return {

        "message":
            "Transaction deleted successfully"

    }, 200


# ============================================================
# API - FINANCIAL INSIGHTS
#
# Exact SRS endpoint:
# GET /insights
#
# /api/insights is also kept for compatibility.
# ============================================================

@main_bp.route(
    "/insights",
    methods=["GET"]
)
@main_bp.route(
    "/api/insights",
    methods=["GET"]
)
def api_insights():

    if "user_id" not in session:

        return {
            "error":
                "User not logged in"
        }, 401

    user_id = session["user_id"]

    # --------------------------------------------------------
    # Transactions
    # --------------------------------------------------------

    user_transactions = list(

        transactions_collection.find({

            "user_id": user_id

        })

    )

    # --------------------------------------------------------
    # Budgets
    # --------------------------------------------------------

    user_budgets = list(

        budgets_collection.find({

            "user_id": user_id

        })

    )

    # --------------------------------------------------------
    # Generate insights
    # --------------------------------------------------------

    insights = generate_financial_insights(

        user_transactions,

        user_budgets

    )

    return {

        "insights":
            insights

    }, 200


# ============================================================
# LOGOUT
# ============================================================

@main_bp.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("main.home")
    )