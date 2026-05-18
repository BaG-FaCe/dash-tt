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
# Config via environment variables
# ---------------------------------------------------------------------------
os.environ.setdefault("MARIADB_HOST",     "127.0.0.1")
os.environ.setdefault("MARIADB_PORT",     "3306")
os.environ.setdefault("MARIADB_USER",     "root")
os.environ.setdefault("MARIADB_PASSWORD", "admin")
os.environ.setdefault("MARIADB_DATABASE", "climateproject")
os.environ.setdefault("SESSION_KEY",      None)

SESSION_KEY = os.getenv("SESSION_KEY")

DB_CONFIG = {
    "host":     os.getenv("MARIADB_HOST"),
    "port":     int(os.getenv("MARIADB_PORT")),
    "user":     os.getenv("MARIADB_USER"),
    "password": os.getenv("MARIADB_PASSWORD"),
    "database": os.getenv("MARIADB_DATABASE"),
}
DB_TABLE = "environmental_data"

MQTT_BROKER  = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))

# ESP32 sensor topic (unchanged)
SENSOR_TOPIC = "home/esp32/status"

# GPS topics published by the phone/GPS app
GPS_LOCATION_TOPIC = "sensors2mqtt/haha"

# Control topic for start/stop/continue signal
CONTROL_TOPIC = "sensor/control/continue"


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Control state  (thread-safe, written by MQTT control callback)
# ---------------------------------------------------------------------------
class ControlState:
    """
    Holds the control flag for start/stop/continue signal.
    Defaults to False (stopped) and only starts when explicitly set to true via MQTT.
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


# ---------------------------------------------------------------------------
# GPS state  (thread-safe, written by MQTT GPS callback, read by sensor handler)
# ---------------------------------------------------------------------------
class GpsState:
    """
    Holds the most recent GPS fix received via MQTT (sensors2mqtt/haha/location).
    Falls back to STATIC_LAT / STATIC_LON env vars for testing without a live
    GPS source.
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


# ---------------------------------------------------------------------------
# Data enrichment
# ---------------------------------------------------------------------------
def enrich(payload: dict, gps: GpsState) -> dict:
    """
    Merge the ESP32 MQTT payload with GPS data and system time to produce a
    complete DB row.

    Fields taken from ESP32 payload : user_id, altitude,
                                       temperature, humidity,
                                       barometric_pressure, height
    Fields set by this backend      : session_id (from SESSION_KEY env var),
                                       measurement_date, created_at (system UTC),
                                       latitude, longitude (from MQTT GPS),
                                       active (always True)

    The ESP32 clock is NOT used: its NTP sync is unreliable and the timestamp
    can be epoch (2000-01-01) when the device has no network time yet.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for MariaDB

    return {
        # session key from backend manager
        "session_id":           SESSION_KEY or payload.get("session_id", "unknown"),
        # sensor readings from ESP32
        "user_id":              int("".join(filter(str.isdigit, payload["user_id"])) or 0),
        "altitude":             float(payload["altitude"]),
        "temperature":          float(payload["temperature"]),
        "humidity":             float(payload["humidity"]),
        "barometric_pressure":  float(payload["barometric_pressure"]),
        "height":               float(payload["height"]),

        # system UTC timestamp (replaces unreliable ESP32 clock)
        "measurement_date":     now,
        "created_at":           now,

        # position from MQTT GPS topic
        "latitude":             gps.latitude,
        "longitude":            gps.longitude,

        # record is active by definition when freshly inserted
        "active":               True,
    }


# ---------------------------------------------------------------------------
# Combined MQTT backend  (ESP32 sensor + MQTT GPS on one broker connection)
# ---------------------------------------------------------------------------
class MQTTBackend:
    """
    Single MQTT client that subscribes to three topics on the same broker:
      - SENSOR_TOPIC          -> parse ESP32 payload, enrich, insert into DB (if control flag is true)
      - GPS_LOCATION_TOPIC    -> update GpsState (lat/lon/alt)
      - CONTROL_TOPIC         -> update ControlState (start/stop/continue signal)
    """

    def __init__(self, db: Database, gps: GpsState, control: ControlState):
        self.db      = db
        self.gps     = gps
        self.control = control
        self.client  = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._connected = False

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------
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
            # Ensure control flag is set to False on connection failure
            self.control.update(False)

    @staticmethod
    def _fix_json(raw: str) -> str:
        """
        Fix European-style decimal commas inside JSON numbers.
        e.g. "speedKmph":0,00  ->  "speedKmph":0.00
        Matches patterns like  :0,00  :1,50  :-3,14  but NOT
        the structural comma between two key-value pairs.
        """
        # Replace  <digits>,<digits>  that appear after a colon/space
        # (i.e. they are JSON number values, not object separators)
        return re.sub(r'(:\s*-?\d+),(\d+)', r'\1.\2', raw)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        raw   = msg.payload.decode("utf-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try again after fixing European decimal commas (e.g. 0,00 -> 0.00)
            fixed = self._fix_json(raw)
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError as e:
                print(f"[MQTT] Bad JSON on {topic}: {e}")
                print(f"[MQTT] Raw payload: {raw[:300]}")
                return

        # ---- GPS location update ----------------------------------------
        if topic == GPS_LOCATION_TOPIC:
            self._handle_gps(data)

        # ---- Control signal update ----------------------------------------
        elif topic == CONTROL_TOPIC:
            self._handle_control(data)

        # ---- ESP32 sensor reading ----------------------------------------
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
        """Process ESP32 payload and write to DB (only if control flag is true and connected)."""
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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_forever()   # blocks; signal handler stops it

    def stop(self):
        self.client.disconnect()
        print("[MQTT] Disconnected")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
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