import streamlit as st


def render_controller_verwaltung_page() -> None:
    st.title("Controller Verwaltung")

    sub = st.sidebar.radio(
        "Controller Verwaltung",
        ["Kontrolle ESP32", "Verwaltung ESP32"],
        index=0,
        key="controller_sub_radio",
    )

    if sub == "Kontrolle ESP32":
        st.subheader("Kontrolle ESP32")
    else:
        st.subheader("Verwaltung ESP32")

    st.info("Leere Seite (nach Login).")
