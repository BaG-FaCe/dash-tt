import streamlit as st

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
            st.title("Startseite")
            st.info("Leere Seite (nach Login).")

        elif main_page == "Dashboard":
            sub = st.sidebar.radio(
                "Dashboard Unterkategorien",
                ["Visualisierung", "Manueller Eintrag"],
                index=0,
                key="dashboard_sub_radio",
            )
            st.title("Dashboard")
            if sub == "Visualisierung":
                st.subheader("Visualisierung")
            else:
                st.subheader("Manueller Eintrag")
            st.info("Leere Seite (nach Login).")

        elif main_page == "Controller Verwaltung":
            sub = st.sidebar.radio(
                "Controller Verwaltung",
                ["Kontrolle ESP32", "Verwaltung ESP32"],
                index=0,
                key="controller_sub_radio",
            )
            st.title("Controller Verwaltung")
            if sub == "Kontrolle ESP32":
                st.subheader("Kontrolle ESP32")
            else:
                st.subheader("Verwaltung ESP32")
            st.info("Leere Seite (nach Login).")

        else:  # Einstellungen
            st.title("Einstellungen")
            st.info("Leere Seite (nach Login).")

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
