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
    st.title("Cafe Manager")

    if st.session_state.pending_shared_login:
        st.subheader("Shop iPad — who are you?")
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
            if st.button("Continue"):
                chosen = staff_by_name[chosen_name]
                st.session_state.current_user = {"id": chosen["id"], "name": chosen["name"], "role": chosen["role"]}
                st.session_state.pending_shared_login = False
                st.rerun()
        st.stop()

    else:
        pin_entry = st.text_input("Enter your PIN", type="password", max_chars=6)
        if st.button("Log in"):
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

# ---------- Sidebar navigation ----------
st.sidebar.title("Cafe Manager")
st.sidebar.write(f"Logged in as **{current_user['name']}** ({current_user['role']})")
if st.sidebar.button("Log out"):
    st.session_state.current_user = None
    st.rerun()

nav_options = ["Tasks", "Master Stock List", "Recipes", "Suppliers"]
if is_manager:
    nav_options.append("Invoices")
    nav_options.append("Staff")
page = st.sidebar.radio("Go to", nav_options)


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
    st.title("Today's tasks")
    st.caption("Daily instructions for the kitchen and floor team.")

    conn = db.get_connection()
    all_tasks = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    conn.close()

    for section in ["Kitchen", "Floor"]:
        st.subheader(section)
        section_tasks = [t for t in all_tasks if t["section"] == section]
        if not section_tasks:
            st.write("No tasks yet.")
        for t in section_tasks:
            checked = st.checkbox(
                t["title"], value=bool(t["done"]), key=f"task_check_{t['id']}"
            )
            if t["done"]:
                st.caption(f"✅ Completed by {t['completed_by']} at {t['completed_at']}")

            if checked and not t["done"]:
                conn = db.get_connection()
                conn.execute(
                    "UPDATE tasks SET done=1, completed_by=?, completed_at=? WHERE id=?",
                    (current_user["name"], datetime.now().strftime("%-I:%M %p"), t["id"])
                )
                conn.commit()
                conn.close()
                st.rerun()
            elif not checked and t["done"]:
                conn = db.get_connection()
                conn.execute(
                    "UPDATE tasks SET done=0, completed_by=NULL, completed_at=NULL WHERE id=?",
                    (t["id"],)
                )
                conn.commit()
                conn.close()
                st.rerun()
        st.write("")

    if is_manager:
        st.divider()
        st.subheader("Add a new task")
        with st.form("add_task_form", clear_on_submit=True):
            task_title = st.text_input("Task description")
            task_section = st.selectbox("Section", ["Kitchen", "Floor"])
            submitted = st.form_submit_button("Add task")
            if submitted:
                if not task_title:
                    st.error("Please enter a task description.")
                else:
                    conn = db.get_connection()
                    conn.execute(
                        "INSERT INTO tasks (title, section, created_by, created_at, done) VALUES (?, ?, ?, ?, 0)",
                        (task_title, task_section, current_user["name"], date.today().isoformat())
                    )
                    conn.commit()
                    conn.close()
                    st.success("Task added.")
                    st.rerun()

        st.divider()
        st.subheader("Remove a task")
        conn = db.get_connection()
        removable = conn.execute("SELECT id, title, section FROM tasks ORDER BY section, title").fetchall()
        conn.close()
        if removable:
            labels = {f"[{t['section']}] {t['title']}": t["id"] for t in removable}
            to_remove_label = st.selectbox("Choose a task to remove", list(labels.keys()))
            if st.button("Remove task"):
                conn = db.get_connection()
                conn.execute("DELETE FROM tasks WHERE id = ?", (labels[to_remove_label],))
                conn.commit()
                conn.close()
                st.success("Task removed.")
                st.rerun()


# =========================================================
# PAGE 1: MASTER STOCK LIST
# =========================================================
if page == "Master Stock List":
    st.title("Master stock list")
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
        st.info("No ingredients yet. Add your first one below.")
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

    st.divider()
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
                st.rerun()

    st.divider()
    st.subheader("Edit or delete an existing ingredient")

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

            col_update, col_delete = st.columns(2)
            with col_update:
                update_submitted = st.form_submit_button("Update ingredient")
            with col_delete:
                delete_submitted = st.form_submit_button("Delete ingredient")

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
                    st.rerun()

            if delete_submitted:
                conn = db.get_connection()
                conn.execute("DELETE FROM ingredients WHERE id=?", (selected_id,))
                conn.commit()
                conn.close()
                st.success(f"Deleted {current['name']}.")
                st.rerun()


# =========================================================
# PAGE 2: RECIPES
# =========================================================
elif page == "Recipes":
    st.title("Recipes")
    st.caption("Prep, Dish, and Beverage recipes — costed automatically from the Master Stock List.")

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

    # ---------- Recipe list, grouped by type ----------
    conn = db.get_connection()
    all_recipes = conn.execute("SELECT * FROM recipes ORDER BY type, name").fetchall()
    conn.close()

    if not all_recipes:
        st.info("No recipes yet. Add your first one below.")
    else:
        for rtype in ["Prep", "Dish", "Beverage"]:
            group = [r for r in all_recipes if r["type"] == rtype]
            if not group:
                continue
            st.subheader(rtype)
            for r in group:
                cost = db.compute_recipe_cost(r["id"])
                cols = st.columns([3, 2, 2, 2, 2])
                cols[0].write(f"**{r['name']}**")
                if rtype == "Prep":
                    cols[1].write(f"Yields {r['yield_qty']:g}{r['yield_unit']}")
                    cols[2].write(f"Batch cost: ${cost:.2f}")
                    cols[3].write(f"Cost/unit: ${cost / r['yield_qty']:.4f}" if r["yield_qty"] else "-")
                else:
                    pct = (cost / r["selling_price"] * 100) if r["selling_price"] else None
                    status = db.food_cost_status(pct)
                    cols[1].write(f"Cost: ${cost:.2f}")
                    cols[2].write(f"Price: ${r['selling_price']:.2f}" if r["selling_price"] else "No price set")
                    if pct is not None:
                        badge = {"ok": "🟢", "warning": "🟡", "alert": "🔴"}[status]
                        cols[3].write(f"{badge} {pct:.1f}% food cost")
            st.write("")

    st.divider()
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
                st.success(f"Added {r_name} ({r_type}).")
                st.rerun()

    st.divider()
    st.subheader("Build or edit a recipe")

    all_recipe_options = recipe_options()
    if not all_recipe_options:
        st.info("Add a recipe above first, then come back here to add its ingredients.")
    else:
        selected_recipe_name = st.selectbox("Choose a recipe to build", list(all_recipe_options.keys()))
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

        st.write(f"**Current ingredients in {recipe['name']}:**")
        if not lines:
            st.write("No ingredients added yet.")
        else:
            for line in lines:
                if line["ingredient_id"] is not None:
                    label = f"{line['ingredient_name']} — {line['quantity']:g}{line['ingredient_unit']}"
                else:
                    label = f"{line['sub_recipe_name']} (Prep) — {line['quantity']:g}{line['sub_recipe_unit']}"
                row_col1, row_col2 = st.columns([5, 1])
                row_col1.write(label)
                if row_col2.button("Remove", key=f"remove_line_{line['id']}"):
                    conn = db.get_connection()
                    conn.execute("DELETE FROM recipe_lines WHERE id = ?", (line["id"],))
                    conn.commit()
                    conn.close()
                    st.rerun()

        # Live cost summary
        live_cost = db.compute_recipe_cost(selected_recipe_id)
        if recipe["type"] == "Prep":
            st.info(
                f"Batch cost: ${live_cost:.2f}  |  "
                f"Cost per {recipe['yield_unit']}: "
                f"${(live_cost / recipe['yield_qty']) if recipe['yield_qty'] else 0:.4f}"
            )
        else:
            if recipe["selling_price"]:
                pct = live_cost / recipe["selling_price"] * 100
                status = db.food_cost_status(pct)
                badge = {"ok": "🟢", "warning": "🟡", "alert": "🔴"}[status]
                st.info(f"Food cost: ${live_cost:.2f}  |  Selling price: ${recipe['selling_price']:.2f}  |  {badge} **{pct:.1f}% food cost**")
                if status == "alert":
                    st.error("⚠️ This recipe is at or above the 30% food cost alert threshold.")
                elif status == "warning":
                    st.warning("This recipe is above the 25% target food cost.")
            else:
                st.info(f"Food cost: ${live_cost:.2f}  |  No selling price set yet.")

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

        st.write("")
        if st.button("Delete this entire recipe", key=f"delete_recipe_{selected_recipe_id}"):
            conn = db.get_connection()
            used_elsewhere = conn.execute(
                "SELECT COUNT(*) AS c FROM recipe_lines WHERE sub_recipe_id = ?", (selected_recipe_id,)
            ).fetchone()["c"]
            if used_elsewhere > 0:
                st.error(f"Can't delete — this Prep is used in {used_elsewhere} other recipe(s). Remove it from those first.")
                conn.close()
            else:
                conn.execute("DELETE FROM recipes WHERE id = ?", (selected_recipe_id,))
                conn.commit()
                conn.close()
                st.success(f"Deleted {recipe['name']}.")
                st.rerun()


# =========================================================
# PAGE 3: SUPPLIERS
# =========================================================
elif page == "Suppliers":
    st.title("Suppliers")
    st.caption("Every supplier you buy from, and which ingredients link to them.")

    conn = db.get_connection()
    suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    conn.close()

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

            st.markdown("---")
            st.write("**Edit this supplier**")
            with st.form(f"edit_supplier_form_{s['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    es_name = st.text_input("Supplier name", value=s["name"], key=f"name_{s['id']}")
                    es_uen = st.text_input("UEN / Tax number", value=s["uen"] or "", key=f"uen_{s['id']}")
                    es_email = st.text_input("Email", value=s["email"] or "", key=f"email_{s['id']}")
                with col2:
                    es_phone = st.text_input("Contact number", value=s["phone"] or "", key=f"phone_{s['id']}")
                    es_address = st.text_input("Address", value=s["address"] or "", key=f"address_{s['id']}")
                    es_terms = st.text_input("Payment terms", value=s["payment_terms"] or "", key=f"terms_{s['id']}")
                    es_days = st.text_input("Delivery days", value=s["delivery_days"] or "", key=f"days_{s['id']}")

                col_u, col_d = st.columns(2)
                with col_u:
                    upd_submitted = st.form_submit_button("Update supplier")
                with col_d:
                    del_submitted = st.form_submit_button("Delete supplier")

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
                        st.rerun()

                if del_submitted:
                    conn = db.get_connection()
                    linked_count = conn.execute("""
                        SELECT COUNT(*) AS c FROM ingredients
                        WHERE primary_supplier_id=? OR backup_supplier_id=?
                    """, (s["id"], s["id"])).fetchone()["c"]
                    if linked_count > 0:
                        st.error(
                            f"Can't delete — {linked_count} ingredient(s) still link to this supplier. "
                            "Change those ingredients' supplier first."
                        )
                        conn.close()
                    else:
                        conn.execute("DELETE FROM suppliers WHERE id=?", (s["id"],))
                        conn.commit()
                        conn.close()
                        st.success(f"Deleted {s['name']}.")
                        st.rerun()

    st.divider()
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
                st.rerun()


# =========================================================
# PAGE: STAFF  (managers / owner only)
# =========================================================
elif page == "Staff":
    st.title("Staff & PIN logins")
    st.caption("Manage who can log in to this app and what they can do.")

    conn = db.get_connection()
    staff_rows = conn.execute("SELECT * FROM staff ORDER BY role, name").fetchall()
    conn.close()

    table_data = []
    for s in staff_rows:
        table_data.append({
            "Name": s["name"],
            "PIN": s["pin"],
            "Role": s["role"],
            "Shared device?": "Yes" if s["is_shared_device"] else "No",
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    st.divider()
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
                    st.rerun()
                conn.close()

    st.divider()
    st.subheader("Remove a staff member")
    if staff_rows:
        staff_labels = {f"{s['name']} ({s['role']})": s["id"] for s in staff_rows}
        chosen_label = st.selectbox("Choose a staff member to remove", list(staff_labels.keys()))
        if st.button("Remove staff member"):
            chosen_id = staff_labels[chosen_label]
            conn = db.get_connection()
            owner_count = conn.execute("SELECT COUNT(*) AS c FROM staff WHERE role = 'owner'").fetchone()["c"]
            target = conn.execute("SELECT role FROM staff WHERE id = ?", (chosen_id,)).fetchone()
            if target["role"] == "owner" and owner_count <= 1:
                st.error("Can't remove the only owner account. Add another owner/manager first.")
            else:
                conn.execute("DELETE FROM staff WHERE id = ?", (chosen_id,))
                conn.commit()
                st.success("Removed.")
                st.rerun()
            conn.close()


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

        if scan["supplier_matched"]:
            st.write(f"**Supplier:** {scan['supplier_input']} → matched to existing supplier **{scan['supplier_matched']}**")
        else:
            st.write(f"**Supplier:** {scan['supplier_input']} — ⚠️ not matched to an existing supplier (add manually on the Suppliers page if needed)")
        st.write(f"**Invoice date (as read):** {scan['invoice_date'] or 'not detected'}")

        conn = db.get_connection()
        all_ingredient_names = [r["name"] for r in conn.execute("SELECT name FROM ingredients").fetchall()]
        conn.close()

        for idx, row in enumerate(scan["rows"]):
            st.markdown("---")
            cols = st.columns([3, 2, 2])
            cols[0].write(f"**{row['description']}**  \n{row['pack_size']}")
            cols[1].write(f"Invoice price: ${row['new_price']:.2f}")

            if row["status"] == "unmatched":
                cols[2].write("🔴 No confident match")
                choice_options = ["-- skip this item --"] + all_ingredient_names
                st.selectbox(
                    "Match to an ingredient (or skip)",
                    choice_options,
                    key=f"inv_match_choice_{idx}"
                )
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
            applied_count = 0
            conn = db.get_connection()
            for idx, row in enumerate(scan["rows"]):
                if row["status"] == "unmatched":
                    chosen = st.session_state.get(f"inv_match_choice_{idx}")
                    if chosen and chosen != "-- skip this item --":
                        old = conn.execute("SELECT purchase_price FROM ingredients WHERE name = ?", (chosen,)).fetchone()
                        old_price = old["purchase_price"] if old else None
                        conn.execute(
                            "UPDATE ingredients SET purchase_price=?, last_updated=? WHERE name=?",
                            (row["new_price"], date.today().isoformat(), chosen)
                        )
                        conn.execute(
                            "INSERT INTO invoice_log (scanned_at, supplier_name, ingredient_name, old_price, new_price, pct_change, applied_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (date.today().isoformat(), scan["supplier_matched"] or scan["supplier_input"], chosen,
                             old_price, row["new_price"], None, current_user["name"])
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
                            (date.today().isoformat(), scan["supplier_matched"] or scan["supplier_input"], row["matched_ingredient"],
                             row["old_price"], row["new_price"], row["pct_change"], current_user["name"])
                        )
                        applied_count += 1
            conn.commit()
            conn.close()
            st.success(f"Applied {applied_count} price update(s).")
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
