- [ ] Update requirements.txt to add folium + streamlit-folium for OpenStreetMap maps
- [ ] Update gui/dashboard.py:
  - [ ] Tie dashboard auto-refresh to an endless 2-second rerun loop (enabled by default)
  - [ ] Replace current pydeck/mapbox GPS visualization with OpenStreetMap (points and/or route)
  - [ ] Add sidebar controls: points-vs-route mode and “how many points at a time” (show last N)
- [ ] Run the app to verify:
  - [ ] Page reruns every ~2 seconds
  - [ ] Map renders with OpenStreetMap tiles
  - [ ] Mode/controls work (points count + route)

## Nutzung und Bedienung
- [ ] Grafische Elemente in der App prüfen:
  - [ ] Dashboard zeigt relevante Kennzahlen in klaren Blöcken
  - [ ] Kartenansicht verwendet OpenStreetMap für GPS-Punkte und Routen
  - [ ] Tooltipps oder Beschriftungen ergänzen, damit Nutzer sofort verstehen, was dargestellt wird
- [ ] Bedienungshinweise hinzufügen:
  - [ ] Startseite / Dashboard: Übersicht über aktuelle Daten und Status
  - [ ] Navigation: Menüpunkt für Einstellungen, Dashboard und Startseite deutlich machen
  - [ ] Hinweise auf Dashboard-Steuerung: Auswahl zwischen "Punkte" und "Route", Anzeige letzter N Punkte
- [ ] Unterstreichungen und Hervorhebungen einbauen:
  - [ ] Wichtige Texte in deutsch annotieren (z. B. "Aktuelle Position", "Letzte Messwerte", "Karte aktualisiert alle 2 Sekunden")
  - [ ] Farben oder Icons für Statusinformationen nutzen (z. B. grün = aktiv, rot = Fehler)

## Portainer Deployment
- [ ] Docker-Image erstellen
  - [ ] Prüfen, ob `Dockerfile` existiert und lauffähig ist
  - [ ] Image bauen: `docker build -t app-gui .`
- [ ] Container in Portainer einrichten
  - [ ] Neues Container-Deployment wählen
  - [ ] Image-Name `app-gui` eintragen oder im Registry-Pfad verwenden
  - [ ] Ports weiterleiten: z. B. `8000:8000` (je nachdem, welcher Port im `app.py` genutzt wird)
  - [ ] Volume-Mounts prüfen, falls persistente Dateien oder Konfiguration benötigt werden
- [ ] Netzwerke und Umgebungsvariablen
  - [ ] Falls externe Services verwendet werden, das passende Netzwerk auswählen
  - [ ] Umgebungsvariablen in Portainer setzen, z. B. API-Keys, Log-Level oder Pfade
- [ ] Start und Kontrolle
  - [ ] Container starten und Logs prüfen
  - [ ] Verfügbarkeit testen: `http://<host>:<port>` im Browser öffnen
  - [ ] Bei Problemen: Logs lesen, Container neu starten, Konfiguration prüfen

## Deutsche Anleitungsschritte für Portainer
1. Portainer öffnen und zum Bereich "Stacks" oder "Containers" wechseln.
2. Bei "Containers" auf "Add container" klicken.
3. Name vergeben, z. B. `app-gui`.
4. Unter "Image" das zuvor gebaute Image `app-gui` eintragen.
5. Port Mapping konfigurieren:
   - Host-Port: `8000`
   - Container-Port: `8000` (oder den Port aus `app.py`)
6. Bei Bedarf Umgebungsvariablen hinzufügen.
7. Auf "Deploy the container" klicken.
8. Nach dem Start auf "Logs" klicken und prüfen, ob die App erfolgreich gestartet ist.
9. Im Browser `http://<IP-des-Servers>:8000` aufrufen.
10. Wenn alles funktioniert, kann der Container unter "Containers" überwacht und bei Bedarf neu gestartet werden.
