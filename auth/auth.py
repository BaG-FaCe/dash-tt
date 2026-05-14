import os
import hmac
import hashlib
import base64

import streamlit as st

# Optional deps (fallback handled)
try:
    import pymysql  # type: ignore
except Exception:  # pragma: no cover
    pymysql = None

try:
    import bcrypt  # type: ignore
except Exception:  # pragma: no cover
    bcrypt = None


def _db_error(msg: str) -> None:
    st.error(msg)
    st.stop()


def get_db_connection():
    """
    MariaDB connection via pymysql.
    Config via environment variables:
      - MARIADB_HOST (default 127.0.0.1)
      - MARIADB_PORT (default 3306)
      - MARIADB_USER (default dashboard)
      - MARIADB_PASSWORD (default dashpw)
      - MARIADB_DATABASE (default climateproject)
    """
    if pymysql is None:
        _db_error(
            "MariaDB-Anbindung nicht möglich: 'pymysql' ist nicht installiert."
        )

    host = os.getenv("MARIADB_HOST", "mariadb")
    port = int(os.getenv("MARIADB_PORT", "3306"))
    user = os.getenv("MARIADB_USER", "dashboard")
    password = os.getenv("MARIADB_PASSWORD", "dashpw")
    database = os.getenv("MARIADB_DATABASE", "climateproject")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def hash_password(password: str) -> str:
    """
    Returns a string that encodes the algorithm so verify_password can work.
    Prefer bcrypt; fallback to PBKDF2-HMAC-SHA256.
    """
    if bcrypt is not None:
        pw_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(pw_bytes, salt)
        return "bcrypt$" + hashed.decode("utf-8")

    # PBKDF2 fallback (stdlib only)
    salt = os.urandom(16)
    iterations = 200_000
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    payload = (
        base64.b64encode(salt).decode("ascii")
        + "$"
        + str(iterations)
        + "$"
        + base64.b64encode(dk).decode("ascii")
    )
    return "pbkdf2$" + payload


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False

    if password_hash.startswith("bcrypt$"):
        if bcrypt is None:
            return False
        hashed = password_hash[len("bcrypt$") :].encode("utf-8")
        return bcrypt.checkpw(password.encode("utf-8"), hashed)

    if password_hash.startswith("pbkdf2$"):
        try:
            rest = password_hash[len("pbkdf2$") :]
            salt_b64, iterations_str, dk_b64 = rest.split("$", 2)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            iterations = int(iterations_str)
            expected_dk = base64.b64decode(dk_b64.encode("ascii"))
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                iterations,
            )
            return hmac.compare_digest(dk, expected_dk)
        except Exception:
            return False

    return False


def _normalize_changed_at_column(cursor) -> str:
    """
    Tries to detect whether the column is `changed_at` or literally `changed at`.
    """
    try:
        db = os.getenv("MARIADB_DATABASE", "climateproject")
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME='users'
            """,
            (db,),
        )
        cols = {row["COLUMN_NAME"] for row in cursor.fetchall()}
        if "changed_at" in cols:
            return "changed_at"
        if "changed at" in cols:
            return "`changed at`"
    except Exception:
        pass
    return "changed_at"


def user_exists(username: str) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM users WHERE username=%s LIMIT 1",
                (username,),
            )
            row = cursor.fetchone()
            return row is not None


def fetch_user_by_username(username: str):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, password, email, role, status, created_at, changed_at, created_by
                FROM users
                WHERE username=%s
                LIMIT 1
                """,
                (username,),
            )
            return cursor.fetchone()


def _resolve_created_by_id(created_by: str | int):
    """
    Schema-Hinweis:
    created_by scheint bei euch ein INTEGER (FK) zu sein (Fehler 1366).
    created_by wird daher vom Username auf die User.id gemappt.
    """
    if created_by is None:
        return None

    if isinstance(created_by, int):
        return created_by

    if isinstance(created_by, str) and created_by.isdigit():
        return int(created_by)

    created_by_username = str(created_by)
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username=%s LIMIT 1",
                (created_by_username,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return row.get("id")


def create_user(username: str, email: str, password: str, created_by: str | int):
    password_hash = hash_password(password)

    role = "user"
    status = "active"
    created_by_id = _resolve_created_by_id(created_by)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            changed_at_col = _normalize_changed_at_column(cursor)

            sql = f"""
                INSERT INTO users
                    (username, password, email, role, status, created_at, {changed_at_col}, created_by)
                VALUES
                    (%s, %s, %s, %s, %s, NOW(), NOW(), %s)
            """
            cursor.execute(
                sql,
                (username, password_hash, email, role, status, created_by_id),
            )
            return True


def login():
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.write("")
    with col2:
        st.image("graphics/logo.png", width=400)
    with col3:
        st.write("")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.write("")
    with col2:
        st.title("Login", text_alignment="center")
        st.markdown(
            "Bitte melden Sie sich an, um Zugriff auf das Dashboard zu erhalten.",
            text_alignment="center",
        )
    with col3:
        st.write("")

    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        button_login = st.button(
            "Anmelden", key="login", type="primary", use_container_width=True
        )
    with col2:
        st.write("")
    with col3:
        button_register = st.button(
            "Registrieren", key="register", type="secondary", use_container_width=True
        )

    if "open_register" not in st.session_state:
        st.session_state.open_register = False

    if button_register:
        st.session_state.open_register = True

    st.write("")
    if button_login:
        if not username or not password:
            st.error("Bitte Benutzername und Passwort eingeben.")
            return

        try:
            user = fetch_user_by_username(username)
            if not user:
                st.error("Ungültige Anmeldeinformationen")
                return

            ok = verify_password(password, user.get("password"))
            if not ok:
                st.error("Ungültige Anmeldeinformationen")
                return

            st.success("Erfolgreich eingeloggt!")
            st.session_state.logged_in = True
            st.session_state.open_register = False
            st.rerun()
        except Exception as e:
            st.error(f"Login fehlgeschlagen (DB/Hash): {e}")


@st.dialog(title="Regestrierung für Tettnang Umwelt Dashboard")
def register_user():
    st.write("Bitte füllen Sie das folgende Formular aus, um sich zu registrieren.")
    username = st.text_input("Benutzername")
    email = st.text_input("E-Mail-Adresse")
    password = st.text_input("Passwort", type="password")
    confirm_password = st.text_input("Passwort bestätigen", type="password")

    if st.button("Registrieren", type="primary"):
        if password != confirm_password:
            st.error("Die Passwörter stimmen nicht überein.")
            return
        if not username or not email or not password:
            st.error("Alle Felder müssen ausgefüllt werden.")
            return

        try:
            if user_exists(username):
                st.warning(
                    f"User '{username}' wurde bereits erstellt. Bitte einen anderen Benutzernamen nehmen."
                )
                return

            create_user(
                username=username,
                email=email,
                password=password,
                created_by="admin",
            )

            st.success("Registrierung erfolgreich! Sie können sich jetzt anmelden.")
            st.session_state.open_register = False
        except Exception as e:
            st.error(f"Registrierung fehlgeschlagen (DB/Hash): {e}")
