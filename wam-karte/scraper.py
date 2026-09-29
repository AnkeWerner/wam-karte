import re
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from config import URL, BASE_URL, HEADERS, DATE_PATTERN, NOISE_WORDS, LOCATION_MAPPING

def is_cell_ignored(text):
    clean = text.strip().lower()
    # Einzelne Punkte, Striche oder leere Einträge ignorieren
    if clean in ["", ".", "-", "–", "—", "ausgefallen"] or "ausgefallen" in clean:
        return True
    if clean.endswith("online") or "online dwz" in clean or "dwz siehe oben" in clean:
        return True
    return False

def parse_end_date_iso(date_str):
    try:
        clean = re.sub(r"[^\d\.\-–—\/]", "", date_str).strip()
        if not clean:
            return ""

        parts = re.split(r"[\-–—\/]", clean)
        last_part = parts[-1].strip()

        match_my = re.search(r"\.(\d{1,2})\.(\d{2,4})$", last_part)
        if not match_my:
            match_my = re.search(r"\.(\d{1,2})\.(\d{2,4})$", clean)

        if not match_my:
            return ""

        month = int(match_my.group(1))
        year = int(match_my.group(2))
        if year < 100:
            year += 2000

        day_match = re.search(r"^(\d{1,2})", last_part)
        if not day_match:
            return ""
        day = int(day_match.group(1))

        dt = datetime(year, month, day)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""

def fetch_events():
    response = requests.get(URL, headers=HEADERS, verify=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    events = []
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            
            if len(cells) < 3:
                continue

            # Die letzte Spalte ("erl.") strikt abschneiden
            valid_cells = cells[:-1]

            date_cell_text = valid_cells[1].get_text(strip=True)
            date_match = re.search(DATE_PATTERN, date_cell_text)
            if not date_match:
                continue

            date_str = date_match.group(0).strip()
            iso_end_date = parse_end_date_iso(date_cell_text)

            row_text_without_erl = " ".join([c.get_text(strip=True) for c in valid_cells])
            if "ausgefallen" in row_text_without_erl.lower() or "stand vom" in row_text_without_erl.lower():
                continue

            turnier_infos = []
            links = []
            
            turnier_cells = valid_cells[2:]

            for cell in turnier_cells:
                cell_text = cell.get_text(separator=" ", strip=True)

                if not is_cell_ignored(cell_text):
                    clean_cell_text = re.sub(r"[\-–—].*online.*$", "", cell_text, flags=re.IGNORECASE).strip()
                    # Isolierte Punkte und Striche säubern
                    clean_cell_text = re.sub(r"^\s*[\.\-–—]\s*$", "", clean_cell_text).strip()

                    if clean_cell_text and not is_cell_ignored(clean_cell_text):
                        turnier_infos.append(clean_cell_text)

                        for a in cell.find_all("a", href=True):
                            href = a["href"]
                            full_link = urllib.parse.urljoin(BASE_URL, href)
                            link_title = a.get_text(strip=True) or "Ausschreibung / Link"
                            links.append({"title": link_title, "url": full_link})

            if not turnier_infos:
                continue

            clean_text = row_text_without_erl.replace(date_str, "").strip()
            clean_text = re.sub(r"\b(Sa|So|Mo|Di|Mi|Do|Fr|Sa\/So|So\/Sa)\b", "", clean_text, flags=re.IGNORECASE)
            clean_text = re.sub(r"\d+\.", "", clean_text)
            clean_text = re.sub(r"[,\-\/:\+\(\)]", " ", clean_text)

            raw_words = clean_text.split()
            city_words = []
            for w in raw_words:
                w_clean = w.lower().strip(".")
                if w_clean not in NOISE_WORDS and not w_clean.isdigit() and len(w_clean) > 1:
                    city_words.append(w)

            raw_location = " ".join(city_words).strip()
            clean_location = raw_location

            for key, target_city in LOCATION_MAPPING.items():
                if key in raw_location.lower() or key in row_text_without_erl.lower():
                    clean_location = target_city
                    break

            unique_infos = list(dict.fromkeys(turnier_infos))
            turnier_typ = ", ".join(unique_infos)

            events.append({
                "date": date_str,
                "iso_date": iso_end_date,
                "location": clean_location,
                "type": turnier_typ,
                "links": links
            })

    print(f"Gefundene gültige Turniere: {len(events)}")
    return events
    
