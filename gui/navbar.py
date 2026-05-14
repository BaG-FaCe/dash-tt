import streamlit as st

from gui.controller_verwaltung import render_controller_verwaltung_page
from gui.dashboard import render_dashboard_page
from gui.einstellungen import render_einstellungen_page
from gui.startseite import render_startseite_page


def render_navbar_side_dashboard():
    """
    Generic empty page after login with a navbar in sidebar/top/side.
    - Primary: streamlit_plugins.components.navbar (try/except)
    - Fallback: native Streamlit sidebar navigation with the requested pages.
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

    # DEBUG: bypass plugin navbar to verify native sidebar rendering.
    # Later we can re-enable st_navbar and keep only fallback_navigation() for content routing.
    fallback_navigation()


def render_navbar_top_dashboard():
    # Top-Header mit Logout oben rechts (ohne Plugin-Abhängigkeit)
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
