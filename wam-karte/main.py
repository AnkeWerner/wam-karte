from scraper import fetch_events
from map_builder import build_map

def main():
    print("Starte Turniersuche...")
    events = fetch_events()
    
    print("Erstelle interaktive Karte...")
    wam_map = build_map(events)
    
    output_file = "index.html"
    wam_map.save(output_file)
    print(f"Fertig! '{output_file}' wurde erfolgreich erzeugt.")

if __name__ == "__main__":
    main()
  
