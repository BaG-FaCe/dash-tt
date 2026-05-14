# TODO - Auth mit MariaDB + Passwort-Hashing - Auth mit MariaDB + Passwort-Hashing

- [ ] `auth/auth.py` erweitern: DB-Connection (MariaDB lokal) über Umgebungsvariablen konfigurieren
- [ ] Passwort-Hashing implementieren (bcrypt bevorzugt, fallback auf PBKDF2 falls bcrypt nicht verfügbar ist)
- [ ] `register_user()` anpassen:
  - [ ] Felder validieren (username/email/password/confirm)
  - [ ] Prüfen ob username bereits existiert → Meldung + Abbruch
  - [ ] User mit gehashtem Passwort in `climateproject.users` anlegen (inkl. Felder laut Vorgabe)
- [ ] `login()` anpassen:
  - [ ] User anhand username laden
  - [ ] Passwort gegen Hash verifizieren
  - [ ] bei Erfolg `st.session_state.logged_in=True` + rerun
- [ ] Minimal testen: Code-Syntax + Streamlit Dialog-Flow (open_register/logged_in)
