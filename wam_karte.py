import os
import re
import urllib.parse
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
BASE_URL = "https://www.svw.info"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

response = requests.get(URL, headers=headers, verify=False)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

events = []

# Suche nach allen Tabellen auf der Seite
tables = soup.find_all("table")

date_pattern = r"\b\d{1,2}\.(?:\/\d{1,2}\.)?\d{1,2}\.(?:\d{2}|\d{4})\b"

# Wörter, die aus dem Ortsnamen herausgefiltert werden
noise_words = [
    "ok", "jgt", "ssgt", "kjpt", "bjpt", "bam", "wam", "wjpt", "mfc", "mhc", "u12", "u8", "u10", "u14", "u18", "u25", "u08",
    "finale", "ko", "ausgefallen", "ist", "jugend", "abt", "schach", "verein", "schachabt", "sabt", "spvgg",
    "sc", "sf", "sv", "vfl", "cup", "biber", "stand", "vom", "der", "u.", "und", "mit", "oder", "für",
    "in", "a.d.f.", "a.n.", "a.d.m.", "online", "dwz", "siehe", "oben", "parallel", "zur", "bjem", "stgt",
    "mädchen", "schnellschach", "mädchentag", "frühlingsturnier", "familien", "meisterschaft", "off", "offene",
    "stuttgarter", "kinder", "jugendliche", "jünger", "altersklassen", "spielberechtigt", "stichtag", "joker", "neuen", "bei", "es", "sind", "römer"
]

location_mapping = {
    "rommelshausen": "Kernen im Remstal",
    "jedesheim": "Jedesheim Illertissen",
    "renningen": "Renningen",
    "ottenbronn": "Althengstett Ottenbronn",
    "althengstett": "Althengstett",
    "welzheim": "Welzheim",
    "leipheim": "Leipheim",
    "magstadt": "Magstadt",
    "böblingen": "Böblingen",
    "filderstadt": "Filderstadt",
    "heumaden": "Stuttgart Heumaden",
    "niefern": "Niefern-Öschelbronn",
    "öschelbronn": "Niefern-Öschelbronn",
    "sillenbuch": "Stuttgart Sillenbuch",
    "neuhausen": "Neuhausen auf den Fildern",
    "freiberg": "Freiberg am Neckar",
    "sulzbach": "Sulzbach an der Murr",
    "karlsruher": "Karlsruhe"
}

def is_cell_ignored(text, is_andere_form=False):
    clean = text.strip().lower()
    if clean in ["", "-", "–", "—", "ausgefallen"] or "ausgefallen" in clean:
        return True
    
    # Neu: Wenn es die Spalte "andere Turnierform" ist und der Text auf "online" endet -> ignorieren
    if is_andere_form and clean.endswith("online"):
        return True
        
    return False

for table in tables:
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        
        # Ignoriere die letzte Spalte ("erl.")
        working_cells = cells[:-1]
        
        row_text = " ".join([c.get_text(strip=True) for c in working_cells])
        date_match = re.search(date_pattern, row_text)
        
        if not date_match:
            continue
            
        date_str = date_match.group(0)
        
        if "stand vom" in row_text.lower() or "spielberechtigt" in row_text.lower():
            continue

        # Untersuche Turnier-Spalten (WJPT, WAM, SSGT, andere)
        turnier_infos = []
        links = []
        
        # Spalten-Inhalte durchgehen (ab Index 1, da Index 0 das Datum/Wochentag ist)
        turnier_cells = working_cells[1:]
        num_turnier_cells = len(turnier_cells)
        
        for idx, cell in enumerate(turnier_cells):
            cell_text = cell.get_text(separator=" ", strip=True)
            
            # Annahme: Die Spalte "andere Turnierform" ist typischerweise die vierte Turnierspalte (Index 3)
            # bzw. die vorletzte Arbeitsspalte vor dem Ort.
            is_andere_form = (idx == 3 or (num_turnier_cells >= 4 and idx == num_turnier_cells - 2))
            
            if not is_cell_ignored(cell_text, is_andere_form=is_andere_form):
                # Sammle Text
                turnier_infos.append(cell_text)
                
                # Sammle evtl. Links
                for a in cell.find_all("a", href=True):
                    href = a["href"]
                    full_link = urllib.parse.urljoin(BASE_URL, href)
                    link_title = a.get_text(strip=True) or "Ausschreibung / Link"
                    links.append({"title": link_title, "url": full_link})

        # WENN in allen Turnierspalten nur Ignoriertes steht -> Zeile überspringen
        if not turnier_infos:
            continue

        # Ortsextraktion aus der Zeile
        clean_text = row_text.replace(date_str, "").strip()
        clean_text = re.sub(r"\b(Sa|So|Mo|Di|Mi|Do|Fr|Sa\/So|So\/Sa)\b", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"\d+\.", "", clean_text)
        clean_text = re.sub(r"[,\-\/:\+\(\)]", " ", clean_text)

        raw_words = clean_text.split()
        city_words = []
        for w in raw_words:
            w_clean = w.lower().strip(".")
            if w_clean not in noise_words and not w_clean.isdigit() and len(w_clean) > 1:
                city_words.append(w)

        raw_location = " ".join(city_words).strip()
        clean_location = raw_location

        for key, target_city in location_mapping.items():
            if key in raw_location.lower() or key in row_text.lower():
                clean_location = target_city
                break

        turnier_typ = ", ".join(dict.fromkeys(turnier_infos))

        if len(clean_location) >= 3 and not any(e["date"] == date_str and e["location"] == clean_location for e in events):
            events.append({
                "date": date_str,
                "location": clean_location,
                "type": turnier_typ,
                "links": links,
                "full_info": row_text
            })

print(f"Gefundene gültige Turniere: {len(events)}")

# 2. Geocoding & Karte initialisieren
geolocator = Nominatim(user_agent="wam_schach_karte_app_v7")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

markers_added = 0
for event in events:
    search_query = f"{event['location']}, Baden-Württemberg, Germany"
    location_data = geocode(search_query)

    if not location_data:
        location_data = geocode(f"{event['location']}, Germany")

    if location_data:
        # Erstelle HTML für Links
        links_html = ""
        if event["links"]:
            links_html = "<div style='margin-top: 8px; border-top: 1px solid #ccc; padding-top: 5px;'>"
            for l in event["links"]:
                links_html += f"<a href='{l['url']}' target='_blank' style='color: #0066cc; font-weight: bold; text-decoration: underline;'>🔗 {l['title']}</a><br>"
            links_html += "</div>"

        popup_html = f"""
        <div style='font-family: sans-serif; font-size: 13px; line-height: 1.4;'>
            <h4 style='margin: 0 0 5px 0; color: #1a5f7a;'>{event['type']}</h4>
            <b>Datum:</b> {event['date']}<br>
            <b>Ort:</b> {event['location']}<br>
            {links_html}
            <br><small style='color: #666;'>{event['full_info']}</small>
        </div>
        """
        folium.Marker(
            location=[location_data.latitude, location_data.longitude],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{event['date']} - {event['location']} ({event['type']})",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(wam_map)
        markers_added += 1
        print(f"✔ Marker: {event['date']} [{event['type']}] in {event['location']}")

print(f"\nErfolgreich auf der Karte gesetzte Marker: {markers_added}")

# 3. als index.html speichern
wam_map.save("index.html")
print("index.html erfolgreich erzeugt!")
