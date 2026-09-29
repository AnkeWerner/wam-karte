import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from config import URL, BASE_URL, HEADERS, DATE_PATTERN, NOISE_WORDS, LOCATION_MAPPING

def is_cell_ignored(text):
    clean = text.strip().lower()
    if clean in ["", "-", "–", "—", "ausgefallen"] or "ausgefallen" in clean:
        return True
    if clean.endswith("online") or "online dwz" in clean or "dwz siehe oben" in clean:
        return True
    return False

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
            
            working_cells = cells[:-1]
            row_text = " ".join([c.get_text(strip=True) for c in working_cells])
            
            if "ausgefallen" in row_text.lower():
                continue

            date_match = re.search(DATE_PATTERN, row_text)
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
                if w_clean not in NOISE_WORDS and not w_clean.isdigit() and len(w_clean) > 1:
                    city_words.append(w)

            raw_location = " ".join(city_words).strip()
            clean_location = raw_location

            for key, target_city in LOCATION_MAPPING.items():
                if key in raw_location.lower() or key in row_text.lower():
                    clean_location = target_city
                    break

            unique_infos = list(dict.fromkeys(turnier_infos))
            turnier_typ = ", ".join(unique_infos)

            events.append({
                "date": date_str,
                "location": clean_location,
                "type": turnier_typ,
                "links": links
            })

    print(f"Gefundene gültige Turniere: {len(events)}")
    return events
      
