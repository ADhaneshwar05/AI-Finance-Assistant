import os
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


# ---------------------------------------------------------
# Dataset location
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATASET_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "expense_data.csv"
)


# ---------------------------------------------------------
# Load dataset
# ---------------------------------------------------------

def load_dataset():

    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(
            f"Dataset not found at: {DATASET_PATH}"
        )

    data = pd.read_csv(DATASET_PATH)

    required_columns = ["description", "category"]

    for column in required_columns:
        if column not in data.columns:
            raise ValueError(
                f"Dataset must contain '{column}' column."
            )

    data = data.dropna(
        subset=["description", "category"]
    )

    data["description"] = (
        data["description"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    data["category"] = (
        data["category"]
        .astype(str)
        .str.strip()
    )

    return data


# ---------------------------------------------------------
# Train ML model
# ---------------------------------------------------------

def train_model():

    data = load_dataset()

    X = data["description"]
    y = data["category"]

    model = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2)
            )
        ),
        (
            "classifier",
            LogisticRegression(
                max_iter=1000
            )
        )
    ])

    model.fit(X, y)

    return model


# ---------------------------------------------------------
# Train model when application starts
# ---------------------------------------------------------

model = train_model()


# ---------------------------------------------------------
# Predict expense category
# ---------------------------------------------------------

def categorize_expense(description):

    if not description or not str(description).strip():
        return "Other"

    description = str(description).lower().strip()

    prediction = model.predict([description])

    return prediction[0]