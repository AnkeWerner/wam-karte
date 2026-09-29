import folium
from folium.plugins import MarkerCluster, LocateControl
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from assets import generate_head_meta, generate_custom_ui

def build_map(events):
    geolocator = Nominatim(user_agent="wam_schach_karte_app_v40")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    wam_map = folium.Map(location=[48.7758, 9.1829], zoom_start=8)

    LocateControl(
        auto_start=False,
        flyTo=True,
        keepCurrentZoomLevel=False,
        strings={"title": "Mein Standort"}
    ).add_to(wam_map)

    group_wam = MarkerCluster(name="Amateurturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
    group_wjpt = MarkerCluster(name="Jugendturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
    group_ssgt = MarkerCluster(name="Schulschachturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
    group_frauen = MarkerCluster(name="Mädchen- & Frauenturniere", spiderfyOnMaxZoom=True).add_to(wam_map)
    group_andere = MarkerCluster(name="Andere Turnierformen", spiderfyOnMaxZoom=True).add_to(wam_map)

    markers_added = 0
    failed_locations = []

    print("\n--- Geocoding Status ---")
    for event in events:
        location_name = event['location']
        search_query = f"{location_name}, Baden-Württemberg, Germany"
        location_data = geocode(search_query)

        if not location_data:
            location_data = geocode(f"{location_name}, Germany")

        if location_data:
            print(f"✔ Ort gefunden: '{location_name}' ({location_data.latitude:.4f}, {location_data.longitude:.4f}) | Datum: {event['date']} (ISO: {event['iso_date']})")
            
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

            # Reine Text-Strings für den Filter aufbereiten (ohne HTML)
            raw_search_text = f"{event['date']} - {event['location']} ({event['type']})".lower()
            iso_date_clean = str(event['iso_date']).strip()

            marker = folium.Marker(
                location=[location_data.latitude, location_data.longitude],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{event['date']} - {event['location']} ({event['type']})",
                icon=folium.Icon(color="orange", icon="chess-rook", prefix="fa")
            )

            # WICHTIG: Eigenschaften direkt in das JS-Objekt schreiben
            marker.add_child(folium.Element(f"""
                <script>
                    window.addEventListener('load', function() {{
                        var m = {marker.get_name()};
                        m.options.search_text = "{raw_search_text}";
                        m.options.iso_date = "{iso_date_clean}";
                    }});
                </script>
            """))

            type_upper = event["type"].upper()
            standard_matched = False

            if "WAM" in type_upper or "BAM" in type_upper:
                marker.add_to(group_wam)
                standard_matched = True

            if any(kw in type_upper for kw in ["WJPT", "JGT", "KJPT", "BJPT", "BJEM", "KINDER", "JUGENDLICHE", "JUGEND"]):
                marker.add_to(group_wjpt)
                standard_matched = True

            if "SSGT" in type_upper:
                marker.add_to(group_ssgt)
                standard_matched = True

            if any(kw in type_upper for kw in ["MÄDCHEN", "FRAUEN", "MAEDCHEN", "MÄDCHENTAG"]):
                marker.add_to(group_frauen)
                standard_matched = True

            andere_keywords = ["SCHACH-WE", "BEGINNER", "CUP", "OPEN", "SONDER", "OFFENE", "SCHNELLSCHACH", "MEISTERSCHAFT"]
            is_andere_explicit = any(kw in type_upper for kw in andere_keywords)

            if is_andere_explicit or not standard_matched:
                marker.add_to(group_andere)

            markers_added += 1
        else:
            print(f"❌ Ort NICHT gefunden: '{location_name}' | Datum: {event['date']}")
            failed_locations.append(location_name)

    folium.LayerControl(collapsed=False).add_to(wam_map)

    wam_map.get_root().header.add_child(folium.Element(generate_head_meta()))
    wam_map.get_root().html.add_child(folium.Element(generate_custom_ui(wam_map.get_name())))

    print(f"\nSummary: {markers_added} Marker erfolgreich auf der Karte gesetzt.")
    return wam_map
            
