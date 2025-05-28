import os
import joblib
import json
import numpy as np
from score import score_flood_risk

# Load model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "flood_risk_model_v2.pkl")
ml_model = joblib.load(MODEL_PATH)

def get_city_static_data():
    static_path = os.path.join(os.path.dirname(__file__), "static", "city_static_data.json")
    with open(static_path, "r") as f:
        return json.load(f)
    
# Load city static data
city_static_data = get_city_static_data()

# Define supported cities
valid_cities = list(city_static_data.keys())

def hybrid_score(ml_vector, rule_vector, city_name):
    if city_name not in valid_cities:
        raise ValueError(f"City '{city_name}' not in supported city list")

    rule_score, rule_label = score_flood_risk(rule_vector)
    ml_prob = ml_model.predict_proba([ml_vector])[0][1]
    ml_score = round(ml_prob * 100, 2)

    # Extract drainage
    drainage = city_static_data.get(city_name, {}).get("drainage_index", 0)

    # Compute weighted ML influence
    ml_confidence = abs(ml_prob - 0.5) * 2
    vulnerability = min((40 - drainage) / 40, 1)
    rule_strength = rule_score / 100
    ml_weight = max(0.05, min(ml_confidence * vulnerability * rule_strength, 0.4))

    # Final score computation
    final_score = ml_weight * ml_score + (1 - ml_weight) * rule_score

    # Risk label
    if final_score > 75:
        label = "High"
    elif final_score > 50:
        label = "Moderate"
    elif final_score > 30:
        label = "Low"
    else:
        label = "Lowest"

    return round(final_score, 2), label, round(rule_score, 2), ml_score