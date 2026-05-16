import os

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import time
from PIL import Image

from auth.auth import login, register_user
from gui.navbar import render_navbar_side_dashboard, render_navbar_top_dashboard

# --- MariaDB credentials via env (fülle die Werte später im Container ein) ---
os.environ.setdefault("MARIADB_HOST", "127.0.0.1")
os.environ.setdefault("MARIADB_PORT", "3306")
os.environ.setdefault("MARIADB_USER", "dashboard")
os.environ.setdefault("MARIADB_PASSWORD", "dashpw")
os.environ.setdefault("MARIADB_DATABASE", "climateproject")



# Deploy-Button, Hamburger-Menü und Footer ausblenden





#-----------------------------
#Standartwerte setzen für spätere verwendung
st.set_page_config(
    page_title="Tettnang Umwelt Dashboard",
    page_icon="graphics/logo.png",
    layout="wide",  # "centered" oder "wide"
    initial_sidebar_state="expanded",  # "auto", "expanded", "collapsed"
)
# -----------------------------
# Session State defaults
# -----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "open_register" not in st.session_state:
    st.session_state.open_register = False

# -----------------------------
# Main App Flow
# -----------------------------
if not st.session_state.logged_in:
    login()

    # Registrierungs-Modal nur anzeigen, solange NICHT eingeloggt
    if st.session_state.open_register:
        register_user()
else:
    render_navbar_top_dashboard()

