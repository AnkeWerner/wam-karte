import urllib.parse
from config import URL

def get_favicon_and_preview_urls():
    favicon_svg = urllib.parse.quote("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <rect width="100" height="100" rx="20" fill="#1a5f7a"/>
      <path d="M 25 80 L 75 80 L 75 70 L 25 70 Z M 30 70 L 35 45 L 65 45 L 70 70 Z M 32 45 L 30 30 L 38 30 L 38 37 L 46 37 L 46 30 L 54 30 L 54 37 L 62 37 L 62 30 L 70 30 L 68 45 Z" fill="#f2a900"/>
    </svg>""")
    
    preview_svg = urllib.parse.quote("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
      <rect width="1200" height="630" fill="#1a5f7a"/>
      <g opacity="0.08" fill="#ffffff">
        <rect x="0" y="0" width="150" height="150"/><rect x="300" y="0" width="150" height="150"/><rect x="600" y="0" width="150" height="150"/><rect x="900" y="0" width="150" height="150"/>
        <rect x="150" y="150" width="150" height="150"/><rect x="450" y="150" width="150" height="150"/><rect x="750" y="150" width="150" height="150"/><rect x="1050" y="150" width="150" height="150"/>
        <rect x="0" y="300" width="150" height="150"/><rect x="300" y="300" width="150" height="150"/><rect x="600" y="300" width="150" height="150"/><rect x="900" y="300" width="150" height="150"/>
        <rect x="150" y="450" width="150" height="150"/><rect x="450" y="450" width="150" height="150"/><rect x="750" y="450" width="150" height="150"/><rect x="1050" y="450" width="150" height="150"/>
      </g>
      <g transform="translate(100, 165) scale(3.5)">
        <path d="M 25 80 L 75 80 L 75 70 L 25 70 Z M 30 70 L 35 45 L 65 45 L 70 70 Z M 32 45 L 30 30 L 38 30 L 38 37 L 46 37 L 46 30 L 54 30 L 54 37 L 62 37 L 62 30 L 70 30 L 68 45 Z" fill="#f2a900"/>
      </g>
      <text x="450" y="260" font-family="Arial, sans-serif" font-weight="bold" font-size="64" fill="#ffffff">Schachturniere</text>
      <text x="450" y="340" font-family="Arial, sans-serif" font-weight="bold" font-size="52" fill="#f2a900">Baden-Württemberg</text>
      <text x="450" y="420" font-family="Arial, sans-serif" font-size="32" fill="#e0e0e0">Interaktive Karte &amp; Termine (WAM, WJPT etc.)</text>
    </svg>""")
    
    return f"data:image/svg+xml,{favicon_svg}", f"data:image/svg+xml,{preview_svg}"

def generate_head_meta():
    favicon_data_url, preview_data_url = get_favicon_and_preview_urls()
    return f"""
    <title>Schachturnier-Karte Baden-Württemberg</title>
    <link rel="icon" type="image/svg+xml" href="{favicon_data_url}">
    <meta property="og:title" content="Schachturnier-Karte Baden-Württemberg">
    <meta property="og:description" content="Interaktive Übersicht aller Schachturniere (WAM, WJPT, Jugend- &amp; Amateurturniere) in Baden-Württemberg.">
    <meta property="og:image" content="{preview_data_url}">
    <meta property="og:type" content="website">
    """

def generate_custom_ui(map_var_name):
    return f"""
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

    function parseGermanDateToIso(text) {{
        if (!text) return "";
        var match = text.match(/(\\d{{1,2}})\\.(\\d{{1,2}})\\.(\\d{{4}})/);
        if (match) {{
            var day = match[1].padStart(2, '0');
            var month = match[2].padStart(2, '0');
            var year = match[3];
            return year + '-' + month + '-' + day;
        }}
        return "";
    }}

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
                <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                    <input type="checkbox" id="futureOnlyFilter" onchange="filterMapMarkers()" style="cursor: pointer;">
                    <label for="futureOnlyFilter" style="font-size: 12px; font-weight: bold; color: #333; cursor: pointer; user-select: none;">
                        📅 Nur künftige Termine (ab heute)
                    </label>
                </div>
                <div style="display: flex; gap: 6px; margin-bottom: 8px;">
                    <button onclick="setAllFilters(true)" style="flex: 1; padding: 6px 4px; font-size: 11px; font-weight: bold; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 4px;">Alle auswählen</button>
                    <button onclick="setAllFilters(false)" style="flex: 1; padding: 6px 4px; font-size: 11px; font-weight: bold; cursor: pointer; background-color: #6c757d; color: white; border: none; border-radius: 4px;">Alle abwählen</button>
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
        var futureFilterEl = document.getElementById('futureOnlyFilter');
        if (!inputEl) return;
        
        var query = inputEl.value.toLowerCase().trim();
        var futureOnly = futureFilterEl ? futureFilterEl.checked : false;

        var today = new Date();
        var yyyy = today.getFullYear();
        var mm = String(today.getMonth() + 1).padStart(2, '0');
        var dd = String(today.getDate()).padStart(2, '0');
        var todayIso = yyyy + '-' + mm + '-' + dd;

        allRegisteredMarkers.forEach(function(item) {{
            var marker = item.marker;
            var group = item.group;
            
            var tooltipText = marker.getTooltip ? marker.getTooltip().getContent() : "";
            var searchText = marker.options.search_text || tooltipText.toLowerCase();
            
            var isoDate = marker.options.iso_date || parseGermanDateToIso(tooltipText);

            var textMatches = (query === "" || searchText.includes(query));
            
            var dateMatches = true;
            if (futureOnly) {{
                if (isoDate && isoDate.length === 10) {{
                    dateMatches = (isoDate >= todayIso);
                }} else {{
                    dateMatches = true;
                }}
            }}

            if (textMatches && dateMatches) {{
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
    import urllib.parse
from config import URL

def get_favicon_and_preview_urls():
    favicon_svg = urllib.parse.quote("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <rect width="100" height="100" rx="20" fill="#1a5f7a"/>
      <path d="M 25 80 L 75 80 L 75 70 L 25 70 Z M 30 70 L 35 45 L 65 45 L 70 70 Z M 32 45 L 30 30 L 38 30 L 38 37 L 46 37 L 46 30 L 54 30 L 54 37 L 62 37 L 62 30 L 70 30 L 68 45 Z" fill="#f2a900"/>
    </svg>""")
    
    preview_svg = urllib.parse.quote("""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">
      <rect width="1200" height="630" fill="#1a5f7a"/>
      <g opacity="0.08" fill="#ffffff">
        <rect x="0" y="0" width="150" height="150"/><rect x="300" y="0" width="150" height="150"/><rect x="600" y="0" width="150" height="150"/><rect x="900" y="0" width="150" height="150"/>
        <rect x="150" y="150" width="150" height="150"/><rect x="450" y="150" width="150" height="150"/><rect x="750" y="150" width="150" height="150"/><rect x="1050" y="150" width="150" height="150"/>
        <rect x="0" y="300" width="150" height="150"/><rect x="300" y="300" width="150" height="150"/><rect x="600" y="300" width="150" height="150"/><rect x="900" y="300" width="150" height="150"/>
        <rect x="150" y="450" width="150" height="150"/><rect x="450" y="450" width="150" height="150"/><rect x="750" y="450" width="150" height="150"/><rect x="1050" y="450" width="150" height="150"/>
      </g>
      <g transform="translate(100, 165) scale(3.5)">
        <path d="M 25 80 L 75 80 L 75 70 L 25 70 Z M 30 70 L 35 45 L 65 45 L 70 70 Z M 32 45 L 30 30 L 38 30 L 38 37 L 46 37 L 46 30 L 54 30 L 54 37 L 62 37 L 62 30 L 70 30 L 68 45 Z" fill="#f2a900"/>
      </g>
      <text x="450" y="260" font-family="Arial, sans-serif" font-weight="bold" font-size="64" fill="#ffffff">Schachturniere</text>
      <text x="450" y="340" font-family="Arial, sans-serif" font-weight="bold" font-size="52" fill="#f2a900">Baden-Württemberg</text>
      <text x="450" y="420" font-family="Arial, sans-serif" font-size="32" fill="#e0e0e0">Interaktive Karte &amp; Termine (WAM, WJPT etc.)</text>
    </svg>""")
    
    return f"data:image/svg+xml,{favicon_svg}", f"data:image/svg+xml,{preview_svg}"

def generate_head_meta():
    favicon_data_url, preview_data_url = get_favicon_and_preview_urls()
    return f"""
    <title>Schachturnier-Karte Baden-Württemberg</title>
    <link rel="icon" type="image/svg+xml" href="{favicon_data_url}">
    <meta property="og:title" content="Schachturnier-Karte Baden-Württemberg">
    <meta property="og:description" content="Interaktive Übersicht aller Schachturniere (WAM, WJPT, Jugend- &amp; Amateurturniere) in Baden-Württemberg.">
    <meta property="og:image" content="{preview_data_url}">
    <meta property="og:type" content="website">
    """

def generate_custom_ui(map_var_name):
    return f"""
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

    <script src="https://cdn.jsdelivr.net/npm/eruda"></script>
    <script>
    if (typeof eruda !== 'undefined') {{
        eruda.init();
    }}

    var allRegisteredMarkers = [];

    // Hilfsfunktion: Konvertiert 'DD.MM.YYYY' in 'YYYY-MM-DD'
    function parseGermanDateToIso(text) {{
        if (!text) return "";
        var match = text.match(/(\\d{{1,2}})\\.(\\d{{1,2}})\\.(\\d{{4}})/);
        if (match) {{
            var day = match[1].padStart(2, '0');
            var month = match[2].padStart(2, '0');
            var year = match[3];
            return year + '-' + month + '-' + day;
        }}
        return "";
    }}

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
                <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                    <input type="checkbox" id="futureOnlyFilter" onchange="filterMapMarkers()" style="cursor: pointer;">
                    <label for="futureOnlyFilter" style="font-size: 12px; font-weight: bold; color: #333; cursor: pointer; user-select: none;">
                        📅 Nur künftige Termine (ab heute)
                    </label>
                </div>
                <div style="display: flex; gap: 6px; margin-bottom: 8px;">
                    <button onclick="setAllFilters(true)" style="flex: 1; padding: 6px 4px; font-size: 11px; font-weight: bold; cursor: pointer; background-color: #007bff; color: white; border: none; border-radius: 4px;">Alle auswählen</button>
                    <button onclick="setAllFilters(false)" style="flex: 1; padding: 6px 4px; font-size: 11px; font-weight: bold; cursor: pointer; background-color: #6c757d; color: white; border: none; border-radius: 4px;">Alle abwählen</button>
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
            console.log("🔍 Registrierte Marker:", allRegisteredMarkers.length);
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
        var futureFilterEl = document.getElementById('futureOnlyFilter');
        if (!inputEl) return;
        
        var query = inputEl.value.toLowerCase().trim();
        var futureOnly = futureFilterEl ? futureFilterEl.checked : false;

        var today = new Date();
        var yyyy = today.getFullYear();
        var mm = String(today.getMonth() + 1).padStart(2, '0');
        var dd = String(today.getDate()).padStart(2, '0');
        var todayIso = yyyy + '-' + mm + '-' + dd;

        console.log("====================================");
        console.log("📅 [FILTER RUN] Heutiges Datum (ISO):", todayIso);
        console.log("📅 [FILTER RUN] Zukunftsfilter aktiv?:", futureOnly);

        var shownCount = 0;
        var hiddenCount = 0;

        allRegisteredMarkers.forEach(function(item) {{
            var marker = item.marker;
            var group = item.group;
            
            var tooltipText = marker.getTooltip ? marker.getTooltip().getContent() : "";
            var searchText = marker.options.search_text || tooltipText.toLowerCase();
            
            // ISO-Datum erst aus options, ansonsten per Regex direkt aus dem Tooltip lesen
            var isoDate = marker.options.iso_date || parseGermanDateToIso(tooltipText);

            var textMatches = (query === "" || searchText.includes(query));
            
            var dateMatches = true;
            if (futureOnly) {{
                if (isoDate && isoDate.length === 10) {{
                    dateMatches = (isoDate >= todayIso);
                }} else {{
                    dateMatches = true; // Fallback: nicht ausblenden, falls unbelegbar
                }}
            }}

            if (textMatches && dateMatches) {{
                if (!group.hasLayer(marker)) {{
                    group.addLayer(marker);
                }}
                shownCount++;
                console.log("✔ [SICHTBAR] ISO-Datum:", isoDate, "| >= Heute?:", dateMatches);
            }} else {{
                if (group.hasLayer(marker)) {{
                    group.removeLayer(marker);
                }}
                hiddenCount++;
                console.log("❌ [AUSGEBLENDET] ISO-Datum:", isoDate, "| Datum-Match?:", dateMatches, "| Text-Match?:", textMatches);
            }}
        }});

        console.log("📊 RESULTAT -> Sichtbar:", shownCount, "| Ausgeblendet:", hiddenCount);
    }}
    </script>
    """
    
