from flask import Flask, render_template, request
import requests
import pandas as pd
import plotly.express as px
import plotly
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import json

app = Flask(__name__)

def get_location(name):
    geolocator = Nominatim(user_agent="urban_app")
    return geolocator.geocode(name)

def fetch_infrastructure(lat, lon, key, value):
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:60];
    (
      node["{key}"~"{value}"](around:2000,{lat},{lon});
      way["{key}"~"{value}"](around:2000,{lat},{lon});
      relation["{key}"~"{value}"](around:2000,{lat},{lon});
    );
    out center;
    """
    headers = {"User-Agent": "urban-app"}
    try:
        res = requests.get(url, params={"data": query}, headers=headers)
        return res.json()
    except:
        return None

def parse_data(data, key, center):
    rows = []
    if not data:
        return pd.DataFrame()
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat and lon:
            distance = geodesic((center[0], center[1]), (lat, lon)).km
            rows.append({
                "lat": lat,
                "lon": lon,
                "name": tags.get("name", "Unknown"),
                "type": tags.get(key),
                "distance": round(distance, 2)
            })
    return pd.DataFrame(rows)

@app.route("/", methods=["GET", "POST"])
def home():
    data_bundle = []
    center_lat = None
    center_lon = None
    error = None
    if request.method == "POST":
        location = request.form.get("location")
        infra_input = request.form.get("infra")
        loc = get_location(location)
        if not loc:
            return render_template("index.html", error="Location not found")
        center_lat = loc.latitude
        center_lon = loc.longitude
        pairs = [p.strip() for p in infra_input.split("|")]
        for pair in pairs:
            if "=" not in pair: continue
            key, value = pair.split("=")
            key = key.strip()
            value = value.strip()
            data = fetch_infrastructure(center_lat, center_lon, key, value)
            df = parse_data(data, key, (center_lat, center_lon))
            if not df.empty:
                df = df.sort_values("distance")
                avg_val = df["distance"].mean()
                fig = px.bar(df, x="distance", y="name", orientation="h", title=f"{value} near {location}", labels={"distance": "Distance (km)"})
                fig.add_vline(x=avg_val, line_dash="dash", line_color="red")
                fig.add_annotation(x=avg_val, y=1, yref="paper", text=f"Avg = {round(avg_val,2)} km", showarrow=True, arrowhead=2, font=dict(color="red", size=14))
                graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
                data_bundle.append({"type": value, "graph": graphJSON, "data": df.to_dict(orient="records")})
        if not data_bundle: error = "No data found."
    return render_template("index.html", data_bundle=data_bundle, center_lat=center_lat, center_lon=center_lon, error=error)

if __name__ == "__main__":
    app.run(debug=True)