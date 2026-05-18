import hashlib
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from auth.auth import get_db_connection

import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh



# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_df(sql: str, params: tuple | list | None = None) -> pd.DataFrame:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
    return pd.DataFrame(rows)


def _execute(sql: str, params: tuple | list | None = None) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
        conn.commit()


def _get_unique_session_ids() -> list[str]:
    df = _fetch_df(
        "SELECT DISTINCT session_id FROM environmental_data ORDER BY session_id"
    )
    return [] if df.empty else [str(x) for x in df["session_id"].tolist()]


def _fetch_timeseries_for_session(session_id: str, points_shown: int) -> pd.DataFrame:
    sql = """
        SELECT
            measurement_date, altitude, temperature, humidity,
            barometric_pressure, latitude, longitude
        FROM environmental_data
        WHERE session_id = %s
        ORDER BY measurement_date ASC
        LIMIT %s
    """
    df = _fetch_df(sql, (session_id, int(points_shown)))
    if df.empty:
        return df

    df["measurement_date"] = pd.to_datetime(df["measurement_date"], errors="coerce")
    for col in ["altitude", "temperature", "humidity", "barometric_pressure",
                "latitude", "longitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(subset=["measurement_date", "altitude", "temperature",
                              "humidity", "barometric_pressure", "latitude", "longitude"])


def _fetch_full_session_for_edit(session_id: str) -> pd.DataFrame:
    """Fetch all columns + rowid-equivalent (measurement_date as PK) for the editor."""
    sql = """
        SELECT measurement_date, altitude, temperature, humidity,
               barometric_pressure, latitude, longitude
        FROM environmental_data
        WHERE session_id = %s
        ORDER BY measurement_date ASC
    """
    df = _fetch_df(sql, (session_id,))
    if df.empty:
        return df
    df["measurement_date"] = pd.to_datetime(df["measurement_date"], errors="coerce")
    for col in ["altitude", "temperature", "humidity", "barometric_pressure",
                "latitude", "longitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Map  –  only re-rendered when GPS data actually changed
# ---------------------------------------------------------------------------

def _geo_hash(df: pd.DataFrame) -> str:
    if df.empty:
        return "empty"
    return hashlib.md5(df[["latitude", "longitude"]].values.tobytes()).hexdigest()


def _build_folium_map(df: pd.DataFrame, show_route: bool, map_points_limit: int) -> folium.Map:
    if df.empty:
        return folium.Map(location=[52.3, 9.2], zoom_start=10, control_scale=True)

    center = [float(df["latitude"].mean()), float(df["longitude"].mean())]
    m = folium.Map(location=center, zoom_start=12, control_scale=True)

    points = df.tail(int(map_points_limit)).copy()

    if show_route and len(points) >= 2:
        coords = list(zip(points["latitude"].astype(float),
                          points["longitude"].astype(float)))
        folium.PolyLine(coords, color="blue", weight=3, opacity=0.75).add_to(m)
        folium.Marker(list(coords[0]),  popup="Start",
                      icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(list(coords[-1]), popup="End",
                      icon=folium.Icon(color="red",   icon="stop")).add_to(m)
    else:
        for _, r in points.iterrows():
            folium.CircleMarker(
                location=[float(r["latitude"]), float(r["longitude"])],
                radius=3, color="blue", fill=True, fill_opacity=0.7,
            ).add_to(m)
    return m


def _render_map(df: pd.DataFrame, show_route: bool, map_points_limit: int) -> None:
    current_hash = _geo_hash(df)
    if (current_hash != st.session_state.get("_map_geo_hash")
            or "cached_folium_map" not in st.session_state):
        st.session_state["cached_folium_map"] = _build_folium_map(df, show_route, map_points_limit)
        st.session_state["_map_geo_hash"] = current_hash

    st_folium(st.session_state["cached_folium_map"], width=None, height=360, returned_objects=[])


# ---------------------------------------------------------------------------
# Charts  –  interactive Plotly
# ---------------------------------------------------------------------------

_CHART_DEFS = [
    ("altitude",            "Höhe (m)",               "#3b82f6"),
    ("temperature",         "Temperatur (°C)",       "#ef4444"),
    ("humidity",            "Luftfeuchte (%)",       "#10b981"),
    ("barometric_pressure", "Luftdruck (hPa)",      "#f59e0b"),
]


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """
    Convert #RRGGBB / #RGB (hex) to rgba(r,g,b,a) accepted by Plotly.
    Returns original color if it can't be parsed.
    """
    c = hex_color.strip()
    if c.startswith("#"):
        c = c[1:]
    if len(c) == 3:  # #RGB -> #RRGGBB
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return hex_color

    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _apply_alpha_to_color(color: str, alpha: float) -> str:
    """
    Ensure the returned color is Plotly-compatible for scatter.fillcolor.
    - hex (#RRGGBB / #RGB) -> rgba(...)
    - rgb(...) -> rgba(..., alpha)
    - rgba(...) -> replace alpha
    - named CSS colors -> keep as-is (safe fallback; no alpha applied)
    """
    c = color.strip()

    if c.startswith("#"):
        return _hex_to_rgba(c, alpha)

    if c.startswith("rgba(") and c.endswith(")"):
        # replace existing alpha
        inside = c[len("rgba("):-1]
        parts = [p.strip() for p in inside.split(",")]
        if len(parts) == 4:
            return f"rgba({parts[0]},{parts[1]},{parts[2]},{alpha})"
        return c

    if c.startswith("rgb(") and c.endswith(")"):
        inside = c[len("rgb("):-1]
        parts = [p.strip() for p in inside.split(",")]
        if len(parts) == 3:
            return f"rgba({parts[0]},{parts[1]},{parts[2]},{alpha})"
        return c

    # named CSS colors (e.g. 'blue') -> keep as-is to avoid producing invalid strings
    return c


def _make_plotly_chart(df: pd.DataFrame, col: str, title: str, color: str) -> go.Figure:
    series = df[["measurement_date", col]].dropna()

    fillcolor = _apply_alpha_to_color(color, 0.08)

    fig = go.Figure(go.Scatter(
        x=series["measurement_date"],
        y=series[col],
        mode="lines",
        line=dict(color=color, width=1.8),
        name=title,
        # Rich hover tooltip: timestamp + value
        hovertemplate="<b>%{x|%Y-%m-%d %H:%M:%S}</b><br>%{y:.2f}<extra></extra>",
        fill="tozeroy",
        fillcolor=fillcolor,
    ))

    fig.update_layout(
        height=320,
        margin=dict(l=8, r=8, t=85, b=8),
        title=dict(
            text=title,
            y=0.97,
            font=dict(size=15, color="#374151"),
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        uirevision=col,          # preserves zoom/pan across data refreshes

        # X-axis: range slider + quick-select buttons
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor="#e5e7eb",
            rangeslider=dict(visible=True, thickness=0.06, bgcolor="#f3f4f6"),
            rangeselector=dict(
                buttons=[
                    dict(count=1,  label="1m",  step="minute", stepmode="backward"),
                    dict(count=5,  label="5m",  step="minute", stepmode="backward"),
                    dict(count=15, label="15m", step="minute", stepmode="backward"),
                    dict(count=1,  label="1h",  step="hour",   stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="#f9fafb",
                activecolor=color,
                font=dict(size=11),
                x=0, y=1.12,   # vorher 1.26
            ),
        ),

        # Y-axis: clean grid
        yaxis=dict(
            showgrid=True,
            gridcolor="#f3f4f6",
            showline=False,
            zeroline=False,
            tickfont=dict(size=11),
        ),

        # Crosshair cursor on hover
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=color),
    )

    # Spike lines (crosshair)
    fig.update_xaxes(showspikes=True, spikecolor="#9ca3af", spikethickness=1,
                     spikedash="dot", spikemode="across")
    fig.update_yaxes(showspikes=True, spikecolor="#9ca3af", spikethickness=1,
                     spikedash="dot")

    return fig


def _render_charts(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("Keine Daten für die gewählte Session gefunden.")
        return

    df = df.sort_values("measurement_date")

    c1, c2 = st.columns(2, gap="medium")
    c3, c4 = st.columns(2, gap="medium")

    for (col, title, color), container in zip(_CHART_DEFS, [c1, c2, c3, c4]):
        fig = _make_plotly_chart(df, col, title, color)
        container.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["autoScale2d", "lasso2d", "select2d"],
                "toImageButtonOptions": {"format": "png", "filename": col},
            },
            key=f"chart_{col}",
        )


# ---------------------------------------------------------------------------
# Manueller Eintrag sub-page
# ---------------------------------------------------------------------------

def _render_manueller_eintrag() -> None:
    st.subheader("Manueller Eintrag & Session-Verwaltung")

    session_ids = _get_unique_session_ids()
    if not session_ids:
        st.info("Keine Sessions in der Datenbank gefunden.")
        return

    # ── Section 1: Session umbenennen ────────────────────────────────────────
    with st.expander("Session umbenennen", expanded=True):
        st.markdown(
            "Benennt **alle Zeilen** der gewählten Session in der Tabelle "
            "`environmental_data` um (UPDATE auf `session_id`)."
        )

        col_a, col_b = st.columns(2)
        old_name = col_a.selectbox("Session auswählen", options=session_ids,
                                   key="rename_old_session")
        new_name = col_b.text_input("Neuer Name", key="rename_new_session",
                                    placeholder="z. B. rundgang_schlosspark_2026_05_19")

        if st.button("Umbenennen", key="btn_rename", type="primary"):
            new_name_stripped = new_name.strip()
            if not new_name_stripped:
                st.error("Bitte einen neuen Namen eingeben.")
            elif new_name_stripped == old_name:
                st.warning("Neuer Name ist identisch mit dem alten – keine Änderung.")
            elif new_name_stripped in session_ids:
                st.error(f"Session '{new_name_stripped}' existiert bereits.")
            else:
                try:
                    _execute(
                        "UPDATE environmental_data SET session_id = %s WHERE session_id = %s",
                        (new_name_stripped, old_name),
                    )
                    st.success(f"Session '{old_name}' wurde zu '{new_name_stripped}' umbenannt.")
                    # Clear caches so the dropdown & visualisation pick up the change
                    for k in ["cached_folium_map", "_map_geo_hash"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Fehler beim Umbenennen: {exc}")

    # ── Section 2: Datenpunkte manuell hinzufügen ────────────────────────────
    with st.expander("Datenpunkt manuell hinzufügen", expanded=False):
        st.markdown("Fügt einen einzelnen Messwert zur gewählten Session hinzu.")

        target_session = st.selectbox("Ziel-Session", options=session_ids,
                                      key="add_row_session")
        r1, r2 = st.columns(2)
        r3, r4 = st.columns(2)
        r5, r6 = st.columns(2)
        r7, _  = st.columns(2)

        mdate   = r1.date_input("Datum",         value=datetime.now(timezone.utc).date(), key="add_date")
        mtime   = r2.time_input("Uhrzeit (UTC)", value=datetime.now(timezone.utc).time(), key="add_time")
        alt     = r3.number_input("Altitude (m)",         value=0.0, step=0.1, key="add_alt")
        temp    = r4.number_input("Temperature (°C)",     value=20.0, step=0.1, key="add_temp")
        hum     = r5.number_input("Humidity (%)",         value=50.0, step=0.1,
                                  min_value=0.0, max_value=100.0, key="add_hum")
        baro    = r6.number_input("Barometric Pressure",  value=1013.25, step=0.01, key="add_baro")
        lat     = r7.number_input("Latitude",             value=0.0, step=0.000001,
                                  format="%.6f", key="add_lat")
        lon     = st.number_input("Longitude",            value=0.0, step=0.000001,
                                  format="%.6f", key="add_lon")

        if st.button("Hinzufügen", key="btn_add_row", type="primary"):
            ts = datetime.combine(mdate, mtime).replace(tzinfo=timezone.utc)
            try:
                _execute(
                    """
                    INSERT INTO environmental_data
                        (session_id, measurement_date, altitude, temperature,
                         humidity, barometric_pressure, latitude, longitude)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (target_session, ts.isoformat(), alt, temp, hum, baro, lat, lon),
                )
                st.success(f"Datenpunkt für {ts.strftime('%Y-%m-%d %H:%M:%S UTC')} hinzugefügt.")
            except Exception as exc:
                st.error(f"Fehler beim Einfügen: {exc}")

    # ── Section 3: Daten tabellarisch ansehen & bearbeiten ───────────────────
    with st.expander("Datenpunkte ansehen & bearbeiten", expanded=False):
        edit_session = st.selectbox("Session", options=session_ids, key="edit_view_session")
        df_edit = _fetch_full_session_for_edit(edit_session)

        if df_edit.empty:
            st.info("Keine Daten für diese Session.")
        else:
            st.caption(f"{len(df_edit)} Zeilen – Zellen direkt bearbeitbar. "
                       "Änderungen mit **Speichern** übernehmen.")

            edited = st.data_editor(
                df_edit,
                use_container_width=True,
                num_rows="dynamic",
                hide_index=True,
                key="data_editor_env",
                column_config={
                    "measurement_date": st.column_config.DatetimeColumn(
                        "Zeitstempel", format="YYYY-MM-DD HH:mm:ss"
                    ),
                    "altitude":            st.column_config.NumberColumn("Altitude (m)",        format="%.2f"),
                    "temperature":         st.column_config.NumberColumn("Temperatur (°C)",     format="%.2f"),
                    "humidity":            st.column_config.NumberColumn("Luftfeuchte (%)",     format="%.1f"),
                    "barometric_pressure": st.column_config.NumberColumn("Luftdruck",           format="%.2f"),
                    "latitude":            st.column_config.NumberColumn("Lat",                 format="%.6f"),
                    "longitude":           st.column_config.NumberColumn("Lon",                 format="%.6f"),
                },
            )

            if st.button("💾 Änderungen speichern", key="btn_save_edits", type="primary"):
                errors: list[str] = []
                # We use (session_id, measurement_date) as the natural PK.
                # Iterate over edited rows and UPDATE each one individually.
                for _, row in edited.iterrows():
                    try:
                        _execute(
                            """
                            UPDATE environmental_data
                            SET altitude=%s, temperature=%s, humidity=%s,
                                barometric_pressure=%s, latitude=%s, longitude=%s
                            WHERE session_id=%s AND measurement_date=%s
                            """,
                            (
                                float(row["altitude"]),
                                float(row["temperature"]),
                                float(row["humidity"]),
                                float(row["barometric_pressure"]),
                                float(row["latitude"]),
                                float(row["longitude"]),
                                edit_session,
                                row["measurement_date"],
                            ),
                        )
                    except Exception as exc:
                        errors.append(str(exc))

                if errors:
                    st.error(f"{len(errors)} Fehler beim Speichern:\n" + "\n".join(errors[:5]))
                else:
                    st.success("Alle Änderungen erfolgreich gespeichert.")
                    for k in ["cached_folium_map", "_map_geo_hash"]:
                        st.session_state.pop(k, None)

            # Download as CSV
            csv_bytes = df_edit.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Als CSV herunterladen",
                data=csv_bytes,
                file_name=f"{edit_session}.csv",
                mime="text/csv",
                key="btn_csv_download",
            )


# ---------------------------------------------------------------------------
# Main page entry point
# ---------------------------------------------------------------------------

def render_dashboard_page() -> None:
    st.title("Dashboard")

    sub = st.sidebar.radio(
        "Dashboard Unterkategorien",
        ["Visualisierung", "Manueller Eintrag"],
        index=0,
        key="dashboard_sub_radio",
    )

    if sub == "Manueller Eintrag":
        _render_manueller_eintrag()
        return

    # ── Visualisierung ────────────────────────────────────────────────────────
    st.subheader("Visualisierung")

    with st.sidebar.expander("Auto-Refresh", expanded=True):
        enabled = st.checkbox(
            "Auto-Refresh aktivieren",
            value=st.session_state.get("dashboard_autorefresh_enabled", True),
            key="dashboard_autorefresh_enabled",
        )
        interval_sec = st.number_input(
            "Intervall (Sekunden)",
            min_value=0.5, max_value=60.0,
            value=float(st.session_state.get("dashboard_autorefresh_interval_sec", 2.0)),
            step=0.5, format="%.1f",
            key="dashboard_autorefresh_interval_sec",
        )
        st.caption("Refresh betrifft: Dropdown, Map und Graphen.")

    st.sidebar.slider(
        "Points shown (Charts)",
        min_value=50, max_value=5000,
        value=int(st.session_state.get("dashboard_points_shown", 500)),
        step=50, key="dashboard_points_shown",
    )
    st.sidebar.checkbox(
        "Route anzeigen",
        value=bool(st.session_state.get("dashboard_show_route", True)),
        key="dashboard_show_route",
    )
    st.sidebar.slider(
        "Points shown (Map)",
        min_value=50, max_value=5000,
        value=int(st.session_state.get("dashboard_map_points_limit", 500)),
        step=50, key="dashboard_map_points_limit",
    )

    if enabled:
        st_autorefresh(
            interval=int(max(500, interval_sec * 1000)),
            key="dashboard_graph_autorefresh",
        )

    session_ids = _get_unique_session_ids()
    if not session_ids:
        st.info("Keine Daten in environmental_data gefunden.")
        st.stop()

    if "selected_session_id" not in st.session_state:
        st.session_state.selected_session_id = session_ids[0]
    elif st.session_state.selected_session_id not in session_ids:
        st.session_state.selected_session_id = session_ids[0]

    st.sidebar.selectbox(
        "Session auswählen",
        options=session_ids,
        index=session_ids.index(st.session_state.selected_session_id),
        key="selected_session_id",
    )

    selected_session_id = str(st.session_state.selected_session_id)

    df = _fetch_timeseries_for_session(
        session_id=selected_session_id,
        points_shown=int(st.session_state.dashboard_points_shown),
    )

    st.markdown("---")

    _render_map(
        df,
        show_route=bool(st.session_state.dashboard_show_route),
        map_points_limit=int(st.session_state.dashboard_map_points_limit),
    )

    st.markdown("### Messwerte")
    _render_charts(df)

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    st.caption(f"Letztes Update: {now_utc}")