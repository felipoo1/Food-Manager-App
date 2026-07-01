"""
app.py
-------------------------------------------------------
This is the main screen of your cafe app.
Run it with:  streamlit run app.py
-------------------------------------------------------
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import database as db
import base64
from app_icon import ICON_BASE64

st.set_page_config(page_title="Cafe Manager", layout="wide", page_icon="☕")

# ---------- "Add to Home Screen" icon (iOS/Android) ----------
# Streamlit doesn't officially expose the page's <head>, so this uses a
# commonly-used workaround: injecting the relevant <link>/<meta> tags
# directly. This usually works for getting a custom icon + standalone
# (no browser bar) behavior when added to a phone/iPad home screen, but
# I can't fully guarantee it across every iOS/Android version since I
# can't test it live from here -- if "Add to Home Screen" doesn't pick up
# the icon on your device, it'll just fall back to a plain screenshot icon,
# nothing breaks either way.
_manifest_json = (
    '{"name":"Cafe Manager","short_name":"Cafe Manager","start_url":".",'
    '"display":"standalone","background_color":"#FFF8F0","theme_color":"#FF8C73",'
    f'"icons":[{{"src":"data:image/png;base64,{ICON_BASE64}","sizes":"512x512","type":"image/png"}}]}}'
)
_manifest_b64 = base64.b64encode(_manifest_json.encode()).decode()

st.markdown(f"""
<link rel="apple-touch-icon" href="data:image/png;base64,{ICON_BASE64}">
<link rel="manifest" href="data:application/json;base64,{_manifest_b64}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Cafe Manager">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#FF8C73">
""", unsafe_allow_html=True)


# Bump this number any time the database schema changes (new tables, new
# columns, etc.). It's passed into the cached function below as an argument
# specifically so that changing it forces a fresh run even if the app
# process never fully restarts -- this is what prevents the exact bug where
# new tables silently don't get created because a stale cached "already set
# up" result from before the change was reused.
SCHEMA_VERSION = 8


@st.cache_resource
def _ensure_database_ready(schema_version):
    """
    Runs all one-time setup (create tables, seed starter data, migrations)
    once per running app process AND per schema_version, instead of on
    every single click. Before the original version of this fix, init_db()'s
    ~10 tables and several schema checks were silently re-running on every
    page switch -- this was the single biggest cause of the app feeling slow
    to navigate. The schema_version argument exists so that bumping it after
    a schema change guarantees this actually re-runs, even if Streamlit
    reuses a warm process instead of fully restarting.
    """
    db.init_db()
    db.seed_starter_data()
    db.seed_default_staff()
    db.migrate_manager_role_to_owner()
    return True


_ensure_database_ready(SCHEMA_VERSION)

# ---------- PIN box sizing ----------
# Targets the actual HTML attribute Streamlit sets for single-character
# ---------- PIN box sizing ----------
# Targets the actual HTML attribute Streamlit sets for a 4-character input
# (maxlength="4") rather than a fragile class name -- this is unique to our
# PIN field and nothing else in the app, so it can't accidentally affect
# any other text field.
# Placed here (before the login gate) so it also applies to the login screen,
# not just pages reached after logging in.
st.markdown("""
<style>
input[maxlength="4"] {
    font-size: 2.8rem !important;
    text-align: center !important;
    height: 4.2rem !important;
    width: 11rem !important;
    letter-spacing: 0.5em !important;
    box-sizing: border-box !important;
    display: block !important;
    margin: 0 auto !important;
}
</style>
""", unsafe_allow_html=True)


def pin_entry_boxes(key_prefix, prefill=None):
    """
    Renders ONE centered box you type all 4 digits into continuously -- no
    clicking or tabbing between separate fields. The digits are spaced out
    visually (via letter-spacing) so it still reads like 4 distinct slots.
    Returns whatever's been typed, as a plain string.

    If `prefill` is given (e.g. an existing 4-digit PIN being edited) and the
    box hasn't been touched yet this session, it starts pre-filled instead
    of empty.
    """
    box_key = f"{key_prefix}_pin"
    if prefill and len(prefill) == 4 and box_key not in st.session_state:
        st.session_state[box_key] = prefill

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        value = st.text_input(
            "PIN", max_chars=4, type="default",
            key=box_key, label_visibility="collapsed",
            placeholder="0000"
        )
    return value


def clear_pin_boxes(key_prefix):
    """Clears a PIN box (e.g. after a wrong attempt) by resetting its session state."""
    st.session_state[f"{key_prefix}_pin"] = ""


# ---------- PIN login gate ----------
# Nothing below this runs until someone enters a valid PIN.
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "pending_shared_login" not in st.session_state:
    st.session_state.pending_shared_login = False

if st.session_state.current_user is None:
    st.write("")
    st.write("")
    st.write("")
    st.write("")
    left_spacer, center_box, right_spacer = st.columns([1, 1, 1])

    with center_box:
        with st.container(border=True):
            st.markdown("##### Cafe Manager")

            if st.session_state.pending_shared_login:
                st.caption("Shop iPad — who are you?")
                conn = db.get_connection()
                named_staff = conn.execute(
                    "SELECT id, name, role FROM staff WHERE is_shared_device = 0 ORDER BY name"
                ).fetchall()
                conn.close()
                staff_by_name = {r["name"]: r for r in named_staff}

                if not staff_by_name:
                    st.info("No named staff set up yet — ask a manager to add staff first.")
                else:
                    chosen_name = st.selectbox("Select your name", list(staff_by_name.keys()))
                    if st.button("Continue", width="stretch", type="primary"):
                        chosen = staff_by_name[chosen_name]
                        st.session_state.current_user = {"id": chosen["id"], "name": chosen["name"], "role": chosen["role"]}
                        st.session_state.pending_shared_login = False
                        st.rerun()

            else:
                st.caption("Enter your 4-digit PIN to continue")
                pin_entry = pin_entry_boxes("login_pin")
                if st.button("Log in", width="stretch", type="primary"):
                    if len(pin_entry) < 4 or not pin_entry.isdigit():
                        st.error("Please fill in all 4 digits.")
                    else:
                        conn = db.get_connection()
                        staff_match = conn.execute("SELECT * FROM staff WHERE pin = ?", (pin_entry,)).fetchone()
                        conn.close()
                        if staff_match is None:
                            st.error("PIN not recognized.")
                            clear_pin_boxes("login_pin")
                        elif staff_match["is_shared_device"]:
                            st.session_state.pending_shared_login = True
                            st.rerun()
                        else:
                            st.session_state.current_user = {
                                "id": staff_match["id"], "name": staff_match["name"], "role": staff_match["role"]
                            }
                            st.rerun()
                st.caption("Forgot your PIN? Ask the Owner to reset it for you, or use the Owner account to reset your own from Settings → Change my PIN once logged in.")
    st.stop()

current_user = st.session_state.current_user
is_owner = current_user["role"] == "owner"

# ---------- Sidebar typography (left-aligned, bigger/bolder nav text) ----------
# Streamlit's theme settings don't expose per-element text alignment or font
# weight, so this small CSS block fills that one gap. It only targets the
# sidebar nav buttons/text, nothing else in the app.
# Note: buttons center their content via a flex container, not just text-align
# on the inner <p> -- targeting only the <p> (as before) wasn't enough.
st.markdown("""
<style>
[data-testid="stSidebar"] button {
    justify-content: flex-start !important;
}
[data-testid="stSidebar"] button div {
    justify-content: flex-start !important;
    text-align: left !important;
}
[data-testid="stSidebar"] button p {
    text-align: left !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    font-size: 1.05rem !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- Sidebar navigation (flat text-style links) ----------
st.sidebar.markdown("##### Cafe Manager")
st.sidebar.caption(f"Logged in as **{current_user['name']}** ({current_user['role']})")
st.sidebar.write("")

nav_options = ["Tasks", "Stock Take", "Master Stock List", "Recipes", "Suppliers", "Orders"]
if is_owner:
    nav_options.append("Task History")
    nav_options.append("Invoices")
    nav_options.append("Staff")
    nav_options.append("Sales Sync")
    nav_options.append("Data Export")

if "current_page" not in st.session_state:
    st.session_state.current_page = nav_options[0]
if st.session_state.current_page not in nav_options:
    st.session_state.current_page = nav_options[0]  # safety net if role changed and a page is no longer available

NAV_ICONS = {
    "Tasks": ":material/checklist:",
    "Stock Take": ":material/fact_check:",
    "Master Stock List": ":material/inventory_2:",
    "Recipes": ":material/menu_book:",
    "Suppliers": ":material/local_shipping:",
    "Orders": ":material/shopping_cart:",
    "Task History": ":material/history:",
    "Invoices": ":material/receipt_long:",
    "Staff": ":material/group:",
    "Sales Sync": ":material/sync:",
    "Data Export": ":material/download:",
}

for option in nav_options:
    icon = NAV_ICONS.get(option, ":material/circle:")
    if option == st.session_state.current_page:
        st.sidebar.markdown(f"{icon} **:orange[{option}]**")
    else:
        if st.sidebar.button(option, icon=icon, type="tertiary", width="stretch", key=f"nav_{option}"):
            st.session_state.current_page = option
            st.rerun()

page = st.session_state.current_page

st.sidebar.divider()

conn = db.get_connection()
notif_count = conn.execute("SELECT COUNT(*) AS c FROM notifications WHERE is_read = 0").fetchone()["c"]
error_count = conn.execute("SELECT COUNT(*) AS c FROM notifications WHERE is_read = 0 AND kind = 'error'").fetchone()["c"]
conn.close()

bell_label = f"Notifications ({notif_count})" if notif_count else "Notifications"
if error_count:
    bell_label = f"Notifications ({notif_count}) — ⚠️ {error_count} issue(s)"

if st.sidebar.button(bell_label, icon=":material/notifications:", type="tertiary", width="stretch"):
    st.session_state.show_notifications = not st.session_state.get("show_notifications", False)
    st.rerun()
if st.sidebar.button("Change my PIN", icon=":material/lock_reset:", type="tertiary", width="stretch"):
    st.session_state.show_change_pin = not st.session_state.get("show_change_pin", False)
    st.rerun()
if st.sidebar.button("Log out", icon=":material/logout:", type="tertiary", width="stretch"):
    st.session_state.current_user = None
    st.rerun()

# ---------- Notifications panel (available to everyone) ----------
if st.session_state.get("show_notifications"):
    st.title("Notifications")
    st.caption("Order activity and any errors, visible to everyone in the app. Viewing this clears the alert badge — only new activity since your last visit will show up there again.")

    conn = db.get_connection()
    notif_rows = conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 50").fetchall()
    unread_ids = {r["id"] for r in notif_rows if not r["is_read"]}
    conn.close()

    if unread_ids:
        db.mark_all_notifications_read()

    if not notif_rows:
        st.info("No notifications yet.")
    else:
        for n in notif_rows:
            prefix = "🆕 " if n["id"] in unread_ids else ""
            text = f"{prefix}**{n['created_at']}** — {n['message']}" + (f" _(by {n['created_by']})_" if n["created_by"] else "")
            if n["kind"] == "error":
                st.error(text)
            else:
                st.success(text)

    if st.button("Close"):
        st.session_state.show_notifications = False
        st.rerun()
    st.stop()

# ---------- Change My PIN (self-service, available to anyone logged in) ----------
if st.session_state.get("show_change_pin"):
    st.title("Change my PIN")
    st.caption(f"Changing the PIN for {current_user['name']}. This only changes your own PIN.")

    st.write("**Current PIN**")
    current_pin_entry = pin_entry_boxes("change_pin_current")
    st.write("**New PIN (4 digits)**")
    new_pin_entry = pin_entry_boxes("change_pin_new")
    st.write("**Confirm new PIN**")
    confirm_pin_entry = pin_entry_boxes("change_pin_confirm")

    save_col, cancel_col = st.columns(2)
    with save_col:
        if st.button("Save new PIN", type="primary"):
            if len(current_pin_entry) < 4 or not current_pin_entry.isdigit():
                st.error("Please fill in your current PIN.")
            else:
                conn = db.get_connection()
                me = conn.execute("SELECT * FROM staff WHERE id = ?", (current_user["id"],)).fetchone()
                if me is None or me["pin"] != current_pin_entry:
                    st.error("Current PIN is incorrect.")
                    conn.close()
                elif len(new_pin_entry) < 4 or not new_pin_entry.isdigit():
                    st.error("New PIN must be exactly 4 digits.")
                    conn.close()
                elif new_pin_entry != confirm_pin_entry:
                    st.error("New PIN and confirmation don't match.")
                    conn.close()
                else:
                    clash = conn.execute(
                        "SELECT id FROM staff WHERE pin = ? AND id != ?", (new_pin_entry, current_user["id"])
                    ).fetchone()
                    if clash:
                        st.error("That PIN is already used by someone else — choose a different one.")
                        conn.close()
                    else:
                        conn.execute("UPDATE staff SET pin = ? WHERE id = ?", (new_pin_entry, current_user["id"]))
                        conn.commit()
                        conn.close()
                        st.success("Your PIN has been updated. You'll use the new one next time you log in.")
                        st.session_state.show_change_pin = False
                        st.rerun()
    with cancel_col:
        if st.button("Cancel"):
            st.session_state.show_change_pin = False
            st.rerun()
    st.stop()


def get_supplier_options():
    """Returns a dict of {supplier_name: supplier_id} plus a 'None' option, for dropdowns."""
    conn = db.get_connection()
    rows = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    conn.close()
    options = {"-- none --": None}
    for r in rows:
        options[r["name"]] = r["id"]
    return options


# =========================================================
# PAGE: TASKS
# =========================================================
if page == "Tasks":
    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if "task_mode" not in st.session_state:
        st.session_state.task_mode = "list"
    if not is_owner:
        st.session_state.task_mode = "list"  # safety: only the owner can reach add/edit

    if is_owner:
        title_col, btn1 = st.columns([7, 2])
        with title_col:
            st.title("Weekly task workspace")
        with btn1:
            if st.button("Add New Task", type="primary", use_container_width=True):
                st.session_state.task_mode = "add"
                st.rerun()

        if st.session_state.task_mode != "list":
            if st.button("← Back to list"):
                st.session_state.task_mode = "list"
                st.rerun()
            st.write("")
    else:
        st.title("Weekly task workspace")

    # ---------------- LIST VIEW ----------------
    if st.session_state.task_mode == "list":
        st.caption("Weekly recurring tasks reset every Monday. One-off tasks stay completed once ticked. Click a task to edit it.")

        conn = db.get_connection()
        all_task_defs = conn.execute("SELECT * FROM task_definitions ORDER BY section, title").fetchall()
        # One single query for every task's completion status, instead of one query per task.
        completions = db.get_task_completions_batch(all_task_defs, conn)
        conn.close()

        if "pending_pin_task" not in st.session_state:
            st.session_state.pending_pin_task = None  # holds a unique key like "12-pending" while awaiting PIN

        for day in DAYS:
            day_tasks = [t for t in all_task_defs if t["day_of_week"] == day]
            with st.container(border=True):
                st.subheader(day)
                if not day_tasks:
                    st.caption("No tasks assigned to this day.")
                for section in ["Kitchen", "Floor"]:
                    section_tasks = [t for t in day_tasks if t["section"] == section]
                    if not section_tasks:
                        continue
                    st.markdown(f"**{section}**")

                    conn = db.get_connection()
                    for t in section_tasks:
                        pending_key = f"{t['id']}-pending"
                        is_done, completed_by, completed_at, log_id = completions[t["id"]]

                        with st.container(border=True):
                            row_cols = st.columns([5, 2])
                            with row_cols[0]:
                                title_col, badge_col = st.columns([5, 2])
                                with title_col:
                                    if is_owner:
                                        if st.button(t["title"], type="tertiary", key=f"task_title_{t['id']}"):
                                            st.session_state["edit_task_select"] = f"[{t['day_of_week']} / {t['section']}] {t['title']}"
                                            st.session_state.task_mode = "edit"
                                            st.rerun()
                                    else:
                                        st.write(t["title"])
                                with badge_col:
                                    if t["recurrence"] == "once":
                                        st.badge(f"One-off: {t['specific_date']}", color="gray")
                                    else:
                                        st.badge("Weekly", color="orange")
                                if t["notes"]:
                                    with st.expander("Notes"):
                                        st.write(t["notes"])

                            with row_cols[1]:
                                if is_done:
                                    st.success(f"✅ {completed_by} at {completed_at}")
                                    if st.button("Undo", key=f"undo_{t['id']}"):
                                        conn.execute(
                                            "UPDATE task_log SET reverted=1, reverted_by=?, reverted_at=? WHERE id=?",
                                            (current_user["name"], datetime.now().strftime("%-I:%M %p"), log_id)
                                        )
                                        conn.commit()
                                        st.rerun()
                                elif st.session_state.pending_pin_task == pending_key:
                                    pin_try = pin_entry_boxes(f"task_pin_{t['id']}")
                                    confirm_col, cancel_col = st.columns(2)
                                    with confirm_col:
                                        if st.button("Confirm", key=f"confirm_{t['id']}"):
                                            if len(pin_try) < 4 or not pin_try.isdigit():
                                                st.error("Please fill in all 4 digits.")
                                            else:
                                                staff_match = conn.execute("SELECT * FROM staff WHERE pin = ?", (pin_try,)).fetchone()
                                                if staff_match is None:
                                                    st.error("PIN not recognized.")
                                                    clear_pin_boxes(f"task_pin_{t['id']}")
                                                else:
                                                    week_val = db.get_week_start() if t["recurrence"] == "weekly" else None
                                                    conn.execute(
                                                        "INSERT INTO task_log (task_id, week_start_date, completed_by, completed_at) VALUES (?, ?, ?, ?)",
                                                        (t["id"], week_val, staff_match["name"], datetime.now().strftime("%-I:%M %p"))
                                                    )
                                                    conn.commit()
                                                    st.session_state.pending_pin_task = None
                                                    st.rerun()
                                    with cancel_col:
                                        if st.button("Cancel", key=f"cancel_{t['id']}"):
                                            st.session_state.pending_pin_task = None
                                            st.rerun()
                                else:
                                    if st.button("Mark complete", key=f"complete_{t['id']}"):
                                        st.session_state.pending_pin_task = pending_key
                                        st.rerun()
                    conn.close()
            st.write("")

    # ---------------- ADD VIEW (owner only) ----------------
    elif st.session_state.task_mode == "add":
        st.subheader("Add a new task")
        with st.form("add_task_form", clear_on_submit=True):
            task_title = st.text_input("Task description")
            task_section = st.selectbox("Section", ["Kitchen", "Floor"])
            task_notes = st.text_area("Notes (multi-line instructions for the team)")
            recurrence_choice = st.radio("Repeats?", ["Repeats every week", "One-off (specific date)"], horizontal=True)

            if recurrence_choice == "Repeats every week":
                task_day = st.selectbox("Which day of the week?", DAYS)
                task_specific_date = None
            else:
                task_specific_date = st.date_input("Date", value=date.today())
                task_day = DAYS[task_specific_date.weekday()]

            submitted = st.form_submit_button("Add task")
            if submitted:
                if not task_title:
                    st.error("Please enter a task description.")
                else:
                    conn = db.get_connection()
                    conn.execute(
                        """INSERT INTO task_definitions
                           (title, section, notes, recurrence, day_of_week, specific_date, created_by, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            task_title, task_section, task_notes,
                            "weekly" if recurrence_choice == "Repeats every week" else "once",
                            task_day,
                            task_specific_date.isoformat() if task_specific_date else None,
                            current_user["name"], date.today().isoformat()
                        )
                    )
                    conn.commit()
                    conn.close()
                    st.success("Task added.")
                    st.session_state.task_mode = "list"
                    st.rerun()

    # ---------------- EDIT VIEW (Update + Delete both live here) ----------------
    elif st.session_state.task_mode == "edit":
        st.subheader("Edit task")

        conn = db.get_connection()
        all_defs = conn.execute("SELECT * FROM task_definitions ORDER BY day_of_week, section, title").fetchall()
        conn.close()

        if not all_defs:
            st.info("No tasks to edit yet.")
        else:
            labels = {f"[{t['day_of_week']} / {t['section']}] {t['title']}": t["id"] for t in all_defs}
            chosen_label = st.selectbox("Task", list(labels.keys()), key="edit_task_select")
            chosen_id = labels[chosen_label]
            current = next(t for t in all_defs if t["id"] == chosen_id)

            with st.form(f"edit_task_form_{chosen_id}"):
                e_title = st.text_input("Task description", value=current["title"])
                e_section = st.selectbox("Section", ["Kitchen", "Floor"], index=["Kitchen", "Floor"].index(current["section"]))
                e_notes = st.text_area("Notes (multi-line instructions for the team)", value=current["notes"] or "")
                e_recurrence_choice = st.radio(
                    "Repeats?", ["Repeats every week", "One-off (specific date)"], horizontal=True,
                    index=0 if current["recurrence"] == "weekly" else 1
                )

                if e_recurrence_choice == "Repeats every week":
                    e_day = st.selectbox("Which day of the week?", DAYS, index=DAYS.index(current["day_of_week"]))
                    e_specific_date = None
                else:
                    default_date = date.fromisoformat(current["specific_date"]) if current["specific_date"] else date.today()
                    e_specific_date = st.date_input("Date", value=default_date)
                    e_day = DAYS[e_specific_date.weekday()]

                update_submitted = st.form_submit_button("Update task")
                if update_submitted:
                    if not e_title:
                        st.error("Please enter a task description.")
                    else:
                        conn = db.get_connection()
                        conn.execute(
                            """UPDATE task_definitions
                               SET title=?, section=?, notes=?, recurrence=?, day_of_week=?, specific_date=?
                               WHERE id=?""",
                            (
                                e_title, e_section, e_notes,
                                "weekly" if e_recurrence_choice == "Repeats every week" else "once",
                                e_day,
                                e_specific_date.isoformat() if e_specific_date else None,
                                chosen_id
                            )
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Updated {e_title}.")
                        st.session_state.task_mode = "list"
                        st.rerun()

            st.write("")
            st.write("**Delete this task**")
            st.caption("This will also permanently delete its full completion history.")
            if st.button("Delete this task", key=f"delete_task_{chosen_id}"):
                conn = db.get_connection()
                conn.execute("DELETE FROM task_definitions WHERE id = ?", (chosen_id,))
                conn.commit()
                conn.close()
                st.success("Task removed.")
                st.session_state.task_mode = "list"
                st.rerun()


# =========================================================
# PAGE: STOCK TAKE
# =========================================================
elif page == "Stock Take":
    st.title("Weekly stock take")
    st.caption("Count what's actually on the shelf. Pulled live from the Master Stock List — nothing is duplicated here.")

    conn = db.get_connection()
    ingredients = conn.execute("""
        SELECT * FROM ingredients ORDER BY category, name
    """).fetchall()
    conn.close()

    if not ingredients:
        st.info("No ingredients in the Master Stock List yet — add some first.")
    else:
        with st.form("stock_take_form"):
            count_date = st.date_input("Stock take date", value=date.today())
            st.write("")

            categories = sorted(set(r["category"] or "Uncategorised" for r in ingredients))
            entered_values = {}
            for cat in categories:
                st.markdown(f"**{cat}**")
                cat_items = [r for r in ingredients if (r["category"] or "Uncategorised") == cat]
                for item in cat_items:
                    entered_values[item["id"]] = st.number_input(
                        f"{item['name']} ({item['base_unit']})",
                        min_value=0.0, step=1.0, key=f"count_{item['id']}_{count_date}"
                    )

            submitted = st.form_submit_button("Submit stock take")
            if submitted:
                conn = db.get_connection()
                # Resubmitting the same date overwrites that date's counts, rather than duplicating them
                conn.execute("DELETE FROM stock_takes WHERE count_date = ?", (count_date.isoformat(),))

                flagged_items = []
                for ingredient_id, qty in entered_values.items():
                    ing = conn.execute("SELECT * FROM ingredients WHERE id = ?", (ingredient_id,)).fetchone()
                    expected = ing["current_stock_qty"]  # None if this ingredient has never been counted/initialized
                    variance = None
                    is_flagged = 0
                    if expected is not None:
                        variance = qty - expected
                        tolerance = db.get_variance_tolerance(ing["base_unit"])
                        if abs(variance) > tolerance:
                            is_flagged = 1
                            flagged_items.append((ing["name"], expected, qty, variance, ing["base_unit"]))

                    conn.execute("""
                        INSERT INTO stock_takes
                            (ingredient_id, count_date, quantity_counted, counted_by, expected_qty_before, variance, is_flagged)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (ingredient_id, count_date.isoformat(), qty, current_user["name"], expected, variance, is_flagged))

                    # Recalibrate the running balance to match what staff actually counted —
                    # this becomes the new "expected" baseline until the next stock take.
                    conn.execute("UPDATE ingredients SET current_stock_qty = ? WHERE id = ?", (qty, ingredient_id))

                conn.commit()

                if flagged_items:
                    detail_str = "; ".join(
                        f"{name} (expected {exp:g}{u}, counted {cnt:g}{u}, {var:+g}{u})"
                        for name, exp, cnt, var, u in flagged_items
                    )
                    db.add_notification(
                        "error",
                        f"Stock take on {count_date.isoformat()} flagged {len(flagged_items)} item(s) beyond tolerance: {detail_str}",
                        created_by=current_user["name"], conn=conn
                    )
                conn.close()

                if flagged_items:
                    st.warning(f"Stock take saved, but {len(flagged_items)} item(s) varied beyond the expected tolerance (±1kg/±1L/±1 unit) — check Notifications for details.")
                else:
                    st.success(f"Stock take for {count_date.isoformat()} saved.")
                st.rerun()

    st.divider()
    st.subheader("View a past stock take")

    conn = db.get_connection()
    past_dates = [r["count_date"] for r in conn.execute(
        "SELECT DISTINCT count_date FROM stock_takes ORDER BY count_date DESC"
    ).fetchall()]
    conn.close()

    if not past_dates:
        st.write("No stock takes recorded yet.")
    else:
        chosen_date = st.selectbox("Choose a date", past_dates)
        conn = db.get_connection()
        history_rows = conn.execute("""
            SELECT i.name, i.category, i.base_unit, st.quantity_counted, st.counted_by,
                   st.expected_qty_before, st.variance, st.is_flagged
            FROM stock_takes st
            JOIN ingredients i ON st.ingredient_id = i.id
            WHERE st.count_date = ?
            ORDER BY i.category, i.name
        """, (chosen_date,)).fetchall()
        conn.close()

        history_data = [{
            "Category": r["category"],
            "Ingredient": r["name"],
            "Quantity counted": f"{r['quantity_counted']:g}{r['base_unit']}",
            "Expected (before this count)": f"{r['expected_qty_before']:g}{r['base_unit']}" if r["expected_qty_before"] is not None else "Not yet tracked",
            "Variance": f"{r['variance']:+g}{r['base_unit']}" if r["variance"] is not None else "-",
            "Flagged?": "🔴 Yes" if r["is_flagged"] else "",
            "Counted by": r["counted_by"],
        } for r in history_rows]
        st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Variance report")
    st.caption("Every stock take where the count was off by more than the tolerance (±1kg / ±1L / ±1 unit), most recent first.")

    conn = db.get_connection()
    flagged_rows = conn.execute("""
        SELECT i.name, i.base_unit, st.count_date, st.quantity_counted, st.expected_qty_before, st.variance, st.counted_by
        FROM stock_takes st
        JOIN ingredients i ON st.ingredient_id = i.id
        WHERE st.is_flagged = 1
        ORDER BY st.id DESC
        LIMIT 50
    """).fetchall()
    conn.close()

    if not flagged_rows:
        st.success("No flagged variances on record.")
    else:
        variance_data = [{
            "Date": r["count_date"],
            "Ingredient": r["name"],
            "Expected": f"{r['expected_qty_before']:g}{r['base_unit']}",
            "Counted": f"{r['quantity_counted']:g}{r['base_unit']}",
            "Variance": f"{r['variance']:+g}{r['base_unit']}",
            "Counted by": r["counted_by"],
        } for r in flagged_rows]
        st.dataframe(pd.DataFrame(variance_data), use_container_width=True, hide_index=True)


# =========================================================
# PAGE 1: MASTER STOCK LIST
# =========================================================
if page == "Master Stock List":
    if "stock_mode" not in st.session_state:
        st.session_state.stock_mode = "list"

    title_col, btn1 = st.columns([7, 2])
    with title_col:
        st.title("Master stock list")
    with btn1:
        if st.button("Add New Ingredient", type="primary", use_container_width=True):
            st.session_state.stock_mode = "add"
            st.rerun()

    if st.session_state.stock_mode != "list":
        if st.button("← Back to list"):
            st.session_state.stock_mode = "list"
            st.rerun()
        st.write("")

    # ---------------- LIST VIEW ----------------
    if st.session_state.stock_mode == "list":
        st.caption("Every raw ingredient, its current price, and its cost per recipe unit. Click a name to edit it.")

        conn = db.get_connection()
        ingredients = conn.execute("""
            SELECT i.*, s1.name AS primary_supplier_name, s2.name AS backup_supplier_name
            FROM ingredients i
            LEFT JOIN suppliers s1 ON i.primary_supplier_id = s1.id
            LEFT JOIN suppliers s2 ON i.backup_supplier_id = s2.id
            ORDER BY i.category, i.name
        """).fetchall()
        conn.close()

        if not ingredients:
            st.info("No ingredients yet. Click \"Add New Ingredient\" above to add your first one.")
        else:
            categories = sorted(set(r["category"] or "Uncategorised" for r in ingredients))
            for cat in categories:
                st.subheader(cat)
                cat_rows = [r for r in ingredients if (r["category"] or "Uncategorised") == cat]

                for r in cat_rows:
                    cost = db.cost_per_recipe_unit(r)
                    with st.container(border=True):
                        cols = st.columns([2, 2, 3, 3])
                        with cols[0]:
                            if st.button(r["name"], type="tertiary", key=f"ing_name_{r['id']}"):
                                st.session_state["edit_ingredient_select"] = f"{r['name']} ({r['purchase_size_label']})"
                                st.session_state.stock_mode = "edit"
                                st.rerun()
                        cols[1].write(f"**Supplier:** {r['primary_supplier_name'] or '-'}")
                        cols[2].write(f"**You pay:** ${r['purchase_price']:.2f} for {r['purchase_size_label']}")
                        cols[3].write(f"**Recipes use it in:** {r['recipe_unit_qty']:g}{r['base_unit']} portions, costing ${cost:.3f} each")

                        if r["current_stock_qty"] is not None:
                            display_unit, factor = db.get_order_unit(r["base_unit"])
                            stock_display = r["current_stock_qty"] / factor
                            is_low = r["min_stock_qty"] is not None and r["current_stock_qty"] < r["min_stock_qty"]
                            if is_low:
                                st.error(f"🔴 Low stock: {stock_display:g} {display_unit} on hand (alert set below {r['min_stock_qty'] / factor:g} {display_unit})")
                            else:
                                st.caption(f"📦 Current stock: {stock_display:g} {display_unit} on hand")
            st.caption("(Updated dates shown on the ingredient's own page.)")

    # ---------------- ADD VIEW ----------------
    elif st.session_state.stock_mode == "add":
        st.subheader("Add a new ingredient")
        supplier_options = get_supplier_options()
        UNIT_MAP = {"Kg": ("g", 1000), "g": ("g", 1), "L": ("ml", 1000), "ml": ("ml", 1), "Each": ("each", 1)}

        name = st.text_input("Ingredient name", key="add_ing_name")
        category = st.text_input("Category (e.g. Dairy, Meat, Produce)", key="add_ing_category")

        st.write("**How do you buy this from the supplier?**")
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            pack_qty_input = st.number_input("Pack size", min_value=0.0, step=1.0, help="e.g. 12 for a 12kg bag", key="add_ing_pack_qty")
        with pc2:
            pack_unit_choice = st.selectbox("Pack unit", list(UNIT_MAP.keys()), key="add_ing_pack_unit")
        with pc3:
            container_word = st.text_input("Packaging word (optional)", placeholder="bag, tin, carton...", key="add_ing_container")

        base_unit, factor = UNIT_MAP[pack_unit_choice]
        purchase_price = st.number_input(
            "Total price you pay for ONE pack ($, incl. GST)", min_value=0.0, step=0.01, key="add_ing_price"
        )

        if pack_qty_input > 0 and purchase_price > 0:
            st.info(f"✓ That works out to **${purchase_price / pack_qty_input:.4f} per {pack_unit_choice}** — check this looks right before saving.")

        st.write("**How much does one recipe usually use at a time?**")
        default_portion = 1.0 if base_unit == "each" else 100.0
        recipe_unit_qty = st.number_input(
            f"Recipe portion size, in {base_unit}", min_value=0.0, step=1.0, value=default_portion,
            help=f"e.g. {default_portion:g} if a recipe typically uses {default_portion:g}{base_unit} of this at a time",
            key="add_ing_recipe_unit"
        )
        if pack_qty_input > 0 and purchase_price > 0 and recipe_unit_qty > 0:
            cost_per_portion = (purchase_price / (pack_qty_input * factor)) * recipe_unit_qty
            st.caption(f"= ${cost_per_portion:.4f} per {recipe_unit_qty:g}{base_unit} recipe portion")

        st.write("**Low stock alert (optional — leave at 0 to skip for now)**")
        min_stock_input = st.number_input(
            f"Alert me when stock drops below this many {pack_unit_choice}",
            min_value=0.0, step=1.0, key="add_ing_min_stock"
        )

        col4, col5 = st.columns(2)
        with col4:
            primary_supplier_name = st.selectbox("Primary supplier", list(supplier_options.keys()), key="add_ing_primary_sup")
        with col5:
            backup_supplier_name = st.selectbox("Backup supplier", list(supplier_options.keys()), key="add_ing_backup_sup")

        if st.button("Add ingredient", type="primary"):
            if not name:
                st.error("Please enter an ingredient name.")
            elif pack_qty_input <= 0 or purchase_price <= 0:
                st.error("Pack size and price must be greater than zero.")
            else:
                purchase_qty = pack_qty_input * factor
                purchase_size_label = f"{pack_qty_input:g}{pack_unit_choice}" + (f" {container_word}" if container_word else "")
                min_stock_qty = (min_stock_input * factor) if min_stock_input > 0 else None
                conn = db.get_connection()
                conn.execute("""
                    INSERT INTO ingredients
                        (name, category, primary_supplier_id, backup_supplier_id,
                         purchase_size_label, purchase_qty, base_unit, purchase_price,
                         recipe_unit_qty, min_stock_qty, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, category,
                    supplier_options[primary_supplier_name],
                    supplier_options[backup_supplier_name],
                    purchase_size_label, purchase_qty, base_unit, purchase_price,
                    recipe_unit_qty, min_stock_qty, date.today().isoformat()
                ))
                conn.commit()
                conn.close()
                db.get_cached_ingredients_basic.clear()
                st.success(f"Added {name} to the master stock list.")
                st.session_state.stock_mode = "list"
                st.rerun()

    # ---------------- EDIT VIEW (Update + Delete both live here) ----------------
    elif st.session_state.stock_mode == "edit":
        st.subheader("Edit ingredient")

        conn = db.get_connection()
        all_ingredients = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
        conn.close()

        if not all_ingredients:
            st.info("No ingredients to edit yet.")
        else:
            ingredient_labels = {f"{r['name']} ({r['purchase_size_label']})": r["id"] for r in all_ingredients}
            selected_label = st.selectbox("Ingredient", list(ingredient_labels.keys()), key="edit_ingredient_select")
            selected_id = ingredient_labels[selected_label]

            conn = db.get_connection()
            current = conn.execute("SELECT * FROM ingredients WHERE id = ?", (selected_id,)).fetchone()
            conn.close()

            supplier_options = get_supplier_options()
            supplier_keys = list(supplier_options.keys())

            def _key_for_supplier_id(sid):
                for k, v in supplier_options.items():
                    if v == sid:
                        return k
                return "-- none --"

            UNIT_MAP = {"Kg": ("g", 1000), "g": ("g", 1), "L": ("ml", 1000), "ml": ("ml", 1), "Each": ("each", 1)}

            # Pick a sensible default display unit + pack quantity for editing,
            # based on what's actually stored (e.g. 12000g displays as 12 Kg).
            def _default_pack_display(stored_base_unit, stored_qty):
                if stored_base_unit == "g":
                    return ("Kg", stored_qty / 1000) if stored_qty >= 1000 else ("g", stored_qty)
                if stored_base_unit == "ml":
                    return ("L", stored_qty / 1000) if stored_qty >= 1000 else ("ml", stored_qty)
                return ("Each", stored_qty)

            default_unit, default_pack_qty = _default_pack_display(current["base_unit"], current["purchase_qty"] or 0)

            e_name = st.text_input("Ingredient name", value=current["name"], key=f"edit_ing_name_{selected_id}")
            e_category = st.text_input("Category", value=current["category"] or "", key=f"edit_ing_category_{selected_id}")

            st.write("**How do you buy this from the supplier?**")
            pc1, pc2, pc3 = st.columns(3)
            with pc1:
                e_pack_qty_input = st.number_input(
                    "Pack size", min_value=0.0, step=1.0, value=float(default_pack_qty), key=f"edit_ing_pack_qty_{selected_id}"
                )
            with pc2:
                unit_keys = list(UNIT_MAP.keys())
                e_pack_unit_choice = st.selectbox(
                    "Pack unit", unit_keys, index=unit_keys.index(default_unit), key=f"edit_ing_pack_unit_{selected_id}"
                )
            with pc3:
                # Best-effort extraction of the packaging word from the existing label (e.g. "12kg bag" -> "bag")
                existing_words = (current["purchase_size_label"] or "").split()
                guessed_container = existing_words[-1] if len(existing_words) > 1 else ""
                e_container_word = st.text_input(
                    "Packaging word (optional)", value=guessed_container, placeholder="bag, tin, carton...",
                    key=f"edit_ing_container_{selected_id}"
                )

            e_base_unit, e_factor = UNIT_MAP[e_pack_unit_choice]
            e_purchase_price = st.number_input(
                "Total price you pay for ONE pack ($, incl. GST)", min_value=0.0, step=0.01,
                value=float(current["purchase_price"] or 0), key=f"edit_ing_price_{selected_id}"
            )

            if e_pack_qty_input > 0 and e_purchase_price > 0:
                st.info(f"✓ That works out to **${e_purchase_price / e_pack_qty_input:.4f} per {e_pack_unit_choice}** — check this looks right before saving.")

            st.write("**How much does one recipe usually use at a time?**")
            e_recipe_unit_qty = st.number_input(
                f"Recipe portion size, in {e_base_unit}", min_value=0.0, step=1.0,
                value=float(current["recipe_unit_qty"] or 100), key=f"edit_ing_recipe_unit_{selected_id}"
            )
            if e_pack_qty_input > 0 and e_purchase_price > 0 and e_recipe_unit_qty > 0:
                cost_per_portion = (e_purchase_price / (e_pack_qty_input * e_factor)) * e_recipe_unit_qty
                st.caption(f"= ${cost_per_portion:.4f} per {e_recipe_unit_qty:g}{e_base_unit} recipe portion")

            st.write("**Low stock alert (leave at 0 to turn off)**")
            existing_min = current["min_stock_qty"]
            e_min_stock_input = st.number_input(
                f"Alert me when stock drops below this many {e_pack_unit_choice}",
                min_value=0.0, step=1.0,
                value=float(existing_min / e_factor) if existing_min else 0.0,
                key=f"edit_ing_min_stock_{selected_id}"
            )

            st.write("**Current stock on hand**")
            st.caption("This is the running total the app tracks automatically (from sales and stock takes). Only change this directly if you know it's wrong.")
            existing_stock = current["current_stock_qty"]
            e_current_stock_input = st.number_input(
                f"Current stock, in {e_pack_unit_choice}",
                min_value=0.0, step=1.0,
                value=float(existing_stock / e_factor) if existing_stock is not None else 0.0,
                key=f"edit_ing_current_stock_{selected_id}"
            )

            col4, col5 = st.columns(2)
            with col4:
                e_primary = st.selectbox(
                    "Primary supplier", supplier_keys,
                    index=supplier_keys.index(_key_for_supplier_id(current["primary_supplier_id"])),
                    key=f"edit_ing_primary_{selected_id}"
                )
            with col5:
                e_backup = st.selectbox(
                    "Backup supplier", supplier_keys,
                    index=supplier_keys.index(_key_for_supplier_id(current["backup_supplier_id"])),
                    key=f"edit_ing_backup_{selected_id}"
                )

            if st.button("Update ingredient", type="primary", key=f"update_ing_btn_{selected_id}"):
                if not e_name:
                    st.error("Ingredient name can't be empty.")
                elif e_pack_qty_input <= 0 or e_purchase_price <= 0:
                    st.error("Pack size and price must be greater than zero.")
                else:
                    e_purchase_qty = e_pack_qty_input * e_factor
                    e_size_label = f"{e_pack_qty_input:g}{e_pack_unit_choice}" + (f" {e_container_word}" if e_container_word else "")
                    e_min_stock_qty = (e_min_stock_input * e_factor) if e_min_stock_input > 0 else None
                    e_current_stock_qty = e_current_stock_input * e_factor
                    conn = db.get_connection()
                    conn.execute("""
                        UPDATE ingredients
                        SET name=?, category=?, primary_supplier_id=?, backup_supplier_id=?,
                            purchase_size_label=?, purchase_qty=?, base_unit=?, purchase_price=?,
                            recipe_unit_qty=?, min_stock_qty=?, current_stock_qty=?, last_updated=?
                        WHERE id=?
                    """, (
                        e_name, e_category,
                        supplier_options[e_primary], supplier_options[e_backup],
                        e_size_label, e_purchase_qty, e_base_unit, e_purchase_price,
                        e_recipe_unit_qty, e_min_stock_qty, e_current_stock_qty, date.today().isoformat(), selected_id
                    ))
                    conn.commit()
                    conn.close()
                    db.get_cached_ingredients_basic.clear()
                    st.success(f"Updated {e_name}.")
                    st.session_state.stock_mode = "list"
                    st.rerun()

            st.write("")
            st.write("**Delete this ingredient**")
            conn = db.get_connection()
            used_in_recipes = conn.execute(
                "SELECT COUNT(*) AS c FROM recipe_lines WHERE ingredient_id = ?", (selected_id,)
            ).fetchone()["c"]
            used_in_stock_takes = conn.execute(
                "SELECT COUNT(*) AS c FROM stock_takes WHERE ingredient_id = ?", (selected_id,)
            ).fetchone()["c"]
            conn.close()

            if used_in_recipes > 0:
                st.error(f"Can't delete — this ingredient is used in {used_in_recipes} recipe line(s). Remove it from those recipes first.")
            else:
                if used_in_stock_takes > 0:
                    st.caption(f"Note: this ingredient has {used_in_stock_takes} past stock take record(s), which will also be removed.")
                if st.button("Delete this ingredient", key=f"delete_ing_{selected_id}"):
                    conn = db.get_connection()
                    conn.execute("DELETE FROM ingredients WHERE id=?", (selected_id,))
                    conn.commit()
                    conn.close()
                    db.get_cached_ingredients_basic.clear()
                    st.success(f"Deleted {current['name']}.")
                    st.session_state.stock_mode = "list"
                    st.rerun()


# =========================================================
# PAGE 2: RECIPES
# =========================================================
elif page == "Recipes":
    TYPE_EMOJI = {"Prep": "🥣", "Dish": "🍽️", "Beverage": "🥤"}
    TYPE_COLOR = {"Prep": "#2563EB", "Dish": "#F2722D", "Beverage": "#7C3AED"}

    def recipe_options(type_filter=None, category_filter=None, exclude_id=None):
        conn = db.get_connection()
        query = "SELECT id, name FROM recipes"
        clauses, params = [], []
        if type_filter:
            clauses.append("type = ?")
            params.append(type_filter)
        if category_filter is not None:
            clauses.append("category_id = ?")
            params.append(category_filter)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY name"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return {r["name"]: r["id"] for r in rows if r["id"] != exclude_id}

    def render_category_image_or_placeholder(image_url, rtype, height_px=140):
        if image_url:
            st.image(image_url, use_container_width=True)
        else:
            color = TYPE_COLOR.get(rtype, "#999999")
            emoji = TYPE_EMOJI.get(rtype, "🍴")
            st.markdown(
                f"""<div style="height:{height_px}px; border-radius: 0.5rem; background: {color}1A;
                     display:flex; align-items:center; justify-content:center; margin-bottom: 0.5rem;
                     font-size: 48px;">{emoji}</div>""",
                unsafe_allow_html=True
            )

    if "recipe_mode" not in st.session_state:
        st.session_state.recipe_mode = "categories"
    if "recipe_active_type" not in st.session_state:
        st.session_state.recipe_active_type = "Prep"

    st.title("Recipes")

    search_text = st.text_input(
        "Search recipes", key="recipe_search", label_visibility="collapsed",
        placeholder="Search all recipes by name..."
    )

    if st.session_state.recipe_mode != "categories":
        if st.button("← Back"):
            if st.session_state.recipe_mode in ("add_recipe", "edit_recipe", "edit_category", "remove_category"):
                st.session_state.recipe_mode = "category_detail"
            else:
                st.session_state.recipe_mode = "categories"
            st.rerun()
        st.write("")

    # ======================================================
    # CATEGORIES GRID (top level) -- or search results, if searching
    # ======================================================
    if st.session_state.recipe_mode == "categories" and search_text.strip():
        conn = db.get_connection()
        results = conn.execute("""
            SELECT r.*, rc.name AS category_name
            FROM recipes r
            LEFT JOIN recipe_categories rc ON r.category_id = rc.id
            WHERE r.name ILIKE ?
            ORDER BY r.type, r.name
        """, (f"%{search_text.strip()}%",)).fetchall()
        conn.close()

        if not results:
            st.info(f"No recipes match \"{search_text}\".")
        else:
            st.caption(f"{len(results)} recipe(s) match \"{search_text}\" — click a name to edit it.")
            for r in results:
                cost = db.compute_recipe_cost(r["id"])
                with st.container(border=True):
                    cols = st.columns([3, 2, 3, 2])
                    with cols[0]:
                        if st.button(r["name"], type="tertiary", key=f"search_recipe_{r['id']}"):
                            st.session_state["edit_recipe_select"] = r["name"]
                            st.session_state.recipe_active_category_id = r["category_id"]
                            st.session_state.recipe_mode = "edit_recipe"
                            st.rerun()
                    cols[1].write(f"**Type:** {r['type']}")
                    cols[2].write(f"**Category:** {r['category_name'] or '-'}")
                    cols[3].write(f"**Cost:** ${cost:.2f}")

    elif st.session_state.recipe_mode == "categories":
        type_tabs = st.tabs(["Prep", "Dish", "Beverage"])
        for tab, rtype in zip(type_tabs, ["Prep", "Dish", "Beverage"]):
            with tab:
                top_col1, top_col2 = st.columns([8, 3])
                with top_col2:
                    if st.button("New Category", type="primary", use_container_width=True, key=f"newcat_{rtype}"):
                        st.session_state.recipe_active_type = rtype
                        st.session_state.recipe_mode = "add_category"
                        st.rerun()

                conn = db.get_connection()
                categories = conn.execute(
                    "SELECT * FROM recipe_categories WHERE type = ? ORDER BY name", (rtype,)
                ).fetchall()
                counts = {}
                for c in categories:
                    counts[c["id"]] = conn.execute(
                        "SELECT COUNT(*) AS n FROM recipes WHERE category_id = ?", (c["id"],)
                    ).fetchone()["n"]
                conn.close()

                if not categories:
                    st.info(f"No {rtype} categories yet. Click \"+ New Category\" to create one (e.g. \"Coffee Preps\", \"Pasta\").")
                else:
                    cards_per_row = 3
                    for i in range(0, len(categories), cards_per_row):
                        row_cats = categories[i:i + cards_per_row]
                        row_cols = st.columns(cards_per_row)
                        for col, cat in zip(row_cols, row_cats):
                            with col:
                                with st.container(border=True):
                                    render_category_image_or_placeholder(cat["image_url"], rtype)
                                    if st.button(cat["name"], type="tertiary", key=f"cat_open_{cat['id']}"):
                                        st.session_state.recipe_active_category_id = cat["id"]
                                        st.session_state.recipe_active_type = rtype
                                        st.session_state.recipe_mode = "category_detail"
                                        st.rerun()
                                    n = counts[cat["id"]]
                                    st.caption(f"{n} recipe{'s' if n != 1 else ''}")

    # ======================================================
    # ADD CATEGORY
    # ======================================================
    elif st.session_state.recipe_mode == "add_category":
        rtype = st.session_state.recipe_active_type
        st.subheader(f"New {rtype} Category")

        cat_name = st.text_input("Category Name", placeholder="What's the name of this category?")
        uploaded_image = st.file_uploader("Recipe Category Image (optional)", type=["png", "jpg", "jpeg"])

        if st.button("Submit", type="primary"):
            if not cat_name:
                st.error("Please enter a category name.")
            else:
                image_url = None
                if uploaded_image is not None:
                    if "SUPABASE_URL" not in st.secrets or "SUPABASE_SERVICE_KEY" not in st.secrets:
                        st.warning("Image upload isn't set up yet (missing Supabase Storage secrets) — saving the category without an image for now.")
                    else:
                        image_url = db.upload_category_image(
                            uploaded_image.getvalue(), uploaded_image.name, uploaded_image.type
                        )
                        if image_url is None:
                            st.warning("Image upload failed — saving the category without an image for now.")

                conn = db.get_connection()
                conn.execute(
                    "INSERT INTO recipe_categories (name, type, image_url, created_at) VALUES (?, ?, ?, ?)",
                    (cat_name, rtype, image_url, date.today().isoformat())
                )
                conn.commit()
                conn.close()
                st.success(f"Created category \"{cat_name}\".")
                st.session_state.recipe_mode = "categories"
                st.rerun()

    # ======================================================
    # CATEGORY DETAIL (recipes within one category)
    # ======================================================
    elif st.session_state.recipe_mode == "category_detail":
        cat_id = st.session_state.recipe_active_category_id
        conn = db.get_connection()
        category = conn.execute("SELECT * FROM recipe_categories WHERE id = ?", (cat_id,)).fetchone()
        conn.close()

        if category is None:
            st.error("This category no longer exists.")
            st.session_state.recipe_mode = "categories"
            st.stop()

        rtype = category["type"]
        head_col1, head_col2, head_col3, head_col4 = st.columns([5, 2, 2, 2])
        with head_col1:
            st.subheader(category["name"])
            st.caption(f"{rtype} category")
        with head_col2:
            if st.button("Add New Recipe", type="primary", use_container_width=True):
                st.session_state.recipe_mode = "add_recipe"
                st.rerun()
        with head_col3:
            if st.button("Edit Category", use_container_width=True):
                st.session_state.recipe_mode = "edit_category"
                st.rerun()
        with head_col4:
            if st.button("Remove Category", use_container_width=True):
                st.session_state.recipe_mode = "remove_category"
                st.rerun()

        st.caption("Click a recipe name to edit it. Costs shown include 9% GST.")

        conn = db.get_connection()
        recipes_in_cat = conn.execute(
            "SELECT * FROM recipes WHERE category_id = ? ORDER BY name", (cat_id,)
        ).fetchall()
        conn.close()

        if not recipes_in_cat:
            st.info("No recipes in this category yet. Click \"+ Add New Recipe\" above.")
        else:
            for r in recipes_in_cat:
                cost = db.compute_recipe_cost(r["id"])
                with st.container(border=True):
                    cols = st.columns([3, 2, 2, 2])
                    with cols[0]:
                        if st.button(r["name"], type="tertiary", key=f"recipe_name_{r['id']}"):
                            st.session_state["edit_recipe_select"] = r["name"]
                            st.session_state.recipe_mode = "edit_recipe"
                            st.rerun()
                    if rtype == "Prep":
                        cols[1].write(f"**Yields:** {r['yield_qty']:g}{r['yield_unit']}" if r["yield_qty"] else "**Yields:** -")
                        cols[2].write(f"**Batch cost:** ${cost:.2f}")
                        cols[3].write(f"**Cost/unit:** ${cost / r['yield_qty']:.4f}" if r["yield_qty"] else "**Cost/unit:** -")
                    else:
                        cols[1].write(f"**Food cost:** ${cost:.2f}")
                        if r["selling_price"]:
                            pct = cost / r["selling_price"] * 100
                            status = db.food_cost_status(pct)
                            badge = {"ok": "🟢", "warning": "🟡", "alert": "🔴"}[status]
                            cols[2].write(f"**Food cost %:** {badge} {pct:.1f}%")
                            cols[3].write(f"**Selling price:** ${r['selling_price']:.2f}")
                        else:
                            cols[2].write("**Food cost %:** -")
                            cols[3].write("**Selling price:** Not set")

    # ======================================================
    # EDIT CATEGORY
    # ======================================================
    elif st.session_state.recipe_mode == "edit_category":
        cat_id = st.session_state.recipe_active_category_id
        conn = db.get_connection()
        category = conn.execute("SELECT * FROM recipe_categories WHERE id = ?", (cat_id,)).fetchone()
        conn.close()

        st.subheader(f"Edit Category: {category['name']}")
        new_name = st.text_input("Category Name", value=category["name"])
        st.caption("Current image:")
        render_category_image_or_placeholder(category["image_url"], category["type"], height_px=100)
        uploaded_image = st.file_uploader("Replace image (optional)", type=["png", "jpg", "jpeg"])

        if st.button("Save changes", type="primary"):
            if not new_name:
                st.error("Category name can't be empty.")
            else:
                image_url = category["image_url"]
                if uploaded_image is not None and "SUPABASE_URL" in st.secrets and "SUPABASE_SERVICE_KEY" in st.secrets:
                    new_url = db.upload_category_image(uploaded_image.getvalue(), uploaded_image.name, uploaded_image.type)
                    if new_url:
                        image_url = new_url
                conn = db.get_connection()
                conn.execute(
                    "UPDATE recipe_categories SET name = ?, image_url = ? WHERE id = ?",
                    (new_name, image_url, cat_id)
                )
                conn.commit()
                conn.close()
                st.success("Updated.")
                st.session_state.recipe_mode = "category_detail"
                st.rerun()

    # ======================================================
    # REMOVE CATEGORY
    # ======================================================
    elif st.session_state.recipe_mode == "remove_category":
        cat_id = st.session_state.recipe_active_category_id
        conn = db.get_connection()
        category = conn.execute("SELECT * FROM recipe_categories WHERE id = ?", (cat_id,)).fetchone()
        recipe_count = conn.execute("SELECT COUNT(*) AS c FROM recipes WHERE category_id = ?", (cat_id,)).fetchone()["c"]
        conn.close()

        st.subheader(f"Remove Category: {category['name']}")
        if recipe_count > 0:
            st.error(f"Can't delete — this category still has {recipe_count} recipe(s) in it. Move or remove those first.")
        else:
            st.warning(f"This will permanently delete the \"{category['name']}\" category.")
            if st.button("Confirm delete", type="primary"):
                conn = db.get_connection()
                conn.execute("DELETE FROM recipe_categories WHERE id = ?", (cat_id,))
                conn.commit()
                conn.close()
                st.success("Deleted.")
                st.session_state.recipe_mode = "categories"
                st.rerun()

    # ======================================================
    # ADD RECIPE (within a category)
    # ======================================================
    elif st.session_state.recipe_mode == "add_recipe":
        cat_id = st.session_state.recipe_active_category_id
        conn = db.get_connection()
        category = conn.execute("SELECT * FROM recipe_categories WHERE id = ?", (cat_id,)).fetchone()
        conn.close()
        rtype = category["type"]

        st.subheader(f"Add a new recipe to \"{category['name']}\"")

        with st.form("add_recipe_form", clear_on_submit=True):
            r_name = st.text_input("Recipe name")

            col1, col2 = st.columns(2)
            with col1:
                r_yield_qty = st.number_input("Yield quantity (Prep only, e.g. 500)", min_value=0.0, step=1.0)
                r_yield_unit = st.selectbox("Yield unit (Prep only)", ["g", "ml", "each"])
            with col2:
                r_selling_price = st.number_input("Selling price $ (Dish / Beverage only)", min_value=0.0, step=0.01)

            submitted = st.form_submit_button("Add recipe")
            if submitted:
                if not r_name:
                    st.error("Please enter a recipe name.")
                else:
                    conn = db.get_connection()
                    conn.execute("""
                        INSERT INTO recipes (name, type, category_id, yield_qty, yield_unit, selling_price)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        r_name, rtype, cat_id,
                        r_yield_qty if rtype == "Prep" else None,
                        r_yield_unit if rtype == "Prep" else None,
                        r_selling_price if rtype in ("Dish", "Beverage") else None,
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Added {r_name}. Click its name in the list to add ingredients.")
                    st.session_state.recipe_mode = "category_detail"
                    st.rerun()

    # ======================================================
    # EDIT RECIPE
    # ======================================================
    elif st.session_state.recipe_mode == "edit_recipe":
        st.subheader("Edit a recipe")

        all_recipe_options = recipe_options()
        if not all_recipe_options:
            st.info("Add a recipe first, then come back here to edit it.")
        else:
            selected_recipe_name = st.selectbox("Choose a recipe", list(all_recipe_options.keys()), key="edit_recipe_select")
            selected_recipe_id = all_recipe_options[selected_recipe_name]

            conn = db.get_connection()
            recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (selected_recipe_id,)).fetchone()
            lines = conn.execute("""
                SELECT rl.*, i.name AS ingredient_name, i.base_unit AS ingredient_unit,
                       sr.name AS sub_recipe_name, sr.yield_unit AS sub_recipe_unit
                FROM recipe_lines rl
                LEFT JOIN ingredients i ON rl.ingredient_id = i.id
                LEFT JOIN recipes sr ON rl.sub_recipe_id = sr.id
                WHERE rl.parent_recipe_id = ?
            """, (selected_recipe_id,)).fetchall()
            conn.close()

            # ---- Recipe details (name, production, portions) ----
            st.write("**Recipe details**")
            with st.form(f"edit_recipe_details_{selected_recipe_id}"):
                e_name = st.text_input("Recipe name", value=recipe["name"])
                if recipe["type"] == "Prep":
                    col1, col2 = st.columns(2)
                    with col1:
                        e_yield_qty = st.number_input("Production Quantity", min_value=0.0, step=1.0, value=float(recipe["yield_qty"] or 0))
                    with col2:
                        unit_choices = ["g", "ml", "each"]
                        e_yield_unit = st.selectbox(
                            "UOM", unit_choices,
                            index=unit_choices.index(recipe["yield_unit"]) if recipe["yield_unit"] in unit_choices else 0
                        )
                    e_selling_price = None
                    e_portions = None
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        e_selling_price = st.number_input("Selling price $", min_value=0.0, step=0.01, value=float(recipe["selling_price"] or 0))
                    with col2:
                        e_portions = st.number_input(
                            "No. of Portions (optional)", min_value=0.0, step=1.0,
                            value=float(recipe["portions"] or 0),
                            help="Leave at 0 if this recipe is already defined as a single serving."
                        )
                    e_yield_qty, e_yield_unit = None, None

                details_submitted = st.form_submit_button("Update recipe details")
                if details_submitted:
                    if not e_name:
                        st.error("Recipe name can't be empty.")
                    else:
                        conn = db.get_connection()
                        conn.execute(
                            "UPDATE recipes SET name=?, yield_qty=?, yield_unit=?, selling_price=?, portions=? WHERE id=?",
                            (e_name, e_yield_qty, e_yield_unit, e_selling_price,
                             e_portions if e_portions and e_portions > 0 else None, selected_recipe_id)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Updated {e_name}.")
                        st.rerun()

            # ---- Tags ----
            st.write("**Tags**")
            conn = db.get_connection()
            all_tag_rows = conn.execute("SELECT tags FROM recipes WHERE tags IS NOT NULL AND tags != ''").fetchall()
            conn.close()
            all_known_tags = sorted(set(
                t.strip() for row in all_tag_rows for t in row["tags"].split(",") if t.strip()
            ))
            current_tags = [t.strip() for t in (recipe["tags"] or "").split(",") if t.strip()]

            tag_col1, tag_col2 = st.columns([3, 2])
            with tag_col1:
                chosen_tags = st.multiselect(
                    "Selected tags", options=sorted(set(all_known_tags) | set(current_tags)),
                    default=current_tags, key=f"tags_select_{selected_recipe_id}"
                )
            with tag_col2:
                new_tag = st.text_input("Or add a new tag", key=f"new_tag_{selected_recipe_id}")

            if st.button("Save tags", key=f"save_tags_{selected_recipe_id}"):
                final_tags = list(chosen_tags)
                if new_tag.strip() and new_tag.strip() not in final_tags:
                    final_tags.append(new_tag.strip())
                conn = db.get_connection()
                conn.execute("UPDATE recipes SET tags = ? WHERE id = ?", (", ".join(final_tags), selected_recipe_id))
                conn.commit()
                conn.close()
                st.success("Tags saved.")
                st.rerun()

            # ---- Conversions ----
            st.write("**Conversions**")
            conn = db.get_connection()
            conversions = conn.execute("SELECT * FROM recipe_conversions WHERE recipe_id = ?", (selected_recipe_id,)).fetchall()
            conn.close()

            if conversions:
                for conv in conversions:
                    cv_col1, cv_col2 = st.columns([5, 1])
                    cv_col1.write(f"{conv['from_qty']:g} {conv['from_unit']} = {conv['to_qty']:g} {conv['to_unit']}")
                    if cv_col2.button("Remove", key=f"remove_conv_{conv['id']}"):
                        conn = db.get_connection()
                        conn.execute("DELETE FROM recipe_conversions WHERE id = ?", (conv["id"],))
                        conn.commit()
                        conn.close()
                        st.rerun()
            else:
                st.caption("No conversions defined yet (e.g. \"1 Shot = 30 ml\").")

            with st.form(f"add_conversion_{selected_recipe_id}", clear_on_submit=True):
                cf1, cf2, cf3, cf4 = st.columns(4)
                with cf1:
                    conv_from_qty = st.number_input("Quantity", min_value=0.0, step=1.0, value=1.0, key=f"conv_fq_{selected_recipe_id}")
                with cf2:
                    conv_from_unit = st.text_input("Unit", placeholder="e.g. Shot", key=f"conv_fu_{selected_recipe_id}")
                with cf3:
                    conv_to_qty = st.number_input("Equals", min_value=0.0, step=1.0, key=f"conv_tq_{selected_recipe_id}")
                with cf4:
                    conv_to_unit = st.selectbox("In unit", ["g", "ml", "each"], key=f"conv_tu_{selected_recipe_id}")

                if st.form_submit_button("+ Add item"):
                    if not conv_from_unit or conv_from_qty <= 0 or conv_to_qty <= 0:
                        st.error("Please fill in all conversion fields with values greater than zero.")
                    else:
                        conn = db.get_connection()
                        conn.execute(
                            "INSERT INTO recipe_conversions (recipe_id, from_qty, from_unit, to_qty, to_unit) VALUES (?, ?, ?, ?, ?)",
                            (selected_recipe_id, conv_from_qty, conv_from_unit.strip(), conv_to_qty, conv_to_unit)
                        )
                        conn.commit()
                        conn.close()
                        st.success("Conversion added.")
                        st.rerun()

            st.markdown("---")
            st.write(f"**Current ingredients in {recipe['name']}:**")
            if not lines:
                st.write("No ingredients added yet.")
            else:
                conn = db.get_connection()
                for line in lines:
                    line_cost = db.compute_line_cost(line, conn)
                    if line["ingredient_id"] is not None:
                        label = f"{line['ingredient_name']} — {line['quantity']:g}{line['ingredient_unit']}"
                    else:
                        label = f"{line['sub_recipe_name']} (Prep) — {line['quantity']:g}{line['sub_recipe_unit']}"
                    row_col1, row_col2, row_col3 = st.columns([4, 2, 1])
                    row_col1.write(label)
                    row_col2.write(f"${line_cost:.3f}")
                    if row_col3.button("Remove", key=f"remove_line_{line['id']}"):
                        conn.execute("DELETE FROM recipe_lines WHERE id = ?", (line["id"],))
                        conn.commit()
                        conn.close()
                        st.rerun()
                conn.close()

            # Live cost summary
            live_cost = db.compute_recipe_cost(selected_recipe_id)
            if recipe["type"] == "Prep":
                st.info(
                    f"Batch cost (incl. 9% GST): ${live_cost:.2f}  |  "
                    f"Cost per {recipe['yield_unit']}: "
                    f"${(live_cost / recipe['yield_qty']) if recipe['yield_qty'] else 0:.4f}"
                )
            else:
                if recipe["selling_price"]:
                    pct = live_cost / recipe["selling_price"] * 100
                    status = db.food_cost_status(pct)
                    badge = {"ok": "🟢", "warning": "🟡", "alert": "🔴"}[status]
                    st.info(f"Total cost (incl. 9% GST): ${live_cost:.2f}  |  Selling price: ${recipe['selling_price']:.2f}  |  {badge} **{pct:.1f}% food cost**")
                    if status == "alert":
                        st.error("⚠️ This recipe is at or above the 30% food cost alert threshold.")
                    elif status == "warning":
                        st.warning("This recipe is above the 25% target food cost.")
                else:
                    st.info(f"Total cost (incl. 9% GST): ${live_cost:.2f}  |  No selling price set yet.")

                if recipe["portions"] and recipe["portions"] > 0:
                    st.caption(f"Cost per portion (÷ {recipe['portions']:g} portions): ${live_cost / recipe['portions']:.3f}")

            st.write("**Add an ingredient or Prep recipe to this:**")
            component_type_choices = ["Raw ingredient"]
            if recipe["type"] in ("Dish", "Beverage"):
                component_type_choices.append("Prep recipe")

            component_type = st.radio("Component type", component_type_choices, horizontal=True, key=f"comp_type_{selected_recipe_id}")

            if component_type == "Raw ingredient":
                ing_rows = db.get_cached_ingredients_basic()
                ing_labels = {f"{r['name']} ({r['base_unit']})": (r["id"], r["base_unit"]) for r in ing_rows}
                if ing_labels:
                    chosen_label = st.selectbox(
                        "Ingredient", list(ing_labels.keys()),
                        key=f"add_line_ingredient_{selected_recipe_id}"
                    )
                    chosen_id, chosen_unit = ing_labels[chosen_label]
                    qty = st.number_input(
                        f"Quantity used ({chosen_unit})", min_value=0.0, step=1.0,
                        key=f"add_line_qty_ingredient_{selected_recipe_id}"
                    )
                else:
                    st.write("No ingredients in your Master Stock List yet.")
                    chosen_id, qty = None, 0
            else:
                prep_options = recipe_options(type_filter="Prep", exclude_id=selected_recipe_id)
                if prep_options:
                    chosen_label = st.selectbox(
                        "Prep recipe", list(prep_options.keys()),
                        key=f"add_line_prep_{selected_recipe_id}"
                    )
                    chosen_id = prep_options[chosen_label]
                    conn = db.get_connection()
                    prep_unit = conn.execute("SELECT yield_unit FROM recipes WHERE id = ?", (chosen_id,)).fetchone()["yield_unit"]
                    prep_conversions = conn.execute(
                        "SELECT DISTINCT from_unit FROM recipe_conversions WHERE recipe_id = ?", (chosen_id,)
                    ).fetchall()
                    conn.close()

                    unit_options = [prep_unit] + [c["from_unit"] for c in prep_conversions]
                    entry_unit = st.selectbox(
                        "Enter quantity in", unit_options,
                        key=f"add_line_prep_unit_{selected_recipe_id}"
                    )
                    qty_entered = st.number_input(
                        f"Quantity used ({entry_unit})", min_value=0.0, step=1.0,
                        key=f"add_line_qty_prep_{selected_recipe_id}"
                    )
                    qty = db.convert_to_base_unit(chosen_id, qty_entered, entry_unit, prep_unit)
                    if entry_unit != prep_unit and qty_entered > 0:
                        st.caption(f"= {qty:g}{prep_unit}")
                else:
                    st.write("No Prep recipes available yet.")
                    chosen_id, qty = None, 0

            line_submitted = st.button("Add to recipe", key=f"add_line_submit_{selected_recipe_id}")
            if line_submitted:
                if not chosen_id or qty <= 0:
                    st.error("Please choose a component and enter a quantity greater than zero.")
                else:
                    conn = db.get_connection()
                    if component_type == "Raw ingredient":
                        conn.execute(
                            "INSERT INTO recipe_lines (parent_recipe_id, ingredient_id, quantity) VALUES (?, ?, ?)",
                            (selected_recipe_id, chosen_id, qty)
                        )
                    else:
                        conn.execute(
                            "INSERT INTO recipe_lines (parent_recipe_id, sub_recipe_id, quantity) VALUES (?, ?, ?)",
                            (selected_recipe_id, chosen_id, qty)
                        )
                    conn.commit()
                    conn.close()
                    st.success("Added.")
                    st.rerun()

            st.write("")
            st.write("**Delete this recipe**")
            conn = db.get_connection()
            used_elsewhere = conn.execute(
                "SELECT COUNT(*) AS c FROM recipe_lines WHERE sub_recipe_id = ?", (selected_recipe_id,)
            ).fetchone()["c"]
            conn.close()

            if used_elsewhere > 0:
                st.error(f"Can't delete — this Prep is used in {used_elsewhere} other recipe(s). Remove it from those first.")
            else:
                if st.button("Delete this recipe", key=f"delete_recipe_{selected_recipe_id}"):
                    conn = db.get_connection()
                    conn.execute("DELETE FROM recipes WHERE id = ?", (selected_recipe_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted {recipe['name']}.")
                    st.session_state.recipe_mode = "category_detail"
                    st.rerun()


# =========================================================
# PAGE 3: SUPPLIERS
# =========================================================
elif page == "Suppliers":
    if "supplier_mode" not in st.session_state:
        st.session_state.supplier_mode = "list"

    title_col, btn1 = st.columns([7, 2])
    with title_col:
        st.title("Suppliers")
    with btn1:
        if st.button("Add New Supplier", type="primary", use_container_width=True):
            st.session_state.supplier_mode = "add"
            st.rerun()

    if st.session_state.supplier_mode != "list":
        if st.button("← Back to list"):
            st.session_state.supplier_mode = "list"
            st.rerun()
        st.write("")

    # ---------------- LIST VIEW ----------------
    if st.session_state.supplier_mode == "list":
        st.caption("Every supplier you buy from. Click a name to view or edit its details.")

        conn = db.get_connection()
        suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()

        if not suppliers:
            st.info("No suppliers yet. Click \"Add New Supplier\" above to add your first one.")
        else:
            for s in suppliers:
                with st.container(border=True):
                    cols = st.columns([2, 2, 2, 2])
                    with cols[0]:
                        if st.button(s["name"], type="tertiary", key=f"supplier_name_{s['id']}"):
                            st.session_state["edit_supplier_select"] = s["name"]
                            st.session_state.supplier_mode = "edit"
                            st.rerun()
                    cols[1].write(f"**Email:** {s['email'] or '-'}")
                    cols[2].write(f"**Phone:** {s['phone'] or '-'}")
                    cols[3].write(f"**Terms:** {s['payment_terms'] or '-'}")

    # ---------------- ADD VIEW ----------------
    elif st.session_state.supplier_mode == "add":
        st.subheader("Add a new supplier")

        with st.form("add_supplier_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                s_name = st.text_input("Supplier name")
                s_uen = st.text_input("UEN / Tax number")
                s_email = st.text_input("Email")
            with col2:
                s_phone = st.text_input("Contact number")
                s_address = st.text_input("Address")
                s_terms = st.text_input("Payment terms (e.g. Net 30)")
                s_days = st.text_input("Delivery days (e.g. Mon, Thu)")

            submitted = st.form_submit_button("Add supplier")
            if submitted:
                if not s_name:
                    st.error("Please enter a supplier name.")
                else:
                    conn = db.get_connection()
                    conn.execute("""
                        INSERT INTO suppliers (name, uen, email, phone, address, payment_terms, delivery_days)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (s_name, s_uen, s_email, s_phone, s_address, s_terms, s_days))
                    conn.commit()
                    conn.close()
                    st.success(f"Added {s_name}.")
                    st.session_state.supplier_mode = "list"
                    st.rerun()

    # ---------------- EDIT VIEW (Update + Delete both live here) ----------------
    elif st.session_state.supplier_mode == "edit":
        st.subheader("Edit supplier")

        conn = db.get_connection()
        all_suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()

        if not all_suppliers:
            st.info("No suppliers to edit yet.")
        else:
            supplier_labels = {r["name"]: r["id"] for r in all_suppliers}
            chosen_label = st.selectbox("Supplier", list(supplier_labels.keys()), key="edit_supplier_select")
            chosen_id = supplier_labels[chosen_label]
            s = next(r for r in all_suppliers if r["id"] == chosen_id)

            conn = db.get_connection()
            linked = conn.execute("""
                SELECT name, 'Primary' AS role FROM ingredients WHERE primary_supplier_id = ?
                UNION ALL
                SELECT name, 'Backup' AS role FROM ingredients WHERE backup_supplier_id = ?
            """, (s["id"], s["id"])).fetchall()
            conn.close()

            if linked:
                st.write("**Linked ingredients:**")
                for item in linked:
                    st.write(f"- {item['name']} ({item['role']})")
            else:
                st.caption("No ingredients linked to this supplier yet.")

            with st.form(f"edit_supplier_form_{s['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    es_name = st.text_input("Supplier name", value=s["name"])
                    es_uen = st.text_input("UEN / Tax number", value=s["uen"] or "")
                    es_email = st.text_input("Email", value=s["email"] or "")
                with col2:
                    es_phone = st.text_input("Contact number", value=s["phone"] or "")
                    es_address = st.text_input("Address", value=s["address"] or "")
                    es_terms = st.text_input("Payment terms", value=s["payment_terms"] or "")
                    es_days = st.text_input("Delivery days", value=s["delivery_days"] or "")

                upd_submitted = st.form_submit_button("Update supplier")
                if upd_submitted:
                    if not es_name:
                        st.error("Supplier name can't be empty.")
                    else:
                        conn = db.get_connection()
                        conn.execute("""
                            UPDATE suppliers
                            SET name=?, uen=?, email=?, phone=?, address=?, payment_terms=?, delivery_days=?
                            WHERE id=?
                        """, (es_name, es_uen, es_email, es_phone, es_address, es_terms, es_days, s["id"]))
                        conn.commit()
                        conn.close()
                        st.success(f"Updated {es_name}.")
                        st.session_state.supplier_mode = "list"
                        st.rerun()

            st.write("")
            st.write("**Delete this supplier**")
            if linked:
                st.error(f"Can't delete — {len(linked)} ingredient(s) still link to this supplier. Change those ingredients' supplier first.")
            else:
                if st.button("Delete this supplier", key=f"delete_supplier_{s['id']}"):
                    conn = db.get_connection()
                    conn.execute("DELETE FROM suppliers WHERE id=?", (s["id"],))
                    conn.commit()
                    conn.close()
                    st.success(f"Deleted {s['name']}.")
                    st.session_state.supplier_mode = "list"
                    st.rerun()


# =========================================================
# PAGE: ORDERS
# =========================================================
elif page == "Orders":
    if "order_mode" not in st.session_state:
        st.session_state.order_mode = "list"

    title_col, btn1 = st.columns([7, 2])
    with title_col:
        st.title("Orders")
    with btn1:
        if st.button("New Order", icon=":material/add:", type="primary", use_container_width=True):
            st.session_state.order_mode = "new"
            st.rerun()

    if st.session_state.order_mode != "list":
        if st.button("← Back to orders"):
            st.session_state.order_mode = "list"
            st.rerun()
        st.write("")

    # ---------------- LIST VIEW ----------------
    if st.session_state.order_mode == "list":
        st.caption("Past and pending orders to suppliers.")

        conn = db.get_connection()
        all_orders = conn.execute("""
            SELECT o.*, s.name AS supplier_name
            FROM orders o
            JOIN suppliers s ON o.supplier_id = s.id
            ORDER BY o.id DESC
        """).fetchall()
        conn.close()

        if not all_orders:
            st.info("No orders yet. Click \"New Order\" above to create one.")
        else:
            for o in all_orders:
                with st.container(border=True):
                    cols = st.columns([3, 2, 2, 2, 2])
                    cols[0].write(f"**{o['supplier_name']}**")
                    status_badge = {"draft": ("gray", "Draft"), "sent": ("green", "Sent"), "error": ("red", "Error")}
                    color, label = status_badge.get(o["status"], ("gray", o["status"]))
                    with cols[1]:
                        st.badge(label, color=color)
                    cols[2].write(f"**Delivery:** {o['delivery_date'] or 'Not set'}")
                    cols[3].write(f"**Created:** {o['created_at']}")
                    cols[4].write(f"**By:** {o['created_by']}")

                    conn = db.get_connection()
                    order_lines = conn.execute("""
                        SELECT ol.quantity, i.name, i.base_unit
                        FROM order_lines ol JOIN ingredients i ON ol.ingredient_id = i.id
                        WHERE ol.order_id = ?
                    """, (o["id"],)).fetchall()
                    conn.close()

                    with st.expander(f"{len(order_lines)} item(s)"):
                        for line in order_lines:
                            display_unit, factor = db.get_order_unit(line["base_unit"])
                            st.write(f"- {line['name']} — {line['quantity'] / factor:g} {display_unit}")
                        if o["supplier_note"]:
                            st.caption(f"Note to supplier: {o['supplier_note']}")
                        if o["internal_note"]:
                            st.caption(f"Internal note: {o['internal_note']}")

                    if o["status"] == "error" and o["error_message"]:
                        st.warning(f"Last attempt failed: {o['error_message']}")

                    if o["status"] in ("draft", "error"):
                        conn = db.get_connection()
                        supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (o["supplier_id"],)).fetchone()
                        conn.close()
                        message = db.build_order_message(o["id"])

                        wa_link = db.build_whatsapp_link(supplier["phone"], message)
                        email_subject = f"New order from Cafe Manager — {supplier['name']}"

                        link_cols = st.columns(3)
                        with link_cols[0]:
                            if wa_link:
                                st.link_button("Send via WhatsApp", wa_link, use_container_width=True)
                            else:
                                st.caption("No phone number on file for WhatsApp.")
                            if st.button("Mark as sent (WhatsApp)", key=f"mark_sent_{o['id']}"):
                                conn = db.get_connection()
                                conn.execute(
                                    "UPDATE orders SET status='sent', channel='whatsapp', sent_at=? WHERE id=?",
                                    (date.today().isoformat(), o["id"])
                                )
                                conn.commit()
                                db.add_notification(
                                    "info", f"Order to {supplier['name']} marked as sent via WhatsApp.",
                                    order_id=o["id"], created_by=current_user["name"], conn=conn
                                )
                                conn.close()
                                st.success("Marked as sent.")
                                st.rerun()
                        with link_cols[1]:
                            if supplier["email"]:
                                if st.button("Send Email Now", key=f"send_email_{o['id']}", type="primary", use_container_width=True):
                                    with st.spinner("Sending..."):
                                        success, error = db.send_order_email(supplier["email"], email_subject, message)
                                    conn = db.get_connection()
                                    if success:
                                        conn.execute(
                                            "UPDATE orders SET status='sent', channel='email', sent_at=? WHERE id=?",
                                            (date.today().isoformat(), o["id"])
                                        )
                                        conn.commit()
                                        db.add_notification(
                                            "info", f"Order emailed automatically to {supplier['name']} ({supplier['email']}).",
                                            order_id=o["id"], created_by=current_user["name"], conn=conn
                                        )
                                        conn.close()
                                        st.success(f"Email sent to {supplier['email']}.")
                                        st.rerun()
                                    else:
                                        conn.execute(
                                            "UPDATE orders SET status='error', error_message=? WHERE id=?",
                                            (error, o["id"])
                                        )
                                        conn.commit()
                                        db.add_notification(
                                            "error", f"Email to {supplier['name']} failed: {error}",
                                            order_id=o["id"], created_by=current_user["name"], conn=conn
                                        )
                                        conn.close()
                                        st.error(f"Email failed: {error}")
                                        st.rerun()
                            else:
                                st.caption("No email on file for this supplier.")

                        if not wa_link and not supplier["email"]:
                            st.error("This supplier has no phone number or email on file — add one via the Suppliers page before this order can be sent.")

    # ---------------- NEW ORDER VIEW ----------------
    elif st.session_state.order_mode == "new":
        conn = db.get_connection()
        suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()

        if not suppliers:
            st.info("No suppliers yet — add one via the Suppliers page first.")
        else:
            supplier_labels = {s["name"]: s["id"] for s in suppliers}
            chosen_supplier_name = st.selectbox("Supplier", list(supplier_labels.keys()), key="new_order_supplier")
            chosen_supplier_id = supplier_labels[chosen_supplier_name]

            st.title(f"Order from {chosen_supplier_name}")

            conn = db.get_connection()
            supplier_row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (chosen_supplier_id,)).fetchone()
            supplier_ingredients = conn.execute("""
                SELECT * FROM ingredients
                WHERE primary_supplier_id = ? OR backup_supplier_id = ?
                ORDER BY name
            """, (chosen_supplier_id, chosen_supplier_id)).fetchall()
            conn.close()

            st.caption(f"📧 {supplier_row['email'] or 'No email on file'}  ·  📞 {supplier_row['phone'] or 'No phone on file'}")

            if not supplier_ingredients:
                st.warning(f"No ingredients are linked to {chosen_supplier_name} yet. Set this supplier as Primary or Backup on at least one ingredient first.")
            else:
                search_text = st.text_input("Search ingredients...", key="order_search", label_visibility="collapsed", placeholder="Search ingredients...")
                visible_ingredients = [
                    ing for ing in supplier_ingredients
                    if not search_text.strip() or search_text.strip().lower() in ing["name"].lower()
                ]

                running_total = 0.0
                item_count = 0

                for ing in visible_ingredients:
                    display_unit, factor = db.get_order_unit(ing["base_unit"])
                    cost_per_display_unit = (ing["purchase_price"] / ing["purchase_qty"]) * factor if ing["purchase_qty"] else 0

                    with st.container(border=True):
                        st.write(f"**{ing['name']}** ({display_unit})")
                        st.caption(f"${cost_per_display_unit:.2f} per {display_unit}")

                        last_stock = db.get_latest_stock_take_qty(ing["id"])
                        last_stock_display = (last_stock / factor) if last_stock is not None else 0.0

                        col1, col2 = st.columns(2)
                        with col1:
                            st.number_input(
                                "In Stock (reference only)", min_value=0.0, step=1.0,
                                value=float(last_stock_display), key=f"order_instock_{ing['id']}"
                            )
                        with col2:
                            qty_to_order = st.number_input(
                                f"To Order ({display_unit})", min_value=0.0, step=1.0,
                                key=f"order_qty_{ing['id']}"
                            )

                        if qty_to_order > 0:
                            item_count += 1
                            running_total += qty_to_order * cost_per_display_unit

                delivery_date = st.date_input("Requested delivery date", value=None, key="order_delivery_date")
                supplier_note = st.text_area("Note for supplier (included in the message)", key="order_supplier_note")

                st.write("")
                summary_col1, summary_col2 = st.columns(2)
                summary_col1.metric("Item count", item_count)
                summary_col2.metric("Order total", f"${running_total:.2f}")

                internal_note = st.text_area(
                    "Internal note (not sent to supplier)",
                    key="order_internal_note",
                    help="Visible only inside this app, for your own team."
                )

                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.order_mode = "list"
                        st.rerun()
                with btn_col2:
                    preview_clicked = st.button("Preview", use_container_width=True)
                with btn_col3:
                    create_clicked = st.button("Create Order", type="primary", use_container_width=True)

                if preview_clicked:
                    if item_count == 0:
                        st.error("Enter a quantity greater than zero for at least one item to preview.")
                    else:
                        preview_lines = [f"New order for {chosen_supplier_name}:", ""]
                        if delivery_date:
                            preview_lines.append(f"Requested delivery date: {delivery_date.isoformat()}")
                            preview_lines.append("")
                        for ing in supplier_ingredients:
                            qty = st.session_state.get(f"order_qty_{ing['id']}", 0)
                            if qty and qty > 0:
                                display_unit, _ = db.get_order_unit(ing["base_unit"])
                                preview_lines.append(f"- {ing['name']} — {qty:g} {display_unit}")
                        if supplier_note:
                            preview_lines.append("")
                            preview_lines.append(f"Note: {supplier_note}")
                        preview_lines.append("")
                        preview_lines.append("Thank you!")
                        st.text_area("Message preview", "\n".join(preview_lines), height=200, disabled=True)

                if create_clicked:
                    chosen_lines = {}
                    for ing in supplier_ingredients:
                        qty = st.session_state.get(f"order_qty_{ing['id']}", 0)
                        if qty and qty > 0:
                            _, factor = db.get_order_unit(ing["base_unit"])
                            chosen_lines[ing["id"]] = qty * factor  # store in base unit (g/ml/each)

                    if not chosen_lines:
                        st.error("Enter a quantity greater than zero for at least one item.")
                    else:
                        conn = db.get_connection()
                        conn.execute(
                            "INSERT INTO orders (supplier_id, status, supplier_note, internal_note, delivery_date, created_by, created_at) VALUES (?, 'draft', ?, ?, ?, ?, ?)",
                            (chosen_supplier_id, supplier_note or None, internal_note or None,
                             delivery_date.isoformat() if delivery_date else None, current_user["name"], date.today().isoformat())
                        )
                        new_order = conn.execute(
                            "SELECT id FROM orders WHERE supplier_id = ? ORDER BY id DESC LIMIT 1", (chosen_supplier_id,)
                        ).fetchone()
                        order_id = new_order["id"]
                        for iid, qty in chosen_lines.items():
                            conn.execute(
                                "INSERT INTO order_lines (order_id, ingredient_id, quantity) VALUES (?, ?, ?)",
                                (order_id, iid, qty)
                            )
                        conn.commit()

                        supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (chosen_supplier_id,)).fetchone()
                        if not supplier["phone"] and not supplier["email"]:
                            conn.execute("UPDATE orders SET status='error', error_message=? WHERE id=?",
                                         ("No phone or email on file for this supplier.", order_id))
                            conn.commit()
                            db.add_notification(
                                "error", f"Order to {supplier['name']} has no way to be sent — no phone or email on file.",
                                order_id=order_id, created_by=current_user["name"], conn=conn
                            )
                        else:
                            db.add_notification(
                                "info", f"New order created for {supplier['name']} ({len(chosen_lines)} item(s)).",
                                order_id=order_id, created_by=current_user["name"], conn=conn
                            )
                        conn.close()

                        st.success(f"Order created for {chosen_supplier_name}.")
                        st.session_state.order_mode = "list"
                        st.rerun()


# =========================================================
# PAGE: STAFF  (owner only)
# =========================================================
elif page == "Staff":
    if not is_owner:
        st.error("This page is restricted to the Owner account.")
        st.stop()

    if "staff_mode" not in st.session_state:
        st.session_state.staff_mode = "list"

    title_col, btn1 = st.columns([7, 2])
    with title_col:
        st.title("Staff & PIN logins")
    with btn1:
        if st.button("Add New Staff", type="primary", use_container_width=True):
            st.session_state.staff_mode = "add"
            st.rerun()

    if st.session_state.staff_mode != "list":
        if st.button("← Back to list"):
            st.session_state.staff_mode = "list"
            st.rerun()
        st.write("")

    conn = db.get_connection()
    staff_rows = conn.execute("SELECT * FROM staff ORDER BY role, name").fetchall()
    conn.close()

    # ---------------- LIST VIEW ----------------
    if st.session_state.staff_mode == "list":
        st.caption("Manage who can log in to this app. Click a name to edit it.")

        for s in staff_rows:
            with st.container(border=True):
                cols = st.columns([2, 2, 2, 2])
                with cols[0]:
                    if st.button(s["name"], type="tertiary", key=f"staff_name_{s['id']}"):
                        st.session_state["edit_staff_select"] = f"{s['name']} ({s['role']})"
                        st.session_state.staff_mode = "edit"
                        st.rerun()
                cols[1].write(f"**PIN:** {s['pin']}")
                cols[2].write(f"**Role:** {s['role']}")
                cols[3].write(f"**Shared device:** {'Yes' if s['is_shared_device'] else 'No'}")

    # ---------------- ADD VIEW ----------------
    elif st.session_state.staff_mode == "add":
        st.subheader("Add a new staff member")
        with st.form("add_staff_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Name")
                st.write("PIN (4 digits)")
                new_pin = pin_entry_boxes("add_staff_pin")
            with col2:
                new_role = st.selectbox("Role", ["staff", "owner"])
                new_shared = st.checkbox("This is a shared device PIN (e.g. shop iPad)")

            submitted = st.form_submit_button("Add staff member")
            if submitted:
                if not new_name or len(new_pin) < 4 or not new_pin.isdigit():
                    st.error("Please enter a name and a complete 4-digit PIN.")
                else:
                    conn = db.get_connection()
                    existing = conn.execute("SELECT id FROM staff WHERE pin = ?", (new_pin,)).fetchone()
                    if existing:
                        st.error("That PIN is already in use — choose a different one.")
                    else:
                        conn.execute(
                            "INSERT INTO staff (name, pin, role, is_shared_device) VALUES (?, ?, ?, ?)",
                            (new_name, new_pin, new_role, 1 if new_shared else 0)
                        )
                        conn.commit()
                        st.success(f"Added {new_name}.")
                        st.session_state.staff_mode = "list"
                        st.rerun()
                    conn.close()

    # ---------------- EDIT VIEW (Update + Delete both live here) ----------------
    elif st.session_state.staff_mode == "edit":
        st.subheader("Edit staff member")
        if not staff_rows:
            st.info("No staff yet — add one first.")
        else:
            edit_labels = {f"{s['name']} ({s['role']})": s["id"] for s in staff_rows}
            edit_chosen_label = st.selectbox("Staff member", list(edit_labels.keys()), key="edit_staff_select")
            edit_id = edit_labels[edit_chosen_label]

            conn = db.get_connection()
            edit_current = conn.execute("SELECT * FROM staff WHERE id = ?", (edit_id,)).fetchone()
            conn.close()

            with st.form(f"edit_staff_form_{edit_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    e_name = st.text_input("Name", value=edit_current["name"])
                    st.write("PIN (4 digits)")
                    e_pin = pin_entry_boxes(f"edit_staff_pin_{edit_id}", prefill=edit_current["pin"])
                with col2:
                    role_choices = ["staff", "owner"]
                    e_role = st.selectbox("Role", role_choices, index=role_choices.index(edit_current["role"]))
                    e_shared = st.checkbox("This is a shared device PIN (e.g. shop iPad)", value=bool(edit_current["is_shared_device"]))

                update_submitted = st.form_submit_button("Update staff member")
                if update_submitted:
                    if not e_name or len(e_pin) < 4 or not e_pin.isdigit():
                        st.error("Name can't be empty, and PIN must be a complete 4 digits.")
                    else:
                        conn = db.get_connection()
                        pin_clash = conn.execute(
                            "SELECT id FROM staff WHERE pin = ? AND id != ?", (e_pin, edit_id)
                        ).fetchone()
                        if pin_clash:
                            st.error("That PIN is already used by someone else — choose a different one.")
                            conn.close()
                        else:
                            owner_count = conn.execute("SELECT COUNT(*) AS c FROM staff WHERE role='owner'").fetchone()["c"]
                            if edit_current["role"] == "owner" and e_role != "owner" and owner_count <= 1:
                                st.error("Can't change the role of the only owner account. Add another owner first.")
                                conn.close()
                            else:
                                conn.execute(
                                    "UPDATE staff SET name=?, pin=?, role=?, is_shared_device=? WHERE id=?",
                                    (e_name, e_pin, e_role, 1 if e_shared else 0, edit_id)
                                )
                                conn.commit()
                                conn.close()
                                st.success(f"Updated {e_name}.")
                                st.session_state.staff_mode = "list"
                                st.rerun()

            st.write("")
            st.write("**Delete this staff member**")
            conn = db.get_connection()
            owner_count = conn.execute("SELECT COUNT(*) AS c FROM staff WHERE role = 'owner'").fetchone()["c"]
            conn.close()

            if edit_current["role"] == "owner" and owner_count <= 1:
                st.error("Can't remove the only owner account. Add another owner first.")
            else:
                if st.button("Delete this staff member", key=f"delete_staff_{edit_id}"):
                    conn = db.get_connection()
                    conn.execute("DELETE FROM staff WHERE id = ?", (edit_id,))
                    conn.commit()
                    conn.close()
                    st.success("Removed.")
                    st.session_state.staff_mode = "list"
                    st.rerun()


# =========================================================
# PAGE: SALES SYNC  (owner only)
# =========================================================
elif page == "Sales Sync":
    if not is_owner:
        st.error("This page is restricted to the Owner account.")
        st.stop()

    st.title("Sales sync")
    st.caption(
        "Pulls your POS's daily sales report by email and deducts ingredient stock accordingly. "
        "This only runs when you click the button below — it can't check automatically in the background."
    )

    if st.button("Check for new sales email", type="primary", icon=":material/sync:"):
        with st.spinner("Connecting to the mailbox..."):
            result, error = db.fetch_latest_pos_sales_email()
        if error:
            st.error(error)
        else:
            conn = db.get_connection()
            already_done = conn.execute(
                "SELECT * FROM sales_sync_log WHERE email_message_id = ?", (result["message_id"],)
            ).fetchone()
            conn.close()

            if already_done:
                st.info(f"This email was already processed on {already_done['processed_at']} — nothing new to do.")
            else:
                with st.spinner("Reading the report..."):
                    parsed_items = db.parse_pos_sales_file(result["file_bytes"])
                if not parsed_items:
                    st.warning("Found an email with an .xls attachment, but couldn't read any sales items from it. The report format may have changed.")
                else:
                    matched = db.match_sales_items_to_recipes_and_ingredients(parsed_items)
                    st.session_state.sales_sync_review = {
                        "email_message_id": result["message_id"],
                        "filename": result["filename"],
                        "matches": matched,
                    }
                    st.rerun()

    if "sales_sync_review" in st.session_state:
        review = st.session_state.sales_sync_review
        st.divider()
        st.subheader(f"Review: {review['filename']}")
        st.caption("Confident matches are pre-checked. Items with no match get a placeholder recipe created so they're never just lost — uncheck any you'd rather skip.")

        confirmed_items = []
        unmatched_to_create = []
        for i, m in enumerate(review["matches"]):
            cols = st.columns([3, 2, 3, 2])
            cols[0].write(f"**{m['pos_name']}**")
            cols[1].write(f"Sold: {m['quantity_sold']:g}")

            if m["match_type"] is None:
                with cols[2]:
                    create_it = st.checkbox("Create as new recipe", value=True, key=f"sync_create_{i}")
                cols[3].caption("❓ No match found")
                if create_it:
                    unmatched_to_create.append(m["pos_name"])
                continue

            with cols[2]:
                include = st.checkbox(
                    f"{m['match_name']} ({m['match_type']})",
                    value=m["score"] >= 0.6,
                    key=f"sync_include_{i}"
                )
            cols[3].caption(f"Confidence: {m['score']:.0%}")

            if include:
                confirmed_items.append({
                    "match_type": m["match_type"], "match_id": m["match_id"], "quantity_sold": m["quantity_sold"]
                })

        if unmatched_to_create:
            st.info(f"{len(unmatched_to_create)} item(s) will get a new placeholder recipe created (filed under Recipes → Dish → 'Unmapped POS Items') so they're trackable instead of disappearing.")

        apply_col, cancel_col = st.columns(2)
        with apply_col:
            if st.button("Apply confirmed changes", type="primary", use_container_width=True):
                summary = db.apply_sales_deductions(confirmed_items, unmatched_to_create, review["email_message_id"], current_user["name"])
                st.success(
                    f"Stock updated for {summary['ingredients_deducted']} ingredient(s)."
                    + (f" {len(summary['skipped_uninitialized'])} skipped (never stock-counted)." if summary["skipped_uninitialized"] else "")
                )
                if summary["created_placeholders"]:
                    st.info(f"Created {len(summary['created_placeholders'])} new placeholder recipe(s): {', '.join(summary['created_placeholders'])}")
                if summary["low_stock_alerts"]:
                    st.warning(f"{len(summary['low_stock_alerts'])} ingredient(s) are now below their low-stock threshold — check Notifications.")
                del st.session_state.sales_sync_review
                st.rerun()
        with cancel_col:
            if st.button("Discard this review", use_container_width=True):
                del st.session_state.sales_sync_review
                st.rerun()

    st.divider()
    st.subheader("Sync history")
    conn = db.get_connection()
    sync_history = conn.execute("SELECT * FROM sales_sync_log ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    if not sync_history:
        st.caption("No sales reports processed yet.")
    else:
        history_data = [{
            "Processed": r["processed_at"], "By": r["processed_by"], "Items matched": r["items_matched"]
        } for r in sync_history]
        st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)


# =========================================================
# PAGE: DATA EXPORT  (owner only)
# =========================================================
elif page == "Data Export":
    if not is_owner:
        st.error("This page is restricted to the Owner account.")
        st.stop()

    st.title("Data export")
    st.caption("Download everything in the app as a single Excel file — every table, on its own sheet.")

    st.warning(
        "⚠️ This file includes staff PIN codes in plain text (the Staff sheet). "
        "Store and share it carefully — anyone with this file can see every login PIN."
    )

    st.write(
        "This also works as a real backup of your data — useful given the app's database "
        "lives on Supabase rather than this repository."
    )

    if st.button("Generate export", type="primary"):
        with st.spinner("Building the export file..."):
            file_bytes = db.export_all_tables_to_excel()
        st.session_state["export_file_bytes"] = file_bytes
        st.success("Export ready — click below to download.")

    if "export_file_bytes" in st.session_state:
        st.download_button(
            "Download Excel export",
            data=st.session_state["export_file_bytes"],
            file_name=f"cafe_manager_export_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )


# =========================================================
# PAGE: TASK HISTORY  (owner only)
# =========================================================
elif page == "Task History":
    if not is_owner:
        st.error("This page is restricted to the Owner account.")
        st.stop()

    st.title("Task completion history")
    st.caption("Every task completion, who did it, and when — across all days and weeks.")

    conn = db.get_connection()
    staff_names = ["All staff"] + [r["completed_by"] for r in conn.execute("SELECT DISTINCT completed_by FROM task_log WHERE completed_by IS NOT NULL ORDER BY completed_by").fetchall()]
    conn.close()

    chosen_staff = st.selectbox("Filter by staff member", staff_names)

    conn = db.get_connection()
    query = """
        SELECT td.title, td.section, td.day_of_week, td.recurrence,
               tl.week_start_date, tl.completed_by, tl.completed_at, tl.id AS log_id,
               tl.reverted, tl.reverted_by, tl.reverted_at
        FROM task_log tl
        JOIN task_definitions td ON tl.task_id = td.id
    """
    params = []
    if chosen_staff != "All staff":
        query += " WHERE tl.completed_by = ?"
        params.append(chosen_staff)
    query += " ORDER BY tl.id DESC"
    history_rows = conn.execute(query, params).fetchall()
    conn.close()

    if not history_rows:
        st.info("No completions recorded yet.")
    else:
        table_data = [{
            "Task": r["title"],
            "Day": r["day_of_week"],
            "Section": r["section"],
            "Type": "Weekly" if r["recurrence"] == "weekly" else "One-off",
            "Week of": r["week_start_date"] or "-",
            "Completed by": r["completed_by"],
            "Completed at": r["completed_at"],
            "Status": (
                f"↩️ Reverted by {r['reverted_by']} at {r['reverted_at']}" if r["reverted"] else "✅ Completed"
            ),
        } for r in history_rows]
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
        st.caption(f"{len(history_rows)} completion record(s) shown, including any later reverted.")


# =========================================================
# PAGE: INVOICES  (owner only)
# =========================================================
elif page == "Invoices":
    if not is_owner:
        st.error("This page is restricted to the Owner account.")
        st.stop()

    st.title("Invoice scanning")
    st.caption("Upload a photo of a supplier invoice. Small price changes (under 10%) are pre-approved; bigger changes need your tick before applying.")

    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.warning(
            "No API key found yet. Add `ANTHROPIC_API_KEY` under this app's "
            "Settings → Secrets on Streamlit Community Cloud, then refresh this page."
        )
    else:
        uploaded_file = st.file_uploader(
            "Upload invoice (photo or PDF)", type=["png", "jpg", "jpeg", "pdf"]
        )

        if uploaded_file is not None:
            is_pdf = uploaded_file.type == "application/pdf" or uploaded_file.name.lower().endswith(".pdf")
            if is_pdf:
                st.caption(f"📄 PDF uploaded: {uploaded_file.name}")
            else:
                st.image(uploaded_file, width=300)

            if st.button("Scan invoice"):
                import anthropic
                import base64
                import json

                with st.spinner("Reading the invoice..."):
                    try:
                        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                        file_bytes = uploaded_file.getvalue()
                        b64_data = base64.b64encode(file_bytes).decode("utf-8")

                        if is_pdf:
                            file_content_block = {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": b64_data
                                }
                            }
                        else:
                            media_type = uploaded_file.type or "image/jpeg"
                            file_content_block = {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64_data
                                }
                            }

                        # PDFs may contain multiple invoices across pages.
                        # We always ask for an array of invoices (even for images,
                        # which will just return a one-element array) so the same
                        # parsing logic handles both cases cleanly.
                        # betas=["pdfs-2024-09-25"] is required for PDF document
                        # support -- without it the API silently fails even on
                        # recent models.
                        api_kwargs = dict(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=4096,
                            system=(
                                "You extract structured data from supplier invoices for a cafe's "
                                "stock system. A PDF may contain multiple invoices across pages — "
                                "extract ALL of them. Respond with ONLY valid JSON, no preamble, "
                                "no markdown code fences, no extra commentary."
                            ),
                            messages=[{
                                "role": "user",
                                "content": [
                                    file_content_block,
                                    {"type": "text", "text": (
                                        "Extract every invoice in this document. For each invoice give the "
                                        "supplier name, invoice date, and every line item (description, "
                                        "pack size if shown, and total price for that line). "
                                        "Respond as a JSON array — one element per invoice — exactly in "
                                        "this shape: "
                                        '[{"supplier_name": "", "invoice_date": "", "line_items": '
                                        '[{"description": "", "pack_size": "", "price": 0.0}]}]'
                                    )}
                                ]
                            }]
                        )
                        if is_pdf:
                            api_kwargs["extra_headers"] = {"anthropic-beta": "pdfs-2024-09-25"}

                        response = client.messages.create(**api_kwargs)

                        raw_text = response.content[0].text.strip()
                        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                        parsed_raw = json.loads(raw_text)

                        # Normalise: always work with a list of invoices
                        if isinstance(parsed_raw, dict):
                            invoices = [parsed_raw]
                        else:
                            invoices = parsed_raw

                        # Merge all invoices' line items for the review screen.
                        # If multiple invoices from the same supplier are in one
                        # PDF we combine them; different suppliers stay separate
                        # but all get processed in one review pass.
                        all_line_items = []
                        supplier_name_raw = invoices[0].get("supplier_name", "") if invoices else ""
                        invoice_date_raw = invoices[0].get("invoice_date", "") if invoices else ""
                        for inv in invoices:
                            for item in inv.get("line_items", []):
                                item["_source_date"] = inv.get("invoice_date", "")
                                item["_source_supplier"] = inv.get("supplier_name", "")
                                all_line_items.append(item)

                        parsed = {
                            "supplier_name": supplier_name_raw,
                            "invoice_date": invoice_date_raw,
                            "line_items": all_line_items,
                            "_invoice_count": len(invoices),
                        }

                        conn = db.get_connection()
                        ingredient_rows = conn.execute("SELECT * FROM ingredients").fetchall()
                        supplier_rows = conn.execute("SELECT name FROM suppliers").fetchall()
                        conn.close()

                        ingredient_names = [r["name"] for r in ingredient_rows]
                        ingredient_by_name = {r["name"]: r for r in ingredient_rows}
                        supplier_names = [r["name"] for r in supplier_rows]

                        matched_supplier, _ = db.find_best_match(parsed.get("supplier_name", ""), supplier_names)

                        review_rows = []
                        for item in parsed.get("line_items", []):
                            description = item.get("description", "")
                            new_price = float(item.get("price", 0) or 0)
                            match_name, score = db.find_best_match(description, ingredient_names)

                            if match_name:
                                old_price = ingredient_by_name[match_name]["purchase_price"] or 0
                                pct_change = ((new_price - old_price) / old_price * 100) if old_price else None
                                status = "unmatched"
                                if pct_change is not None:
                                    status = "alert" if abs(pct_change) >= 10 else "auto"
                            else:
                                old_price, pct_change, status = None, None, "unmatched"

                            review_rows.append({
                                "description": description,
                                "pack_size": item.get("pack_size", ""),
                                "new_price": new_price,
                                "matched_ingredient": match_name,
                                "old_price": old_price,
                                "pct_change": pct_change,
                                "status": status,
                            })

                        st.session_state.invoice_scan = {
                            "supplier_input": parsed.get("supplier_name", ""),
                            "supplier_matched": matched_supplier,
                            "invoice_date": parsed.get("invoice_date", ""),
                            "rows": review_rows,
                            "_invoice_count": parsed.get("_invoice_count", 1),
                        }
                        st.rerun()

                    except json.JSONDecodeError as e:
                        st.error(
                            "Couldn't read structured data from that invoice. "
                            + ("For PDFs: check the file isn't password-protected or corrupted. " if is_pdf else "Try a clearer, well-lit photo. ")
                            + f"Details: {e}"
                        )
                    except Exception as e:
                        st.error(f"Something went wrong while scanning: {e}")

    # ---------- Review screen (built from the last scan, if any) ----------
    if "invoice_scan" in st.session_state:
        scan = st.session_state.invoice_scan
        st.divider()
        st.subheader("Review extracted invoice")

        conn = db.get_connection()
        all_supplier_names = [r["name"] for r in conn.execute("SELECT name FROM suppliers ORDER BY name").fetchall()]
        all_ingredient_names = [r["name"] for r in conn.execute("SELECT name FROM ingredients ORDER BY name").fetchall()]
        conn.close()

        invoice_count = scan.get("_invoice_count", 1)
        if invoice_count > 1:
            st.info(f"📄 This PDF contained **{invoice_count} separate invoices** — all {len(scan['rows'])} line items below have been combined for review.")
        else:
            st.write(f"**Invoice date (as read):** {scan['invoice_date'] or 'not detected'}")

        # ---- Supplier handling ----
        if scan["supplier_matched"]:
            st.write(f"**Supplier:** {scan['supplier_input']} → matched to existing supplier **{scan['supplier_matched']}**")
        else:
            st.write(f"**Supplier:** {scan['supplier_input']} — not matched to an existing supplier.")
            supplier_action = st.radio(
                "How should we handle this supplier?",
                ["Create a new supplier", "Match to an existing supplier"],
                key="inv_supplier_action", horizontal=True
            )
            if supplier_action == "Create a new supplier":
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("New supplier name", value=scan["supplier_input"], key="inv_new_supplier_name")
                    st.text_input("UEN / Tax number", key="inv_new_supplier_uen")
                    st.text_input("Email", key="inv_new_supplier_email")
                with col2:
                    st.text_input("Contact number", key="inv_new_supplier_phone")
                    st.text_input("Address", key="inv_new_supplier_address")
                    st.text_input("Payment terms", key="inv_new_supplier_terms")
                    st.text_input("Delivery days", key="inv_new_supplier_days")
            elif all_supplier_names:
                st.selectbox("Match to existing supplier", all_supplier_names, key="inv_supplier_match_choice")
            else:
                st.info("No existing suppliers to match to — use 'Create a new supplier' instead.")

        # ---- Line items ----
        for idx, row in enumerate(scan["rows"]):
            st.markdown("---")
            cols = st.columns([3, 2, 2])
            cols[0].write(f"**{row['description']}**  \n{row['pack_size']}")
            cols[1].write(f"Invoice price: ${row['new_price']:.2f}")

            if row["status"] == "unmatched":
                cols[2].write("🔴 No confident match")
                choice_options = ["-- skip this item --", "+ Create new ingredient"] + all_ingredient_names
                chosen = st.selectbox(
                    "Match to an ingredient, create new, or skip",
                    choice_options,
                    key=f"inv_match_choice_{idx}"
                )
                if chosen == "+ Create new ingredient":
                    st.write("**New ingredient details:**")
                    nc1, nc2, nc3 = st.columns(3)
                    with nc1:
                        st.text_input("Ingredient name", value=row["description"], key=f"inv_new_ing_name_{idx}")
                        st.text_input("Category", key=f"inv_new_ing_category_{idx}")
                    with nc2:
                        st.selectbox("Base unit", ["g", "ml", "each"], key=f"inv_new_ing_unit_{idx}")
                        st.number_input(
                            "Purchase quantity (in base unit)", min_value=0.0, step=1.0,
                            key=f"inv_new_ing_qty_{idx}"
                        )
                    with nc3:
                        st.number_input(
                            "Recipe unit size (e.g. 100 for '100g')", min_value=0.0, step=1.0, value=100.0,
                            key=f"inv_new_ing_recipe_unit_{idx}"
                        )
                        st.text_input("Purchase size label", value=row["pack_size"], key=f"inv_new_ing_size_label_{idx}")
            else:
                badge = "🟡 Needs review" if row["status"] == "alert" else "🟢 Small change — pre-approved"
                cols[2].write(
                    f"{badge}  \nMatched: **{row['matched_ingredient']}**  \n"
                    f"${row['old_price']:.2f} → ${row['new_price']:.2f} ({row['pct_change']:+.1f}%)"
                )
                st.checkbox(
                    f"Apply this price update to {row['matched_ingredient']}",
                    value=(row["status"] == "auto"),
                    key=f"inv_apply_{idx}"
                )

        st.markdown("---")
        if st.button("Apply confirmed changes"):
            conn = db.get_connection()

            # Step 1: resolve the supplier (existing match, newly created, or already auto-matched)
            resolved_supplier_id = None
            resolved_supplier_name = scan["supplier_matched"]

            if scan["supplier_matched"]:
                existing_sup = conn.execute("SELECT id FROM suppliers WHERE name = ?", (scan["supplier_matched"],)).fetchone()
                resolved_supplier_id = existing_sup["id"] if existing_sup else None
            elif st.session_state.get("inv_supplier_action") == "Create a new supplier":
                new_sup_name = st.session_state.get("inv_new_supplier_name", "").strip()
                if new_sup_name:
                    already = conn.execute("SELECT id FROM suppliers WHERE name = ?", (new_sup_name,)).fetchone()
                    if already:
                        resolved_supplier_id = already["id"]
                    else:
                        conn.execute(
                            "INSERT INTO suppliers (name, uen, email, phone, address, payment_terms, delivery_days) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (new_sup_name,
                             st.session_state.get("inv_new_supplier_uen", ""),
                             st.session_state.get("inv_new_supplier_email", ""),
                             st.session_state.get("inv_new_supplier_phone", ""),
                             st.session_state.get("inv_new_supplier_address", ""),
                             st.session_state.get("inv_new_supplier_terms", ""),
                             st.session_state.get("inv_new_supplier_days", ""))
                        )
                        conn.commit()
                        resolved_supplier_id = conn.execute("SELECT id FROM suppliers WHERE name = ?", (new_sup_name,)).fetchone()["id"]
                    resolved_supplier_name = new_sup_name
            else:
                match_choice = st.session_state.get("inv_supplier_match_choice")
                if match_choice:
                    matched_row = conn.execute("SELECT id FROM suppliers WHERE name = ?", (match_choice,)).fetchone()
                    resolved_supplier_id = matched_row["id"] if matched_row else None
                    resolved_supplier_name = match_choice

            log_supplier_label = resolved_supplier_name or scan["supplier_input"]
            applied_count = 0

            # Step 2: apply each line item
            for idx, row in enumerate(scan["rows"]):
                if row["status"] == "unmatched":
                    chosen = st.session_state.get(f"inv_match_choice_{idx}")

                    if chosen == "+ Create new ingredient":
                        new_name = st.session_state.get(f"inv_new_ing_name_{idx}", "").strip()
                        new_qty = st.session_state.get(f"inv_new_ing_qty_{idx}", 0)
                        if new_name and new_qty and new_qty > 0:
                            conn.execute("""
                                INSERT INTO ingredients
                                    (name, category, primary_supplier_id, backup_supplier_id,
                                     purchase_size_label, purchase_qty, base_unit, purchase_price,
                                     recipe_unit_qty, last_updated)
                                VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                            """, (
                                new_name,
                                st.session_state.get(f"inv_new_ing_category_{idx}", ""),
                                resolved_supplier_id,
                                st.session_state.get(f"inv_new_ing_size_label_{idx}", row["pack_size"]),
                                new_qty,
                                st.session_state.get(f"inv_new_ing_unit_{idx}", "g"),
                                row["new_price"],
                                st.session_state.get(f"inv_new_ing_recipe_unit_{idx}", 100.0),
                                date.today().isoformat()
                            ))
                            conn.execute(
                                "INSERT INTO invoice_log (scanned_at, supplier_name, ingredient_name, old_price, new_price, pct_change, applied_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (date.today().isoformat(), log_supplier_label, new_name, None, row["new_price"], None, current_user["name"])
                            )
                            applied_count += 1

                    elif chosen and chosen != "-- skip this item --":
                        old = conn.execute("SELECT purchase_price FROM ingredients WHERE name = ?", (chosen,)).fetchone()
                        old_price = old["purchase_price"] if old else None
                        conn.execute(
                            "UPDATE ingredients SET purchase_price=?, last_updated=? WHERE name=?",
                            (row["new_price"], date.today().isoformat(), chosen)
                        )
                        conn.execute(
                            "INSERT INTO invoice_log (scanned_at, supplier_name, ingredient_name, old_price, new_price, pct_change, applied_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (date.today().isoformat(), log_supplier_label, chosen, old_price, row["new_price"], None, current_user["name"])
                        )
                        applied_count += 1
                else:
                    if st.session_state.get(f"inv_apply_{idx}"):
                        conn.execute(
                            "UPDATE ingredients SET purchase_price=?, last_updated=? WHERE name=?",
                            (row["new_price"], date.today().isoformat(), row["matched_ingredient"])
                        )
                        conn.execute(
                            "INSERT INTO invoice_log (scanned_at, supplier_name, ingredient_name, old_price, new_price, pct_change, applied_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (date.today().isoformat(), log_supplier_label, row["matched_ingredient"],
                             row["old_price"], row["new_price"], row["pct_change"], current_user["name"])
                        )
                        applied_count += 1

            conn.commit()
            conn.close()
            db.get_cached_ingredients_basic.clear()
            st.success(f"Applied {applied_count} update(s).")
            del st.session_state.invoice_scan
            st.rerun()

    st.divider()
    st.subheader("Recent price changes from invoices")
    conn = db.get_connection()
    log_rows = conn.execute("SELECT * FROM invoice_log ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    if log_rows:
        log_data = [{
            "Date": r["scanned_at"],
            "Supplier": r["supplier_name"],
            "Ingredient": r["ingredient_name"],
            "Old price": f"${r['old_price']:.2f}" if r["old_price"] is not None else "-",
            "New price": f"${r['new_price']:.2f}",
            "Applied by": r["applied_by"],
        } for r in log_rows]
        st.dataframe(pd.DataFrame(log_data), use_container_width=True, hide_index=True)
    else:
        st.write("No invoice-driven price changes yet.")
