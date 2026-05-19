import streamlit as st


def render_controller_verwaltung_page() -> None:
    st.title("Controller Verwaltung")

    sub = st.sidebar.radio(
        "Controller Verwaltung",
        ["Kontrolle ESP32"],
        index=0,
        key="controller_sub_radio",
    )

    if sub == "Kontrolle ESP32":
        render_esp32_control()


def render_esp32_control() -> None:
    """Bedienoberfläche zur Steuerung der ESP32-Datenerfassung."""
    st.subheader("ESP32 Kontrolle")

    manager = st.session_state.backend_manager

    # Backend Status und Steuerung
    st.markdown("### Backend Status")
    col1, col2, col3 = st.columns(3, gap="small")

    with col1:
        # Display momentanen Backend-Status
        status = "Läuft" if manager.is_running() else "Gestoppt"
        st.metric("Backend Status", status)

    with col2:
        # Display Session Key (abgekürzt) für Debugging-Zwecke
        session_key = manager.get_session_key()
        st.metric("Session Key", session_key[:16] if len(session_key) > 16 else session_key)

    with col3:
        # Backend starten/stoppen
        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("Start Backend", key="btn_start_backend", use_container_width=True):
                if manager.start_backend():
                    st.success("Backend gestartet!")
                    st.rerun()
                else:
                    st.error("Backend konnte nicht gestartet werden")

        with col_stop:
            if st.button("Stop Backend", key="btn_stop_backend", use_container_width=True):
                if manager.stop_backend():
                    st.success("Backend gestoppt!")
                    # Stoppe den Control Signal, damit die Datenerfassung sofort aufhört, auch wenn das Backend noch kurz braucht, um vollständig zu terminieren.
                    st.session_state.control_signal = False
                    st.rerun()
                else:
                    st.error("Backend konnte nicht gestoppt werden")

    st.divider()

    st.markdown("### Datenerfassung Steuerung")

    if not manager.is_running():
        st.warning("Backend muss laufen, um die Datenerfassung zu steuern!")
    else:
        # Toggle für Datenerfassung: Start/Stop
        col1, col2 = st.columns([1, 2], gap="small")

        with col1:
            control_toggle = st.toggle(
                "Datenerfassung",
                value=st.session_state.control_signal,
                key="control_toggle",
            )

        with col2:
            if control_toggle != st.session_state.control_signal:
                st.session_state.control_signal = control_toggle
                if manager.send_control_signal(control_toggle):
                    if control_toggle:
                        st.success("Datenerfassung gestartet!")
                    else:
                        st.info("Datenerfassung gestoppt!")
                else:
                    st.error("Fehler beim Senden des Steuersignals")

        # Status indikatorino neihbourino
        if st.session_state.control_signal:
            st.success("Datenerfassung aktiv - ESP32 Daten werden aufgezeichnet")
        else:
            st.info("Datenerfassung inaktiv - ESP32 Daten werden ignoriert")

    st.divider()

    #Session Information
    st.markdown("### Session Information")
    session_key = manager.get_session_key()
    st.code(session_key, language="text")
    st.caption(f"Diese Session-ID wird mit allen aufgezeichneten Daten gespeichert und ermöglicht die Zuordnung von Messungen.")
