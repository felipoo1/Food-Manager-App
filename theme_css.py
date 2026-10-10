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
CARD = "#e7ddcb"        # day / ingredient card fill — deliberately a step
CARD_INNER = "#fbf7f1"  # darker than N200 so it reads on the cream page
N700, N800, N900 = "#645c50", "#474238", "#2e2b25"
INK = "#201e1d"
ACCENT, ACCENT_100, ACCENT_700 = "#c67139", "#fff2eb", "#8c491a"
ACCENT_300 = "#eab48d"
SAGE, SAGE_100, SAGE_200, SAGE_800, SAGE_900 = "#7a8a5e", "#e9ede1", "#d5ddc6", "#4b5636", "#3f4a2c"
NEW_TODO_BORDER = ACCENT_300

_CSS = f"""
<style>
/* ── type ──────────────────────────────────────────────── */
h1, h2, h3, h4, h5 {{
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-weight: 700 !important; letter-spacing: -0.015em !important;
  /* 1.12 clipped the descenders on "Weekly task workspace" */
  line-height: 1.25 !important;
}}
h1 {{
  font-size: 2.05rem !important; margin: 0 0 0.6rem !important;
  padding: 0 0 0.05em !important; overflow: visible !important;
}}
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

/* body copy: Streamlit's default runs larger than the mock */
[data-testid="stMainBlockContainer"] [data-testid="stMarkdown"] p {{
  font-size: 0.92rem !important; line-height: 1.45 !important;
}}
[data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"] p {{
  font-size: 0.83rem !important; color: {N700} !important;
}}
[data-testid="stMainBlockContainer"] h3 {{ font-size: 1.05rem !important; }}

/* Day / ingredient cards. Set on the wrapper only — the earlier attempt
   also painted "> div" chains, which caught inner content and washed the
   two tones back together. */
[data-testid="stMainBlockContainer"] div[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMainBlockContainer"] div.stVerticalBlockBorderWrapper {{
  background: {CARD} !important;
  border: 1px solid #d7cab1 !important;
  border-radius: 18px !important;
}}
/* Keyed containers — st.container(key=...) emits a stable .st-key-<key>
   class. Layout (grids) and shading hang off these, never off testids. */

/* grids: a keyed container becomes a CSS grid, so cards wrap like the mock
   instead of being squeezed by st.columns */
[class*="st-key-grid3-"] {{
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
  gap: 14px !important; align-items: start !important;
}}
[class*="st-key-grid4-"] {{
  display: grid !important;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 215px), 1fr)) !important;
  gap: 14px !important; align-items: start !important;
}}
@media (max-width: 1100px) {{ [class*="st-key-grid3-"] {{ grid-template-columns: repeat(2, minmax(0,1fr)) !important; }} }}
@media (max-width: 700px)  {{ [class*="st-key-grid3-"] {{ grid-template-columns: minmax(0,1fr) !important; }} }}
[class*="st-key-grid"] > * {{ width: auto !important; min-width: 0 !important; }}

/* surfaces */
[class*="st-key-daycard-"], [class*="st-key-card-"] {{
  background: {CARD} !important;
  border-radius: 20px !important;
  padding: 16px !important;
  gap: 6px !important;
}}
[class*="st-key-card-"] {{ gap: 3px !important; height: 100% !important; }}
[class*="st-key-task-open-"], [class*="st-key-task-done-"] {{
  border-radius: 14px !important;
  padding: 9px 12px !important;
  gap: 2px !important;
}}
[class*="st-key-task-open-"] {{ background: {CARD_INNER} !important; border: 1px solid {N300} !important; }}
[class*="st-key-task-done-"] {{ background: {N300} !important; border: 1px solid transparent !important; }}

/* Streamlit gives markdown a negative bottom margin — inside our cards that
   pulled the next box up over the text. Zero it. */
:is([class*="st-key-daycard-"], [class*="st-key-card-"], [class*="st-key-stock"])
  :is([data-testid="stElementContainer"], [data-testid="stMarkdown"],
      [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] > *,
      [data-testid="stCaptionContainer"], [data-testid="stCheckbox"], p) {{
  margin-top: 0 !important; margin-bottom: 0 !important;
  height: auto !important; min-height: 0 !important;
}}
[class*="st-key-daycard-"] [data-testid="stMarkdownContainer"] > div:first-child {{ padding-bottom: 4px; }}

/* Stacking fix: Streamlit lays these out as flex columns with its own
   negative margins on markdown/caption, which pulled each block up over the
   one above. Make our cards plain block flow and space children explicitly. */
:is([class*="st-key-daycard-"], [class*="st-key-task-open-"], [class*="st-key-task-done-"], [class*="st-key-card-"]) {{
  display: block !important;
}}
:is([class*="st-key-daycard-"], [class*="st-key-task-open-"], [class*="st-key-task-done-"], [class*="st-key-card-"]) > * {{
  position: static !important; transform: none !important;
  height: auto !important; min-height: 0 !important; flex: none !important;
  margin: 0 0 8px 0 !important;
}}
:is([class*="st-key-task-open-"], [class*="st-key-task-done-"]) > * {{ margin-bottom: 3px !important; }}
:is([class*="st-key-daycard-"], [class*="st-key-task-open-"], [class*="st-key-task-done-"], [class*="st-key-card-"]) > *:last-child {{
  margin-bottom: 0 !important;
}}
:is([class*="st-key-daycard-"], [class*="st-key-task-"], [class*="st-key-card-"])
  :is([data-testid="stElementContainer"], [data-testid="stMarkdown"], [data-testid="stMarkdownContainer"],
      [data-testid="stCaptionContainer"], [data-testid="stCheckbox"], [data-testid="stButton"], label, p) {{
  margin-top: 0 !important; margin-bottom: 0 !important; position: static !important;
  height: auto !important;
}}

/* recipe costing: ingredient table + price check, same box as stock take */
[class*="st-key-costtable"], [class*="st-key-pricecheck"] {{
  background: {CARD} !important; border-radius: 20px !important; padding: 8px 18px 12px !important; gap: 0 !important;
}}
[class*="st-key-pricecheck"] {{ padding: 16px 18px !important; gap: 10px !important; max-width: 520px; }}
[class*="st-key-costrow-"] {{ border-top: 1px solid {N300} !important; padding: 7px 0 !important; }}
[class*="st-key-costhead"] {{ padding: 8px 0 6px !important; }}
[class*="st-key-costhead"] p {{
  font-size: 0.7rem !important; font-weight: 700 !important; letter-spacing: .08em !important;
  text-transform: uppercase !important; color: {N700} !important; margin: 0 !important;
}}
:is([class*="st-key-costtable"], [class*="st-key-pricecheck"]) [data-testid="stMarkdown"],
:is([class*="st-key-costtable"], [class*="st-key-pricecheck"]) p {{ margin: 0 !important; }}
[class*="st-key-pricecheck"] [data-testid="stNumberInput"] input {{ background: {N100} !important; font-weight: 700 !important; }}

/* task rows */
[class*="st-key-task-"] [data-testid="stCheckbox"] p {{
  font-size: 0.9rem !important; line-height: 1.3 !important; color: {INK} !important;
}}
[class*="st-key-task-done-"] [data-testid="stCheckbox"] p {{ color: {N700} !important; }}
[class*="st-key-task-"] [data-testid="stCaptionContainer"] {{
  padding-left: 1.65rem !important;
}}
[class*="st-key-task-"] [data-testid="stCaptionContainer"] p {{
  font-size: 0.72rem !important; line-height: 1.35 !important; color: {N700} !important;
}}
[data-testid="stCheckbox"] label[data-baseweb="checkbox"] > span:first-child {{
  border-radius: 999px !important; border: 2px solid {N400} !important; background: transparent !important;
}}
[data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {{
  background: {N800} !important; border-color: {N800} !important;
}}

/* small text links (Edit etc.) — any button keyed link-... */
[class*="st-key-link-"] {{ margin: 0 !important; }}
[class*="st-key-link-"] button {{
  min-height: 0 !important; padding: 0 !important; border: 0 !important; background: none !important;
  font-size: 0.75rem !important; font-weight: 700 !important; color: {ACCENT_700} !important;
}}
[class*="st-key-task-"] [class*="st-key-link-"] {{ padding-left: 1.65rem !important; margin-top: 2px !important; }}
[class*="st-key-link-"] button:hover {{ text-decoration: underline !important; }}

/* card title buttons (recipe categories) */
[class*="st-key-cardtitle-"] button {{
  min-height: 0 !important; padding: 2px 4px !important; border: 0 !important; background: none !important;
  font-size: 1rem !important; font-weight: 800 !important; color: {INK} !important; text-align: left !important;
}}

/* pills filter row (master stock categories, recipe types) */
[class*="st-key-pills-"] button {{
  border-radius: 999px !important; padding: 6px 15px !important; min-height: 0 !important;
  border: 1px solid {N300} !important; background: {CARD_INNER} !important; color: {N800} !important;
  font-weight: 600 !important;
}}
[class*="st-key-pills-"] button[kind="pillsActive"],
[class*="st-key-pills-"] [data-testid="stBaseButton-pillsActive"] {{
  background: {N800} !important; border-color: {N800} !important; color: #fff !important;
}}
[class*="st-key-pills-"] [data-testid="stBaseButton-pillsActive"] p {{ color: #fff !important; }}

/* stock take table — one rounded box, header row + divided rows */
[class*="st-key-stocktable"] {{
  background: {CARD} !important; border-radius: 20px !important; padding: 6px 18px 10px !important; gap: 0 !important;
}}
[class*="st-key-stockrow-"] {{ border-top: 1px solid {N300} !important; padding: 8px 0 !important; }}
[class*="st-key-stockhead"] {{ padding: 10px 0 8px !important; }}
[class*="st-key-stockhead"] p {{
  font-size: 0.7rem !important; font-weight: 700 !important; letter-spacing: .08em !important;
  text-transform: uppercase !important; color: {N700} !important; margin: 0 !important;
}}
[class*="st-key-stockrow-"] [data-testid="stNumberInputStepDown"],
[class*="st-key-stockrow-"] [data-testid="stNumberInputStepUp"] {{ display: none !important; }}
[class*="st-key-stockrow-"] input {{ background: {N100} !important; }}
[class*="st-key-stockrow-"] [data-testid="stNumberInput"] > div {{ background: {N100} !important; }}

/* a task card inside a day card: cream, so the nesting reads */
[data-testid="stMainBlockContainer"] div[data-testid="stVerticalBlockBorderWrapper"]
  div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: {CARD_INNER} !important;
  border: 1px solid {N300} !important;
  border-radius: 14px !important;
}}
/* day heading inside a card */
[data-testid="stMainBlockContainer"] div[data-testid="stVerticalBlockBorderWrapper"] h3 {{
  font-size: 1.1rem !important; margin: 0 0 0.25rem !important;
}}
/* task title button: read as text, not a control */
[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-tertiary"] {{
  padding: 0 !important; min-height: 0 !important; text-align: left !important;
  justify-content: flex-start !important; font-weight: 600 !important;
  color: {INK} !important; background: transparent !important;
  max-width: none !important; margin: 0 !important;
}}
/* badges: sand pills rather than Streamlit's grey/orange */
[data-testid="stMainBlockContainer"] [data-testid="stBadge"] {{
  background: {N200} !important; color: {N800} !important;
  border-radius: 999px !important; font-size: 0.72rem !important;
}}

/* completion notice: Streamlit's bright green fights the warm palette.
   Sage is the design system's second accent. */
[data-testid="stAlertContainer"], [data-testid="stNotificationContentSuccess"] {{
  background: #e9ede1 !important; color: #3f4a2c !important;
  border-radius: 12px !important; width: 100% !important;
}}
[data-testid="stAlertContainer"] p {{ white-space: normal !important; }}
[data-testid="stAlertContainer"] p {{ color: #3f4a2c !important; }}

/* ══ SIDEBAR ═══════════════════════════════════════════════
   The nav items are tertiary buttons at width="stretch". Streamlit
   centres those by default and spaces them generously — both undone
   here, and the active page (a disabled button) gets the solid pill. */
[data-testid="stSidebar"] {{
  background: {N100} !important; border-right: 0 !important;
}}
[data-testid="stSidebarUserContent"] {{
  padding: 1.1rem 0.7rem 1.5rem !important;
}}
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] {{
  gap: 0.12rem !important;
}}
/* the group-heading markdown block needs its own height or the next nav
   pill overlaps it */
[data-testid="stSidebar"] [data-testid="stMarkdown"]:has(div[style*="uppercase"]) {{
  min-height: 34px !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdown"] {{ margin: 0 !important; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  font-size: 0.7rem !important; color: {N600} !important;
  margin: 0 0 0.3rem 0.75rem !important;
}}

/* every sidebar button: flat, left-aligned, pill, tight */
[data-testid="stSidebar"] button {{
  width: 100% !important;
  justify-content: flex-start !important;
  text-align: left !important;
  gap: 0.6rem !important;
  padding: 0.38rem 0.75rem !important;
  min-height: 0 !important;
  border: 0 !important; border-radius: 999px !important;
  background: transparent !important;
  color: {INK} !important;
  font-family: 'Nunito', system-ui, sans-serif !important;
  font-size: 0.845rem !important; font-weight: 500 !important;
  line-height: 1.2 !important;
  box-shadow: none !important;
}}
/* Streamlit nests the icon + label in a div inside the button and centres
   THAT, so left-aligning the button alone does nothing. Push the inner
   wrapper full width and shove its contents left. */
[data-testid="stSidebar"] button > div,
[data-testid="stSidebar"] button > span,
[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {{
  width: 100% !important;
  display: flex !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 0.6rem !important;
  text-align: left !important;
  margin-right: auto !important;
}}
[data-testid="stSidebar"] button p {{
  font-size: 0.845rem !important; font-weight: 500 !important;
  text-align: left !important; margin: 0 !important;
  margin-right: auto !important;
}}
[data-testid="stSidebar"] button [data-testid="stIconMaterial"],
[data-testid="stSidebar"] button span[class*="material"] {{
  font-size: 0.95rem !important; color: {N500} !important;
  flex: none !important;
}}
[data-testid="stSidebar"] button:disabled [data-testid="stIconMaterial"] {{
  color: {N300} !important;
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

/* lone action buttons at the top of a page: stop them stretching to the
   full column width, which reads as a banner rather than a button */
[data-testid="stMainBlockContainer"] [data-testid="stBaseButton-primary"] {{
  max-width: 220px !important; margin-left: auto !important;
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

/* ── invoices: new-item cards ─────────────────────────── */
[class*="st-key-grid2-newitems"] {{
  display: grid !important;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr)) !important;
  gap: 14px !important; align-items: start !important; margin-top: 4px !important;
}}
[class*="st-key-newcard-"] {{
  display: block !important;
  background: {CARD_INNER} !important; border: 2px solid transparent !important;
  border-radius: 20px !important; padding: 16px 18px !important;
  box-shadow: 0 1px 2px rgba(70,50,30,.06), 0 2px 8px rgba(70,50,30,.05) !important;
}}
[class*="st-key-newcard-"] > * {{
  position: static !important; transform: none !important; height: auto !important;
  min-height: 0 !important; flex: none !important; margin: 0 0 10px 0 !important;
}}
[class*="st-key-newcard-"] > *:last-child {{ margin-bottom: 0 !important; }}
[class*="st-key-newcard-"] :is([data-testid="stMarkdown"], [data-testid="stMarkdownContainer"], p) {{ margin: 0 !important; }}
[class*="st-key-newcard-"] label p {{ font-size: 0.75rem !important; font-weight: 600 !important; color: {N700} !important; }}
[class*="st-key-newcard-"] :is([data-testid="stTextInput"], [data-testid="stNumberInput"], [data-testid="stSelectbox"]) > div > div,
[class*="st-key-newcard-"] [data-baseweb="select"] > div,
[class*="st-key-newcard-"] [data-baseweb="input"] {{
  border-radius: 999px !important; background: {N100} !important; border-color: {N300} !important;
}}
[class*="st-key-newcard-"] input {{ background: transparent !important; font-weight: 600 !important; }}
[class*="st-key-newcard-"] [data-testid="stExpander"] details {{
  border: 0 !important; background: {N200} !important; border-radius: 14px !important;
}}
[class*="st-key-newcard-"] [data-testid="stExpander"] summary p {{ font-size: 0.8rem !important; font-weight: 600 !important; }}

/* Create new · Match · Skip — one pill track, dark active segment */
[class*="st-key-seg-"] [data-testid="stButtonGroup"] {{ width: 100% !important; }}
[class*="st-key-seg-"] [data-testid="stButtonGroup"] > div {{
  display: flex !important; width: 100% !important; gap: 2px !important;
  padding: 3px !important; background: {N200} !important; border-radius: 999px !important;
}}
[class*="st-key-seg-"] button {{
  flex: 1 1 0 !important; min-height: 0 !important; padding: 7px 8px !important;
  border: 0 !important; border-radius: 999px !important; background: transparent !important;
  color: {N800} !important; box-shadow: none !important;
}}
[class*="st-key-seg-"] button p {{ font-size: 0.82rem !important; font-weight: 700 !important; color: inherit !important; }}
[class*="st-key-seg-"] button:hover {{ background: {N300} !important; }}
[class*="st-key-seg-"] [data-testid$="segmented_controlActive"],
[class*="st-key-seg-"] button[kind$="segmented_controlActive"] {{ background: {INK} !important; color: {N100} !important; }}
[class*="st-key-seg-"] [data-testid$="segmented_controlActive"] p {{ color: {N100} !important; }}

/* suggestion chips */
[class*="st-key-sugs-"] {{ gap: 6px !important; flex-wrap: wrap !important; }}
[class*="st-key-sug-"] button {{
  min-height: 0 !important; padding: 6px 13px !important; border-radius: 999px !important;
  border: 1px solid {N300} !important; background: {N100} !important; color: {INK} !important;
}}
[class*="st-key-sug-"] button p {{ font-size: 0.8rem !important; font-weight: 600 !important; }}
[class*="st-key-sug-"] button:hover {{ background: {N200} !important; border-color: {ACCENT} !important; }}

/* "Nothing close" strip */
[class*="st-key-nomatch-"] {{
  background: {ACCENT_100} !important; border-radius: 14px !important; padding: 10px 14px !important; gap: 10px !important;
}}
[class*="st-key-nomatch-"] p {{ font-size: 0.8rem !important; color: #6b3613 !important; }}
[class*="st-key-nomatch-"] [class*="st-key-link-"] {{ margin-left: auto !important; }}

/* category pills inside a card: sage when chosen */
[class*="st-key-catpills-"] button {{
  min-height: 0 !important; padding: 4px 11px !important; border-radius: 999px !important;
  border: 1px solid {N300} !important; background: {N100} !important; color: {N700} !important;
}}
[class*="st-key-catpills-"] button p {{ font-size: 0.75rem !important; font-weight: 600 !important; }}
[class*="st-key-catpills-"] [data-testid="stBaseButton-pillsActive"] {{
  background: {SAGE_200} !important; border-color: {SAGE} !important; color: {SAGE_900} !important;
}}
[class*="st-key-catpills-"] [data-testid="stBaseButton-pillsActive"] p {{ color: {SAGE_900} !important; }}
</style>
"""


def inject_theme() -> None:
    """Inject the Command Centre CSS. Call once per script run."""
    st.markdown(_CSS, unsafe_allow_html=True)


def tag(label: str, tone: str = "neutral") -> str:
    """A pill span for st.markdown(..., unsafe_allow_html=True).

    tone: "neutral" (default), "ok" (sage) or "alert" (terracotta).
    """
    bg, fg = {
        "alert": (ACCENT_100, ACCENT_700),
        "ok": ("#e9ede1", "#4b5636"),
    }.get(tone, (N200, N800))
    return (
        f'<span style="display:inline-flex;align-items:center;font-size:0.72rem;'
        f'padding:3px 10px;border-radius:999px;background:{bg};color:{fg};'
        f'white-space:nowrap">{label}</span>'
    )


def day_header(name: str, datestr: str) -> str:
    """Day name + date on one baseline row, as in the mock — replaces
    st.subheader(day), which rendered the name alone at the wrong weight."""
    return (
        f'<div style="display:flex;align-items:baseline;gap:10px;margin:0 0 2px">'
        f'<span style="flex:1;font-family:Nunito,sans-serif;font-weight:800;'
        f'font-size:1.12rem;color:{INK};line-height:1.2">{name}</span>'
        f'<span style="font-size:0.72rem;white-space:nowrap;color:{N700}">{datestr}</span>'
        f'</div>'
    )


def done_row(who: str, when: str, note=None) -> str:
    """One sage row for a completed task: filled tick, who, when, optional note.
    Replaces the stacked st.success + st.info boxes."""
    note_html = (
        f'<div style="font-size:0.76rem;color:#4b5636;margin-top:3px">{note}</div>'
        if note else ''
    )
    return (
        f'<div style="display:flex;align-items:flex-start;gap:9px;padding:8px 11px;'
        f'border-radius:12px;background:#e9ede1">'
        f'<span style="flex:none;width:18px;height:18px;border-radius:999px;'
        f'background:#7a8a5e;color:#fff;display:grid;place-items:center;'
        f'font-size:10px;font-weight:700;line-height:1">&#10003;</span>'
        f'<div style="flex:1;min-width:0">'
        f'<div style="font-size:0.82rem;font-weight:700;color:#3f4a2c">{who}'
        f'<span style="font-weight:400;color:#5c6a44"> &middot; {when}</span></div>'
        f'{note_html}</div></div>'
    )


def page_header(title: str, caption: str, button_label=None, key=None) -> bool:
    """Title + caption on the left, primary button bottom-right, as in the mock.
    Returns True when the button was clicked."""
    import streamlit as st
    left, right = st.columns([8, 2], vertical_alignment="bottom")
    with left:
        st.title(title)
        if caption:
            st.caption(caption)
    clicked = False
    if button_label:
        with right:
            with st.container(horizontal=True, horizontal_alignment="right"):
                clicked = st.button(button_label, type="primary", key=key)
    return clicked


def card_html(title: str, lines, chip: str = "") -> str:
    """Card body in the mock's rhythm: heading (+ optional chip), then lines.
    lines: list of (text, style) where style is "meta", "strong" or "faint"."""
    styles = {
        "meta":   f"font-size:0.78rem;color:{N700}",
        "strong": f"font-size:0.84rem;font-weight:700;color:{N900}",
        "faint":  f"font-size:0.72rem;color:{N600}",
    }
    body = "".join(
        f'<div style="{styles.get(s, styles["meta"])};line-height:1.35;margin-top:2px">{t}</div>'
        for t, s in lines if t
    )
    return (
        f'<div style="display:flex;align-items:flex-start;gap:6px;margin-bottom:2px">'
        f'<div style="flex:1;min-width:0;font-family:Nunito,sans-serif;font-weight:800;'
        f'font-size:1.02rem;line-height:1.25;color:{INK}">{title}</div>{chip}</div>{body}'
    )


def section_head(title: str, note: str = "") -> str:
    """H2 in the display face with a small note that wraps under it on narrow screens."""
    note_html = (f'<span style="font-size:0.8rem;white-space:nowrap;color:{N700}">{note}</span>' if note else "")
    return (
        f'<div style="display:flex;flex-wrap:wrap;align-items:baseline;column-gap:12px;row-gap:2px;margin:14px 0 6px">'
        f'<span style="flex:1;font-family:Nunito,sans-serif;font-weight:800;font-size:1.3rem;color:{INK}">{title}</span>'
        f'{note_html}</div>'
    )


def _tile(k, v, sub, bg, fg, lab):
    return (
        f'<div style="display:flex;flex-direction:column;gap:2px;padding:14px 18px;background:{bg};border-radius:20px">'
        f'<div style="font-size:0.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:{lab}">{k}</div>'
        f'<div style="font-family:Nunito,sans-serif;font-weight:800;font-size:1.65rem;line-height:1.15;color:{fg}">{v}</div>'
        f'<div style="font-size:0.75rem;color:{lab}">{sub}</div></div>'
    )


TARGET_FOOD_COST = 30


def recipe_stats_html(recipe, total, per_portion, price, n_lines, is_prep) -> str:
    """The tiles across the top of a recipe's costing view."""
    tiles = []
    if is_prep:
        yq, yu = recipe["yield_qty"], recipe["yield_unit"] or ""
        per_unit = total / yq if yq else 0
        tiles.append(_tile("Batch cost", f"${total:.2f}", f"{n_lines} ingredients", CARD, INK, N700))
        tiles.append(_tile("Yield", f"{yq:g} {yu}" if yq else "Not set", "Production quantity", CARD, INK, N700))
        tiles.append(_tile(f"Cost / {yu or 'unit'}", f"${per_unit:.4f}", "Used by dishes", N800, N100, N300))
    else:
        tiles.append(_tile("Cost / portion", f"${per_portion:.2f}", f"{n_lines} ingredients", CARD, INK, N700))
        tiles.append(_tile("Selling price", f"${price:.2f}" if price else "Not set",
                           f"${price / 1.09:.2f} ex GST" if price else "Add one below", CARD, INK, N700))
        if price:
            fc = per_portion / price * 100
            over = fc > TARGET_FOOD_COST
            bg, fg, lab = (ACCENT_100, "#6b3613", ACCENT_700) if over else ("#e9ede1", "#3f4a2c", "#4b5636")
            tiles.append(_tile("Food cost", f"{fc:.1f}%", f"Target {TARGET_FOOD_COST}% or under", bg, fg, lab))
            gp = price - per_portion
            tiles.append(_tile("Gross profit", f"${gp:.2f}", f"{gp / price * 100:.0f}% margin", N800, N100, N300))
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:6px 0 4px">'
        + "".join(tiles) + "</div>"
    )


def price_check_html(cost, price) -> str:
    """GST breakdown + verdict under the price input."""
    if price <= 0:
        return f'<div style="font-size:0.85rem;color:{N700}">Enter a selling price to see food cost and margin.</div>'
    ex = price / 1.09
    rows = [("Price ex GST", f"${ex:.2f}"), ("GST (9%)", f"${price - ex:.2f}"),
            ("Ingredient cost", f"− ${cost:.2f}"), ("Gross profit", f"${price - cost:.2f}")]
    body = "".join(
        f'<div style="display:flex;gap:12px;font-size:0.9rem;padding:2px 0"><span style="flex:1;color:{N700}">{k}</span>'
        f'<span style="font-weight:700">{v}</span></div>' for k, v in rows
    )
    fc = cost / price * 100
    target_price = cost / (TARGET_FOOD_COST / 100) if cost else 0
    if fc > TARGET_FOOD_COST:
        bg, fg = ACCENT_100, "#6b3613"
        head = f"Food cost is above {TARGET_FOOD_COST}%"
        sub = f"Raise the price to ${target_price:.2f} or trim the costliest ingredient."
    else:
        bg, fg = "#e9ede1", "#3f4a2c"
        head = f"Within the {TARGET_FOOD_COST}% target"
        sub = (f"You could go down to ${target_price:.2f} before food cost passes {TARGET_FOOD_COST}%."
               if cost else "No ingredient costs yet — check prices on the Master Stock List.")
    return (
        f'{body}<div style="margin-top:8px;padding:12px 14px;border-radius:14px;background:{bg};color:{fg}">'
        f'<div style="font-weight:700;font-size:0.88rem">{head}</div>'
        f'<div style="font-size:0.8rem;line-height:1.4;margin-top:2px">{sub}</div></div>'
    )


def newitems_head_html(total: int, sorted_n: int) -> str:
    """Title, helper line and sorted-progress bar above the new-item cards."""
    pct = round(sorted_n / total * 100) if total else 0
    noun = "item isn't" if total == 1 else "items aren't"
    return (
        f'<div style="display:flex;flex-wrap:wrap;align-items:flex-end;gap:8px 18px;margin:10px 0 2px">'
        f'<div style="flex:1;min-width:220px">'
        f'<div style="font-family:Nunito,sans-serif;font-weight:800;font-size:1.2rem;line-height:1.25;color:{INK}">'
        f'{total} {noun} in Master Stock yet</div>'
        f'<div style="font-size:0.82rem;color:{N700};margin-top:2px">'
        f'Create each one, match it to something you already stock, or skip it.</div></div>'
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<div style="width:90px;height:8px;border-radius:999px;background:{N300};overflow:hidden">'
        f'<div style="height:100%;width:{pct}%;border-radius:999px;background:{SAGE}"></div></div>'
        f'<span style="font-size:0.78rem;font-weight:700;white-space:nowrap;color:{N800}">{sorted_n} of {total} sorted</span>'
        f'</div></div>'
    )


def newitem_head_html(desc: str, qty_line: str, total: str, status: str, tone: str) -> str:
    """Card header: sage initial circle, printed line + qty/price, status pill over the line total."""
    import html as _h
    initial = _h.escape((desc.strip()[:1] or "?").upper())
    return (
        f'<div style="display:flex;align-items:flex-start;gap:12px">'
        f'<div style="flex:none;width:46px;height:46px;border-radius:50%;background:{SAGE_100};'
        f'display:grid;place-items:center;font-family:Nunito,sans-serif;font-weight:800;font-size:1.15rem;color:{SAGE_800}">{initial}</div>'
        f'<div style="flex:1;min-width:0">'
        f'<div style="font-size:0.72rem;font-weight:700;letter-spacing:.05em;color:{N600};line-height:1.3">{_h.escape(desc)}</div>'
        f'<div style="font-size:0.85rem;color:{N800};margin-top:2px">{_h.escape(qty_line)}</div></div>'
        f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">'
        f'{tag(status, tone)}'
        f'<span style="font-family:Nunito,sans-serif;font-weight:800;font-size:1.05rem;white-space:nowrap;color:{INK}">{total}</span>'
        f'</div></div>'
    )


def unit_cost_strip_html(unit_cost: str, supplier: str) -> str:
    import html as _h
    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:4px 12px;padding:9px 14px;border-radius:14px;'
        f'background:{SAGE_100};font-size:0.8rem;color:{SAGE_900}">'
        f'<span style="flex:1;min-width:120px">Unit cost <strong>{_h.escape(unit_cost)}</strong></span>'
        f'<span style="white-space:nowrap">from {_h.escape(supplier)}</span></div>'
    )


def skip_note_html() -> str:
    return (
        f'<div style="padding:9px 14px;border-radius:14px;background:{N200};font-size:0.8rem;'
        f'line-height:1.4;color:{N700}">Stays on the invoice total but won\'t be added to stock or prices.</div>'
    )
