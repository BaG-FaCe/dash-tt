"""
backend_manager.py
==================
Manages backend subprocess and MQTT control signal publishing.
Allows the GUI to:
  1. Start/stop the backend process
  2. Send control signals (start/stop/continue) via MQTT
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
    Manages the backend process and MQTT control publishing.
    """

    def __init__(self, mqtt_broker: str = "127.0.0.1", mqtt_port: int = 1883):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.control_topic = "sensor/control/continue"
        
        self.backend_process = None
        self._mqtt_client = None
        self._lock = threading.Lock()
        self.session_key = None
        
        # Determine backend script path
        self.backend_script = Path(__file__).parent / "backend.py"

    def _init_mqtt(self):
        """Initialize MQTT client for publishing control signals."""
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
        Start the backend process in the background.
        Generates a new session key for this session.
        Returns True if successful, False if already running or error.
        """
        with self._lock:
            if self.backend_process is not None and self.backend_process.poll() is None:
                print("[BackendManager] Backend already running")
                return False

            try:
                # Generate a new session key (UUID + timestamp)
                self.session_key = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                print(f"[BackendManager] Generated session key: {self.session_key}")
                
                # Set up environment for backend process
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
        Stop the backend process and generate a new session key.
        Returns True if successful, False if not running or error.
        """
        with self._lock:
            if self.backend_process is None or self.backend_process.poll() is not None:
                print("[BackendManager] Backend not running")
                return False

            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
                print("[BackendManager] Backend stopped")
                # Generate a new session key for the next session
                self.session_key = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                print(f"[BackendManager] Generated new session key for next session: {self.session_key}")
                return True
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
                self.backend_process.wait()
                print("[BackendManager] Backend killed (timeout)")
                # Generate a new session key for the next session
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
        """Get the current session key."""
        with self._lock:
            return self.session_key or "Keine Session"

    def send_control_signal(self, continue_flag: bool) -> bool:
        """
        Send control signal to backend via MQTT.
        
        Args:
            continue_flag: True to start/continue, False to stop
            
        Returns:
            True if signal sent successfully, False otherwise
        """
        if not self._init_mqtt():
            print("[BackendManager] MQTT not available")
            return False

        try:
            payload = json.dumps({"continue": continue_flag})
            self._mqtt_client.publish(self.control_topic, payload, qos=1)
            print(f"[BackendManager] Published control signal: continue={continue_flag}")
            return True
        except Exception as e:
            print(f"[BackendManager] Failed to publish control signal: {e}")
            return False

    def cleanup(self):
        """Clean up resources."""
        self.stop_backend()
        if self._mqtt_client is not None:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            print("[BackendManager] MQTT client closed")
