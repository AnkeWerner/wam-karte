import re
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup
import folium
from folium.plugins import MarkerCluster, LocateControl
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


# =============================================================
# 0. Grundeinstellungen
# =============================================================

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.svw.info/wts/terminuebersichten/18322-terminuebersicht-wjpt-und-wam-2025-26"
BASE_URL = "https://www.svw.info"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


# =============================================================
# 1. Quellseite abrufen
# =============================================================

response = requests.get(
    URL,
    headers=HEADERS,
    verify=False,
    timeout=30
)

response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")


# =============================================================
# 2. Hilfsdaten
# =============================================================

events = []
tables = soup.find_all("table")

date_pattern = (
    r"\d{1,2}\s*[\-–—\/]\s*\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b"
    r"|\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b"
)

noise_words = [
    "ok", "jgt", "ssgt", "kjpt", "bjpt", "bjem", "bam", "wam", "wjpt",
    "mfc", "mhc", "u12", "u8", "u10", "u14", "u18", "u25", "u08",
    "finale", "ko", "ausgefallen", "ist", "jugend", "abt", "abt.",
    "schach", "verein", "schachabt", "schachabt.", "sabt", "sabt.",
    "spvgg", "sc", "sf", "sv", "vfl", "cup", "biber", "stand", "vom",
    "der", "u.", "und", "mit", "oder", "für", "in", "a.d.f.", "a.n.",
    "a.d.m.", "online", "dwz", "siehe", "oben", "parallel", "zur",
    "schnellschach", "frühlingsturnier", "familien", "meisterschaft",
    "off", "offene", "kinder", "jugendliche", "jünger", "altersklassen",
    "spielberechtigt", "stichtag", "joker", "neuen", "bei", "es", "sind",
    "römer"
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


# =============================================================
# 3. Hilfsfunktionen
# =============================================================

def is_cell_ignored(text):
    """Prüft, ob eine Tabellenzelle ignoriert werden soll."""

    clean = text.strip().lower()

    if clean in ["", "-", "–", "—", "ausgefallen"]:
        return True

    if "ausgefallen" in clean:
        return True

    if clean.endswith("online"):
        return True

    if "online dwz" in clean:
        return True

    if "dwz siehe oben" in clean:
        return True

    return False


def parse_event_date(date_str):
    """
    Wandelt das Enddatum eines Termins in YYYY-MM-DD um.

    Beispiele:
        7.11.2026      -> 2026-11-07
        7.11.26        -> 2026-11-07
        7.-8.11.2026   -> 2026-11-08
        7.-8.11.26     -> 2026-11-08

    Bei mehrtägigen Veranstaltungen wird bewusst das
    Enddatum verwendet. Dadurch bleibt eine Veranstaltung
    bis zu ihrem tatsächlichen Ende sichtbar.
    """

    # Mehrtägiger Termin mit vierstelligem Jahr
    match = re.search(
        r"(\d{1,2})\s*[\-–—\/]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})",
        date_str
    )

    if match:
        _, end_day, month, year = match.groups()

        return (
            f"{int(year):04d}-"
            f"{int(month):02d}-"
            f"{int(end_day):02d}"
        )

    # Mehrtägiger Termin mit zweistelligem Jahr
    match = re.search(
        r"(\d{1,2})\s*[\-–—\/]\s*(\d{1,2})\.(\d{1,2})\.(\d{2})",
        date_str
    )

    if match:
        _, end_day, month, year = match.groups()

        year = int(year)
        year = 2000 + year if year < 50 else 1900 + year

        return (
            f"{year:04d}-"
            f"{int(month):02d}-"
            f"{int(end_day):02d}"
        )

    # Einzeltermin mit vierstelligem Jahr
    match = re.search(
        r"(\d{1,2})\.(\d{1,2})\.(\d{4})",
        date_str
    )

    if match:
        day, month, year = match.groups()

        return (
            f"{int(year):04d}-"
            f"{int(month):02d}-"
            f"{int(day):02d}"
        )

    # Einzeltermin mit zweistelligem Jahr
    match = re.search(
        r"(\d{1,2})\.(\d{1,2})\.(\d{2})",
        date_str
    )

    if match:
        day, month, year = match.groups()

        year = int(year)
        year = 2000 + year if year < 50 else 1900 + year

        return (
            f"{year:04d}-"
            f"{int(month):02d}-"
            f"{int(day):02d}"
        )

    return None


# =============================================================
# 4. Tabellen auswerten
# =============================================================

for table in tables:

    rows = table.find_all("tr")

    for row in rows:

        cells = row.find_all(["td", "th"])

        if len(cells) < 3:
            continue

        working_cells = cells[:-1]

        row_text = " ".join(
            c.get_text(" ", strip=True)
            for c in working_cells
        )

        # Ausgefallene Veranstaltungen nicht übernehmen
        if "ausgefallen" in row_text.lower():
            continue

        # Datum suchen
        date_match = re.search(date_pattern, row_text)

        if not date_match:
            continue

        date_str = date_match.group(0).strip()

        # Hinweise / Infotexte überspringen
        row_lower = row_text.lower()

        if "stand vom" in row_lower:
            continue

        if "spielberechtigt" in row_lower:
            continue

        # -----------------------------------------------------
        # Turnierinformationen sammeln
        # -----------------------------------------------------

        turnier_infos = []
        links = []

        turnier_cells = working_cells[1:]

        for cell in turnier_cells:

            cell_text = cell.get_text(
                separator=" ",
                strip=True
            )

            if is_cell_ignored(cell_text):
                continue

            clean_cell_text = re.sub(
                r"[\-–—].*online.*$",
                "",
                cell_text,
                flags=re.IGNORECASE
            ).strip()

            if not clean_cell_text:
                continue

            if is_cell_ignored(clean_cell_text):
                continue

            turnier_infos.append(clean_cell_text)

            # Links sammeln
            for a in cell.find_all("a", href=True):

                href = a["href"]

                full_link = urllib.parse.urljoin(
                    BASE_URL,
                    href
                )

                link_title = (
                    a.get_text(strip=True)
                    or "Ausschreibung / Link"
                )

                links.append({
                    "title": link_title,
                    "url": full_link
                })

        if not turnier_infos:
            continue

        # -----------------------------------------------------
        # Ort ermitteln
        # -----------------------------------------------------

        clean_text = row_text.replace(
            date_str,
            ""
        ).strip()

        clean_text = re.sub(
            r"\b(Sa|So|Mo|Di|Mi|Do|Fr|Sa\/So|So\/Sa)\b",
            "",
            clean_text,
            flags=re.IGNORECASE
        )

        clean_text = re.sub(
            r"\d+\.",
            "",
            clean_text
        )

        clean_text = re.sub(
            r"[,\-\/:\+\(\)]",
            " ",
            clean_text
        )

        raw_words = clean_text.split()

        city_words = []

        for word in raw_words:

            word_clean = word.lower().strip(".")

            if (
                word_clean not in noise_words
                and not word_clean.isdigit()
                and len(word_clean) > 1
            ):
                city_words.append(word)

        raw_location = " ".join(city_words).strip()

        clean_location = raw_location

        # bekannte Orte vereinheitlichen
        for key, target_city in location_mapping.items():

            if (
                key in raw_location.lower()
                or key in row_text.lower()
            ):
                clean_location = target_city
                break

        # Doppelte Turnierinformationen entfernen
        unique_infos = list(
            dict.fromkeys(turnier_infos)
        )

        turnier_typ = ", ".join(unique_infos)

        # ISO-Datum für den JavaScript-Filter
        date_iso = parse_event_date(date_str)

        events.append({
            "date": date_str,
            "date_iso": date_iso,
            "location": clean_location,
            "type": turnier_typ,
            "links": links
        })


print(
    f"Gefundene gültige Turniere: {len(events)}"
)


# =============================================================
# 5. Karte initialisieren
# =============================================================

geolocator = Nominatim(
    user_agent="wam_schach_karte_app_v36"
)

geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1
)

wam_map = folium.Map(
    location=[48.7758, 9.1829],
    zoom_start=8
)


# =============================================================
# 6. Standort-Button
# =============================================================

LocateControl(
    auto_start=False,
    flyTo=True,
    keepCurrentZoomLevel=False,
    strings={
        "title": "Mein Standort"
    }
).add_to(wam_map)


# =============================================================
# 7. Ebenen / Kategorien
# =============================================================

group_wam = MarkerCluster(
    name="Amateurturniere",
    spiderfyOnMaxZoom=True
).add_to(wam_map)

group_wjpt = MarkerCluster(
    name="Jugendturniere",
    spiderfyOnMaxZoom=True
).add_to(wam_map)

group_ssgt = MarkerCluster(
    name="Schulschachturniere",
    spiderfyOnMaxZoom=True
).add_to(wam_map)

group_frauen = MarkerCluster(
    name="Mädchen- & Frauenturniere",
    spiderfyOnMaxZoom=True
).add_to(wam_map)

group_andere = MarkerCluster(
    name="Andere Turnierformen",
    spiderfyOnMaxZoom=True
).add_to(wam_map)


# =============================================================
# 8. Marker erzeugen
# =============================================================

markers_added = 0


for event in events:

    search_query = (
        f"{event['location']}, "
        f"Baden-Württemberg, Germany"
    )

    location_data = geocode(search_query)

    if not location_data:
        location_data = geocode(
            f"{event['location']}, Germany"
        )

    if not location_data:
        print(
            f"⚠ Ort nicht gefunden: "
            f"{event['location']}"
        )
        continue

    # ---------------------------------------------------------
    # Links für Popup
    # ---------------------------------------------------------

    links_html = ""

    if event["links"]:

        links_html = (
            "<div style='margin-top: 8px; "
            "border-top: 1px solid #ccc; "
            "padding-top: 5px;'>"
        )

        for link in event["links"]:

            # HTML-Sonderzeichen in Linktext absichern
            link_title = (
                link["title"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            links_html += (
                f"<a href='{link['url']}' "
                f"target='_blank' "
                f"rel='noopener noreferrer' "
                f"style='color: #0066cc; "
                f"font-weight: bold; "
                f"text-decoration: underline;'>"
                f"🔗 {link_title}</a><br>"
            )

        links_html += "</div>"

    # ---------------------------------------------------------
    # Popup
    # ---------------------------------------------------------

    popup_html = f"""
    <div style='font-family: sans-serif;
                font-size: 13px;
                line-height: 1.4;'>
        <h4 style='margin: 0 0 5px 0;
                   color: #1a5f7a;'>
            {event['type']}
        </h4>

        <b>Datum:</b> {event['date']}<br>
        <b>Ort:</b> {event['location']}<br>

        {links_html}
    </div>
    """

    # ---------------------------------------------------------
    # Marker-Funktion
    # ---------------------------------------------------------

    def make_marker(event=event,
                    location_data=location_data,
                    popup_html=popup_html):

        marker = folium.Marker(
            location=[
                location_data.latitude,
                location_data.longitude
            ],
            popup=folium.Popup(
                popup_html,
                max_width=280
            ),
            tooltip=(
                f"{event['date']} - "
                f"{event['location']} "
                f"({event['type']})"
            ),
            icon=folium.Icon(
                color="orange",
                icon="chess-rook",
                prefix="fa"
            )
        )

        # Suchtext
        marker.options["search_text"] = (
            f"{event['location']} "
            f"{event['date']} "
            f"{event['type']}"
        ).lower()

        # ISO-Datum für den Datumsfilter
        marker.options["event_date"] = (
            event["date_iso"]
        )

        return marker

    # ---------------------------------------------------------
    # Kategorien bestimmen
    # ---------------------------------------------------------

    type_upper = event["type"].upper()

    standard_matched = False

    # WAM / BAM
    if "WAM" in type_upper or "BAM" in type_upper:

        make_marker().add_to(group_wam)

        standard_matched = True

    # Jugend
    if any(
        keyword in type_upper
        for keyword in [
            "WJPT",
            "JGT",
            "KJPT",
            "BJPT",
            "BJEM",
            "KINDER",
            "JUGENDLICHE",
            "JUGEND"
        ]
    ):

        make_marker().add_to(group_wjpt)

        standard_matched = True

    # Schulschach
    if "SSGT" in type_upper:

        make_marker().add_to(group_ssgt)

        standard_matched = True

    # Mädchen / Frauen
    if any(
        keyword in type_upper
        for keyword in [
            "MÄDCHEN",
            "FRAUEN",
            "MAEDCHEN",
            "MÄDCHENTAG"
        ]
    ):

        make_marker().add_to(group_frauen)

        standard_matched = True

    # ---------------------------------------------------------
    # Andere Turnierformen
    # ---------------------------------------------------------

    andere_keywords = [
        "SCHACH-WE",
        "BEGINNER",
        "CUP",
        "OPEN",
        "SONDER",
        "OFFENE",
        "SCHNELLSCHACH",
        "MEISTERSCHAFT"
    ]

    is_andere_explicit = any(
        keyword in type_upper
        for keyword in andere_keywords
    )

    if is_andere_explicit or not standard_matched:

        make_marker().add_to(group_andere)

    markers_added += 1


# =============================================================
# 9. Layer Control
# =============================================================

folium.LayerControl(
    collapsed=False
).add_to(wam_map)

map_var_name = wam_map.get_name()


# =============================================================
# 10. Favicon
# =============================================================

favicon_svg = urllib.parse.quote(
    """<svg xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 100 100">

    <rect width="100" height="100"
          rx="20" fill="#1a5f7a"/>

    <path d="
        M 25 80 L 75 80
        L 75 70 L 25 70 Z

        M 30 70 L 35 45
        L 65 45 L 70 70 Z

        M 32 45 L 30 30
        L 38 30 L 38 37
        L 46 37 L 46 30
        L 54 30 L 54 37
        L 62 37 L 62 30
        L 70 30 L 68 45 Z"
        fill="#f2a900"/>
    </svg>"""
)

favicon_data_url = (
    f"data:image/svg+xml,{favicon_svg}"
)


# =============================================================
# 11. Open-Graph-Vorschau
# =============================================================

preview_svg = urllib.parse.quote(
    """<svg xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 1200 630"
    width="1200"
    height="630">

    <rect width="1200"
          height="630"
          fill="#1a5f7a"/>

    <g opacity="0.08"
       fill="#ffffff">

        <rect x="0" y="0"
              width="150" height="150"/>

        <rect x="300" y="0"
              width="150" height="150"/>

        <rect x="600" y="0"
              width="150" height="150"/>

        <rect x="900" y="0"
              width="150" height="150"/>

        <rect x="150" y="150"
              width="150" height="150"/>

        <rect x="450" y="150"
              width="150" height="150"/>

        <rect x="750" y="150"
              width="150" height="150"/>

        <rect x="1050" y="150"
              width="150" height="150"/>

        <rect x="0" y="300"
              width="150" height="150"/>

        <rect x="300" y="300"
              width="150" height="150"/>

        <rect x="600" y="300"
              width="150" height="150"/>

        <rect x="900" y="300"
              width="150" height="150"/>

        <rect x="150" y="450"
              width="150" height="150"/>

        <rect x="450" y="450"
              width="150" height="150"/>

        <rect x="750" y="450"
              width="150" height="150"/>

        <rect x="1050" y="450"
              width="150" height="150"/>
    </g>

    <!-- Schachturm -->
    <g transform="translate(100, 165) scale(3.5)">

        <path d="
            M 25 80 L 75 80
            L 75 70 L 25 70 Z

            M 30 70 L 35 45
            L 65 45 L 70 70 Z

            M 32 45 L 30 30
            L 38 30 L 38 37
            L 46 37 L 46 30
            L 54 30 L 54 37
            L 62 37 L 62 30
            L 70 30 L 68 45 Z"
            fill="#f2a900"/>
    </g>

    <text x="450" y="260"
          font-family="Arial, sans-serif"
          font-weight="bold"
          font-size="64"
          fill="#ffffff">
        Schachturniere
    </text>

    <text x="450" y="340"
          font-family="Arial, sans-serif"
          font-weight="bold"
          font-size="52"
          fill="#f2a900">
        Baden-Württemberg
    </text>

    <text x="450" y="420"
          font-family="Arial, sans-serif"
          font-size="32"
          fill="#e0e0e0">
        Interaktive Karte &amp; Termine
        (WAM, WJPT etc.)
    </text>

    </svg>"""
)

preview_data_url = (
    f"data:image/svg+xml,{preview_svg}"
)


# =============================================================
# 12. Meta-Tags & Favicon
# =============================================================

head_meta_html = f"""
<!-- Website Titel -->
<title>Schachturnier-Karte Baden-Württemberg</title>

<!-- Favicon -->
<link rel="icon"
      type="image/svg+xml"
      href="{favicon_data_url}">

<!-- Open Graph -->
<meta property="og:title"
      content=
