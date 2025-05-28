import flask
from flask import Flask, render_template, request,jsonify, make_response , send_from_directory
import json
import os
import requests
from dotenv import load_dotenv
from prediction import get_data
from score import score_flood_risk  # ✅ Using rule-based scoring
from llm_runner import generate_summary
import markdown2
from datetime import datetime
from hybrid_score import hybrid_score

load_dotenv()
app = flask.Flask(__name__)

# Supported cities
cities = [
    "Delhi", "Mumbai", "Kolkata", "Chennai", "Bangalore", "Hyderabad", "Ahmedabad", "Pune",
    "Patna", "Guwahati", "Lucknow", "Kanpur", "Nagpur", "Thiruvananthapuram", "Ranchi", "Raipur",
    "Coimbatore", "Madurai", "Varanasi", "Surat", "Vijayawada", "Bhubaneswar", "Agartala",
    "Jammu", "Dehradun", "Jamshedpur", "Nashik", "Udaipur", "Bikaner", "Silchar",
    "Alappuzha", "Thrissur", "Mangaluru", "Bilaspur", "Panaji", "Imphal", "Itanagar",
    "Aizawl", "Kohima", "Shillong", "Tirunelveli", "Dibrugarh", "Nanded", "Srinagar", "Puducherry",
    "Shimla", "Gangtok", "Dispur", "Amaravati", "Jaipur", "Bhagalpur", "Udupi", "Devanahalli"
]

@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")

@app.route("/plots.html")
def plots():
    return render_template("plots.html")

@app.route('/plots')
def show_plots():
    return render_template('plots.html')


@app.route('/plot-data')
def plot_data():
    try:
        with open('plot_data_cache.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/dashboard.html")
def dashboard():
    return render_template("dashboard.html")

@app.route('/heatmaps-data')
def heatmaps_data():
    try:
        with open('plot_data_cache.json', 'r') as f:
            data = json.load(f)

        # Top 5 high-risk cities
        top_risk = sorted(data, key=lambda x: x['score'], reverse=True)[:5]
        top_risk_cities = [{"city": d["city"], "score": d["score"]} for d in top_risk]

        # Top 5 rainfall cities
        top_rain = sorted(data, key=lambda x: x['rain_3d'], reverse=True)[:5]
        top_rainfall_cities = [{"city": d["city"], "rainfall": d["rain_3d"]} for d in top_rain]

        # Distribution for donut chart
        risk_levels = {"High Risk": 0, "Moderate Risk": 0, "Low Risk": 0}
        for d in data:
            risk_levels[d["risk"]] += 1

        # Heatmap coordinates
        heatmap_points = [{"lat": d["latitude"], "lon": d["longitude"], "score": d["score"]} for d in data]

        return jsonify({
            "top_risk": top_risk_cities,
            "top_rainfall": top_rainfall_cities,
            "distribution": risk_levels,
            "heatmap": heatmap_points
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/digest.html")
def digest():
    return render_template("digest.html",cities=cities)


@app.route('/generate-summary', methods=['POST'])
def generate_summary_api():
    data = request.get_json()
    mode = data.get("mode")
    city = data.get("city")

    try:
        with open("plot_data_cache.json", "r") as f:
            all_data = json.load(f)
    except Exception as e:
        return jsonify({"summary": f"Error loading cached data: {e}"}), 500

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
            return jsonify({"summary": f"No data available for {city}."})

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
        return jsonify({"error": "Invalid request"}), 400

    summary = generate_summary(prompt.strip())
    return jsonify({"summary": summary})


@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    summary = request.form.get("summary")
    city = request.form.get("city")

    if not summary:
        return "No summary to generate PDF", 400

    # Convert Markdown to HTML
    html_body = markdown2.markdown(summary)

    # Timestamp for header
    timestamp = datetime.now().strftime("%I:%M %p, %d %b %Y")


    # Build final HTML for PDF
    rendered_html = render_template("pdf_template.html",
        region=city.upper() if city else "COUNTRY",
        timestamp = datetime.now().strftime("%I:%M %p, %d %b %Y"),
        html_body=html_body
    )

    # Convert HTML to PDF (e.g. using pdfkit or weasyprint)
    # Example using pdfkit:


    import pdfkit
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')

    pdf = pdfkit.from_string(rendered_html, False,configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=flood_summary_{city}.pdf'
    return response

@app.route('/plot_data_cache.json')
def serve_plot_data():
    # assumes plot_data_cache.json lives next to app.py
    return send_from_directory(os.path.dirname(__file__), "plot_data_cache.json", mimetype="application/json")

@app.route('/preview-pdf', methods=['POST'])
def preview_pdf():
    summary = request.form.get("summary")
    city = request.form.get("city")

    if not summary:
        return "No summary to preview", 400

    html_body = markdown2.markdown(summary)
    rendered_html = render_template("pdf_template.html",
        region=city.upper() if city else "COUNTRY",
        timestamp = datetime.now().strftime("%I:%M %p, %d %b %Y"),
        html_body=html_body
    )

    import pdfkit
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')

    pdf = pdfkit.from_string(rendered_html, False, configuration=config)

    # Return as inline content
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=preview.pdf'
    return response


@app.route("/predicts.html")
def predicts():
    return render_template("predicts.html", cities=cities, cityname="Information about the city")

@app.route("/predicts.html", methods=["GET", "POST"])
def get_predicts():
    print("[INFO] get_predicts() called")

    cityname = request.form.get("city", "")
    # ✅ FIX: Treat cities as list of strings, not dicts
    cities_selected = [{'name': c, "sel": "selected" if c.lower() == cityname.lower() else ""} for c in cities]

    try:
        print("City received from form:", cityname)

        # Get lat/lon using WeatherAPI
        api_key = os.getenv("WEATHER_API_KEY")
        forecast_url = "https://api.weatherapi.com/v1/forecast.json"
        params = {
            "key": api_key,
            "q": f"{cityname},India",
            "days": 3
        }

        response = requests.get(forecast_url, params=params)
        print("Forecast API Status:", response.status_code)

        data = response.json()
        if "location" not in data:
            raise Exception("❌ Could not retrieve location")

        lat = data["location"]["lat"]
        lon = data["location"]["lon"]
        resolved_name = data["location"]["name"].strip().title()
        print(f"✅ Resolved City: {resolved_name}, Lat: {lat}, Lon: {lon}")

        
        final = [round(x, 2) for x in get_data(lat, lon, resolved_name)]

        if final is None:
            raise Exception("❌ Weather data unavailable")

        # Score prediction using custom rule-based logic
        # Build ML-specific vector for model
        rain_3d = final[0]
        temp = final[5]
        humidity = final[3]
        elevation = final[6]
        rain_elev_ratio = rain_3d / (elevation + 1)
        is_flood_prone = 1 if resolved_name in [
            "Patna", "Mumbai", "Chennai", "Kolkata", "Guwahati", "Bhubaneswar",
            "Visakhapatnam", "Thiruvananthapuram", "Alappuzha"
        ] else 0

        ml_vector = [rain_3d, temp, humidity, elevation, rain_elev_ratio, is_flood_prone]

        risk_score, risk_label, rule_score, ml_score = hybrid_score(ml_vector,final, resolved_name)


        return render_template("predicts.html",
            cityname=f"Information about {resolved_name}",
            cities=cities_selected,

            # Weather stats
            temp=round(final[5], 2),
            percip=round(final[1], 2),
            humidity=round(final[3], 2),
            cloudcover=round(final[4], 2),

            # Risk & scoring
            risk=risk_label,
            score=risk_score,
            rule_score=rule_score,     # ✅ shown in breakdown
            ml_score=ml_score,         # ✅ shown in breakdown

            # Supporting data
            rain_3d=round(final[0], 2),
            rain_2d=round(final[1], 2),
            pop=int(final[2] * 100),
            soil_moisture=round(final[8], 2),
            elevation=round(final[6], 2),
            drainage=int(final[7]),

            # ✅ Add lat/lon + city pin for frontend map
            lat=lat,
            lon=lon,
            pin_city=resolved_name
        )


    except Exception as e:
        print("❌Prediction failed:", e)
        return render_template("predicts.html", repr(e))


if __name__ == "__main__":
    app.run(debug=True)



