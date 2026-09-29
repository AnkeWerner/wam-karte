import urllib3

# SSL-Warnungen unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.svw.info/wts/terminuebersichten/18322-terminuebersicht-wjpt-und-wam-2025-26"
# BASE_URL = "https://www.svw.info"
# BASE_URL = "https://www.svw.info/wts/terminuebersichten"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

DATE_PATTERN = r"\d{1,2}\s*[\.\/]?\s*[\-–—\/]\s*\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b|\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})\b"

NOISE_WORDS = [
    "ok", "jgt", "ssgt", "kjpt", "bjpt", "bjem", "bam", "wam", "wjpt", "mfc", "mhc", "u12", "u8", "u10", "u14", "u18", "u25", "u08",
    "finale", "ko", "ausgefallen", "ist", "jugend", "abt", "abt.", "schach", "verein", "schachabt", "schachabt.", "sabt", "sabt.", "spvgg",
    "sc", "sf", "sv", "vfl", "cup", "biber", "stand", "vom", "der", "u.", "und", "mit", "oder", "für",
    "in", "a.d.f.", "a.n.", "a.d.m.", "online", "dwz", "siehe", "oben", "parallel", "zur",
    "schnellschach", "frühlingsturnier", "familien", "meisterschaft", "off", "offene",
    "kinder", "jugendliche", "jünger", "altersklassen", "spielberechtigt", "stichtag", "joker", "neuen", "bei", "es", "sind", "römer"
]

LOCATION_MAPPING = {
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
