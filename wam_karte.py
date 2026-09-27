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
candidate_elements = soup.find_all(["tr", "p", "li", "div"])

date_pattern = r"\b\d{1,2}\.(?:\/\d{1,2}\.)?\d{1,2}\.(?:\d{2}|\d{4})\b"

# Liste von Wörtern, die nicht zum Ortsnamen gehören
noise_words = [
    "ok", "jgt", "ssgt", "kjpt", "bjpt", "bam", "wam", "wjpt", "mfc", "u12",
    "finale", "ko", "ausgefallen", "ist", "jugend", "abt", "schach", "verein",
    "sc", "sf", "sv", "vfl", "cup", "biber", "stand", "vom", "der", "u.", "und",
    "in", "a.d.f.", "a.n.", "a.d.m."
]

for el in candidate_elements:
    text = el.get_text(separator=" ", strip=True)
    
    date_match = re.search(date_pattern, text)
    if date_match:
        date_str = date_match.group(0)
        
        # Ausschluss von "Stand vom ..."
        if "stand vom" in text.lower():
            continue

        # Text bereinigen
        clean_text = text.replace(date_str, "").strip()
        clean_text = re.sub(r"\b(Sa|So|Mo|Di|Mi|Do|Fr|Sa\/So|So\/Sa)\b", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\d+\.", "", clean_text)  # Entfernt Ordinalzahlen wie "25."
        clean_text = re.sub(r"[,\-\/:]", " ", clean_text)

        # Einzelne Wörter filtern für Geocoding
        raw_words = clean_text.split()
        city_words = []
        for w in raw_words:
            w_lower = w.lower().strip(".")
            if w_lower not in noise_words and not w_lower.isdigit():
                city_words.append(w)

        clean_location = " ".join(city_words).strip()

        # Spezialfälle korrigieren
        if "neuhausen" in text.lower():
            clean_location = "Neuhausen auf den Fildern"
        elif "sillenbuch" in text.lower():
            clean_location = "Stuttgart Sillenbuch"
        elif "freiberg" in text.lower():
            clean_location = "Freiberg am Neckar"
        elif "sulzbach" in text.lower():
            clean_location = "Sulzbach an der Murr"

        if len(clean_location) >= 3 and not any(e["date"] == date_str and e["location"] == clean_location for e in events):
            events.append({
                "date": date_str,
                "location": clean_location,
                "full_info": text
            })

print(f"Gefundene & bereinigte Termine: {len(events)}")

# 2. Geocoding & Karte initialisieren
geolocator = Nominatim(user_agent="wam_schach_karte_app_v3")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

markers_added = 0
for event in events:
    search_query = f"{event['location']}, Baden-Württemberg, Germany"
    location_data = geocode(search_query)

    if not location_data:
        # Fallback-Suche ohne Bundesland
        location_data = geocode(f"{event['location']}, Germany")

    if location_data:
        popup_html = f"""
        <div style='font-family: sans-serif; font-size: 13px;'>
            <h4 style='margin: 0 0 5px 0; color: #1a5f7a;'>WAM / WJPT Turnier</h4>
            <b>Datum:</b> {event['date']}<br>
            <b>Ort:</b> {event['location']}<br><br>
            <small style='color: #555;'>{event['full_info']}</small>
        </div>
        """
        folium.Marker(
            location=[location_data.latitude, location_data.longitude],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{event['date']} - {event['location']}",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(wam_map)
        markers_added += 1
        print(f"✔ Marker gesetzt: {event['date']} in {event['location']}")
    else:
        print(f"❌ Ort nicht gefunden: '{event['location']}'")

print(f"\nErfolgreich auf der Karte gesetzte Marker: {markers_added}")

# 3. als index.html speichern
wam_map.save("index.html")
print("index.html erfolgreich erzeugt!")
