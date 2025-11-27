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
def predict_input(Age, Income_Monthly, Family_Size, Sex, Region, Employment_Status,
                  Has_Disability, Previous_Aid, Aid_Type_Applied):

    # Create DataFrame matching training columns
    df = pd.DataFrame([{
        "Age": Age,
        "Income_Monthly": Income_Monthly,
        "Family_Size": Family_Size,
        "Sex": Sex,
        "Region": Region,
        "Employment_Status": Employment_Status,
        "Has_Disability": Has_Disability,
        "Previous_Aid": Previous_Aid,
        "Aid_Type_Applied": Aid_Type_Applied
    }])

    # One-hot encode exactly like training
    df_encoded = pd.get_dummies(df)

    # Align with the model’s training columns
    df_encoded = df_encoded.reindex(columns=model_columns, fill_value=0)

    # Scale numeric columns only
    df_encoded[["Age", "Income_Monthly", "Family_Size"]] = scaler.transform(
        df_encoded[["Age", "Income_Monthly", "Family_Size"]]
    )

    # Predict
    prediction = model.predict(df_encoded)[0]
    probability = model.predict_proba(df_encoded)[0].max()

    return prediction, round(probability * 100, 2)
