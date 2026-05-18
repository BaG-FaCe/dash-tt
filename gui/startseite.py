import streamlit as st


def render_startseite_page() -> None:
    st.title("Startseite")
    st.markdown("""
    ## Willkommen zum Tettnang Umwelt Dashboard!
    """)
    st.info("Hier könnne Sie Informationen über das Dashboard und die verfügbaren Funktionen finden.")
    st.markdown("""
    ### Funktionen:
    - **Datenvisualisierung**: Interaktive Grafiken und Diagramme zur Analyse der Umweltdaten.
    - **Controller Verwaltung**: Überwachung und Steuerung der angeschlossenen ESP32-Controller.
    - **Benutzerverwaltung**: Verwaltung von Benutzerkonten und Berechtigungen.
    - **Echtzeit-Updates**: Live-Datenaktualisierungen für aktuelle Informationen.
    """)
    st.markdown("""
    ### Navigation:
    Verwenden Sie die Navigationsleiste auf der linken Seite, um zu den verschiedenen Funktionen des Dashboards zu gelangen.
    """)
    st.markdown("""    ### Kontakt:
    Bei Fragen oder Problemen wenden Sie sich bitte an den Support unter (es gibt keinen support, nur Gott kann dir bei Supportanfragen helfen).
    """)
    
