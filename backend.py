#this file servers for the backend of the app
#its main purposes:
#       fetch the mqtt data and enrich it
#       fetch gps data and enrich the dataload with it
#       pipe the data back into the database

import os

import mysql.connector
import random
import sys
import signal
from datetime import datetime

# --- MariaDB credentials via env (fülle die Werte später im Container ein) ---
os.environ.setdefault("MARIADB_HOST", "127.0.0.1")
os.environ.setdefault("MARIADB_PORT", "3306")
os.environ.setdefault("MARIADB_USER", "dashboard")
os.environ.setdefault("MARIADB_PASSWORD", "dashpw")
os.environ.setdefault("MARIADB_DATABASE", "climateproject")

DB_CONFIG = {
    "host":     os.getenv("MARIADB_HOST", "127.0.01"),
    "port":     int(os.getenv("MARIADB_PORT", "3306")),
    "user":     os.getenv("MARIADB_USER", "dashboard"),
    "password": os.getenv("MARIADB_PASSWORD", "dashpw"),
    "database": os.getenv("MARIADB_DATABASE", "climateproject"),
    "table":    "environmental_data"}

def mqtt_subscriber():
    # Hier würde die Logik für das Abonnieren von MQTT-Daten und das Einfügen in die Datenbank implementiert werden.
    pass