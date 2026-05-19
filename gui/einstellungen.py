import streamlit as st

from auth.auth import create_user, fetch_user_by_username, fetch_all_users, update_user, user_exists


def _render_personal_settings(user: dict) -> None:
    st.header("Meine Einstellungen")
    st.info("Hier können Sie Ihr eigenes Passwort ändern.")

    st.text_input("Benutzername", value=user.get("username", ""), disabled=True)
    st.text_input("E-Mail", value=user.get("email", ""), disabled=True)

    with st.expander("Passwort ändern"):
        new_password = st.text_input("Neues Passwort", type="password", key="new_password")
        confirm_password = st.text_input(
            "Passwort bestätigen", type="password", key="confirm_password"
        )
        if st.button("Passwort speichern", key="save_password"):
            if not new_password:
                st.error("Bitte geben Sie ein neues Passwort ein.")
            elif new_password != confirm_password:
                st.error("Die Passwörter stimmen nicht überein.")
            else:
                success = update_user(user.get("username"), password=new_password)
                if success:
                    st.success("Passwort erfolgreich geändert.")
                else:
                    st.error("Passwort konnte nicht gespeichert werden.")




def _render_admin_user_overview() -> None:
    st.header("Benutzerverwaltung für Admins")
    st.info("Als Administrator sehen Sie hier alle Benutzer und können Konten anpassen.")

    users = fetch_all_users()
    if not users:
        st.warning("Keine Benutzer gefunden.")
        return

    st.dataframe(users, use_container_width=True)

    usernames = [user["username"] for user in users]
    selected_username = st.selectbox("Benutzer auswählen", usernames, key="admin_selected_user")
    selected_user = next((user for user in users if user["username"] == selected_username), None)
    if selected_user is None:
        st.error("Der ausgewählte Benutzer konnte nicht geladen werden.")
        return

    st.subheader(f"Einstellungen für {selected_username}")
    role = st.selectbox(
        "Rolle",
        ["user", "admin"],
        index=0 if selected_user.get("role") == "user" else 1,
        key="admin_role",
    )
    status = st.selectbox(
        "Status",
        ["active", "inactive"],
        index=0 if selected_user.get("status") == "active" else 1,
        key="admin_status",
    )
    email = st.text_input(
        "E-Mail",
        value=selected_user.get("email", ""),
        key="admin_email",
    )

    with st.expander("Passwort für diesen Benutzer setzen"):
        admin_new_password = st.text_input(
            "Neues Passwort (optional)", type="password", key="admin_new_password"
        )
        admin_confirm_password = st.text_input(
            "Passwort bestätigen", type="password", key="admin_confirm_password"
        )

    if st.button("Benutzer speichern", key="admin_save_user"):
        if admin_new_password and admin_new_password != admin_confirm_password:
            st.error("Die Passwörter stimmen nicht überein.")
            return

        password_value = admin_new_password if admin_new_password else None
        success = update_user(
            selected_username,
            email=email,
            role=role,
            status=status,
            password=password_value,
        )
        if success:
            st.success(f"Benutzer '{selected_username}' wurde aktualisiert.")
            st.rerun()
        else:
            st.error("Die Benutzerinformationen konnten nicht gespeichert werden.")

    with st.expander("Neuen Benutzer erstellen"):
        new_username = st.text_input("Neuer Benutzername", key="new_user_username")
        new_email = st.text_input("E-Mail für neuen Benutzer", key="new_user_email")
        new_role = st.selectbox(
            "Rolle für neuen Benutzer",
            ["user", "admin"],
            index=0,
            key="new_user_role",
        )
        new_status = st.selectbox(
            "Status für neuen Benutzer",
            ["active", "inactive"],
            index=0,
            key="new_user_status",
        )
        new_password = st.text_input(
            "Passwort", type="password", key="new_user_password"
        )
        new_confirm_password = st.text_input(
            "Passwort bestätigen", type="password", key="new_user_confirm_password"
        )

        if st.button("Neuen Benutzer erstellen", key="admin_create_user"):
            if not new_username or not new_email or not new_password:
                st.error("Bitte Benutzername, E-Mail und Passwort angeben.")
            elif new_password != new_confirm_password:
                st.error("Die Passwörter stimmen nicht überein.")
            elif user_exists(new_username):
                st.warning(f"Benutzer '{new_username}' existiert bereits.")
            else:
                created = create_user(
                    username=new_username,
                    email=new_email,
                    password=new_password,
                    created_by=st.session_state.get("current_user") or "admin",
                    role=new_role,
                    status=new_status,
                )
                if created:
                    st.success(f"Neuer Benutzer '{new_username}' erfolgreich erstellt.")
                    st.rerun()
                else:
                    st.error("Benutzer konnte nicht erstellt werden. Prüfen Sie die Eingaben.")


def render_einstellungen_page() -> None:
    st.title("Einstellungen")

    current_username = st.session_state.get("current_user")
    if not current_username:
        st.error("Keine Benutzerdaten gefunden. Bitte melden Sie sich erneut an.")
        return

    user = fetch_user_by_username(current_username)
    if not user:
        st.error("Benutzer konnte nicht geladen werden.")
        return

    role = st.session_state.get("user_role", "user")
    _render_personal_settings(user)

    if role == "admin":
        st.markdown("---")
        _render_admin_user_overview()
