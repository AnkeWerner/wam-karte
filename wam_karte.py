import urllib3

# Warnungen bzgl. SSL-Zertifikaten unterdrücken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Adresse mit 'www.' nutzen
URL = "https://www.svw.info/wts/terminuebersichten/18322-terminuebersicht-wjpt-und-wam-2025-26"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# verify=False ignoriert den SSL-Zertifikatsfehler des Verbandsservers
response = requests.get(URL, headers=headers, verify=False)
