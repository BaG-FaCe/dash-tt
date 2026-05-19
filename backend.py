import os
import re
import json
import signal
import sys
import threading
from datetime import datetime, timezone

import mysql.connector
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


# ---------------------------------------------------------------------------
# Konfiguration über Umgebungsvariablen
# ACHTUNG: Diese muessen entweder gesetzt werden als env in Container umgebung (Portainer)
# oder die defaults muessen hier im code angepasst werden beim local deployment (z.B. localhost statt 172.21.0.3)
# ---------------------------------------------------------------------------
os.environ.setdefault("MARIADB_HOST",     "172.24.240.214")
os.environ.setdefault("MARIADB_PORT",     "3306")
os.environ.setdefault("MARIADB_USER",     "root")
os.environ.setdefault("MARIADB_PASSWORD", "admin")
os.environ.setdefault("MARIADB_DATABASE", "climateproject")
os.environ.setdefault("SESSION_KEY",      "")

SESSION_KEY = os.getenv("SESSION_KEY")

DB_CONFIG = {
    "host":     os.getenv("MARIADB_HOST"),
    "port":     int(os.getenv("MARIADB_PORT")),
    "user":     os.getenv("MARIADB_USER"),
    "password": os.getenv("MARIADB_PASSWORD"),
    "database": os.getenv("MARIADB_DATABASE"),
}
DB_TABLE = "environmental_data"

MQTT_BROKER  = os.getenv("MQTT_BROKER", "172.24.240.214")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))

# ESP32 Topic
SENSOR_TOPIC = "home/esp32/status"

# GPS topics (Wird ueber handy gepusht)
GPS_LOCATION_TOPIC = "sensors2mqtt/haha"

# Control topic fuer esp32
CONTROL_TOPIC = "sensor/control/continue"


class Database:
    def __init__(self, config: dict, table: str):
        self.config = config
        self.table  = table
        self._conn   = None
        self._cursor = None

    def connect(self):
        self._conn   = mysql.connector.connect(**self.config)
        self._cursor = self._conn.cursor()
        print(f"[DB] Connected to {self.config['host']}:{self.config['port']} "
              f"-> {self.config['database']}")

    def insert(self, row: dict):
        columns      = ", ".join(row.keys())
        placeholders = ", ".join(["%s"] * len(row))
        sql = f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})"
        try:
            self._cursor.execute(sql, list(row.values()))
            self._conn.commit()
            print(f"[DB] Inserted row id={self._cursor.lastrowid}")
        except mysql.connector.Error as e:
            self._conn.rollback()
            print(f"[DB] Insert failed: {e}")
            raise

    def close(self):
        if self._cursor:
            self._cursor.close()
        if self._conn:
            self._conn.close()
        print("[DB] Connection closed")

class ControlState:
    """
    Verwaltet das Steuervorzeichen (Start/Stop/Fortsetzen).

    Standardmäßig auf False (gestoppt) und wird erst dann auf True gesetzt,
    wenn es explizit via MQTT empfangen wurde.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._continue = False

    def update(self, value: bool):
        with self._lock:
            self._continue = value
        print(f"[CONTROL] Updated to: {value}")

    @property
    def should_continue(self) -> bool:
        with self._lock:
            return self._continue

class GpsState:
    """
    Hält den zuletzt empfangenen GPS-Fix über MQTT (sensors2mqtt/haha/location) vor.

    Für Tests ohne Live-GPS wird auf die Umgebungsvariablen STATIC_LAT / STATIC_LON
    zurückgegriffen.
    """

    def __init__(self):
        self._lock      = threading.Lock()
        static_lat      = os.getenv("STATIC_LAT")
        static_lon      = os.getenv("STATIC_LON")
        self._latitude  = float(static_lat) if static_lat else None
        self._longitude = float(static_lon) if static_lon else None
        self._altitude  = None

    def update(self, lat: float, lon: float, alt: float | None = None):
        with self._lock:
            self._latitude  = lat
            self._longitude = lon
            self._altitude  = alt
        print(f"[GPS] Fix via MQTT: lat={lat:.6f}, lon={lon:.6f}"
              + (f", alt={alt:.1f}m" if alt is not None else ""))

    @property
    def latitude(self):
        with self._lock:
            return self._latitude

    @property
    def longitude(self):
        with self._lock:
            return self._longitude

    @property
    def altitude(self):
        with self._lock:
            return self._altitude

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._latitude is not None and self._longitude is not None


# Datenanreicherung

def enrich(payload: dict, gps: GpsState) -> dict:
    """
    Kombiniert die ESP32-MQTT-Nutzdaten mit GPS-Daten und Systemzeit, um eine
    vollständige Datenbankzeile zu erzeugen.

    Felder aus den ESP32-Nutzdaten : user_id, altitude,
                                      temperature, humidity,
                                      barometric_pressure, height
    Felder, die dieses Backend setzt : session_id (aus SESSION_KEY-Umgebungsvariable),
                                         measurement_date, created_at (System-UTC),
                                         latitude, longitude (aus MQTT-GPS),
                                         active (immer True)

    Die ESP32-Uhr wird NICHT verwendet: deren NTP-Synchronisation ist unzuverlässig
    und der Zeitstempel kann Epoch-Zeit (2000-01-01) sein, wenn das Gerät noch keine
    Netzwerkzeit hat.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for MariaDB

    return {
        # session_id aus Umgebungsvariable oder Payload (falls SESSION_KEY nicht gesetzt ist, z.B. im Testmodus)
        "session_id":           SESSION_KEY or payload.get("session_id", "unknown"),
        # user_id als Integer extrahieren (z.B. "user_123" -> 123), falls es im Payload vorhanden ist; sonst 0
        "user_id":              int("".join(filter(str.isdigit, payload["user_id"])) or 0),
        "altitude":             float(payload["altitude"]),
        "temperature":          float(payload["temperature"]),
        "humidity":             float(payload["humidity"]),
        "barometric_pressure":  float(payload["barometric_pressure"]),
        "height":               float(payload["height"]),

        # automatisch gesetzte Felder
        "measurement_date":     now,
        "created_at":           now,

        # GPS-Daten aus MQTT (können None sein, wenn noch kein Fix)
        "latitude":             gps.latitude,
        "longitude":            gps.longitude,

        # immer aktiv, da wir nur Daten speichern, wenn das Steuersignal auf True steht
        "active":               True,
    }



# Kombinierter MQTT-Backend (ESP32-Sensor + MQTT-GPS auf einer Broker-Verbindung)

class MQTTBackend:
    """
    Ein einzelner MQTT-Client, der drei Topics auf demselben Broker abonniert:

      - SENSOR_TOPIC       -> ESP32-Nutzdaten parsen, anreichern und in die DB einfügen
                                (nur wenn das Steuersignal aktiv ist)
      - GPS_LOCATION_TOPIC -> GpsState aktualisieren (lat/lon/alt)
      - CONTROL_TOPIC      -> ControlState aktualisieren (Start/Stop/Fortsetzen)
    """

    def __init__(self, db: Database, gps: GpsState, control: ControlState):
        self.db      = db
        self.gps     = gps
        self.control = control
        self.client  = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._connected = False

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._connected = True
            print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
            client.subscribe(SENSOR_TOPIC)
            print(f"[MQTT] Subscribed -> {SENSOR_TOPIC}")
            client.subscribe(GPS_LOCATION_TOPIC)
            print(f"[MQTT] Subscribed -> {GPS_LOCATION_TOPIC}")
            client.subscribe(CONTROL_TOPIC)
            print(f"[MQTT] Subscribed -> {CONTROL_TOPIC}")
        else:
            self._connected = False
            print(f"[MQTT] Connection failed, rc={rc}")
            # sicherstellen, dass wir im Fehlerfall nicht weiter versuchen, Sensor-Daten zu verarbeiten
            self.control.update(False)

    @staticmethod
    def _fix_json(raw: str) -> str:
        """
        Fix European-style decimal commas inside JSON numbers.
        e.g. "speedKmph":0,00  ->  "speedKmph":0.00
        Matches patterns like  :0,00  :1,50  :-3,14  but NOT
        the structural comma between two key-value pairs.
        """
        # Ersetze  <digits>,<digits>  durch  <digits>.<digits>  (nur innerhalb von Zahlen, nicht zwischen JSON-Elementen)
        # (z.b. "temperature":23,5  ->  "temperature":23.5)
        return re.sub(r'(:\s*-?\d+),(\d+)', r'\1.\2', raw)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        raw   = msg.payload.decode("utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError as e:
                print(f"[MQTT] Bad JSON on {topic}: {e}")
                print(f"[MQTT] Raw payload: {raw[:300]}")
                return

        # GPS location update
        if topic == GPS_LOCATION_TOPIC:
            self._handle_gps(data)

        # Control Signal updaten
        elif topic == CONTROL_TOPIC:
            self._handle_control(data)

        # ESP32 sensoren auslesen und in DB einfügen (nur wenn control signal auf True steht)
        elif topic == SENSOR_TOPIC:
            self._handle_sensor(data)

    def _handle_control(self, data: dict):
        """
        Update control state from sensor/control/continue payload.
        Expects: {"continue": true/false} or just a boolean
        """
        try:
            # Handle if payload is a boolean directly
            if isinstance(data, bool):
                self.control.update(data)
            # Handle if payload is a dict with 'continue' key
            elif isinstance(data, dict):
                continue_flag = data.get("continue", False)
                self.control.update(continue_flag)
            else:
                print(f"[CONTROL] Unexpected payload type: {type(data)}")
        except (KeyError, ValueError, TypeError) as e:
            print(f"[CONTROL] Could not parse control payload: {e}")

    def _handle_gps(self, data: dict):
        """
        Update GPS state from sensors2mqtt/haha payload.

        Expected structure:
          {
            "status": "connected",
            "time": "...",
            "sensors": [
              {
                "type": "location",
                "values": {
                  "latitude": ..., "longitude": ..., "altitude": ...
                }
              }
            ]
          }
        """
        try:
            sensors = data.get("sensors", [])
            for sensor in sensors:
                if sensor.get("type") == "location":
                    values = sensor["values"]
                    lat = float(values["latitude"])
                    lon = float(values["longitude"])
                    alt = float(values["altitude"]) if "altitude" in values else None
                    self.gps.update(lat, lon, alt)
                    return
            # No location-type sensor in this message -- silently skip
        except (KeyError, ValueError, TypeError) as e:
            print(f"[GPS] Could not parse location payload: {e}")

    def _handle_sensor(self, data: dict):
        """Verarbeitet die ESP32-Nutzdaten und schreibt in die DB (nur wenn das Steuersignal aktiv ist und der MQTT-Client verbunden ist)."""
        print(f"[MQTT] Sensor  T={data.get('temperature')}°C  "
              f"H={data.get('humidity')}%  "
              f"P={data.get('barometric_pressure')}hPa  "
              f"Alt={data.get('altitude')}m")

        # Check if we should continue processing
        if not self._connected:
            print("[WARN] Not connected to MQTT broker -- ignoring sensor data")
            return

        if not self.control.should_continue:
            print("[WARN] Control flag is False -- ignoring sensor data")
            return

        if not self.gps.ready:
            print("[WARN] No GPS fix yet -- lat/lon will be NULL")

        try:
            row = enrich(data, self.gps)
            self.db.insert(row)
        except KeyError as e:
            print(f"[ERROR] Missing payload field: {e}")
        except Exception as e:
            print(f"[ERROR] Could not process sensor message: {e}")

    def start(self) -> None:
        """Connect to MQTT broker and block with loop_forever()."""
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_forever()


    def stop(self):
        self.client.disconnect()
        print("[MQTT] Disconnected")


def main():
    db      = Database(DB_CONFIG, DB_TABLE)
    gps     = GpsState()
    control = ControlState()

    db.connect()

    backend = MQTTBackend(db, gps, control)

    def shutdown(sig, frame):
        print("\n[SYS] Shutting down...")
        backend.stop()
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("[SYS] Backend running. Press Ctrl+C to stop.")
    print(f"[SYS] Session Key: {SESSION_KEY or 'Not set'}")
    print(f"[SYS] Listening for GPS on: {GPS_LOCATION_TOPIC}")
    print(f"[SYS] Listening for sensors on: {SENSOR_TOPIC}")
    print(f"[SYS] Listening for control on: {CONTROL_TOPIC}")
    backend.start()   # blocks here


if __name__ == "__main__":
    main()