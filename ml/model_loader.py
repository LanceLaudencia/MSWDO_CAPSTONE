import os
import joblib
import pandas as pd
from django.conf import settings

# ---------------- Paths ----------------
BASE_DIR = settings.BASE_DIR
ML_DIR = os.path.join(BASE_DIR, "ml")

MODEL_PATH = os.path.join(ML_DIR, "model.pkl")
SCALER_PATH = os.path.join(ML_DIR, "scaler.pkl")
COLUMNS_PATH = os.path.join(ML_DIR, "model_columns.pkl")

# ---------------- Load ML objects ----------------
model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
model_columns = joblib.load(COLUMNS_PATH)

# ---------------- Prediction Function ----------------
def predict_input(data):
    """
    TEMPORARY RULE-BASED LOGIC
    Replace later with trained ML model
    """

    income = data.get("monthly_income", 0)
    household = data.get("household_size", 1)
    has_disability = data.get("has_disability", 0)
    is_senior = data.get("is_senior", 0)
    previous_aid = data.get("previous_aid", 0)

    score = 0

    if income <= 10000:
        score += 2
    if household >= 4:
        score += 1
    if has_disability:
        score += 2
    if is_senior:
        score += 1
    if not previous_aid:
        score += 1

    return 1 if score >= 4 else 0
