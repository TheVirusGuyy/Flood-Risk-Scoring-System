import json
import requests
from datetime import datetime, timedelta

INPUT_PATH = "static/city_static_data.json"
BACKUP_PATH = "static/city_static_data_backup.json"  # in case something breaks
API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
DAY_OFFSET = 3  # Use data from x days ago

# Load city data
with open(INPUT_PATH, "r") as f:
    cities = json.load(f)

# Backup original
with open(BACKUP_PATH, "w") as backup:
    json.dump(cities, backup, indent=2)

updated = 0 
failed = 0

print("🌱 Updating soil moisture values from NASA POWER API...\n")
for city, data in cities.items():
    lat = round(data.get("latitude", 0), 2)
    lon = round(data.get("longitude", 0), 2)

    if not lat or not lon:
        print(f"⚠️  Skipping {city} due to missing coordinates.")
        failed += 1
        continue

    # Store current value in case we need to revert
    current_sm = data.get("soil_moisture")
    
    date_str = (datetime.utcnow().date() - timedelta(days=DAY_OFFSET)).strftime("%Y%m%d")
    params = {
        "parameters": "GWETROOT",
        "start": date_str,
        "end": date_str,
        "latitude": lat,
        "longitude": lon,
        "community": "ag",
        "format": "JSON"
    }
    
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()  # Raises exception for 4XX/5XX responses
        json_data = response.json()
        sm_raw = json_data.get("properties", {}).get("parameter", {}).get("GWETROOT", {}).get(date_str)

        if sm_raw is None or sm_raw == -999:
            print(f"❌ {city}: No soil moisture data available. Keeping previous value.")
            failed += 1
            continue

        sm_percent = round(sm_raw * 100, 2)
        cities[city]["soil_moisture"] = sm_percent
        print(f"✅ {city}: {sm_percent}%")
        updated += 1

    except Exception as e:
        print(f"❌ {city}: Error fetching soil moisture → {e}. Keeping previous value.")
        # Restore original value if it existed
        if current_sm is not None:
            cities[city]["soil_moisture"] = current_sm
        failed += 1

# Write updated data back to file
with open(INPUT_PATH, "w") as f:
    json.dump(cities, f, indent=2)

print(f"\n🔁 Finished updating {updated} cities. Failed: {failed}")