import os
import re
from bs4 import BeautifulSoup
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import requests

# 1. Quellseite abrufen (SVW WAM Termine)
URL = "https://svw.info/wts/terminuebersichten/18322-terminuebersicht-wjpt-und-wam-2025-26"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

response = requests.get(URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

# 2. Termine extrahieren
events = []
text_content = soup.get_text()

pattern = r"((?:Sa|So|Mo|Di|Mi|Do|Fr)?-?(?:Sa|So|Mo|Di|Mi|Do|Fr)?,\s*\d{1,2}\.\d{1,2}\.(?:\d{2}|\d{4})),\s*([^;\n]+)"
matches = re.findall(pattern, text_content)

for date_str, location in matches:
    clean_location = location.strip()
    if len(clean_location) > 2 and len(clean_location) < 50:
        events.append({"date": date_str.strip(), "location": clean_location})

geolocator = Nominatim(user_agent="wam_schach_karte")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# 3. Karte initialisieren (Baden-Württemberg)
wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

# 4. Orte geocodieren und Marker setzen
for event in events:
    query = f"{event['location']}, Baden-Württemberg, Germany"
    location_data = geocode(query)

    if not location_data:
        location_data = geocode(f"{event['location']}, Germany")

    if location_data:
        popup_html = f"""
        <div style='font-family: sans-serif;'>
            <h4>WAM Turnier</h4>
            <b>Datum:</b> {event['date']}<br>
            <b>Ort:</b> {event['location']}
        </div>
        """
        folium.Marker(
            location=[location_data.latitude, location_data.longitude],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{event['date']} - {event['location']}",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(wam_map)

# 5. Karte als index.html speichern (wichtig für GitHub Pages!)
wam_map.save("index.html")
print("Karte erfolgreich erstellt!")
