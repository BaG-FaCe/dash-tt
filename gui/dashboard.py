import streamlit as st


def render_dashboard_page() -> None:
    st.title("Dashboard")

    sub = st.sidebar.radio(
        "Dashboard Unterkategorien",
        ["Visualisierung", "Manueller Eintrag"],
        index=0,
        key="dashboard_sub_radio",
    )

    if sub == "Visualisierung":
        st.subheader("Visualisierung")
    else:
        st.subheader("Manueller Eintrag")

    st.info("Leere Seite (nach Login).")
