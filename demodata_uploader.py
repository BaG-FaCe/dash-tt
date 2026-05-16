"""
climate_demo_uploader.py
Lädt jede Sekunde Demo-Klimadaten in die MariaDB-Tabelle 'sessions'
in der Datenbank 'climateproject' auf localhost hoch.

- session_id bleibt über alle Uploads gleich (wird einmalig beim Start generiert)
- user_id ist immer 1
- Jede Sekunde wird eine neue Zeile eingefügt (plain INSERT)

Voraussetzungen:
    pip install mysql-connector-python
"""

import time
import uuid
import random
import signal
import sys
from datetime import datetime

try:
    import mysql.connector
except ImportError:
    print("Bitte installiere mysql-connector-python:")
    print("  pip install mysql-connector-python")
    sys.exit(1)

# ── Datenbank-Konfiguration ───────────────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",        # ← ggf. anpassen
    "password": "1234",            # ← ggf. anpassen
    "database": "climateproject",
}

TABLE_NAME = "environmental_data"

# ── Feste Werte ───────────────────────────────────────────────────────────────
FIXED_SESSION_ID = str(uuid.uuid4())   # einmalig beim Start generiert, dann konstant
FIXED_USER_ID    = 1                   # immer user_id = 1

# ── Simulations-Parameter ─────────────────────────────────────────────────────
LAT_RANGE      = (48.65, 48.85)
LON_RANGE      = (9.05,  9.30)
ALT_RANGE      = (200.0, 500.0)
TEMP_RANGE     = (-10.0, 40.0)
HUMIDITY_RANGE = (10.0,  100.0)
PRESSURE_RANGE = (950.0, 1050.0)
HEIGHT_RANGE   = (0.0,   10.0)

# ─────────────────────────────────────────────────────────────────────────────

def generate_row() -> dict:
    """Erzeugt eine Zeile – session_id und user_id bleiben immer gleich."""
    return {
        "session_id":          FIXED_SESSION_ID,
        "user_id":             FIXED_USER_ID,
        "latitude":            round(random.uniform(*LAT_RANGE), 6),
        "longitude":           round(random.uniform(*LON_RANGE), 6),
        "altitude":            round(random.uniform(*ALT_RANGE), 2),
        "measurement_date":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature":         round(random.uniform(*TEMP_RANGE), 2),
        "humidity":            round(random.uniform(*HUMIDITY_RANGE), 2),
        "barometric_pressure": round(random.uniform(*PRESSURE_RANGE), 2),
        "height":              round(random.uniform(*HEIGHT_RANGE), 2),
        "active":              random.choice([0, 1]),
    }


INSERT_SQL = (
    "INSERT INTO `environmental_data` "
    "(session_id, user_id, latitude, longitude, altitude, "
    "measurement_date, temperature, humidity, barometric_pressure, height, active) "
    "VALUES "
    "(%(session_id)s, %(user_id)s, %(latitude)s, %(longitude)s, %(altitude)s, "
    "%(measurement_date)s, %(temperature)s, %(humidity)s, %(barometric_pressure)s, "
    "%(height)s, %(active)s)"
)


def main():
    print("Verbinde mit MariaDB ...")
    try:
        conn   = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"Verbunden mit '{DB_CONFIG['database']}' auf {DB_CONFIG['host']}")
    except mysql.connector.Error as e:
        print(f"Verbindungsfehler: {e}")
        sys.exit(1)

    print(f"Session-ID (fix): {FIXED_SESSION_ID}")
    print(f"User-ID    (fix): {FIXED_USER_ID}\n")

    # Sauberes Beenden mit Strg+C
    def on_exit(sig, frame):
        print("\n\nBeende ... Verbindung wird geschlossen.")
        cursor.close()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT,  on_exit)
    signal.signal(signal.SIGTERM, on_exit)

    count = 0
    print("Starte Upload (Strg+C zum Beenden) ...\n")
    print(f"{'#':>6}  {'temp':>7}  {'hum':>6}  {'pres':>10}  {'lat':>10}  {'lon':>10}")
    print("-" * 65)

    while True:
        row = generate_row()
        try:
            cursor.execute(INSERT_SQL, row)
            conn.commit()
            count += 1
            print(
                f"{count:>6}  "
                f"{row['temperature']:>6.2f}C  "
                f"{row['humidity']:>5.1f}%  "
                f"{row['barometric_pressure']:>9.2f}hPa  "
                f"{row['latitude']:>10.6f}  "
                f"{row['longitude']:>10.6f}"
            )
        except mysql.connector.Error as e:
            print(f"  [Fehler]: {e}")
            try:
                conn.reconnect(attempts=3, delay=1)
            except mysql.connector.Error:
                print("  Konnte Verbindung nicht wiederherstellen - beende.")
                sys.exit(1)

        time.sleep(1)


if __name__ == "__main__":
    main()