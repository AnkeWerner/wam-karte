import os
import re
import urllib3
import requests
from bs4 import BeautifulSoup
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# 0. SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Quellseite abrufen
URL = "https://www.svw.info/wts/terminuebersichten/18322-terminuebersicht-wjpt-und-wam-2025-26"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

response = requests.get(URL, headers=headers, verify=False)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

events = []

# Suche in allen Tabellenzeilen (tr) und Absätzen (p/div)
candidate_elements = soup.find_all(["tr", "p", "li", "div"])

# Muster für Datum (z. B. 25.10.2025, 25./26.10.2025, 05.10.25)
date_pattern = r"\b\d{1,2}\.(?:\/\d{1,2}\.)?\d{1,2}\.(?:\d{2}|\d{4})\b"

for el in candidate_elements:
    text = el.get_text(separator=" ", strip=True)
    
    # Suche nach Datum im Text
    date_match = re.search(date_pattern, text)
    if date_match:
        date_str = date_match.group(0)
        
        # Restlichen Text als Ort/Bezeichnung aufbereiten
        clean_text = text.replace(date_str, "").strip()
        
        # Typische Füllwörter und Tage entfernen
        clean_text = re.sub(r"\b(Sa|So|Mo|Di|Mi|Do|Fr|Sa\/So|So\/Sa)\b", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"[,\-\/:]", " ", clean_text)
        
        # WAM / WJPT Nummerierungen bereinigen
        words = clean_text.split()
        filtered_words = [w for w in words if w.lower() not in ["wam", "wjpt", "turnier", "runde", "ausrichter", "und"]]
        
        location_candidate = " ".join(filtered_words).strip()
        
        # Wenn ein sinnvoller Ort übrig bleibt
        if 2 < len(location_candidate) < 40 and not any(e["location"] == location_candidate for e in events):
            events.append({"date": date_str, "location": location_candidate, "full_info": text})

print(f"Gefundene Termine: {len(events)}")
for e in events:
    print(f" - {e['date']}: {e['location']}")

# 3. Geocoding & Karte initialisieren
geolocator = Nominatim(user_agent="wam_schach_karte_app_v2")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

markers_added = 0
for event in events:
    # Ortssuche für Baden-Württemberg eingrenzen
    search_query = f"{event['location']}, Baden-Württemberg, Germany"
    location_data = geocode(search_query)

    if not location_data:
        location_data = geocode(f"{event['location']}, Germany")

    if location_data:
        popup_html = f"""
        <div style='font-family: sans-serif; font-size: 14px;'>
            <h4 style='margin-bottom: 5px; color: #1a5f7a;'>WAM / WJPT Turnier</h4>
            <b>Datum:</b> {event['date']}<br>
            <b>Ort:</b> {event['location']}<br>
            <small style='color: #666;'>{event['full_info']}</small>
        </div>
        """
        folium.Marker(
            location=[location_data.latitude, location_data.longitude],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{event['date']} - {event['location']}",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(wam_map)
        markers_added += 1

print(f"Erfolgreich auf der Karte gesetzte Marker: {markers_added}")

# 4. Als index.html speichern
wam_map.save("index.html")
print("index.html erfolgreich erzeugt!")
