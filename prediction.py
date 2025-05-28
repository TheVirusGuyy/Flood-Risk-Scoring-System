import requests
from datetime import datetime, timedelta
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("WEATHER_API_KEY")

with open("static/city_static_data.json") as f:
    city_static_data = json.load(f)

def safe_get_json(url, params, retries=3, delay=2):
    """Robust fetch with retry and JSON decoding safety"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200 or not resp.text.strip():
                raise Exception(f"Empty or invalid response (status {resp.status_code})")
            return resp.json()
        except Exception as e:
            if attempt == retries - 1:
                raise Exception(f"Failed after {retries} attempts → {e}")
            time.sleep(delay * (2 ** attempt))


def get_data(lat, lon, city):
    try:
        print("\nInside get_data")
        city = city.strip().title()
        print("City:", city, "Lat:", lat, "Lon:", lon)

        # Step 1: Past 3-day rainfall
        print("Getting past 3-day rainfall")
        today = datetime.utcnow().date()
        rain_3d_total = 0
        for i in range(0, 4):
            date = today - timedelta(days=i)
            url = "https://api.weatherapi.com/v1/history.json"
            params = {
                "key": api_key,
                "q": f"{lat},{lon}",
                "dt": date.strftime("%Y-%m-%d")
            }
            try:
                data = safe_get_json(url, params)
                day_rain = data["forecast"]["forecastday"][0]["day"].get("totalprecip_mm", 0)
                print(f"Rain on {date}: {day_rain} mm")
                rain_3d_total += day_rain
            except Exception as e:
                print(f"⚠️ Rain history failed on {date}: {e}")

        # Step 2: Forecast data (next 2 days)
        print("Getting current + forecast data")
        forecast_url = "https://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": api_key,
            "q": f"{lat},{lon}",
            "days": 3,
            "aqi": "no",
            "alerts": "no"
        }

        data = safe_get_json(forecast_url, params)
        current = data.get("current", {})
        forecast_days = data.get("forecast", {}).get("forecastday", [])

        temp_now = current.get("temp_c", 25.0)
        humidity_now = current.get("humidity", 60)
        cloud_now = current.get("cloud", 50)

        rain_next_2d = 0
        pop_max_2d = 0
        for day in forecast_days[:2]:
            rain_next_2d += day["day"].get("totalprecip_mm", 0)
            pop_max_2d = max(pop_max_2d, day["day"].get("daily_chance_of_rain", 0) / 100.0)

        print(f"Rain Next 2 Days: {rain_next_2d} mm")
        print(f"Max POP Next 2 Days: {pop_max_2d}")

        # Step 3: Static features
        print("Looking for static city data")
        static = city_static_data.get(city)
        if static is None:
            raise Exception("City not found in static_data.json")

        elevation = static.get("elevation", 100)
        drainage = static.get("drainage_index", 50)
        soil_moisture = static.get("soil_moisture", 50.0)

        vector = [
            rain_3d_total, rain_next_2d, pop_max_2d,
            humidity_now, cloud_now, temp_now,
            elevation, drainage, soil_moisture
        ]

        if len(vector) != 9 or any(v is None for v in vector):
            raise Exception("Incomplete or invalid feature vector")

        print("✅ Feature vector ready")
        return vector

    except Exception as e:
        print("❌ get_data() failed:", str(e))
        raise
