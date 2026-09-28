import os
import re
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup
import folium
from folium.plugins import MarkerCluster, Search
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
tables = soup.find_all("table")

date_pattern = r"\d{1,2}\s*[\.\/]?\s*[\-–—\/]\s*\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b|\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b"

# Wörter, die rein für die Ortsnamenserkennung gefiltert werden
noise_words = [
    "ok", "jgt", "ssgt", "kjpt", "bjpt", "bjem", "bam", "wam", "wjpt", "mfc", "mhc", "u12", "u8", "u10", "u14", "u18", "u25", "u08",
    "finale", "ko", "ausgefallen", "ist", "jugend", "abt", "abt.", "schach", "verein", "schachabt", "schachabt.", "sabt", "sabt.", "spvgg",
    "sc", "sf", "sv", "vfl", "cup", "biber", "stand", "vom", "der", "u.", "und", "mit", "oder", "für",
    "in", "a.d.f.", "a.n.", "a.d.m.", "online", "dwz", "siehe", "oben", "parallel", "zur",
    "schnellschach", "frühlingsturnier", "familien", "meisterschaft", "off", "offene",
    "kinder", "jugendliche", "jünger", "altersklassen", "spielberechtigt", "stichtag", "joker", "neuen", "bei", "es", "sind", "römer"
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
    "stuttgart": "Stuttgart",
    "stgt": "Stuttgart",
    "stuttgarter": "Stuttgart",
    "wolfbusch": "Stuttgart Wolfbusch",
    "neuhausen": "Neuhausen auf den Fildern",
    "freiberg": "Freiberg am Neckar",
    "sulzbach": "Sulzbach an der Murr",
    "karlsruher": "Karlsruhe",
    "steinhausen": "Steinhausen an der Rottum"
}

def is_cell_ignored(text):
    clean = text.strip().lower()
    if clean in ["", "-", "–", "—", "ausgefallen"] or "ausgefallen" in clean:
        return True
    
    if clean.endswith("online") or "online dwz" in clean or "dwz siehe oben" in clean:
        return True
        
    return False

for table in tables:
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        
        working_cells = cells[:-1]
        row_text = " ".join([c.get_text(strip=True) for c in working_cells])
        
        if "ausgefallen" in row_text.lower():
            continue

        date_match = re.search(date_pattern, row_text)
        if not date_match:
            continue
            
        date_str = date_match.group(0).strip()
        
        if "stand vom" in row_text.lower() or "spielberechtigt" in row_text.lower():
            continue

        turnier_infos = []
        links = []
        turnier_cells = working_cells[1:]
        
        for cell in turnier_cells:
            cell_text = cell.get_text(separator=" ", strip=True)
            
            if not is_cell_ignored(cell_text):
                clean_cell_text = re.sub(r"[\-–—].*online.*$", "", cell_text, flags=re.IGNORECASE).strip()
                
                if clean_cell_text and not is_cell_ignored(clean_cell_text):
                    turnier_infos.append(clean_cell_text)
                    
                    for a in cell.find_all("a", href=True):
                        href = a["href"]
                        full_link = urllib.parse.urljoin(BASE_URL, href)
                        link_title = a.get_text(strip=True) or "Ausschreibung / Link"
                        links.append({"title": link_title, "url": full_link})

        if not turnier_infos:
            continue

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

        unique_infos = list(dict.fromkeys(turnier_infos))
        turnier_typ = ", ".join(unique_infos)

        events.append({
            "date": date_str,
            "location": clean_location,
            "type": turnier_typ,
            "links": links,
            "raw_text": row_text
        })

print(f"Gefundene gültige Turniere: {len(events)}")

# 2. Geocoding & Karte initialisieren
geolocator = Nominatim(user_agent="wam_schach_karte_app_v25")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

# Ebenen mit automatischer Auffächerung
group_wam = MarkerCluster(name="Amateurturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_wjpt = MarkerCluster(name="Jugendturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_ssgt = MarkerCluster(name="Schulschachturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_frauen = MarkerCluster(name="Mädchen- & Frauenturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_andere = MarkerCluster(name="Andere Turnierformen", spiderfyOnMaxZoom=True).add_to(wam_map)

# FeatureGroup für das Such-Plugin
search_group = folium.FeatureGroup(name="Such-Ebene", show=False).add_to(wam_map)

markers_added = 0
for event in events:
    search_query = f"{event['location']}, Baden-Württemberg, Germany"
    location_data = geocode(search_query)

    if not location_data:
        location_data = geocode(f"{event['location']}, Germany")

    if location_data:
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
        </div>
        """

        # Titel für die Suchleiste zusammenbauen (Ort, Datum & Typ)
        search_title = f"{event['location']} ({event['date']} - {event['type']})"

        def make_marker():
            return folium.Marker(
                location=[location_data.latitude, location_data.longitude],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{event['date']} - {event['location']} ({event['type']})",
                icon=folium.Icon(color="orange", icon="chess-rook", prefix="fa"),
            )

        # Marker für Suchfunktion als GeoJson/Marker registrieren
        search_marker = folium.Marker(
            location=[location_data.latitude, location_data.longitude],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=search_title,
            title=search_title,
            icon=folium.Icon(color="orange", icon="chess-rook", prefix="fa"),
        )
        search_marker.add_to(search_group)

        type_upper = event["type"].upper()
        standard_matched = False

        if "WAM" in type_upper or "BAM" in type_upper:
            make_marker().add_to(group_wam)
            standard_matched = True

        if any(kw in type_upper for kw in ["WJPT", "JGT", "KJPT", "BJPT", "BJEM", "KINDER", "JUGENDLICHE", "JUGEND"]):
            make_marker().add_to(group_wjpt)
            standard_matched = True

        if "SSGT" in type_upper:
            make_marker().add_to(group_ssgt)
            standard_matched = True

        if any(kw in type_upper for kw in ["MÄDCHEN", "FRAUEN", "MAEDCHEN", "MÄDCHENTAG"]):
            make_marker().add_to(group_frauen)
            standard_matched = True

        andere_keywords = ["SCHACH-WE", "BEGINNER", "CUP", "OPEN", "SONDER", "OFFENE", "SCHNELLSCHACH", "MEISTERSCHAFT"]
        is_andere_explicit = any(kw in type_upper for kw in andere_keywords)

        if is_andere_explicit or not standard_matched:
            make_marker().add_to(group_andere)

        markers_added += 1
        print(f"✔ Marker: {event['date']} [{event['type']}] in {event['location']}")
    else:
        print(f"❌ Ort nicht gefunden: '{event['location']}'")

# Suchleiste oben links zur Karte hinzufügen
Search(
    layer=search_group,
    geom_type="Point",
    placeholder="🔎 Ort, Datum oder Turnier suchen...",
    collapsed=False,
    search_label="title",
    weight=3
).add_to(wam_map)

folium.LayerControl(collapsed=False).add_to(wam_map)

print(f"\nErfolgreich auf der Karte gesetzte Marker: {markers_added}")

# 3. als index.html speichern
wam_map.save("index.html")
print("index.html erfolgreich erzeugt!")
