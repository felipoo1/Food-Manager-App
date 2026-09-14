"""
theme_css.py — drop-in styling for the Cafe Manager Streamlit app.

Gets the app the rest of the way to the TPC Command Centre design: pill
sidebar nav with a solid active state, pill buttons, rounded inputs, card
surfaces, themed dataframes, round tick-boxes and tighter density.

Usage — call it once, anywhere after st.set_page_config(...) in app.py.
Every rule is !important, so it wins regardless of where it runs or what
other st.markdown("<style>") blocks the app injects:

    from theme_css import inject_theme
    inject_theme()

Pair it with the matching .streamlit/config.toml (colours, Nunito, radii).
Streamlit's internal data-testid hooks can change between releases; if a rule
stops biting after an upgrade, that selector is the thing to re-check.
"""

import streamlit as st

# Tokens — keep these in step with .streamlit/config.toml
N100, N200, N300 = "#f9f4ed", "#eee7db", "#dcd3c4"
N400, N600, N700, N800, N900 = "#c0b6a5", "#82796a", "#645c50", "#474238", "#2e2b25"
INK = "#201e1d"
ACCENT, ACCENT_100, ACCENT_700 = "#c67139", "#fff2eb", "#8c491a"

_CSS = f"""
<style>
/* ── type ─────────────────────────────────────────────── */
html, body, [class*="css"] {{ font-family: 'Nunito', system-ui, sans-serif !important; }}
h1, h2, h3, h4 {{
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-weight: 700 !important; letter-spacing: -0.01em !important; line-height: 1.15 !important;
}}
h1 {{ font-size: 2.1rem !important; margin-bottom: 0.15rem !important; }}
h2 {{ font-size: 1.5rem !important; }}
h3 {{ font-size: 1.2rem !important; }}

/* ── density: tighter page gutters, less vertical air ─── */
.block-container {{ padding: 1.6rem 1.8rem 4rem !important; max-width: 1180px !important; }}
[data-testid="stVerticalBlock"] {{ gap: 0.65rem !important; }}
[data-testid="stHorizontalBlock"] {{ gap: 0.6rem !important; }}
hr {{ margin: 0.9rem 0 !important; border-color: {N300}; }}

/* ── sidebar nav: flat pills, solid active state ───────── */
[data-testid="stSidebar"] {{
  border-right: 0 !important;
  background: {N100} !important;
}}
[data-testid="stSidebar"] * {{ color: {INK}; }}
[data-testid="stSidebar"] .stMarkdown p {{ color: {INK} !important; }}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 1.1rem !important; }}
[data-testid="stSidebar"] .stButton > button {{
  width: 100% !important; justify-content: flex-start !important; text-align: left !important;
  padding: 0.5rem 0.85rem !important; border: 0 !important; border-radius: 999px !important;
  background: transparent !important; color: {INK}; font-weight: 400 !important; font-size: 0.92rem !important;
  box-shadow: none !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{ background: {N200}; color: {INK}; }}
[data-testid="stSidebar"] .stButton > button:active {{ background: {N300}; }}
/* the active page: render it as a disabled button, or wrap it in a div with
   class "nav-active" — both pick up the solid pill below */
[data-testid="stSidebar"] .stButton > button:disabled,
[data-testid="stSidebar"] .nav-active .stButton > button {{
  background: {N800} !important; color: {N100} !important;
  font-weight: 700 !important; opacity: 1 !important;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  font-size: 0.62rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important;
  color: {N600}; margin: 0.7rem 0 0.2rem 0.85rem !important;
}}

/* ── buttons ───────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 999px !important; font-weight: 600 !important; font-size: 0.92rem !important;
  padding: 0.45rem 1.1rem !important; transition: background 120ms ease, border-color 120ms ease !important;
}}
button[kind="primary"] {{ background: {ACCENT}; border-color: {ACCENT}; color: {N100}; }}
button[kind="primary"]:hover {{ background: #b2622d !important; border-color: #b2622d !important; }}
button[kind="primary"]:active {{ background: {ACCENT_700}; }}
button[kind="secondary"] {{ background: transparent !important; border: 1px solid {N300}; color: {INK}; }}
button[kind="secondary"]:hover {{ background: {N200}; border-color: {N400}; }}
button[kind="tertiary"] {{ color: {ACCENT_700}; }}

/* ── inputs ────────────────────────────────────────────── */
.stTextInput input, .stNumberInput input, .stDateInput input,
[data-baseweb="select"] > div, .stTextArea textarea {{
  background: {N200} !important; border-color: {N300} !important;
  border-radius: 999px !important; font-size: 0.92rem !important;
}}
.stTextArea textarea {{ border-radius: 16px !important; }}
.stTextInput input:focus, .stNumberInput input:focus {{ border-color: {ACCENT} !important; }}
label, .stTextInput label p, .stNumberInput label p {{
  font-size: 0.78rem !important; color: {N700} !important;
}}
:focus-visible {{ outline: 2px solid {ACCENT}; outline-offset: 2px !important; }}

/* ── cards: st.container(border=True) and expanders ────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: {N200}; border: 0 !important; border-radius: 20px !important;
  padding: 0.9rem 1rem !important;
}}
[data-testid="stExpander"] {{
  background: {N200}; border: 0 !important; border-radius: 20px !important; overflow: hidden !important;
}}
[data-testid="stExpander"] summary {{ font-weight: 600 !important; }}
[data-testid="stMetric"] {{
  background: {N200}; border-radius: 20px !important; padding: 0.7rem 0.95rem !important;
}}
[data-testid="stMetricValue"] {{ font-weight: 700 !important; }}

/* ── tables & dataframes ───────────────────────────────── */
[data-testid="stDataFrame"], [data-testid="stTable"] {{
  border-radius: 18px !important; overflow: hidden !important; border: 1px solid {N300};
}}
[data-testid="stTable"] thead th {{
  background: {N200}; color: {N700};
  font-size: 0.68rem !important; letter-spacing: 0.08em !important; text-transform: uppercase !important;
  font-weight: 700 !important; border-bottom: 1px solid {N300};
}}
[data-testid="stTable"] tbody td {{
  border-bottom: 1px solid rgba(32,30,29,0.08) !important; font-size: 0.9rem !important;
}}
[data-testid="stTable"] tbody tr:hover td {{ background: rgba(32,30,29,0.04) !important; }}

/* ── task tick-boxes: round, ink fill when checked ─────── */
[data-testid="stCheckbox"] label {{ align-items: flex-start !important; gap: 0.6rem !important; }}
[data-testid="stCheckbox"] label > span:first-child {{
  width: 21px !important; height: 21px !important; border-radius: 999px !important;
  border: 2px solid {N400}; background: transparent !important;
}}
[data-testid="stCheckbox"] input:checked + span,
[data-testid="stCheckbox"] label > span[aria-checked="true"] {{
  background: {N800} !important; border-color: {N800} !important;
}}
[data-testid="stCheckbox"] label p {{ font-size: 0.9rem !important; line-height: 1.3 !important; }}

/* ── alerts: terracotta only where it means something ──── */
[data-testid="stAlert"] {{ border-radius: 18px !important; border: 0 !important; }}
[data-testid="stNotification"] {{ border-radius: 18px !important; }}

/* ── chrome ────────────────────────────────────────────── */
#MainMenu, footer {{ visibility: hidden !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}
::selection {{ background: rgba(198,113,57,0.3) !important; }}
</style>
"""


def inject_theme() -> None:
    """Inject the Command Centre CSS. Call once per script run."""
    st.markdown(_CSS, unsafe_allow_html=True)


def tag(label: str, tone: str = "neutral") -> str:
    """Return a pill span, for use inside st.markdown(..., unsafe_allow_html=True).

    tone: "neutral" (default) or "alert" — alert is the only terracotta.
    """
    bg, fg = (ACCENT_100, ACCENT_700) if tone == "alert" else (N200, N800)
    return (
        f'<span style="display:inline-flex;align-items:center;font-size:0.72rem;'
        f'padding:3px 10px;border-radius:999px;background:{bg};color:{fg};'
        f'white-space:nowrap">{label}</span>'
    )
