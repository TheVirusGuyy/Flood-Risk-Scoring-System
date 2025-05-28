def score_flood_risk(features):
    """
    Enhanced rule-based flood risk scoring.
    features = [rain_3d, rain_forecast, pop, humidity, cloud, temp, elevation, drainage, soil_moisture]
    """

    rain_3d, rain_forecast, pop, humidity, cloud, temp, elevation, drainage, soil = features

    # Normalize features (0 to 1 range)
    rain_3d_n = min(rain_3d / 150, 1.0)
    rain_forecast_n = min(rain_forecast / 100, 1.0)
    pop_n = min(max(pop, 0), 1.0)
    humidity_n = min(humidity / 100, 1.0)
    cloud_n = min(cloud / 100, 1.0)
    temp_n = max(0, min((40 - temp) / 40, 1.0))           # cooler = higher risk
    elevation_n = max(0, min((200 - elevation) / 200, 1.0)) # lower = riskier
    drainage_n = max(0, min((100 - drainage) / 100, 1.0))   # lower = riskier
    soil_n = min(soil / 100, 1.0)

    # New surge detection logic
    surge_bonus = 0.0
    if rain_3d < 5 and rain_forecast > 25:
        surge_bonus += 0.07  # mild spike

    if humidity > 90 and rain_forecast > 30:
        surge_bonus += 0.06  # extreme saturation + forecast

    # Updated weights (must sum ~1.0 pre-bonus)
    score = (
        rain_3d_n * 0.23 +
        rain_forecast_n * 0.14 +
        pop_n * 0.12 +
        humidity_n * 0.10 +
        cloud_n * 0.05 +
        temp_n * 0.08 +
        elevation_n * 0.10 +
        drainage_n * 0.06 +
        soil_n * 0.02  # lowered because data is static
    ) + surge_bonus

    # Final score cap
    risk_score = min(round(score * 100, 2), 100)

    # Label boundaries (tightened)
    if risk_score > 75:
        label = "High"
    elif risk_score > 50:
        label = "Moderate"
    elif risk_score > 30:
        label = "Low"
    else:
        label = "Lowest"

    return risk_score, label
