"""
theme_css.py — Command Centre styling for the Cafe Manager Streamlit app.

Rewritten for Streamlit 1.63: targets the current data-testid hooks
(stBaseButton-*, stSidebarUserContent, stElementContainer) rather than the
legacy .stButton classes, which no longer exist and were why the sidebar nav
stayed centred with large gaps.

Usage — call once, anywhere after st.set_page_config(...):

    from theme_css import inject_theme
    inject_theme()

Pair with .streamlit/config.toml for palette, Nunito and radii.
"""

import streamlit as st

N100, N200, N300 = "#f9f4ed", "#eee7db", "#dcd3c4"
N400, N500, N600 = "#c0b6a5", "#a29884", "#82796a"
N700, N800, N900 = "#645c50", "#474238", "#2e2b25"
INK = "#201e1d"
ACCENT, ACCENT_100, ACCENT_700 = "#c67139", "#fff2eb", "#8c491a"

_CSS = f"""
<style>
/* ── type ──────────────────────────────────────────────── */
h1, h2, h3, h4, h5 {{
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-weight: 700 !important; letter-spacing: -0.015em !important;
  line-height: 1.12 !important;
}}
h1 {{ font-size: 2.05rem !important; margin: 0 0 0.6rem !important; padding: 0 !important; }}
h2 {{ font-size: 1.45rem !important; margin: 0.2rem 0 0.4rem !important; }}
h3 {{ font-size: 1.15rem !important; margin: 0.2rem 0 0.3rem !important; }}

/* ── density: pull the page in, close the vertical gaps ── */
.block-container {{
  padding: 1.5rem 2rem 4rem !important; max-width: 1180px !important;
}}
[data-testid="stVerticalBlock"] {{ gap: 0.6rem !important; }}
[data-testid="stHorizontalBlock"] {{ gap: 0.7rem !important; }}
[data-testid="stElementContainer"]:empty {{ display: none !important; }}
hr {{ margin: 0.8rem 0 !important; border-color: {N300} !important; }}

/* ══ SIDEBAR ═══════════════════════════════════════════════
   The nav items are tertiary buttons at width="stretch". Streamlit
   centres those by default and spaces them generously — both undone
   here, and the active page (a disabled button) gets the solid pill. */
[data-testid="stSidebar"] {{
  background: {N100} !important; border-right: 0 !important;
}}
[data-testid="stSidebarUserContent"] {{
  padding: 1.1rem 0.9rem 1.5rem !important;
}}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{
  gap: 0.1rem !important;
}}
[data-testid="stSidebar"] h5 {{
  font-size: 1rem !important; margin: 0 0 0.1rem 0.5rem !important;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  font-size: 0.68rem !important; letter-spacing: 0.08em !important;
  text-transform: uppercase !important; color: {N600} !important;
  margin: 0 0 0.5rem 0.55rem !important;
}}

/* every sidebar button: flat, left-aligned, pill, tight */
[data-testid="stSidebar"] button {{
  width: 100% !important;
  justify-content: flex-start !important;
  text-align: left !important;
  gap: 0.6rem !important;
  padding: 0.42rem 0.75rem !important;
  min-height: 0 !important;
  border: 0 !important; border-radius: 999px !important;
  background: transparent !important;
  color: {INK} !important;
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-size: 0.9rem !important; font-weight: 500 !important;
  line-height: 1.25 !important;
  box-shadow: none !important;
}}
[data-testid="stSidebar"] button p {{
  font-size: 0.9rem !important; font-weight: 500 !important;
  text-align: left !important; margin: 0 !important;
}}
[data-testid="stSidebar"] button [data-testid="stIconMaterial"],
[data-testid="stSidebar"] button span[class*="material"] {{
  font-size: 1.05rem !important; color: {N600} !important;
}}
[data-testid="stSidebar"] button:hover {{ background: {N200} !important; }}
[data-testid="stSidebar"] button:active {{ background: {N300} !important; }}

/* active page — Streamlit renders disabled buttons at low opacity; override */
[data-testid="stSidebar"] button:disabled {{
  background: {N800} !important; opacity: 1 !important; cursor: default !important;
}}
[data-testid="stSidebar"] button:disabled p,
[data-testid="stSidebar"] button:disabled span,
[data-testid="stSidebar"] button:disabled [data-testid="stIconMaterial"] {{
  color: {N100} !important; font-weight: 700 !important;
}}

[data-testid="stSidebar"] hr {{ margin: 0.7rem 0 !important; }}

/* ══ MAIN BUTTONS ══════════════════════════════════════════ */
[data-testid="stMainBlockContainer"] button {{
  border-radius: 999px !important;
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-weight: 600 !important; font-size: 0.92rem !important;
  padding: 0.45rem 1.25rem !important;
  min-height: 0 !important;
  transition: background 120ms ease !important;
}}
[data-testid="stBaseButton-primary"] {{
  background: {ACCENT} !important; border: 0 !important; color: #fff !important;
}}
[data-testid="stBaseButton-primary"]:hover {{ background: #b2622d !important; }}
[data-testid="stBaseButton-primary"]:active {{ background: {ACCENT_700} !important; }}
[data-testid="stBaseButton-secondary"] {{
  background: transparent !important; border: 1px solid {N300} !important; color: {INK} !important;
}}
[data-testid="stBaseButton-secondary"]:hover {{
  background: {N200} !important; border-color: {N400} !important;
}}

/* ── inputs ────────────────────────────────────────────────── */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input {{
  background: {N200} !important; border-color: {N300} !important;
  border-radius: 999px !important; font-size: 0.92rem !important;
}}
[data-baseweb="input"], [data-baseweb="select"] > div {{
  background: {N200} !important; border-color: {N300} !important;
  border-radius: 999px !important;
}}
[data-testid="stTextArea"] textarea {{
  background: {N200} !important; border-color: {N300} !important;
  border-radius: 16px !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  border-color: {ACCENT} !important;
}}
label p {{ font-size: 0.8rem !important; color: {N700} !important; }}

/* ── tabs ──────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {{ gap: 0.3rem !important; border-bottom: 1px solid {N300} !important; }}
[data-baseweb="tab"] {{
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-weight: 600 !important; font-size: 0.92rem !important;
}}
[data-baseweb="tab-highlight"] {{ background: {ACCENT} !important; height: 2.5px !important; }}

/* ── cards ─────────────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
  border-radius: 20px !important;
}}
[data-testid="stExpander"] details {{
  background: {N200} !important; border: 0 !important;
  border-radius: 20px !important; overflow: hidden !important;
}}
[data-testid="stExpander"] summary {{ font-weight: 600 !important; }}
[data-testid="stMetric"] {{
  background: {N200} !important; border-radius: 20px !important;
  padding: 0.7rem 1rem !important;
}}

/* ── tables ────────────────────────────────────────────────── */
[data-testid="stDataFrame"], [data-testid="stTable"] {{
  border-radius: 16px !important; overflow: hidden !important;
  border: 1px solid {N300} !important;
}}
[data-testid="stTable"] thead th {{
  background: {N200} !important; color: {N700} !important;
  font-size: 0.7rem !important; letter-spacing: 0.07em !important;
  text-transform: uppercase !important; font-weight: 700 !important;
}}
[data-testid="stTable"] tbody td {{ font-size: 0.9rem !important; }}

/* ── checkboxes: round, ink fill ───────────────────────────── */
[data-testid="stCheckbox"] label span[aria-checked] {{
  border-radius: 999px !important; border: 2px solid {N400} !important;
}}
[data-testid="stCheckbox"] label span[aria-checked="true"] {{
  background: {N800} !important; border-color: {N800} !important;
}}

/* ── alerts, chrome ────────────────────────────────────────── */
[data-testid="stAlert"] {{ border-radius: 16px !important; border: 0 !important; }}
[data-testid="stNotification"] {{ border-radius: 16px !important; }}
#MainMenu, footer, [data-testid="stDecoration"] {{ display: none !important; }}
::selection {{ background: rgba(198,113,57,0.28) !important; }}
:focus-visible {{ outline: 2px solid {ACCENT} !important; outline-offset: 2px !important; }}
</style>
"""


def inject_theme() -> None:
    """Inject the Command Centre CSS. Call once per script run."""
    st.markdown(_CSS, unsafe_allow_html=True)


def tag(label: str, tone: str = "neutral") -> str:
    """A pill span for st.markdown(..., unsafe_allow_html=True).

    tone: "neutral" (default) or "alert" — alert is the only terracotta.
    """
    bg, fg = (ACCENT_100, ACCENT_700) if tone == "alert" else (N200, N800)
    return (
        f'<span style="display:inline-flex;align-items:center;font-size:0.72rem;'
        f'padding:3px 10px;border-radius:999px;background:{bg};color:{fg};'
        f'white-space:nowrap">{label}</span>'
    )
