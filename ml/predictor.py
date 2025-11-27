# ml/predictor.py
import joblib
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Correct model file names (existing in your project)
MODEL_PATH = os.path.join(BASE_DIR, "eligibility_model.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "scaler.pkl")

# Load model and scaler once
model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)


def predict_applicant(data_dict):
    """
    Accepts a dictionary like:
    {
        "age": 23,
        "income": 15000,
        "dependents": 2,
        ...
    }
    """
    df = pd.DataFrame([data_dict])

    # Try applying scaler
    try:
        df = scaler.transform(df)
    except Exception:
        # If scaler mismatch, skip silently
        pass

    prediction = model.predict(df)[0]
    return prediction
