import pandas as pd
import json
import joblib
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import matplotlib.pyplot as plt
import seaborn as sns

# === Load Data ===
flood_df = pd.read_csv("flood_risk_dataset_india.csv")
with open("static/city_static_data.json", "r") as f:
    city_static = json.load(f)

# === Create City DataFrame with extra features ===
city_df = pd.DataFrame([
    {
        "city": name,
        "lat": data["latitude"],
        "lon": data["longitude"],
    }
    for name, data in city_static.items()
])

# === Match cities to flood data ===
filtered_rows = []
for _, city in city_df.iterrows():
    mask = (
        (flood_df["Latitude"].between(city["lat"] - 0.30, city["lat"] + 0.30)) &
        (flood_df["Longitude"].between(city["lon"] - 0.30, city["lon"] + 0.30))
    )
    matched = flood_df[mask].copy()
    matched["matched_city"] = city["city"]
    filtered_rows.append(matched)

df = pd.concat(filtered_rows, ignore_index=True)

# === Clean and Engineer Features ===
df = df.dropna(subset=["Rainfall (mm)", "Temperature (°C)", "Humidity (%)", "Elevation (m)", "Flood Occurred"])
df["RainElevRatio"] = df["Rainfall (mm)"] / (df["Elevation (m)"] + 1)

flood_prone_cities = {
    "Patna", "Guwahati", "Silchar", "Dibrugarh", "Kolkata", "Varanasi",
    "Bhubaneswar", "Chennai", "Alappuzha", "Thrissur", "Mangaluru",
    "Mumbai", "Panaji", "Puducherry", "Vijayawada", "Visakhapatnam",
    "Thiruvananthapuram", "Tirunelveli", "Imphal", "Dispur"
}
df["IsFloodProneCity"] = df["matched_city"].apply(lambda c: 1 if c in flood_prone_cities else 0)

# === Select Features and Label ===
features = [
    "Rainfall (mm)", "Temperature (°C)", "Humidity (%)",
    "Elevation (m)", "RainElevRatio", "IsFloodProneCity"
]

label = "Flood Occurred"
X = df[features]
y = df[label]

# === Train/Test Split ===
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

# === Handle Class Imbalance ===
imbalance_ratio = y_train.value_counts()[0] / y_train.value_counts()[1]

# === Train XGBoost Classifier ===
model = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=3,
    gamma=0.1,
    use_label_encoder=False,
    eval_metric='logloss',
    scale_pos_weight=imbalance_ratio,
    random_state=42
)

model.fit(X_train, y_train)

# === Evaluate Model ===
y_pred = model.predict(X_test)
y_probs = model.predict_proba(X_test)[:, 1]
print("\n✅ Classification Report:")
print(classification_report(y_test, y_pred))
print(f"✅ ROC AUC Score: {roc_auc_score(y_test, y_probs):.4f}")

# === Confusion Matrix Plot ===
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['No Flood', 'Flood'], yticklabels=['No Flood', 'Flood'])
plt.xlabel("Predicted Label")
plt.ylabel("True Label")
plt.title("Confusion Matrix")
plt.tight_layout()
plt.show()

# === ROC Curve Plot ===
from sklearn.metrics import roc_curve, auc
fpr, tpr, _ = roc_curve(y_test, y_probs)
roc_auc = auc(fpr, tpr)

plt.figure(figsize=(6, 5))
plt.plot(fpr, tpr, label=f"XGBoost (AUC = {roc_auc:.2f})")
plt.plot([0, 1], [0, 1], "k--", label="Random Classifier")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("ROC Curve")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# === Save Model ===
joblib.dump(model, "flood_risk_model_v2.pkl")
print("✅ Model saved as flood_risk_model_v2.pkl")
