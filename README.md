# Klima-/Umwelt-Dashboard (Streamlit)

Dieses Projekt ist ein **Streamlit-basiertes Web-Dashboard** für den Betrieb/Übersicht von Daten rund um **Umwelt/Climate**. Nach dem Login erscheint eine Navigation (Sidebar) mit mehreren Kapiteln.

## Inhaltsverzeichnis
- [Technologien](#technologien)
- [Projektstruktur](#projektstruktur)
- [Seiten / Navigation](#seiten--navigation)
- [Login / Authentifizierung](#login--authentifizierung)
- [Konfiguration](#konfiguration)
- [Starten der App (lokal)](#starten-der-app-lokal)
- [Docker (falls verwendet)](#docker-falls-verwendet)
- [Testing & Debug-Hinweise](#testing--debug-hinweise)
- [TODO](#todo)

## Technologien
- **Python**
- **Streamlit**
- **Pandas / NumPy** (für Datenverarbeitung)
- **MariaDB/MySQL** (über Umgebungsvariablen, siehe Konfiguration)
- Optional/Plugin: `streamlit_plugins.components.navbar` (im Code als Möglichkeit vorhanden)

## Projektstruktur
Wichtige Dateien/Ordner:

- `app.py`
  - Startpunkt der Streamlit-App
  - Session-Logik: Login oder Dashboard-UI
- `auth/`
  - `auth.py`: Login/Registrierung (Benutzerverwaltung)
- `gui/`
  - `navbar.py`: Navigation/Sidebar-Logik (Kapitel-Auswahl)
  - **Pro Seite eine eigene Datei**:
    - `startseite.py`
    - `dashboard.py`
    - `controller_verwaltung.py`
    - `einstellungen.py`
- `graphics/`
  - Bilder/Assets (z.B. Logos, Hintergründe)
- `config.toml`
  - Streamlit-Konfiguration (falls genutzt)

## Seiten / Navigation
Die Navigation passiert über `st.sidebar.radio("Kapitel", ...)` in:

- `gui/navbar.py`
  - **Startseite**
  - **Dashboard**
    - Unterkategorien (ebenfalls als Sidebar-radio):
      - Visualisierung
      - Manueller Eintrag
  - **Controller Verwaltung**
    - Unterkategorien (ebenfalls als Sidebar-radio):
      - Kontrolle ESP32
      - Verwaltung ESP32
  - **Einstellungen**

### Wichtig (Streamlit DuplicateElementId)
In `gui/navbar.py` werden für alle `st.sidebar.radio(...)`-Elemente **separate `key=`** gesetzt, damit Streamlit keine doppelten Widget-IDs erzeugt.

## Login / Authentifizierung
Die Auth-Logik befindet sich in:
- `auth/auth.py`

In `app.py` wird geprüft:
- Wenn `st.session_state.logged_in` **false** ist → `login()` (und ggf. `register_user()`)
- Wenn **true** ist → UI mit Navigation (`render_navbar_top_dashboard()` und `render_navbar_side_dashboard()` wird korrekt nur einmal gerendert)

## Konfiguration
MariaDB-Verbindungsdaten werden aktuell in `app.py` über `os.environ.setdefault(...)` gesetzt. Diese Variablen sind:

- `MARIADB_HOST`
- `MARIADB_PORT`
- `MARIADB_USER`
- `MARIADB_PASSWORD`
- `MARIADB_DATABASE`

Empfehlung: In Docker/Production diese Werte per **Environment Variables** übergeben und nicht hart im Code lassen.

## Starten der App (lokal)
1. Virtuelle Umgebung aktivieren (falls vorhanden):
   
```bash
   source venv/bin/activate
   
```
2. Abhängigkeiten installieren:
   
```bash
   pip install -r requirements.txt
   
```
3. Streamlit starten:
   
```bash
   streamlit run app.py
   ```

## Docker (falls verwendet)
Wenn ein `Dockerfile` vorhanden ist (hier vorhanden), kann die App typischerweise gebaut und gestartet werden. Beispiel (je nach Dockerfile/Setup):
```bash
docker build -t klima-dashboard .
docker run -p 8501:8501 \
  -e MARIADB_HOST=... \
  -e MARIADB_PORT=... \
  -e MARIADB_USER=... \
  -e MARIADB_PASSWORD=... \
  -e MARIADB_DATABASE=... \
  klima-dashboard
```

## Testing & Debug-Hinweise
### Sidebar-Visibility / Navigation
- Seiten werden über `gui/*` Dateien gerendert und über `gui/navbar.py` gesteuert.
- Wenn Streamlit Fehler zu Widgets meldet (z.B. DuplicateElementId), liegt das fast immer an:
  - mehrfach gerenderten Widgets in derselben Run-Iteration
  - fehlenden/identischen `key` Parametern

### (Optional) Plugin-Navbar
Falls die Plugin-Navbar (z.B. `st_navbar`) Probleme macht oder das Layout überlagert, wurde im Code ein deterministischer Fallback (native Sidebar Navigation) genutzt.

## TODO
Siehe auch:
- `TODO.md`
