import streamlit as st

from gui.controller_verwaltung import render_controller_verwaltung_page
from gui.dashboard import render_dashboard_page
from gui.einstellungen import render_einstellungen_page
from gui.startseite import render_startseite_page


def render_navbar_side_dashboard():
    """
    Generische leere Seite nach dem Login mit einer Navigation.

    - Primär: (optional) streamlit_plugins.components.navbar
    - Fallback: Native Streamlit-Sidebar-Navigation mit den gewünschten Seiten.
    """
    # Sidebar top-level (fallback)
    def fallback_navigation():
        main_page = st.sidebar.radio(
            "Kapitel",
            ["Startseite", "Dashboard", "Controller Verwaltung", "Einstellungen"],
            index=0,
            key="kapitel_radio",
        )

        if main_page == "Startseite":
            render_startseite_page()
        elif main_page == "Dashboard":
            render_dashboard_page()
        elif main_page == "Controller Verwaltung":
            render_controller_verwaltung_page()
        else:  # Einstellungen
            render_einstellungen_page()

    # Debug: Plugin-Navigation überspringen, um das native Sidebar-Rendering zu prüfen.
    # Später kann st_navbar wieder aktiviert werden; dann bleibt für das Content-Routing
    # nur fallback_navigation() übrig.
    fallback_navigation()


def render_navbar_top_dashboard():
    # Kopfzeile oben rechts mit Logout (ohne Plugin-Abhängigkeiten)
    left, right = st.columns([8, 2], gap="small")
    with left:
        st.title("")
    with right:
        if st.button("Logout", key="logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.open_register = False
            st.rerun()

    # Darunter weiterhin deine Navigation/Seitenlogik (Fallback via Sidebar)
    render_navbar_side_dashboard()
