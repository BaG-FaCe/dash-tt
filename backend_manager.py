"""
backend_manager.py
==================
Verwaltet den Backend-Subprozess und das Veröffentlichen von MQTT-Steuersignalen.

Ermöglicht der GUI:
  1. Start/Stop des Backend-Prozesses
  2. Senden von Steuersignalen (Start/Stop/Fortsetzen) über MQTT
"""

import os
import subprocess
import json
import threading
import uuid
from pathlib import Path
from datetime import datetime

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


class BackendManager:
    """
    Verwaltet den Backend-Prozess sowie das MQTT-Veröffentlichen von Steuersignalen.
    """

    def __init__(self, mqtt_broker: str = "172.24.240.214", mqtt_port: int = 1883):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.control_topic = "sensor/control/continue"
        
        self.backend_process = None
        self._mqtt_client = None
        self._lock = threading.Lock()
        self.session_key = None
        
        # Ermittlung des Pfads zum Backend-Skript
        self.backend_script = Path(__file__).parent / "backend.py"

    def _init_mqtt(self):
        """Initialisiert den MQTT-Client zum Veröffentlichen von Steuersignalen."""
        if self._mqtt_client is None:
            self._mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2)
            try:
                self._mqtt_client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
                self._mqtt_client.loop_start()
            except Exception as e:
                print(f"[BackendManager] Failed to connect to MQTT: {e}")
                return False
        return True

    def start_backend(self) -> bool:
        """
        Startet den Backend-Prozess im Hintergrund.

        Generiert dabei einen neuen Session-Key für diese Sitzung.
        Gibt True zurück, wenn erfolgreich, sonst False (falls bereits laufend oder Fehler).
        """
        with self._lock:
            if self.backend_process is not None and self.backend_process.poll() is None:
                print("[BackendManager] Backend already running")
                return False

            try:
                # Generiert einen neuen Session-Key (UUID + Zeitstempel)
                self.session_key = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                print(f"[BackendManager] Session-Key generiert: {self.session_key}")

                # Richtet die Umgebungsvariablen für den Backend-Prozess ein
                env = os.environ.copy()
                env["SESSION_KEY"] = self.session_key
                
                self.backend_process = subprocess.Popen(
                    ["python", str(self.backend_script)],
                    cwd=str(self.backend_script.parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )
                print(f"[BackendManager] Started backend process (PID: {self.backend_process.pid})")
                return True
            except Exception as e:
                print(f"[BackendManager] Failed to start backend: {e}")
                return False

    def stop_backend(self) -> bool:
        """
        Stoppt den Backend-Prozess und generiert einen neuen Session-Key.

        Gibt True zurück, wenn erfolgreich, sonst False (falls nicht laufend oder Fehler).
        """
        with self._lock:
            if self.backend_process is None or self.backend_process.poll() is not None:
                print("[BackendManager] Backend not running")
                return False

            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
                print("[BackendManager] Backend gestoppt")
                # Generiert einen neuen Session-Key für die nächste Sitzung
                self.session_key = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                print(
                    f"[BackendManager] Neuer Session-Key für die nächste Sitzung: {self.session_key}"
                )
                return True
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
                self.backend_process.wait()
                print("[BackendManager] Backend beendet (Timeout)")
                # Generiert einen neuen Session-Key für die nächste Sitzung
                self.session_key = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                return True
            except Exception as e:
                print(f"[BackendManager] Failed to stop backend: {e}")
                return False

    def is_running(self) -> bool:
        """Check if backend process is running."""
        with self._lock:
            return self.backend_process is not None and self.backend_process.poll() is None

    def get_session_key(self) -> str:
        """Gibt den aktuellen Session-Key zurück."""
        with self._lock:
            return self.session_key or "Keine Session"

    def send_control_signal(self, continue_flag: bool) -> bool:
        """
        Sendet ein Steuersignal an das Backend über MQTT.

        Args:
            continue_flag: True für Start/Fortsetzen, False zum Stoppen

        Returns:
            True, wenn das Signal erfolgreich veröffentlicht wurde, sonst False
        """
        if not self._init_mqtt():
            print("[BackendManager] MQTT not available")
            return False

        try:
            payload = json.dumps({"continue": continue_flag})
            self._mqtt_client.publish(self.control_topic, payload, qos=1)
            print(f"[BackendManager] Steuersignal veröffentlicht: continue={continue_flag}")
            return True
        except Exception as e:
            print(f"[BackendManager] Failed to publish control signal: {e}")
            return False

    def cleanup(self):
        """Räumt Ressourcen auf (stoppt Backend und beendet MQTT, falls aktiv)."""
        self.stop_backend()
        if self._mqtt_client is not None:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            print("[BackendManager] MQTT client closed")
