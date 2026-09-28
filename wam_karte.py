import os
import re
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup
import folium
from folium.plugins import MarkerCluster, LocateControl
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from datetime import datetime

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

date_pattern = r"\d{1,2}\s*[\.\/]?\s*[\-–—\/]?\s*\d{0,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b|\d{1,2}\.\d{1,2}\."

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

# Zuverlässiges Datums-Parsing (erkennt auch "27.09.", "12.-13.10.2025" etc.)
def parse_to_iso(date_str):
    # Sucht Tag(e), Monat und Jahr
    match = re.search(r'(?:(\d{1,2})[\.\/–—\-]+)?(\d{1,2})\.(\d{1,2})\.?(?:\s*(\d{2,4}))?', date_str)
    if match:
        day_start, day_end, month, year = match.groups()
        day = day_end if day_end else day_start
        
        # Jahr ergänzen, falls nicht in der Tabelle vorhanden
        if not year:
            # Saisonslogik: Monate Sep-Dez -> 2025, Jan-Aug -> 2026
            year = "2025" if int(month) >= 9 else "2026"
        elif len(year) == 2:
            year = "20" + year
            
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return ""
    return ""

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

        date_match = re.search(r'\b\d{1,2}\s*[\.\/]?\s*[\-–—\/]?\s*\d{0,2}\.\d{1,2}\.(?:\d{4}|\d{2})?\b', row_text)
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
        iso_date = parse_to_iso(date_str)

        events.append({
            "date": date_str,
            "iso_date": iso_date,
            "location": clean_location,
            "type": turnier_typ,
            "links": links
        })

print(f"Gefundene gültige Turniere: {len(events)}")

# 2. Geocoding & Karte initialisieren
geolocator = Nominatim(user_agent="wam_schach_karte_app_v38")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

# Standort-Button hinzufügen
LocateControl(
    auto_start=False,
    flyTo=True,
    keepCurrentZoomLevel=False,
    strings={"title": "Mein Standort"}
).add_to(wam_map)

# Ebenen anlegen
group_wam = MarkerCluster(name="Amateurturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_wjpt = MarkerCluster(name="Jugendturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_ssgt = MarkerCluster(name="Schulschachturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_frauen = MarkerCluster(name="Mädchen- & Frauenturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
group_andere = MarkerCluster(name="Andere Turnierformen", spiderfyOnMaxZoom=True).add_to(wam_map)

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

        def make_marker():
            m = folium.Marker(
                location=[location_data.latitude, location_data.longitude],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{event['date']} - {event['location']} ({event['type']})",
                icon=folium.Icon(color="orange", icon="chess-rook", prefix="fa"),
            )
            m.options['search_text'] = f"{event['location']} {event['date']} {event['type']}".lower()
            m.options['iso_date'] = event['iso_date']
            return m

        type_upper = event["type"].upper()
        standard_matched = False

        if "WAM" in type_upper or "BAM" in type_upper:
            m = make_marker()
            m.add_to(group_wam)
            standard_matched = True

        if any(kw in type_upper for kw in ["WJPT", "JGT", "KJPT", "BJPT", "BJEM", "KINDER", "JUGENDLICHE", "JUGEND"]):
            m = make_marker()
            m.add_to(group_wjpt)
            standard_matched = True

        if "SSGT" in type_upper:
            m = make_marker()
            m.add_to(group_ssgt)
            standard_matched = True

        if any(kw in type_upper for kw in ["MÄDCHEN", "FRAUEN", "MAEDCHEN", "MÄDCHENTAG"]):
            m = make_marker()
            m.add_to(group_frauen)
            standard_matched = True

        andere_keywords = ["SCHACH-WE", "BEGINNER", "CUP", "OPEN", "SONDER", "OFFENE", "SCHNELLSCHACH", "MEISTERSCHAFT"]
        is_andere_explicit = any(kw in type_upper for kw in andere_keywords)

        if is_andere_explicit or not standard_matched:
            m = make_marker()
            m.add_to(group_andere)

        markers_added += 1

folium.LayerControl(collapsed=False).add_to(wam_map)

map_var_name = wam_map.get_name()

# Meta-Tags & Favicon
favicon_svg = urllib.parse.quote("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="20" fill="#1a5f7a"/>
  <path d="M 25 80 L 75 80 L 75 70 L 25 70 Z M 30 70 L 35 45 L 65 45 L 70 70 Z M 32 45 L 30 30 L 38 30 L 38 37 L 46 37 L 46 30 L 54 30 L 54 37 L 62 37 L 62 30 L 70 30 L 68 45 Z" fill="#f2a900"/>
</svg>""")
favicon_data_url = f"data:image/svg+xml,{favicon_svg}"

preview_svg = urllib.parse.quote("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
  <rect width="1200" height="630" fill="#1a5f7a"/>
  <g opacity="0.08" fill="#ffffff">
    <rect x="0" y="0" width="150" height="150"/><rect x="300" y="0" width="150" height="150"/><rect x="600" y="0" width="150" height="150"/><rect x="900" y="0" width="150" height="150"/>
    <rect x="150" y="150" width="150" height="150"/><rect x="450" y="150" width="150" height="150"/><rect x="750" y="150" width="150" height="150"/><rect x="1050" y="150" width="150" height="150"/>
  </g>
  <g transform="translate(100, 165) scale(3.5)">
    <path d="M 25 80 L 75 80 L 75 70 L 25 70 Z M 30 70 L 35 45 L 65 45 L 70 70 Z M 32 45 L 30 30 L 38 30 L 38 37 L 46 37 L 46 30 L 54 30 L 54 37 L 62 37 L 62 30 L 70 30 L 68 45 Z" fill="#f2a900"/>
  </g>
  <text x="450" y="260" font-family="Arial, sans-serif" font-weight="bold" font-size="64" fill="#ffffff">Schachturniere</text>
  <text x="450" y="340" font-family="Arial, sans-serif" font-weight="bold" font-size="52" fill="#f2a900">Baden-Württemberg</text>
  <text x="450" y="420" font-family="Arial, sans-serif" font-size="32" fill="#e0e0e0">Interaktive Karte &amp; Termine (WAM, WJPT etc.)</text>
</svg>""")
preview_data_url = f"data:image/svg+xml,{preview_svg}"

head_meta_html = f"""
<title>Schachturnier-Karte Baden-Württemberg</title>
<link rel="icon" type="image/svg+xml" href="{favicon_data_url}">
<meta property="og:title" content="Schachturnier-Karte Baden-Württemberg">
<meta property="og:description" content="Interaktive Übersicht aller Schachturniere (WAM, WJPT, Jugend- &amp; Amateurturniere) in Baden-Württemberg.">
<meta property="og:image" content="{preview_data_url}">
<meta property="og:type" content="website">
"""
wam_map.get_root().header.add_child(folium.Element(head_meta_html))

# UI-Anpassung inkl. funktionierendem Datums-Filter
custom_ui_html = f"""
<style>
.leaflet-top.leaflet-right .leaflet-control-layers {{
    margin-top: 10px !important;
    margin-right: 10px !important;
    padding: 12px !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
    font-family: Arial, sans-serif !important;
    min-width: 240px;
    max-width: 280px;
}}
</style>

<script>
var allRegisteredMarkers = [];

window.addEventListener('load', function() {{
    var layerControl = document.querySelector('.leaflet-control-layers');
    if (layerControl) {{
        var customBox = document.createElement('div');
        customBox.style.cssText = 'margin-bottom: 12px; border-bottom: 1px solid #ddd; padding-bottom: 10px;';

        customBox.innerHTML = `
            <div style="margin-bottom: 8px;">
                <input type="text" id="mapSearchInput" placeholder="🔎 Ort, Datum, WAM..." oninput="filterMapMarkers()" onkeyup="filterMapMarkers()" 
                       style="width: 100%; padding: 7px 9px; border: 1px solid #ccc; border-radius: 5px; font-size: 13px; box-sizing: border-box; outline: none;">
            </div>
            <div style="display: flex; gap: 6px; margin-bottom: 8px;">
                <button onclick="setAllFilters(true)" style="flex: 1; padding: 6px 4px; font-size: 11px; font-weight: bold; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 4px;">Alle auswählen</button>
                <button onclick="setAllFilters(false)" style="flex: 1; padding: 6px 4px; font-size: 11px; font-weight: bold; cursor: pointer; background-color: #6c757d; color: white; border: none; border-radius: 4px;">Alle abwählen</button>
            </div>
            <div style="margin-bottom: 8px; font-size: 12px; display: flex; align-items: center; gap: 6px;">
                <input type="checkbox" id="futureOnlyCheckbox" onchange="filterMapMarkers()" style="cursor: pointer;">
                <label for="futureOnlyCheckbox" style="cursor: pointer; user-select: none;">📅 Nur zukünftige Termine</label>
            </div>
            <div style="font-size: 10px; color: #666; line-height: 1.2;">
                Datenquelle: <a href="{URL}" target="_blank" style="color: #0066cc; text-decoration: underline;">SVW Terminübersicht</a>
            </div>
        `;
        layerControl.insertBefore(customBox, layerControl.firstChild);
    }}

    if (typeof {map_var_name} !== 'undefined') {{
        {map_var_name}.eachLayer(function(layer) {{
            if (layer instanceof L.MarkerClusterGroup) {{
                var group = layer;
                group.eachLayer(function(marker) {{
                    allRegisteredMarkers.push({{
                        marker: marker,
                        group: group
                    }});
                }});
            }}
        }});
    }}
}});

function setAllFilters(selectState) {{
    var checkboxes = document.querySelectorAll('.leaflet-control-layers-overlays input[type="checkbox"]');
    checkboxes.forEach(function(cb) {{
        if (cb.checked !== selectState) {{
            cb.click();
        }}
    }});
}}

function filterMapMarkers() {{
    var inputEl = document.getElementById('mapSearchInput');
    var futureCb = document.getElementById('futureOnlyCheckbox');
    if (!inputEl) return;
    
    var query = inputEl.value.toLowerCase().trim();
    var futureOnly = futureCb ? futureCb.checked : false;

    // Heutiges Datum als YYYY-MM-DD
    var now = new Date();
    var y = now.getFullYear();
    var m = String(now.getMonth() + 1).padStart(2, '0');
    var d = String(now.getDate()).padStart(2, '0');
    var todayStr = y + '-' + m + '-' + d;

    allRegisteredMarkers.forEach(function(item) {{
        var marker = item.marker;
        var group = item.group;
        
        var searchText = marker.options.search_text || "";
        if (!searchText && marker.getTooltip) {{
            searchText = marker.getTooltip().getContent().toLowerCase();
        }}

        var matchesQuery = (query === "" || searchText.includes(query));

        // Datumsprüfung
        var matchesFuture = true;
        if (futureOnly) {{
            var isoDate = marker.options.iso_date || "";
            // Wenn das ISO-Datum vor dem heutigen liegt, Marker ausblenden
            if (isoDate && isoDate < todayStr) {{
                matchesFuture = false;
            }}
        }}

        if (matchesQuery && matchesFuture) {{
            if (!group.hasLayer(marker)) {{
                group.addLayer(marker);
            }}
        }} else {{
            if (group.hasLayer(marker)) {{
                group.removeLayer(marker);
            }}
        }}
    }});
}}
</script>
"""

wam_map.get_root().html.add_child(folium.Element(custom_ui_html))

print(f"\nErfolgreich auf der Karte gesetzte Marker: {markers_added}")

# 3. Als index.html speichern
wam_map.save("index.html")
print("index.html erfolgreich erzeugt!")
                                   
