import json
import os
from datetime import datetime
from dotenv import load_dotenv
from prediction import get_data
from hybrid_score import hybrid_score
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()
weather_api_key = os.getenv("WEATHER_API_KEY")

STATIC_PATH = 'static/city_static_data.json'
CACHE_PATH = 'plot_data_cache.json'
FAILED_CITIES_PATH = 'failed_cities.json'

with open(STATIC_PATH, 'r') as f:
    city_static_data = json.load(f)

existing_data = {}
if os.path.exists(CACHE_PATH):
    try:
        with open(CACHE_PATH, 'r') as f:
            for entry in json.load(f):
                existing_data[entry["city"]] = entry
    except Exception as e:
        print(f"⚠️ Failed to read existing plot_data_cache.json: {e}")

flood_prone_cities = {
    "Patna", "Guwahati", "Silchar", "Dibrugarh", "Kolkata",
    "Bhubaneswar", "Chennai", "Alappuzha", "Thrissur", "Mangaluru",
    "Mumbai", "Panaji", "Puducherry", "Vijayawada", "Visakhapatnam",
    "Thiruvananthapuram", "Tirunelveli", "Imphal", "Dispur"
}

def process_city(city, static_info):
    lat = static_info.get("latitude")
    lon = static_info.get("longitude")

    if not lat or not lon:
        return None, city

    try:
        raw_vector = get_data(lat, lon, city)
        feature_vector = [round(x, 2) for x in raw_vector]

        if len(feature_vector) != 9:
            raise Exception(f"Expected 9 features, got {len(feature_vector)}")

        rain_3d, rain_forecast, pop, humidity, cloud, temp, elevation, drainage, soil_moisture = feature_vector
        rain_elev_ratio = rain_3d / (elevation + 1)
        is_flood_prone = 1 if city in flood_prone_cities else 0
        ml_vector = [rain_3d, temp, humidity, elevation, rain_elev_ratio, is_flood_prone]

        score, label, rule_score, ml_score = hybrid_score(ml_vector, feature_vector, city)
        score = max(0, min(100, score))

        updated_entry = {
            "city": city, "latitude": lat, "longitude": lon, "risk": label, "score": score,
            "rule_score": rule_score, "ml_score": ml_score, "rain_3d": rain_3d,
            "rain_forecast": rain_forecast, "pop": pop, "humidity": humidity,
            "cloud": cloud, "temp": temp, "elevation": elevation,
            "drainage": drainage, "soil_moisture": soil_moisture
        }
        print(f"✔ {city}: Score={score}, Label={label}")
        return updated_entry, None

    except Exception as e:
        print(f"❌ {city}: Failed → {e}")
        return existing_data.get(city), city

print("🌍 Starting parallel data fetch for cities...\n")

output = []
failed_cities = []

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(process_city, city, static_info) for city, static_info in city_static_data.items()]
    for future in as_completed(futures):
        result, failed = future.result()
        if result:
            output.append(result)
        if failed:
            failed_cities.append(failed)

# Write updated data
with open(CACHE_PATH, "w") as f:
    f.write("[\n" + ",\n".join(json.dumps(entry) for entry in output) + "\n]")

# Save failed cities
if failed_cities:
    with open(FAILED_CITIES_PATH, "w") as f:
        json.dump(failed_cities, f, indent=2)

print("\n✅ Parallel update complete.")
if failed_cities:
    print("⚠️ The following cities failed and previous data was retained:")
    for city in failed_cities:
        print(" -", city)
else:
    print("🎉 All cities processed successfully.")
