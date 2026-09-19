from pymongo import MongoClient
from config import Config


client = MongoClient(Config.MONGO_URI)

db = client[Config.MONGO_DB_NAME]


users_collection = db["users"]
transactions_collection = db["transactions"]
budgets_collection = db["budgets"]
predictions_collection = db["predictions"]
insights_collection = db["insights"]


def test_database_connection():
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False
def test_database_write():
    try:
        test_data = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "MongoDB write test"
        }

        result = users_collection.insert_one(test_data)

        print("Test document inserted!")
        print("Document ID:", result.inserted_id)

        return True

    except Exception as e:
        print("Database write failed:", e)
        return False