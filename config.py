import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://localhost:27017/"
    )

    MONGO_DB_NAME = os.getenv(
    "MONGO_DB_NAME",
    "aiFinanceAssistantDB"
)
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "dev-secret-key-change-later"
    )