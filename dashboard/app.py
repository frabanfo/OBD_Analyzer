"""
app.py
Dashboard live OBD2 — avvia con: python dashboard/app.py
Apri nel browser: http://localhost:8050
"""

import threading
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objects as go

from dashboard.data_buffer import DataBuffer
from dashboard.trip_summary import TripSummary, TRIPS_DIR
from dashboard.engine import estimate_power_cv
from dashboard.obd_thread import start_reader

# ---------------------------------------------------------------------------
# Stato globale
# ---------------------------------------------------------------------------
buffer     = DataBuffer()
trip       = TripSummary()
stop_event = threading.Event()

# Metriche disponibili nel grafico 1 (checklist)
# norm: trasforma il valore raw → scala display 0-100
METRICS = {
    "speed":        {"label": "Velocità (km/h)", "color": "#00b4d8",
                     "norm": lambda v: round((v or 0) / 1.6, 1)},   # 160 km/h → 100
    "throttle":     {"label": "Gas (%)",          "color": "#f77f00",
                     "norm": lambda v: round(v or 0, 1)},
    "braking":      {"label": "Freno (%)",        "color": "#e63946",
                     "norm": lambda v: round(min(100.0, abs(v or 0) * 12.5), 1)},  # |m/s²| → 0-100
    "engine_load":  {"label": "Carico (%)",       "color": "#a8dadc",
                     "norm": lambda v: round(v or 0, 1)},
    "coolant_temp": {"label": "T. liquido (°C)",  "color": "#457b9d",
                     "norm": lambda v: round((v or 0) / 1.1, 1)},   # 110°C → 100
}

DEFAULT_METRICS = ["throttle", "braking", "speed"]

def _kpi_card(title: str, elem_id: str, color: str) -> html.Div:
    return html.Div(
        style={"backgroundColor": "#161b22", "borderRadius": "8px",
               "padding": "16px 24px", "minWidth": "130px", "textAlign": "center"},
        children=[
            html.P(title, style={"color": "#8b949e", "margin": "0 0 4px 0",
                                 "fontSize": "11px", "textTransform": "uppercase"}),
            html.Div(id=elem_id,
                     style={"color": color, "fontSize": "36px", "fontWeight": "bold"}),
        ],
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
_NAV_TAB_STYLE = {
    "backgroundColor": "#161b22",
    "color": "#8b949e",
    "border": "none",
    "borderBottom": "2px solid transparent",
    "padding": "10px 28px",
    "fontFamily": "monospace",
    "fontSize": "13px",
    "cursor": "pointer",
}
_NAV_TAB_SELECTED = {
    **_NAV_TAB_STYLE,
    "color": "#e6edf3",
    "borderBottom": "2px solid #00b4d8",
    "backgroundColor": "#161b22",
}

app = dash.Dash(__name__, title="OBD Telemetry")
app.layout = html.Div(
    style={"backgroundColor": "#0d1117", "minHeight": "100vh",
           "fontFamily": "monospace"},
    children=[
        # ── Navbar ─────────────────────────────────────────────────────────
        html.Div(
            style={"backgroundColor": "#161b22", "borderBottom": "1px solid #21262d",
                   "display": "flex", "alignItems": "center", "gap": "0",
                   "padding": "0 20px", "marginBottom": "0"},
            children=[
                html.Span("OBD Telemetry",
                          style={"color": "#e6edf3", "fontWeight": "bold",
                                 "fontSize": "15px", "marginRight": "32px",
                                 "padding": "12px 0"}),
                dcc.Tabs(
                    id="nav-tabs",
                    value="live",
                    children=[
                        dcc.Tab(label="Live",          value="live",
                                style=_NAV_TAB_STYLE,  selected_style=_NAV_TAB_SELECTED),
                        dcc.Tab(label="I miei viaggi", value="trips",
                                style=_NAV_TAB_STYLE,  selected_style=_NAV_TAB_SELECTED),
                    ],
                    style={"border": "none", "height": "44px"},
                    colors={"border": "transparent", "primary": "#00b4d8",
                            "background": "#161b22"},
                ),
            ],
        ),

        # ── Pagina Live ─────────────────────────────────────────────────────
        html.Div(
            id="page-live",
            style={"padding": "20px"},
            children=[
                # Status
                html.Div(
                    style={"display": "flex", "justifyContent": "flex-end",
                           "marginBottom": "12px"},
                    children=[html.Div(id="conn-status",
                                       style={"fontSize": "14px", "color": "#8b949e"})],
                ),

                # KPI cards
                html.Div(
                    style={"display": "flex", "gap": "16px", "marginBottom": "20px"},
                    children=[
                        _kpi_card("RPM",      "kpi-rpm",       "#f0a500"),
                        _kpi_card("MARCIA",   "kpi-gear",      "#00b4d8"),
                        _kpi_card("VELOCITÀ", "kpi-speed-num", "#a8dadc"),
                    ],
                ),

                # Grafico 1: throttle / freno / metriche selezionabili
                html.Div(
                    style={"display": "flex", "gap": "16px", "marginBottom": "16px"},
                    children=[
                        html.Div(
                            style={"backgroundColor": "#161b22", "borderRadius": "8px",
                                   "padding": "16px", "minWidth": "170px"},
                            children=[
                                html.P("Grafico 1",
                                       style={"color": "#8b949e", "margin": "0 0 12px 0",
                                              "fontSize": "12px", "textTransform": "uppercase"}),
                                dcc.Checklist(
                                    id="metric-selector",
                                    options=[
                                        {"label": html.Span(
                                            m["label"],
                                            style={"color": m["color"], "paddingLeft": "6px"}
                                        ), "value": k}
                                        for k, m in METRICS.items()
                                    ],
                                    value=DEFAULT_METRICS,
                                    style={"display": "flex", "flexDirection": "column", "gap": "10px"},
                                    inputStyle={"cursor": "pointer"},
                                ),
                            ],
                        ),
                        html.Div(
                            style={"flex": 1},
                            children=[dcc.Graph(id="main-chart",
                                                config={"displayModeBar": False},
                                                style={"height": "320px"})],
                        ),
                    ],
                ),

                # Grafico 2: Speed + RPM + Potenza stimata (fisso)
                html.Div(
                    style={"backgroundColor": "#161b22", "borderRadius": "8px",
                           "padding": "8px", "marginBottom": "16px"},
                    children=[
                        html.P("RPM · Velocità · Potenza stimata",
                               style={"color": "#8b949e", "margin": "4px 8px 0 8px",
                                      "fontSize": "11px", "textTransform": "uppercase"}),
                        dcc.Graph(id="power-chart",
                                  config={"displayModeBar": False},
                                  style={"height": "280px"}),
                    ],
                ),

                # Summary viaggio
                html.Div(
                    style={"backgroundColor": "#161b22", "borderRadius": "8px",
                           "padding": "16px", "marginBottom": "8px"},
                    children=[
                        html.Div(
                            style={"display": "flex", "justifyContent": "space-between",
                                   "alignItems": "center", "marginBottom": "12px"},
                            children=[
                                html.P("Riepilogo viaggio",
                                       style={"color": "#8b949e", "margin": 0,
                                              "fontSize": "12px", "textTransform": "uppercase"}),
                                html.Div(
                                    style={"display": "flex", "alignItems": "center", "gap": "8px"},
                                    children=[
                                        html.Span("€/L:", style={"color": "#8b949e", "fontSize": "13px"}),
                                        dcc.Input(id="fuel-price", type="number", value=1.87,
                                                  min=0.5, max=5.0, step=0.01,
                                                  style={"width": "70px", "backgroundColor": "#0d1117",
                                                         "color": "#e6edf3", "border": "1px solid #30363d",
                                                         "borderRadius": "4px", "padding": "4px 8px",
                                                         "fontFamily": "monospace"}),
                                        html.Button("Salva", id="save-trip", n_clicks=0,
                                                    style={"backgroundColor": "#1f6feb",
                                                           "color": "#e6edf3", "border": "none",
                                                           "borderRadius": "4px", "padding": "4px 12px",
                                                           "cursor": "pointer", "fontFamily": "monospace",
                                                           "fontSize": "12px"}),
                                        html.Button("Reset", id="reset-trip", n_clicks=0,
                                                    style={"backgroundColor": "#21262d",
                                                           "color": "#8b949e", "border": "1px solid #30363d",
                                                           "borderRadius": "4px", "padding": "4px 12px",
                                                           "cursor": "pointer", "fontFamily": "monospace",
                                                           "fontSize": "12px"}),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            id="trip-summary",
                            style={"display": "flex", "gap": "20px", "flexWrap": "wrap"},
                        ),
                        html.Div(id="save-feedback",
                                 style={"marginTop": "8px", "fontSize": "12px",
                                        "color": "#3fb950", "minHeight": "18px"}),
                    ],
                ),
            ],
        ),

        # ── Pagina I miei viaggi ─────────────────────────────────────────
        html.Div(
            id="page-trips",
            style={"display": "none", "padding": "20px"},
            children=[
                html.Div(
                    style={"display": "flex", "justifyContent": "space-between",
                           "alignItems": "center", "marginBottom": "24px"},
                    children=[
                        html.H3("I miei viaggi",
                                style={"color": "#e6edf3", "margin": 0}),
                        html.Span(id="trips-count",
                                  style={"color": "#8b949e", "fontSize": "13px"}),
                    ],
                ),
                html.Div(id="trips-list",
                         style={"display": "flex", "flexWrap": "wrap", "gap": "16px"}),
            ],
        ),

        dcc.Interval(id="interval", interval=int(config.SCAN_INTERVAL * 1000)),
    ],
)


# ---------------------------------------------------------------------------
# Callbacks — navigazione tab
# ---------------------------------------------------------------------------
@callback(
    Output("page-live",    "style"),
    Output("page-trips",   "style"),
    Output("trips-list",   "children"),
    Output("trips-count",  "children"),
    Input("nav-tabs",      "value"),
)
def switch_tab(tab):
    live_style  = {"padding": "20px"}
    trips_style = {"display": "none", "padding": "20px"}

    if tab == "trips":
        live_style  = {"display": "none", "padding": "20px"}
        trips_style = {"padding": "20px"}
        cards, count = _load_trips_page()
        return live_style, trips_style, cards, count

    return live_style, trips_style, [], ""


# ---------------------------------------------------------------------------
# Callbacks — live
# ---------------------------------------------------------------------------
@callback(
    Output("main-chart",    "figure"),
    Output("power-chart",   "figure"),
    Output("kpi-rpm",       "children"),
    Output("kpi-gear",      "children"),
    Output("kpi-speed-num", "children"),
    Output("conn-status",   "children"),
    Output("conn-status",   "style"),
    Output("trip-summary",  "children"),
    Input("interval",        "n_intervals"),
    Input("metric-selector", "value"),
    State("fuel-price",      "value"),
)
def update(_n, selected_metrics, fuel_price):
    records = buffer.get_all()

    mode_label = "MOCK" if config.MOCK_MODE else "OBD"
    if records:
        conn_text  = f"● {mode_label} · {len(records)} campioni"
        conn_style = {"fontSize": "13px", "color": "#3fb950"}
    else:
        conn_text  = f"○ {mode_label} · In attesa di dati..."
        conn_style = {"fontSize": "13px", "color": "#f85149"}

    latest    = records[-1] if records else {}
    rpm_val   = latest.get("rpm")
    gear_val  = latest.get("gear")
    speed_val = latest.get("speed")

    rpm_str   = f"{rpm_val:,.0f}"  if rpm_val   is not None else "—"
    gear_str  = str(gear_val)      if gear_val  is not None else "—"
    speed_str = f"{speed_val:.0f}" if speed_val is not None else "—"

    fig1    = _build_main_chart(records, selected_metrics or [])
    fig2    = _build_power_chart(records)
    summary = _build_summary(fuel_price)

    return fig1, fig2, rpm_str, gear_str, speed_str, conn_text, conn_style, summary


@callback(
    Output("save-feedback", "children"),
    Output("save-trip",     "style"),
    Input("save-trip",      "n_clicks"),
    State("fuel-price",     "value"),
    prevent_initial_call=True,
)
def save_trip_cb(n, fuel_price):
    saved = trip.save_trip(float(fuel_price or 1.87))
    if saved:
        msg   = "✓ Viaggio salvato"
        color = "#3fb950"
    else:
        msg   = "Nessun dato sufficiente da salvare (< 0.1 km)"
        color = "#f85149"
    btn_style = {"backgroundColor": "#1f6feb", "color": "#e6edf3", "border": "none",
                 "borderRadius": "4px", "padding": "4px 12px", "cursor": "pointer",
                 "fontFamily": "monospace", "fontSize": "12px"}
    return html.Span(msg, style={"color": color}), btn_style


@callback(
    Output("reset-trip", "style"),
    Input("reset-trip", "n_clicks"),
)
def reset_trip(n):
    if n:
        trip.reset()
    return {"backgroundColor": "#21262d", "color": "#8b949e",
            "border": "1px solid #30363d", "borderRadius": "4px",
            "padding": "4px 12px", "cursor": "pointer",
            "fontFamily": "monospace", "fontSize": "12px"}


# ---------------------------------------------------------------------------
# Pagina I miei viaggi — costruzione
# ---------------------------------------------------------------------------
def _load_trips_page():
    """Legge tutti i JSON da data/trips/ e restituisce (cards, count_str)."""
    if not os.path.isdir(TRIPS_DIR):
        return [html.P("Nessun viaggio salvato.",
                       style={"color": "#8b949e"})], ""

    files = sorted(
        [f for f in os.listdir(TRIPS_DIR) if f.endswith(".json")],
        reverse=True,
    )

    if not files:
        return [html.P("Nessun viaggio salvato.",
                       style={"color": "#8b949e"})], ""

    cards = [_trip_card(f) for f in files]
    count = f"{len(files)} viaggio{'i' if len(files) != 1 else ''}"
    return cards, count


def _trip_card(filename: str) -> html.Div:
    fpath = os.path.join(TRIPS_DIR, filename)
    try:
        with open(fpath, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        return html.Div()

    # Formatta data
    try:
        dt = datetime.fromisoformat(d.get("started_at", ""))
        date_str = dt.strftime("%d %b %Y")
        time_str = dt.strftime("%H:%M")
    except Exception:
        date_str = filename[:10]
        time_str = ""

    mins = d.get("elapsed_s", 0) // 60
    secs = d.get("elapsed_s", 0) % 60

    def _val(v, suffix=""):
        return html.Span(f"{v}{suffix}", style={"color": "#e6edf3", "fontWeight": "bold"})

    def _row(label, value_el):
        return html.Div(
            style={"display": "flex", "justifyContent": "space-between",
                   "borderBottom": "1px solid #21262d", "padding": "6px 0"},
            children=[
                html.Span(label, style={"color": "#8b949e", "fontSize": "12px"}),
                value_el,
            ],
        )

    fuel_price = d.get("fuel_price", 1.87)
    cost       = d.get("cost") or round(d.get("fuel_L", 0) * fuel_price, 2)

    return html.Div(
        style={
            "backgroundColor": "#161b22",
            "borderRadius": "10px",
            "padding": "18px 20px",
            "width": "280px",
            "border": "1px solid #21262d",
            "fontFamily": "monospace",
        },
        children=[
            # Header card
            html.Div(
                style={"marginBottom": "12px"},
                children=[
                    html.Div(date_str, style={"color": "#e6edf3", "fontSize": "15px",
                                              "fontWeight": "bold"}),
                    html.Div(time_str, style={"color": "#8b949e", "fontSize": "12px"}),
                ],
            ),
            # Statistiche
            _row("Distanza",    _val(f"{d.get('distance_km', 0):.1f}", " km")),
            _row("Durata",      _val(f"{mins:02d}:{secs:02d}")),
            _row("Vel. media",  _val(f"{d.get('avg_speed', 0):.0f}", " km/h")),
            _row("Vel. massima",_val(f"{d.get('max_speed', 0):.0f}", " km/h")),
            _row("RPM medio",   _val(f"{d.get('avg_rpm', 0)}")),
            _row("Consumo",     _val(f"{d.get('l_100km', 0):.1f}", " L/100km")),
            _row("Carburante",  _val(f"{d.get('fuel_L', 0):.2f}", " L")),
            html.Div(
                style={"display": "flex", "justifyContent": "space-between",
                       "padding": "8px 0 0 0", "marginTop": "4px"},
                children=[
                    html.Span("Costo stimato", style={"color": "#8b949e", "fontSize": "12px"}),
                    html.Span(f"€ {cost:.2f}",
                              style={"color": "#f0a500", "fontWeight": "bold", "fontSize": "16px"}),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Grafico 1 — metriche selezionabili, scala 0-100
# ---------------------------------------------------------------------------
def _build_main_chart(records: list, selected: list) -> go.Figure:
    active = [k for k in selected if k in METRICS]

    if not records or not active:
        return _empty_fig("In attesa di dati..." if not records else "Seleziona una metrica")

    window = records[-min(len(records), config.GRAPH_WINDOW):]
    xs = [r["timestamp"] for r in window]
    fig = go.Figure()

    for key in active:
        meta = METRICS[key]
        ys = [meta["norm"](r.get(key)) for r in window]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, name=meta["label"],
            line={"color": meta["color"], "width": 2}, mode="lines",
        ))

    fig.update_layout(
        **_base_layout(margin_r=20),
        yaxis=dict(range=[0, 105], gridcolor="#21262d", showgrid=True, ticksuffix="%"),
        xaxis={"gridcolor": "#21262d", "showgrid": True},
    )
    return fig


# ---------------------------------------------------------------------------
# Grafico 2 — Speed + RPM + Potenza stimata
# ---------------------------------------------------------------------------
def _build_power_chart(records: list) -> go.Figure:
    if not records:
        return _empty_fig("In attesa di dati...")

    window = records[-min(len(records), config.GRAPH_WINDOW):]
    xs     = [r["timestamp"]        for r in window]
    speeds = [r.get("speed") or 0   for r in window]
    rpms   = [r.get("rpm")   or 0   for r in window]
    maps   = [r.get("intake_pressure") for r in window]
    temps  = [r.get("intake_temp")     for r in window]

    powers = [estimate_power_cv(rpm, m, t)
              for rpm, m, t in zip(rpms, maps, temps)]

    max_cv = config.ENGINE_MAX_CV

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=xs, y=speeds, name="Velocità (km/h)",
        line={"color": "#00b4d8", "width": 2}, mode="lines",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=powers, name="Potenza (CV)",
        line={"color": "#57cc99", "width": 2}, mode="lines",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=rpms, name="RPM",
        line={"color": "#f0a500", "width": 2}, mode="lines",
        yaxis="y2",
    ))

    fig.update_layout(
        **_base_layout(margin_r=60),
        yaxis=dict(
            range=[0, max(165, max_cv * 1.1)],
            gridcolor="#21262d", showgrid=True,
        ),
        yaxis2=dict(
            overlaying="y", side="right",
            range=[0, 7000], showgrid=False,
            tickformat=".0f", title="RPM",
            title_font={"color": "#f0a500"},
            tickfont={"color": "#f0a500"},
        ),
        xaxis={"gridcolor": "#21262d", "showgrid": True},
    )
    return fig


# ---------------------------------------------------------------------------
# Summary viaggio
# ---------------------------------------------------------------------------
def _build_summary(fuel_price) -> list:
    stats = trip.get_stats()
    price = float(fuel_price or 1.87)

    cost  = round(stats["fuel_L"] * price, 2)
    mins  = stats["elapsed_s"] // 60
    secs  = stats["elapsed_s"] %  60
    state_color = "#3fb950" if stats["state"] == "driving" else "#8b949e"

    def _stat(label, value, color="#e6edf3"):
        return html.Div(
            style={"textAlign": "center", "minWidth": "90px"},
            children=[
                html.Div(value,
                         style={"color": color, "fontSize": "22px", "fontWeight": "bold"}),
                html.Div(label,
                         style={"color": "#8b949e", "fontSize": "10px",
                                "textTransform": "uppercase", "marginTop": "2px"}),
            ],
        )

    return [
        _stat("Stato",       stats["state"].upper(), state_color),
        _stat("Durata",      f"{mins:02d}:{secs:02d}"),
        _stat("Distanza",    f"{stats['distance_km']:.1f} km"),
        _stat("Vel. media",  f"{stats['avg_speed']:.0f} km/h"),
        _stat("Vel. max",    f"{stats['max_speed']:.0f} km/h"),
        _stat("RPM medio",   f"{stats['avg_rpm']}"),
        _stat("Consumo",     f"{stats['l_100km']:.1f} L/100"),
        _stat("Carburante",  f"{stats['fuel_L']:.2f} L"),
        _stat("Costo est.",  f"€ {cost:.2f}", "#f0a500"),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _base_layout(margin_r: int = 20) -> dict:
    return dict(
        paper_bgcolor="#161b22",
        plot_bgcolor="#0d1117",
        font={"color": "#e6edf3", "family": "monospace", "size": 11},
        legend={"bgcolor": "#0d1117", "bordercolor": "#21262d", "borderwidth": 1,
                "orientation": "h", "y": 1.08},
        margin={"l": 50, "r": margin_r, "t": 30, "b": 40},
    )


def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **_base_layout(),
        annotations=[{"text": msg, "showarrow": False,
                      "font": {"size": 14, "color": "#8b949e"},
                      "xref": "paper", "yref": "paper", "x": 0.5, "y": 0.5}],
    )
    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mode = "MOCK" if config.MOCK_MODE else "OBD REALE"
    print(f"[OBD Dashboard] Modalità: {mode}")
    print(f"[OBD Dashboard] Apri nel browser: http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")

    reader_thread = start_reader(buffer, trip, stop_event)

    try:
        app.run(
            host=config.DASHBOARD_HOST,
            port=config.DASHBOARD_PORT,
            debug=False,
        )
    finally:
        stop_event.set()
        reader_thread.join(timeout=3)
