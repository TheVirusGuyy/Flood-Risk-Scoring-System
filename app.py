import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
import json
import io
from diskcache import Cache
import hashlib
from dotenv import load_dotenv
from prediction import get_data
from hybrid_score import hybrid_score
from score import score_flood_risk
from llm_runner import generate_summary
import markdown2
from datetime import datetime
import platform

app = FastAPI()
load_dotenv()

cache = Cache(directory='cache_dir')

app.mount("/static", StaticFiles(directory="static"), name="static")
# Mount static files and templates
templates = Jinja2Templates(directory="templates")


# Load supported cities
cities = [
    "Delhi", "Mumbai", "Kolkata", "Chennai", "Bangalore", "Hyderabad", "Ahmedabad", "Pune",
    "Patna", "Guwahati", "Lucknow", "Kanpur", "Nagpur", "Thiruvananthapuram", "Ranchi", "Raipur",
    "Coimbatore", "Madurai", "Varanasi", "Surat", "Vijayawada", "Bhubaneswar", "Agartala",
    "Jammu", "Dehradun", "Jamshedpur", "Nashik", "Udaipur", "Bikaner", "Silchar",
    "Alappuzha", "Thrissur", "Mangaluru", "Bilaspur", "Panaji", "Imphal", "Itanagar",
    "Aizawl", "Kohima", "Shillong", "Tirunelveli", "Dibrugarh", "Nanded", "Srinagar", "Puducherry",
    "Shimla", "Gangtok", "Dispur", "Amaravati", "Jaipur", "Bhagalpur", "Udupi", "Devanahalli"
]

@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/plots.html", response_class=HTMLResponse)
def plots(request: Request):
    return templates.TemplateResponse("plots.html", {"request": request})

@app.get("/plot-data")
def plot_data():
    try:
        with open("plot_data_cache.json", "r") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/plot_data_cache.json")
def serve_plot_data():
    return FileResponse("plot_data_cache.json", media_type="application/json")

@app.get("/dashboard.html", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/digest.html", response_class=HTMLResponse)
def digest(request: Request):
    return templates.TemplateResponse("digest.html", {"request": request, "cities": cities})

@app.post("/generate-summary")
async def generate_summary_api(request: Request):
    data = await request.json()
    mode = data.get("mode")
    city = data.get("city")

    # Build a unique cache key based on summary type and city
    city_key = (city or "").strip().lower()
    key_raw = f"summary:{mode}:{city_key}"
    cache_key = hashlib.sha256(key_raw.encode()).hexdigest()

    # Check cache first
    cached_summary = cache.get(cache_key)
    if cached_summary is not None:
        return JSONResponse(content={"summary": cached_summary, "cached": True})

    # --- The rest of your summary logic (no changes needed here!) ---
    try:
        with open("plot_data_cache.json", "r") as f:
            all_data = json.load(f)
    except Exception as e:
        return JSONResponse(content={"summary": f"Error loading cached data: {e}"}, status_code=500)

    if mode == "country":
        top_cities = sorted(all_data, key=lambda x: x['score'], reverse=True)[:10]
        city_descriptions = []
        for c in top_cities:
            city_descriptions.append(
                f"{c['city']}: Score {c['score']} ({c['risk']}), Rain: {c['rain_3d']}mm, Humidity: {c['humidity']}%, Cloud: {c['cloud']}%, Elevation: {c['elevation']}m, Drainage: {c['drainage']}, Soil: {c['soil_moisture']}%"
            )
        prompt = f"""
            You are a disaster risk analyst preparing a national flood risk advisory for India. You have been given the latest hybrid flood risk scores and key environmental indicators for the top 10 high-risk cities.

            Your task is to generate a professional markdown-formatted summary that reflects **actual environmental differences and scoring insights**, not just a plain restatement of numbers.

            📋 **Guidelines for Writing the Report:**

            - Begin with a brief national outlook that identifies patterns (e.g., coastal cities dominating, high humidity zones, inland flood build-ups).
            - Then provide **a short paragraph for each of the top 5 cities** including:
                - The current risk level (High/Moderate/etc.)
                - What is pushing the score up? (e.g., high rainfall + poor drainage)
                - Any surprising condition (e.g., low rain but still Moderate risk due to poor elevation/drainage)
            - Highlight why a city stands out **compared to others**, based on a mix of variables.
            - Use section headers: `🌍 National Overview:` and `🏙️ City Reports:`
            - Avoid using the same sentence pattern for each city—write as if presenting to experts.
            - Use **bold formatting** for phrases like `**High Risk**` or `**drainage vulnerability**`.

            Your inputs are:

            {chr(10).join(city_descriptions)}
            """
    elif mode == "city" and city:
        city_info = next((c for c in all_data if c['city'].lower() == city.lower()), None)
        if not city_info:
            return JSONResponse(content={"summary": f"No data available for {city}."})

        prompt = f"""
            You are a climate-aware assistant reporting flood risk conditions for the Indian city of **{{city}}**.

            Your goal is to provide a clear, informative and well-structured report, written in natural, accessible language that could be shown directly in a visual PDF dashboard.

            📝 Format:
            - Begin with a bold header like `## 🏙️ Flood Risk Report: {city}`
            - Write **2–3 short paragraphs** summarizing:
            - Current rainfall patterns (3-day and forecast)
            - Atmospheric conditions (humidity, cloud, temperature)
            - Geographic/demographic factors (elevation, drainage, soil moisture)
            - Risk interpretation: Why is the city at low/moderate/high risk?
            - Emphasize **flood-relevant effects**, not just plain weather stats.
            - End with a one-line summary like:
            `**Conclusion**: Based on current indicators, flood risk in {city} is low and manageable.`

            📌 Highlight important terms (risk level, rain, drainage quality) using `**bold formatting**`.

            🔒 Limit response to ~450–500 tokens max.

            Metrics:
            - Rainfall (3 days): {city_info['rain_3d']} mm
            - Forecasted Rain: {city_info['rain_forecast']} mm
            - Probability of Rain: {city_info['pop']}%
            - Humidity: {city_info['humidity']}%
            - Cloud Cover: {city_info['cloud']}%
            - Temperature: {city_info['temp']}°C
            - Elevation: {city_info['elevation']} m
            - Drainage Quality: {city_info['drainage']}
            - Soil Moisture: {city_info['soil_moisture']}%
            - Risk Score: {city_info['score']} → **{city_info['risk']}**
            """
    else:
        return JSONResponse(content={"error": "Invalid request"})

    summary = generate_summary(prompt.strip())
    # Save to cache for 1 hour
    cache.set(cache_key, summary, expire=3600)
    return JSONResponse(content={"summary": summary, "cached": False})


@app.post("/download-pdf")
async def download_pdf(request: Request):
    form = await request.form()
    summary = form.get("summary")
    city = form.get("city")
    html_body = markdown2.markdown(summary)
    rendered_html = templates.get_template("pdf_template.html").render(
        region=city.upper() if city else "COUNTRY",
        timestamp=datetime.now().strftime("%I:%M %p, %d %b %Y"),
        html_body=html_body
    )

    if platform.system() == 'Windows':
        import pdfkit
        config = pdfkit.configuration(wkhtmltopdf=r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe")
        pdf = pdfkit.from_string(rendered_html, False, configuration=config)
    else:
        from weasyprint import HTML
        pdf = HTML(string=rendered_html).write_pdf()

    headers = {
        "Content-Disposition": f"attachment; filename=flood_summary_{city}.pdf"
    }
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type='application/pdf',
        headers=headers
    )

@app.post("/preview-pdf")
async def preview_pdf(request: Request):
    form = await request.form()
    summary = form.get("summary")
    city = form.get("city")

    if not summary:
        return JSONResponse(content={"error": "No summary to preview"}, status_code=400)

    html_body = markdown2.markdown(summary)
    rendered_html = templates.get_template("pdf_template.html").render(
        region=city.upper() if city else "COUNTRY",
        timestamp=datetime.now().strftime("%I:%M %p, %d %b %Y"),
        html_body=html_body
    )

    if platform.system() == 'Windows':
        import pdfkit
        config = pdfkit.configuration(wkhtmltopdf=r"C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe")
        pdf = pdfkit.from_string(rendered_html, False, configuration=config)
    else:
        from weasyprint import HTML
        pdf = HTML(string=rendered_html).write_pdf()

    # Use StreamingResponse for the PDF preview
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=preview.pdf"}
    )




@app.get("/predicts.html", response_class=HTMLResponse)
def predicts(request: Request):
    return templates.TemplateResponse("predicts.html", {"request": request, "cities": cities, "cityname": ""})

@app.post("/predicts.html", response_class=HTMLResponse)
async def get_predicts(request: Request):
    form = await request.form()
    cityname = form.get("city", "").strip().title()
    # This is only needed if you ever have a dropdown or select.
    cities_selected = [{'name': c, "sel": "selected" if c.lower() == cityname.lower() else ""} for c in cities]

    try:
        import requests
        api_key = os.getenv("WEATHER_API_KEY")
        forecast_url = "https://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": api_key,
            "q": f"{cityname},India",
            "days": 3
        }
        response = requests.get(forecast_url, params=params)
        data = response.json()
        if "location" not in data:
            raise Exception("❌ Could not retrieve location")

        lat = data["location"]["lat"]
        lon = data["location"]["lon"]
        resolved_name = data["location"]["name"].strip().title()

        final = [round(x, 2) for x in get_data(lat, lon, resolved_name)]

        rain_3d = final[0]
        temp = final[5]
        humidity = final[3]
        elevation = final[6]
        rain_elev_ratio = rain_3d / (elevation + 1)
        is_flood_prone = 1 if resolved_name in [
            "Patna", "Guwahati", "Silchar", "Dibrugarh", "Kolkata",
            "Bhubaneswar", "Chennai", "Alappuzha", "Thrissur", "Mangaluru",
            "Mumbai", "Panaji", "Puducherry", "Vijayawada", "Visakhapatnam",
            "Thiruvananthapuram", "Tirunelveli", "Imphal", "Dispur"
        ] else 0

        ml_vector = [rain_3d, temp, humidity, elevation, rain_elev_ratio, is_flood_prone]

        risk_score, risk_label, rule_score, ml_score = hybrid_score(ml_vector, final, resolved_name)

        return templates.TemplateResponse("predicts.html", {
            "request": request,
            "cityname": f"Information about {resolved_name}",
            "cities": cities,
            # If ever need selected-state logic, provide it under a different key:
            # "cities_selected": cities_selected,
            "temp": round(final[5], 2),
            "percip": round(final[1], 2),
            "humidity": round(final[3], 2),
            "cloudcover": round(final[4], 2),
            "risk": risk_label,
            "score": risk_score,
            "rule_score": rule_score,
            "ml_score": ml_score,
            "rain_3d": round(final[0], 2),
            "rain_2d": round(final[1], 2),
            "pop": int(final[2] * 100),
            "soil_moisture": round(final[8], 2),
            "elevation": round(final[6], 2),
            "drainage": int(final[7]),
            "lat": lat,
            "lon": lon,
            "pin_city": resolved_name
        })

    except Exception as e:
        return templates.TemplateResponse("predicts.html", {
            "request": request,
            "cityname": repr(e),
            "cities": cities,
        })

@app.get("/heatmaps-data")
def heatmaps_data():
    try:
        with open('plot_data_cache.json', 'r') as f:
            data = json.load(f)

        top_risk = sorted(data, key=lambda x: x['score'], reverse=True)[:5]
        top_risk_cities = [{"city": d["city"], "score": d["score"]} for d in top_risk]

        top_rain = sorted(data, key=lambda x: x['rain_3d'], reverse=True)[:5]
        top_rainfall_cities = [{"city": d["city"], "rainfall": d["rain_3d"]} for d in top_rain]

        risk_levels = {"High Risk": 0, "Moderate Risk": 0, "Low Risk": 0}
        for d in data:
            risk_levels[d["risk"]] += 1

        heatmap_points = [{"lat": d["latitude"], "lon": d["longitude"], "score": d["score"]} for d in data]

        return JSONResponse(content={
            "top_risk": top_risk_cities,
            "top_rainfall": top_rainfall_cities,
            "distribution": risk_levels,
            "heatmap": heatmap_points
        })

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
print("\n📋 Registered routes:")
for route in app.routes:
    print(f"- Name: {route.name} | Path: {getattr(route, 'path', '')}")
