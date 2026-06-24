"""
app.py
-------------------------------------------------------
This is the main screen of your cafe app.
Run it with:  streamlit run app.py
-------------------------------------------------------
"""

import streamlit as st
import pandas as pd
from datetime import date
import database as db

st.set_page_config(page_title="Cafe Manager", layout="wide")

# Make sure the database and starter data exist every time the app starts
db.init_db()
db.seed_starter_data()

# ---------- Sidebar navigation ----------
st.sidebar.title("Cafe Manager")
page = st.sidebar.radio("Go to", ["Master Stock List", "Suppliers"])


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


# =========================================================
# PAGE 2: SUPPLIERS
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
