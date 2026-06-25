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

st.set_page_config(page_title="Cafe Manager", layout="wide")

# Make sure the database and starter data exist every time the app starts
db.init_db()
db.seed_starter_data()
db.seed_default_staff()

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
                st.caption("Enter your PIN to continue")
                pin_entry = st.text_input("PIN", type="password", max_chars=6, label_visibility="collapsed")
                if st.button("Log in", width="stretch", type="primary"):
                    conn = db.get_connection()
                    staff_match = conn.execute("SELECT * FROM staff WHERE pin = ?", (pin_entry,)).fetchone()
                    conn.close()
                    if staff_match is None:
                        st.error("PIN not recognized.")
                    elif staff_match["is_shared_device"]:
                        st.session_state.pending_shared_login = True
                        st.rerun()
                    else:
                        st.session_state.current_user = {
                            "id": staff_match["id"], "name": staff_match["name"], "role": staff_match["role"]
                        }
                        st.rerun()
    st.stop()

current_user = st.session_state.current_user
is_manager = current_user["role"] in ("owner", "manager")

# ---------- Sidebar navigation (flat text-style links) ----------
st.sidebar.markdown("##### Cafe Manager")
st.sidebar.caption(f"Logged in as **{current_user['name']}** ({current_user['role']})")
st.sidebar.write("")

nav_options = ["Tasks", "Stock Take", "Master Stock List", "Recipes", "Suppliers"]
if is_manager:
    nav_options.append("Task History")
    nav_options.append("Invoices")
    nav_options.append("Staff")

if "current_page" not in st.session_state:
    st.session_state.current_page = nav_options[0]
if st.session_state.current_page not in nav_options:
    st.session_state.current_page = nav_options[0]  # safety net if role changed and a page is no longer available

for option in nav_options:
    if option == st.session_state.current_page:
        st.sidebar.markdown(f"**:green[{option}]**")
    else:
        if st.sidebar.button(option, type="tertiary", width="stretch", key=f"nav_{option}"):
            st.session_state.current_page = option
            st.rerun()

page = st.session_state.current_page

st.sidebar.divider()
if st.sidebar.button("Log out", width="stretch"):
    st.session_state.current_user = None
    st.rerun()


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
    if not is_manager:
        st.session_state.task_mode = "list"  # safety: only managers can reach add/edit/remove

    if is_manager:
        title_col, btn1, btn2, btn3 = st.columns([4, 2, 2, 2])
        with title_col:
            st.title("Weekly task workspace")
        with btn1:
            if st.button("+ Add New Task", use_container_width=True):
                st.session_state.task_mode = "add"
                st.rerun()
        with btn2:
            if st.button("Edit Task", use_container_width=True):
                st.session_state.task_mode = "edit"
                st.rerun()
        with btn3:
            if st.button("Remove Task", use_container_width=True):
                st.session_state.task_mode = "remove"
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
        st.caption("Weekly recurring tasks reset every Monday. One-off tasks stay completed once ticked.")

        conn = db.get_connection()
        all_task_defs = conn.execute("SELECT * FROM task_definitions ORDER BY section, title").fetchall()
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
                        is_done, completed_by, completed_at, log_id = db.get_task_completion(t, conn)

                        row_cols = st.columns([5, 2])
                        with row_cols[0]:
                            if t["recurrence"] == "once" and t["specific_date"]:
                                st.write(f"{t['title']}  _(one-off: {t['specific_date']})_")
                            else:
                                st.write(t["title"])
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
                                pin_try = st.text_input("Worker PIN", type="password", key=f"pin_input_{t['id']}")
                                confirm_col, cancel_col = st.columns(2)
                                with confirm_col:
                                    if st.button("Confirm", key=f"confirm_{t['id']}"):
                                        staff_match = conn.execute("SELECT * FROM staff WHERE pin = ?", (pin_try,)).fetchone()
                                        if staff_match is None:
                                            st.error("PIN not recognized.")
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

    # ---------------- ADD VIEW (manager only) ----------------
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

    # ---------------- EDIT VIEW (manager only) ----------------
    elif st.session_state.task_mode == "edit":
        st.subheader("Edit an existing task")

        conn = db.get_connection()
        all_defs = conn.execute("SELECT * FROM task_definitions ORDER BY day_of_week, section, title").fetchall()
        conn.close()

        if not all_defs:
            st.info("No tasks to edit yet.")
        else:
            labels = {f"[{t['day_of_week']} / {t['section']}] {t['title']}": t["id"] for t in all_defs}
            chosen_label = st.selectbox("Choose a task", list(labels.keys()), key="edit_task_select")
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

    # ---------------- REMOVE VIEW (manager only) ----------------
    elif st.session_state.task_mode == "remove":
        st.subheader("Remove a task")
        conn = db.get_connection()
        removable = conn.execute("SELECT id, title, section, day_of_week FROM task_definitions ORDER BY day_of_week, section, title").fetchall()
        conn.close()

        if not removable:
            st.info("No tasks to remove yet.")
        else:
            labels = {f"[{t['day_of_week']} / {t['section']}] {t['title']}": t["id"] for t in removable}
            to_remove_label = st.selectbox("Choose a task to remove", list(labels.keys()), key="remove_task_select")

            st.warning(f"This will permanently delete **{to_remove_label}** and its full completion history.")
            if st.button("Confirm delete", type="primary"):
                conn = db.get_connection()
                conn.execute("DELETE FROM task_definitions WHERE id = ?", (labels[to_remove_label],))
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
                for ingredient_id, qty in entered_values.items():
                    conn.execute(
                        "INSERT INTO stock_takes (ingredient_id, count_date, quantity_counted, counted_by) VALUES (?, ?, ?, ?)",
                        (ingredient_id, count_date.isoformat(), qty, current_user["name"])
                    )
                conn.commit()
                conn.close()
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
            SELECT i.name, i.category, i.base_unit, st.quantity_counted, st.counted_by
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
            "Counted by": r["counted_by"],
        } for r in history_rows]
        st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)


# =========================================================
# PAGE 1: MASTER STOCK LIST
# =========================================================
if page == "Master Stock List":
    if "stock_mode" not in st.session_state:
        st.session_state.stock_mode = "list"

    title_col, btn1, btn2, btn3 = st.columns([4, 2, 2, 2])
    with title_col:
        st.title("Master stock list")
    with btn1:
        if st.button("+ Add New Ingredient", use_container_width=True):
            st.session_state.stock_mode = "add"
            st.rerun()
    with btn2:
        if st.button("Edit Ingredient", use_container_width=True):
            st.session_state.stock_mode = "edit"
            st.rerun()
    with btn3:
        if st.button("Remove Ingredient", use_container_width=True):
            st.session_state.stock_mode = "remove"
            st.rerun()

    if st.session_state.stock_mode != "list":
        if st.button("← Back to list"):
            st.session_state.stock_mode = "list"
            st.rerun()
        st.write("")

    # ---------------- LIST VIEW ----------------
    if st.session_state.stock_mode == "list":
        st.caption("Every raw ingredient, its current price, and its cost per recipe unit.")

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
            st.info("No ingredients yet. Click \"+ Add New Ingredient\" above to add your first one.")
        else:
            categories = sorted(set(r["category"] or "Uncategorised" for r in ingredients))
            for cat in categories:
                st.subheader(cat)
                cat_rows = [r for r in ingredients if (r["category"] or "Uncategorised") == cat]

                table_data = []
                for r in cat_rows:
                    cost = db.cost_per_recipe_unit(r)
                    table_data.append({
                        "Ingredient": r["name"],
                        "Primary supplier": r["primary_supplier_name"] or "-",
                        "Backup supplier": r["backup_supplier_name"] or "-",
                        "Purchase size": r["purchase_size_label"],
                        "Price (incl. GST)": f"${r['purchase_price']:.2f}",
                        "Recipe unit": f"{r['recipe_unit_qty']:g}{r['base_unit']}",
                        "Cost / unit": f"${cost:.3f}",
                        "Updated": r["last_updated"],
                    })
                st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # ---------------- ADD VIEW ----------------
    elif st.session_state.stock_mode == "add":
        st.subheader("Add a new ingredient")
        supplier_options = get_supplier_options()

        with st.form("add_ingredient_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                name = st.text_input("Ingredient name")
                category = st.text_input("Category (e.g. Dairy, Meat, Produce)")
            with col2:
                purchase_size_label = st.text_input("Purchase size label (e.g. '12kg bag')")
                base_unit = st.selectbox("Base unit", ["g", "ml", "each"])
                purchase_qty = st.number_input("Purchase quantity (in base unit)", min_value=0.0, step=1.0)
            with col3:
                purchase_price = st.number_input("Purchase price, GST-inclusive ($)", min_value=0.0, step=0.01)
                recipe_unit_qty = st.number_input("Recipe unit size (e.g. 100 for '100g')", min_value=0.0, step=1.0, value=100.0)

            col4, col5 = st.columns(2)
            with col4:
                primary_supplier_name = st.selectbox("Primary supplier", list(supplier_options.keys()))
            with col5:
                backup_supplier_name = st.selectbox("Backup supplier", list(supplier_options.keys()))

            submitted = st.form_submit_button("Add ingredient")

            if submitted:
                if not name:
                    st.error("Please enter an ingredient name.")
                elif purchase_qty <= 0 or purchase_price <= 0:
                    st.error("Purchase quantity and price must be greater than zero.")
                else:
                    conn = db.get_connection()
                    conn.execute("""
                        INSERT INTO ingredients
                            (name, category, primary_supplier_id, backup_supplier_id,
                             purchase_size_label, purchase_qty, base_unit, purchase_price,
                             recipe_unit_qty, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name, category,
                        supplier_options[primary_supplier_name],
                        supplier_options[backup_supplier_name],
                        purchase_size_label, purchase_qty, base_unit, purchase_price,
                        recipe_unit_qty, date.today().isoformat()
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Added {name} to the master stock list.")
                    st.session_state.stock_mode = "list"
                    st.rerun()

    # ---------------- EDIT VIEW ----------------
    elif st.session_state.stock_mode == "edit":
        st.subheader("Edit an existing ingredient")

        conn = db.get_connection()
        all_ingredients = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
        conn.close()

        if not all_ingredients:
            st.info("No ingredients to edit yet.")
        else:
            ingredient_labels = {f"{r['name']} ({r['purchase_size_label']})": r["id"] for r in all_ingredients}
            selected_label = st.selectbox("Choose an ingredient", list(ingredient_labels.keys()), key="edit_ingredient_select")
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

            unit_choices = ["g", "ml", "each"]

            with st.form(f"edit_ingredient_form_{selected_id}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    e_name = st.text_input("Ingredient name", value=current["name"])
                    e_category = st.text_input("Category", value=current["category"] or "")
                with col2:
                    e_size_label = st.text_input("Purchase size label", value=current["purchase_size_label"] or "")
                    e_base_unit = st.selectbox(
                        "Base unit", unit_choices,
                        index=unit_choices.index(current["base_unit"]) if current["base_unit"] in unit_choices else 0
                    )
                    e_purchase_qty = st.number_input(
                        "Purchase quantity (in base unit)", min_value=0.0, step=1.0,
                        value=float(current["purchase_qty"] or 0)
                    )
                with col3:
                    e_purchase_price = st.number_input(
                        "Purchase price, GST-inclusive ($)", min_value=0.0, step=0.01,
                        value=float(current["purchase_price"] or 0)
                    )
                    e_recipe_unit_qty = st.number_input(
                        "Recipe unit size", min_value=0.0, step=1.0,
                        value=float(current["recipe_unit_qty"] or 100)
                    )

                col4, col5 = st.columns(2)
                with col4:
                    e_primary = st.selectbox(
                        "Primary supplier", supplier_keys,
                        index=supplier_keys.index(_key_for_supplier_id(current["primary_supplier_id"]))
                    )
                with col5:
                    e_backup = st.selectbox(
                        "Backup supplier", supplier_keys,
                        index=supplier_keys.index(_key_for_supplier_id(current["backup_supplier_id"]))
                    )

                update_submitted = st.form_submit_button("Update ingredient")

                if update_submitted:
                    if not e_name:
                        st.error("Ingredient name can't be empty.")
                    elif e_purchase_qty <= 0 or e_purchase_price <= 0:
                        st.error("Purchase quantity and price must be greater than zero.")
                    else:
                        conn = db.get_connection()
                        conn.execute("""
                            UPDATE ingredients
                            SET name=?, category=?, primary_supplier_id=?, backup_supplier_id=?,
                                purchase_size_label=?, purchase_qty=?, base_unit=?, purchase_price=?,
                                recipe_unit_qty=?, last_updated=?
                            WHERE id=?
                        """, (
                            e_name, e_category,
                            supplier_options[e_primary], supplier_options[e_backup],
                            e_size_label, e_purchase_qty, e_base_unit, e_purchase_price,
                            e_recipe_unit_qty, date.today().isoformat(), selected_id
                        ))
                        conn.commit()
                        conn.close()
                        st.success(f"Updated {e_name}.")
                        st.session_state.stock_mode = "list"
                        st.rerun()

    # ---------------- REMOVE VIEW ----------------
    elif st.session_state.stock_mode == "remove":
        st.subheader("Remove an ingredient")

        conn = db.get_connection()
        all_ingredients = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
        conn.close()

        if not all_ingredients:
            st.info("No ingredients to remove yet.")
        else:
            ingredient_labels = {f"{r['name']} ({r['purchase_size_label']})": r["id"] for r in all_ingredients}
            remove_label = st.selectbox("Choose an ingredient to remove", list(ingredient_labels.keys()), key="remove_ingredient_select")
            remove_id = ingredient_labels[remove_label]

            st.warning(f"This will permanently delete **{remove_label}** from the Master Stock List.")
            if st.button("Confirm delete", type="primary"):
                conn = db.get_connection()
                conn.execute("DELETE FROM ingredients WHERE id=?", (remove_id,))
                conn.commit()
                conn.close()
                st.success(f"Deleted {remove_label}.")
                st.session_state.stock_mode = "list"
                st.rerun()


# =========================================================
# PAGE 2: RECIPES
# =========================================================
elif page == "Recipes":
    def recipe_options(type_filter=None, exclude_id=None):
        conn = db.get_connection()
        query = "SELECT id, name FROM recipes"
        clauses, params = [], []
        if type_filter:
            clauses.append("type = ?")
            params.append(type_filter)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY name"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return {r["name"]: r["id"] for r in rows if r["id"] != exclude_id}

    if "recipe_mode" not in st.session_state:
        st.session_state.recipe_mode = "list"

    title_col, btn1, btn2 = st.columns([5, 2, 2])
    with title_col:
        st.title("Recipes")
    with btn1:
        if st.button("+ Add New Recipe", use_container_width=True):
            st.session_state.recipe_mode = "add"
            st.rerun()
    with btn2:
        if st.button("Remove Recipe", use_container_width=True):
            st.session_state.recipe_mode = "remove"
            st.rerun()

    if st.session_state.recipe_mode != "list":
        if st.button("← Back to list"):
            st.session_state.recipe_mode = "list"
            st.rerun()
        st.write("")

    # ---------------- LIST VIEW ----------------
    if st.session_state.recipe_mode == "list":
        st.caption("Click a recipe name to edit it. Costs shown include 9% GST.")

        conn = db.get_connection()
        all_recipes = conn.execute("SELECT * FROM recipes ORDER BY type, name").fetchall()
        conn.close()

        if not all_recipes:
            st.info("No recipes yet. Click \"+ Add New Recipe\" above to add your first one.")
        else:
            for rtype in ["Prep", "Dish", "Beverage"]:
                group = [r for r in all_recipes if r["type"] == rtype]
                if not group:
                    continue
                st.subheader(rtype)

                if rtype == "Prep":
                    header_cols = st.columns([3, 2, 2, 2])
                    header_cols[1].caption("Yields")
                    header_cols[2].caption("Batch cost (incl. GST)")
                    header_cols[3].caption("Cost / unit")
                else:
                    header_cols = st.columns([3, 2, 2, 2])
                    header_cols[1].caption("Total food cost (incl. GST)")
                    header_cols[2].caption("Food cost %")
                    header_cols[3].caption("Selling price (excl. GST)")

                for r in group:
                    cost = db.compute_recipe_cost(r["id"])
                    cols = st.columns([3, 2, 2, 2])

                    with cols[0]:
                        if st.button(r["name"], type="tertiary", key=f"recipe_name_{r['id']}"):
                            st.session_state["edit_recipe_select"] = r["name"]
                            st.session_state.recipe_mode = "edit"
                            st.rerun()

                    if rtype == "Prep":
                        cols[1].write(f"{r['yield_qty']:g}{r['yield_unit']}")
                        cols[2].write(f"${cost:.2f}")
                        cols[3].write(f"${cost / r['yield_qty']:.4f}" if r["yield_qty"] else "-")
                    else:
                        cols[1].write(f"${cost:.2f}")
                        if r["selling_price"]:
                            pct = cost / r["selling_price"] * 100
                            status = db.food_cost_status(pct)
                            badge = {"ok": "🟢", "warning": "🟡", "alert": "🔴"}[status]
                            cols[2].write(f"{badge} {pct:.1f}%")
                            cols[3].write(f"${r['selling_price']:.2f}")
                        else:
                            cols[2].write("-")
                            cols[3].write("No price set")
                st.write("")

    # ---------------- ADD VIEW ----------------
    elif st.session_state.recipe_mode == "add":
        st.subheader("Add a new recipe")

        with st.form("add_recipe_form", clear_on_submit=True):
            r_name = st.text_input("Recipe name")
            r_type = st.selectbox("Recipe category", ["Prep", "Dish", "Beverage"])

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
                        INSERT INTO recipes (name, type, yield_qty, yield_unit, selling_price)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        r_name, r_type,
                        r_yield_qty if r_type == "Prep" else None,
                        r_yield_unit if r_type == "Prep" else None,
                        r_selling_price if r_type in ("Dish", "Beverage") else None,
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Added {r_name} ({r_type}). Click its name in the list to add ingredients.")
                    st.session_state.recipe_mode = "list"
                    st.rerun()

    # ---------------- EDIT VIEW ----------------
    elif st.session_state.recipe_mode == "edit":
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

            # ---- Recipe details (name, yield/price) ----
            st.write("**Recipe details**")
            with st.form(f"edit_recipe_details_{selected_recipe_id}"):
                e_name = st.text_input("Recipe name", value=recipe["name"])
                if recipe["type"] == "Prep":
                    col1, col2 = st.columns(2)
                    with col1:
                        e_yield_qty = st.number_input("Yield quantity", min_value=0.0, step=1.0, value=float(recipe["yield_qty"] or 0))
                    with col2:
                        unit_choices = ["g", "ml", "each"]
                        e_yield_unit = st.selectbox(
                            "Yield unit", unit_choices,
                            index=unit_choices.index(recipe["yield_unit"]) if recipe["yield_unit"] in unit_choices else 0
                        )
                    e_selling_price = None
                else:
                    e_selling_price = st.number_input("Selling price $", min_value=0.0, step=0.01, value=float(recipe["selling_price"] or 0))
                    e_yield_qty, e_yield_unit = None, None

                details_submitted = st.form_submit_button("Update recipe details")
                if details_submitted:
                    if not e_name:
                        st.error("Recipe name can't be empty.")
                    else:
                        conn = db.get_connection()
                        conn.execute(
                            "UPDATE recipes SET name=?, yield_qty=?, yield_unit=?, selling_price=? WHERE id=?",
                            (e_name, e_yield_qty, e_yield_unit, e_selling_price, selected_recipe_id)
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Updated {e_name}.")
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

            st.write("**Add an ingredient or Prep recipe to this:**")
            component_type_choices = ["Raw ingredient"]
            if recipe["type"] in ("Dish", "Beverage"):
                component_type_choices.append("Prep recipe")

            component_type = st.radio("Component type", component_type_choices, horizontal=True, key=f"comp_type_{selected_recipe_id}")

            with st.form(f"add_line_form_{selected_recipe_id}", clear_on_submit=True):
                if component_type == "Raw ingredient":
                    conn = db.get_connection()
                    ing_rows = conn.execute("SELECT id, name, base_unit FROM ingredients ORDER BY name").fetchall()
                    conn.close()
                    ing_labels = {f"{r['name']} ({r['base_unit']})": (r["id"], r["base_unit"]) for r in ing_rows}
                    if ing_labels:
                        chosen_label = st.selectbox("Ingredient", list(ing_labels.keys()))
                        chosen_id, chosen_unit = ing_labels[chosen_label]
                        qty = st.number_input(f"Quantity used ({chosen_unit})", min_value=0.0, step=1.0)
                    else:
                        st.write("No ingredients in your Master Stock List yet.")
                        chosen_id, qty = None, 0
                else:
                    prep_options = recipe_options(type_filter="Prep", exclude_id=selected_recipe_id)
                    if prep_options:
                        chosen_label = st.selectbox("Prep recipe", list(prep_options.keys()))
                        chosen_id = prep_options[chosen_label]
                        conn = db.get_connection()
                        prep_unit = conn.execute("SELECT yield_unit FROM recipes WHERE id = ?", (chosen_id,)).fetchone()["yield_unit"]
                        conn.close()
                        qty = st.number_input(f"Quantity used ({prep_unit})", min_value=0.0, step=1.0)
                    else:
                        st.write("No Prep recipes available yet.")
                        chosen_id, qty = None, 0

                line_submitted = st.form_submit_button("Add to recipe")
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

    # ---------------- REMOVE VIEW ----------------
    elif st.session_state.recipe_mode == "remove":
        st.subheader("Remove a recipe")

        all_recipe_options = recipe_options()
        if not all_recipe_options:
            st.info("No recipes to remove yet.")
        else:
            remove_name = st.selectbox("Choose a recipe to remove", list(all_recipe_options.keys()), key="remove_recipe_select")
            remove_id = all_recipe_options[remove_name]

            st.warning(f"This will permanently delete **{remove_name}** and all its ingredient lines.")
            if st.button("Confirm delete", type="primary"):
                conn = db.get_connection()
                used_elsewhere = conn.execute(
                    "SELECT COUNT(*) AS c FROM recipe_lines WHERE sub_recipe_id = ?", (remove_id,)
                ).fetchone()["c"]
                if used_elsewhere > 0:
                    st.error(f"Can't delete — this Prep is used in {used_elsewhere} other recipe(s). Remove it from those first.")
                else:
                    conn.execute("DELETE FROM recipes WHERE id = ?", (remove_id,))
                    conn.commit()
                    st.success(f"Deleted {remove_name}.")
                    st.session_state.recipe_mode = "list"
                    st.rerun()
                conn.close()


# =========================================================
# PAGE 3: SUPPLIERS
# =========================================================
elif page == "Suppliers":
    if "supplier_mode" not in st.session_state:
        st.session_state.supplier_mode = "list"

    title_col, btn1, btn2, btn3 = st.columns([4, 2, 2, 2])
    with title_col:
        st.title("Suppliers")
    with btn1:
        if st.button("+ Add New Supplier", use_container_width=True):
            st.session_state.supplier_mode = "add"
            st.rerun()
    with btn2:
        if st.button("Edit Supplier", use_container_width=True):
            st.session_state.supplier_mode = "edit"
            st.rerun()
    with btn3:
        if st.button("Remove Supplier", use_container_width=True):
            st.session_state.supplier_mode = "remove"
            st.rerun()

    if st.session_state.supplier_mode != "list":
        if st.button("← Back to list"):
            st.session_state.supplier_mode = "list"
            st.rerun()
        st.write("")

    # ---------------- LIST VIEW ----------------
    if st.session_state.supplier_mode == "list":
        st.caption("Every supplier you buy from, and which ingredients link to them.")

        conn = db.get_connection()
        suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()

        if not suppliers:
            st.info("No suppliers yet. Click \"+ Add New Supplier\" above to add your first one.")

        for s in suppliers:
            with st.expander(f"{s['name']}"):
                st.write(f"**UEN / Tax number:** {s['uen'] or '-'}")
                st.write(f"**Email:** {s['email'] or '-'}")
                st.write(f"**Phone:** {s['phone'] or '-'}")
                st.write(f"**Address:** {s['address'] or '-'}")
                st.write(f"**Payment terms:** {s['payment_terms'] or '-'}")
                st.write(f"**Delivery days:** {s['delivery_days'] or '-'}")

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
                    st.write("**Linked ingredients:** none yet")

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

    # ---------------- EDIT VIEW ----------------
    elif st.session_state.supplier_mode == "edit":
        st.subheader("Edit an existing supplier")

        conn = db.get_connection()
        all_suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()

        if not all_suppliers:
            st.info("No suppliers to edit yet.")
        else:
            supplier_labels = {r["name"]: r["id"] for r in all_suppliers}
            chosen_label = st.selectbox("Choose a supplier", list(supplier_labels.keys()), key="edit_supplier_select")
            chosen_id = supplier_labels[chosen_label]
            s = next(r for r in all_suppliers if r["id"] == chosen_id)

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

    # ---------------- REMOVE VIEW ----------------
    elif st.session_state.supplier_mode == "remove":
        st.subheader("Remove a supplier")

        conn = db.get_connection()
        all_suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
        conn.close()

        if not all_suppliers:
            st.info("No suppliers to remove yet.")
        else:
            supplier_labels = {r["name"]: r["id"] for r in all_suppliers}
            remove_label = st.selectbox("Choose a supplier to remove", list(supplier_labels.keys()), key="remove_supplier_select")
            remove_id = supplier_labels[remove_label]

            st.warning(f"This will permanently delete **{remove_label}**.")
            if st.button("Confirm delete", type="primary"):
                conn = db.get_connection()
                linked_count = conn.execute("""
                    SELECT COUNT(*) AS c FROM ingredients
                    WHERE primary_supplier_id=? OR backup_supplier_id=?
                """, (remove_id, remove_id)).fetchone()["c"]
                if linked_count > 0:
                    st.error(
                        f"Can't delete — {linked_count} ingredient(s) still link to this supplier. "
                        "Change those ingredients' supplier first."
                    )
                else:
                    conn.execute("DELETE FROM suppliers WHERE id=?", (remove_id,))
                    conn.commit()
                    st.success(f"Deleted {remove_label}.")
                    st.session_state.supplier_mode = "list"
                    st.rerun()
                conn.close()


# =========================================================
# PAGE: STAFF  (managers / owner only)
# =========================================================
elif page == "Staff":
    if "staff_mode" not in st.session_state:
        st.session_state.staff_mode = "list"

    title_col, btn1, btn2, btn3 = st.columns([4, 2, 2, 2])
    with title_col:
        st.title("Staff & PIN logins")
    with btn1:
        if st.button("+ Add New Staff", use_container_width=True):
            st.session_state.staff_mode = "add"
            st.rerun()
    with btn2:
        if st.button("Edit Staff", use_container_width=True):
            st.session_state.staff_mode = "edit"
            st.rerun()
    with btn3:
        if st.button("Remove Staff", use_container_width=True):
            st.session_state.staff_mode = "remove"
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
        st.caption("Manage who can log in to this app and what they can do.")
        table_data = []
        for s in staff_rows:
            table_data.append({
                "Name": s["name"],
                "PIN": s["pin"],
                "Role": s["role"],
                "Shared device?": "Yes" if s["is_shared_device"] else "No",
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # ---------------- ADD VIEW ----------------
    elif st.session_state.staff_mode == "add":
        st.subheader("Add a new staff member")
        with st.form("add_staff_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input("Name")
                new_pin = st.text_input("PIN (4-6 digits)", max_chars=6)
            with col2:
                new_role = st.selectbox("Role", ["staff", "manager", "owner"])
                new_shared = st.checkbox("This is a shared device PIN (e.g. shop iPad)")

            submitted = st.form_submit_button("Add staff member")
            if submitted:
                if not new_name or not new_pin:
                    st.error("Please enter a name and PIN.")
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

    # ---------------- EDIT VIEW ----------------
    elif st.session_state.staff_mode == "edit":
        st.subheader("Edit an existing staff member")
        if not staff_rows:
            st.info("No staff yet — add one first.")
        else:
            edit_labels = {f"{s['name']} ({s['role']})": s["id"] for s in staff_rows}
            edit_chosen_label = st.selectbox("Choose a staff member to edit", list(edit_labels.keys()), key="edit_staff_select")
            edit_id = edit_labels[edit_chosen_label]

            conn = db.get_connection()
            edit_current = conn.execute("SELECT * FROM staff WHERE id = ?", (edit_id,)).fetchone()
            conn.close()

            with st.form(f"edit_staff_form_{edit_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    e_name = st.text_input("Name", value=edit_current["name"])
                    e_pin = st.text_input("PIN (4-6 digits)", value=edit_current["pin"], max_chars=6)
                with col2:
                    role_choices = ["staff", "manager", "owner"]
                    e_role = st.selectbox("Role", role_choices, index=role_choices.index(edit_current["role"]))
                    e_shared = st.checkbox("This is a shared device PIN (e.g. shop iPad)", value=bool(edit_current["is_shared_device"]))

                update_submitted = st.form_submit_button("Update staff member")
                if update_submitted:
                    if not e_name or not e_pin:
                        st.error("Name and PIN can't be empty.")
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

    # ---------------- REMOVE VIEW ----------------
    elif st.session_state.staff_mode == "remove":
        st.subheader("Remove a staff member")
        if not staff_rows:
            st.info("No staff to remove yet.")
        else:
            staff_labels = {f"{s['name']} ({s['role']})": s["id"] for s in staff_rows}
            chosen_label = st.selectbox("Choose a staff member to remove", list(staff_labels.keys()), key="remove_staff_select")
            chosen_id = staff_labels[chosen_label]

            st.warning(f"This will permanently remove **{chosen_label}**.")
            if st.button("Confirm delete", type="primary"):
                conn = db.get_connection()
                owner_count = conn.execute("SELECT COUNT(*) AS c FROM staff WHERE role = 'owner'").fetchone()["c"]
                target = conn.execute("SELECT role FROM staff WHERE id = ?", (chosen_id,)).fetchone()
                if target["role"] == "owner" and owner_count <= 1:
                    st.error("Can't remove the only owner account. Add another owner/manager first.")
                else:
                    conn.execute("DELETE FROM staff WHERE id = ?", (chosen_id,))
                    conn.commit()
                    st.success("Removed.")
                    st.session_state.staff_mode = "list"
                    st.rerun()
                conn.close()


# =========================================================
# PAGE: TASK HISTORY  (managers / owner only)
# =========================================================
elif page == "Task History":
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
# PAGE: INVOICES  (managers / owner only)
# =========================================================
elif page == "Invoices":
    st.title("Invoice scanning")
    st.caption("Upload a photo of a supplier invoice. Small price changes (under 10%) are pre-approved; bigger changes need your tick before applying.")

    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.warning(
            "No API key found yet. Add `ANTHROPIC_API_KEY` under this app's "
            "Settings → Secrets on Streamlit Community Cloud, then refresh this page."
        )
    else:
        uploaded_file = st.file_uploader("Upload invoice photo", type=["png", "jpg", "jpeg"])

        if uploaded_file is not None:
            st.image(uploaded_file, width=300)

            if st.button("Scan invoice"):
                import anthropic
                import base64
                import json

                with st.spinner("Reading the invoice..."):
                    try:
                        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                        image_bytes = uploaded_file.getvalue()
                        b64_data = base64.b64encode(image_bytes).decode("utf-8")
                        media_type = uploaded_file.type or "image/jpeg"

                        response = client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=1024,
                            system=(
                                "You extract structured data from supplier invoice photos for a cafe's "
                                "stock system. Respond with ONLY valid JSON, no preamble, no markdown "
                                "code fences, no extra commentary."
                            ),
                            messages=[{
                                "role": "user",
                                "content": [
                                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_data}},
                                    {"type": "text", "text": (
                                        "Extract the supplier name, invoice date, and every line item from this "
                                        "invoice. For each line item give: description, pack size (if shown), "
                                        "and price. Respond as JSON exactly in this shape: "
                                        '{"supplier_name": "", "invoice_date": "", "line_items": '
                                        '[{"description": "", "pack_size": "", "price": 0.0}]}'
                                    )}
                                ]
                            }]
                        )

                        raw_text = response.content[0].text.strip()
                        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(raw_text)

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
                        }
                        st.rerun()

                    except json.JSONDecodeError:
                        st.error("Couldn't read structured data from that photo. Try a clearer, well-lit photo of the invoice.")
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
