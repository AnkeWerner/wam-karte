import os
import re
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup
import folium
from folium.plugins import MarkerCluster
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
geolocator = Nominatim(user_agent="wam_schach_karte_app_v27")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

# Ebenen mit automatischer Auffächerung
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

        search_title = f"{event['location']} {event['date']} {event['type']} {event['raw_text']}".lower()

        def make_marker():
            m = folium.Marker(
                location=[location_data.latitude, location_data.longitude],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{event['date']} - {event['location']} ({event['type']})",
                icon=folium.Icon(color="orange", icon="chess-rook", prefix="fa"),
            )
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
        print(f"✔ Marker: {event['date']} [{event['type']}] in {event['location']}")
    else:
        print(f"❌ Ort nicht gefunden: '{event['location']}'")

folium.LayerControl(collapsed=False).add_to(wam_map)

print(f"\nErfolgreich auf der Karte gesetzte Marker: {markers_added}")

# 3. als index.html speichern
wam_map.save("index.html")

# 4. Erweitertes JavaScript: Echtzeit-Filter-Suchleiste + "Alle an / Alle aus" Buttons
custom_js = """
<script>
document.addEventListener("DOMContentLoaded", function() {
    setTimeout(function() {
        // 1. Buttons "Alle an / Alle aus" in das Layer-Menü einbauen
        var controlContainer = document.querySelector('.leaflet-control-layers-overlays');
        if (controlContainer) {
            var btnContainer = document.createElement('div');
            btnContainer.style.marginBottom = '8px';
            btnContainer.style.paddingBottom = '5px';
            btnContainer.style.borderBottom = '1px solid #ccc';

            btnContainer.innerHTML = `
                <button id="select-all-btn" style="cursor:pointer; font-size:11px; padding:3px 6px; margin-right:4px; border:1px solid #0066cc; background:#0066cc; color:white; border-radius:3px;">Alle an</button>
                <button id="deselect-all-btn" style="cursor:pointer; font-size:11px; padding:3px 6px; border:1px solid #666; background:#f0f0f0; color:#333; border-radius:3px;">Alle aus</button>
            `;

            controlContainer.parentNode.insertBefore(btnContainer, controlContainer);

            document.getElementById('select-all-btn').addEventListener('click', function() {
                var checkboxes = controlContainer.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(function(cb) {
                    if (!cb.checked) { cb.click(); }
                });
            });

            document.getElementById('deselect-all-btn').addEventListener('click', function() {
                var checkboxes = controlContainer.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach(function(cb) {
                    if (cb.checked) { cb.click(); }
                });
            });
        }

        # 2. Interaktive Live-Suchleiste oben links einbauen
        var searchControlDiv = document.createElement('div');
        searchControlDiv.className = 'leaflet-control leaflet-bar';
        searchControlDiv.style.backgroundColor = 'white';
        searchControlDiv.style.padding = '6px 8px';
        searchControlDiv.style.borderRadius = '4px';
        searchControlDiv.style.boxShadow = '0 1px 5px rgba(0,0,0,0.4)';
        searchControlDiv.style.marginTop = '10px';
        searchControlDiv.style.marginLeft = '10px';

        searchControlDiv.innerHTML = `
            <input type="text" id="custom-map-search" placeholder="🔎 Ort, Datum oder Turnier filtern..." style="width: 220px; padding: 4px 6px; border: 1px solid #ccc; border-radius: 3px; font-size: 12px; outline: none;">
        `;

        var topLeftContainer = document.querySelector('.leaflet-top.leaflet-left');
        if (topLeftContainer) {
            topLeftContainer.appendChild(searchControlDiv);
        }

        // Such-Filter Logik
        var searchInput = document.getElementById('custom-map-search');
        if (searchInput) {
            searchInput.addEventListener('input', function(e) {
                var query = e.target.value.toLowerCase().strip ? e.target.value.toLowerCase().strip() : e.target.value.toLowerCase().trim();
                
                // Durchsuche alle Marker
                for (var layerId in map._layers) {
                    var layer = map._layers[layerId];
                    if (layer instanceof L.Marker) {
                        var tooltipText = layer.getTooltip() ? layer.getTooltip().getContent().toLowerCase() : "";
                        var popupText = layer.getPopup() ? layer.getPopup().getContent().toLowerCase() : "";
                        
                        if (tooltipText.includes(query) || popupText.includes(query)) {
                            layer.getElement() && (layer.getElement().style.display = '');
                        } else {
                            layer.getElement() && (layer.getElement().style.display = 'none');
                        }
                    }
                }
            });
        }
    }, 500);
});
</script>
</body>
"""

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("</body>", custom_js)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)

print("index.html erfolgreich erweitert und gespeichert!")
