"""
database.py
-------------------------------------------------------
This file is the "filing cabinet" for the whole app.
It defines what information we store (the tables) and
gives every other page a simple way to read/write data
without needing to know any SQL itself.

This version connects to a real, persistent Postgres
database (hosted on Supabase) instead of a local SQLite
file -- so your data survives app restarts and redeploys.
-------------------------------------------------------
"""

import streamlit as st
import psycopg2
import psycopg2.extras
from datetime import date, timedelta


# =========================================================
# Compatibility layer
# ---------------------------------------------------------
# The rest of this app was written using SQLite-style code:
#   conn.execute("SELECT ... WHERE x = ?", (value,)).fetchone()
# Postgres (via psycopg2) normally needs a separate cursor and
# uses %s instead of ? for placeholders. These two small wrapper
# classes translate between the two styles automatically, so we
# didn't have to rewrite every single query elsewhere in the app.
# =========================================================

class _CursorWrapper:
    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, query, params=None):
        pg_query = query.replace("?", "%s")
        if params is None:
            self._cur.execute(pg_query)
        else:
            self._cur.execute(pg_query, params)
        return self

    def executemany(self, query, seq_of_params):
        pg_query = query.replace("?", "%s")
        self._cur.executemany(pg_query, seq_of_params)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _ConnWrapper:
    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        real_cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return _CursorWrapper(real_cur)

    def execute(self, query, params=()):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_connection():
    """Opens a connection to the Supabase Postgres database."""
    pg_conn = psycopg2.connect(st.secrets["SUPABASE_DB_URL"])
    return _ConnWrapper(pg_conn)


# =========================================================
# Schema
# =========================================================

def init_db():
    """Creates all tables if they don't already exist. Safe to run every time the app starts."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            uen TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            payment_terms TEXT,
            delivery_days TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            primary_supplier_id INTEGER,
            backup_supplier_id INTEGER,
            purchase_size_label TEXT,
            purchase_qty REAL,
            base_unit TEXT,
            purchase_price REAL,
            recipe_unit_qty REAL,
            last_updated TEXT,
            FOREIGN KEY (primary_supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (backup_supplier_id) REFERENCES suppliers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            yield_qty REAL,
            yield_unit TEXT,
            selling_price REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipe_lines (
            id SERIAL PRIMARY KEY,
            parent_recipe_id INTEGER NOT NULL,
            ingredient_id INTEGER,
            sub_recipe_id INTEGER,
            quantity REAL NOT NULL,
            FOREIGN KEY (parent_recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id),
            FOREIGN KEY (sub_recipe_id) REFERENCES recipes(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            pin TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            is_shared_device INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoice_log (
            id SERIAL PRIMARY KEY,
            scanned_at TEXT,
            supplier_name TEXT,
            ingredient_name TEXT,
            old_price REAL,
            new_price REAL,
            pct_change REAL,
            applied_by TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_definitions (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            section TEXT NOT NULL,
            notes TEXT,
            recurrence TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            specific_date TEXT,
            created_by TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_log (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            week_start_date TEXT,
            completed_by TEXT,
            completed_at TEXT,
            reverted INTEGER DEFAULT 0,
            reverted_by TEXT,
            reverted_at TEXT,
            FOREIGN KEY (task_id) REFERENCES task_definitions(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_takes (
            id SERIAL PRIMARY KEY,
            ingredient_id INTEGER NOT NULL,
            count_date TEXT NOT NULL,
            quantity_counted REAL NOT NULL,
            counted_by TEXT,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def find_best_match(target_text, candidates):
    """
    Fuzzy-matches a piece of text (e.g. an invoice line item description)
    against a list of known names (e.g. your ingredient names), using
    Python's built-in difflib -- no extra packages needed.
    Returns (best_match_name, score) or (None, 0) if nothing is close enough.
    """
    import difflib
    if not target_text or not candidates:
        return None, 0.0
    matches = difflib.get_close_matches(target_text, candidates, n=1, cutoff=0.4)
    if not matches:
        return None, 0.0
    best = matches[0]
    score = difflib.SequenceMatcher(None, target_text.lower(), best.lower()).ratio()
    return best, score


def migrate_manager_role_to_owner():
    """
    The app used to support a 'manager' role. Roles are now simplified to
    just 'owner' and 'staff'. Any existing staff with role='manager' are
    upgraded to 'owner' (not downgraded to 'staff') so nobody loses access
    they previously had. Safe to run every time the app starts.
    """
    conn = get_connection()
    conn.execute("UPDATE staff SET role = 'owner' WHERE role = 'manager'")
    conn.commit()
    conn.close()


def seed_default_staff():
    """
    Creates one default Owner PIN and one shared 'Shop iPad' PIN, but only
    if the staff table is currently empty. Safe to call every time the app
    starts -- won't touch real staff you've already added.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM staff")
    if cur.fetchone()["c"] > 0:
        conn.close()
        return

    cur.execute(
        "INSERT INTO staff (name, pin, role, is_shared_device) VALUES (?, ?, ?, ?)",
        ("Owner", "0000", "owner", 0)
    )
    cur.execute(
        "INSERT INTO staff (name, pin, role, is_shared_device) VALUES (?, ?, ?, ?)",
        ("Shop iPad", "9999", "staff", 1)
    )
    conn.commit()
    conn.close()


def compute_recipe_cost(recipe_id, conn=None, _visited=None):
    """
    Recursively calculates the total cost of a recipe by walking through
    every ingredient line and every nested Prep-recipe line.

    This is the engine behind "Prep cost automatically flows into Dish cost."
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    if _visited is None:
        _visited = set()

    if recipe_id in _visited:
        if owns_conn:
            conn.close()
        return 0.0
    _visited.add(recipe_id)

    total = 0.0
    lines = conn.execute("SELECT * FROM recipe_lines WHERE parent_recipe_id = ?", (recipe_id,)).fetchall()

    for line in lines:
        if line["ingredient_id"] is not None:
            ing = conn.execute("SELECT * FROM ingredients WHERE id = ?", (line["ingredient_id"],)).fetchone()
            if ing and ing["purchase_qty"]:
                cost_per_base_unit = ing["purchase_price"] / ing["purchase_qty"]
                total += cost_per_base_unit * line["quantity"]

        elif line["sub_recipe_id"] is not None:
            sub_recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (line["sub_recipe_id"],)).fetchone()
            if sub_recipe and sub_recipe["yield_qty"]:
                sub_total_cost = compute_recipe_cost(line["sub_recipe_id"], conn, _visited)
                cost_per_base_unit = sub_total_cost / sub_recipe["yield_qty"]
                total += cost_per_base_unit * line["quantity"]

    if owns_conn:
        conn.close()
    return total


def compute_line_cost(line, conn):
    """
    Computes the cost contributed by a single recipe_lines row -- either a raw
    ingredient or a nested Prep recipe. Used to show per-ingredient costs in
    the recipe editor, using the exact same math as the recipe's total cost.
    """
    if line["ingredient_id"] is not None:
        ing = conn.execute("SELECT * FROM ingredients WHERE id = ?", (line["ingredient_id"],)).fetchone()
        if ing and ing["purchase_qty"]:
            return (ing["purchase_price"] / ing["purchase_qty"]) * line["quantity"]
        return 0.0
    elif line["sub_recipe_id"] is not None:
        sub_recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (line["sub_recipe_id"],)).fetchone()
        if sub_recipe and sub_recipe["yield_qty"]:
            sub_total_cost = compute_recipe_cost(line["sub_recipe_id"], conn)
            return (sub_total_cost / sub_recipe["yield_qty"]) * line["quantity"]
        return 0.0
    return 0.0


def food_cost_status(food_cost_pct):
    """Returns 'ok', 'warning', or 'alert' based on the 25% target / 30% alert thresholds."""
    if food_cost_pct is None:
        return None
    if food_cost_pct >= 30:
        return "alert"
    if food_cost_pct > 25:
        return "warning"
    return "ok"


def get_week_start(d=None):
    """Returns the ISO date string of the Monday of the week containing the given date (default: today)."""
    if d is None:
        d = date.today()
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()


def get_task_completion(task, conn=None):
    """
    Checks whether a task is currently 'done', looking at the MOST RECENT log
    entry only:
    - 'weekly' tasks reset automatically each week (checks the current week only)
    - 'once' tasks stay done forever once completed
    - if the most recent entry was reverted (undone), the task counts as not-done,
      but the entry itself stays in task_log for the history view.
    Returns (is_done, completed_by, completed_at, log_id) or (False, None, None, None).
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    if task["recurrence"] == "weekly":
        row = conn.execute(
            "SELECT * FROM task_log WHERE task_id = ? AND week_start_date = ? ORDER BY id DESC LIMIT 1",
            (task["id"], get_week_start())
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM task_log WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task["id"],)
        ).fetchone()

    if owns_conn:
        conn.close()

    if row and not row["reverted"]:
        return True, row["completed_by"], row["completed_at"], row["id"]
    return False, None, None, None


def cost_per_recipe_unit(ingredient_row):
    """
    The core costing formula used everywhere in the app:
    cost per recipe unit = (purchase price / purchase quantity) * recipe unit size
    Example: $30.90 for 12000g, recipe unit = 100g
             -> (30.90 / 12000) * 100 = $0.2575
    """
    if not ingredient_row["purchase_qty"] or ingredient_row["purchase_qty"] == 0:
        return 0.0
    return (ingredient_row["purchase_price"] / ingredient_row["purchase_qty"]) * ingredient_row["recipe_unit_qty"]


def seed_starter_data():
    """
    Loads your real starting suppliers and ingredients,
    but only if the database is currently empty -- so this
    never overwrites anything you've already entered.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM suppliers")
    if cur.fetchone()["c"] > 0:
        conn.close()
        return

    suppliers = [
        ("Tong Seng Produce", "201512345A", "orders@tongseng.com.sg", "+65 9123 4567",
         "123 Pasir Panjang Rd, Singapore", "Net 30", "Mon, Thu"),
        ("Huber's Butchery", "", "", "", "", "", ""),
        ("Phoon Huat", "", "", "", "", "", ""),
    ]
    cur.executemany("""
        INSERT INTO suppliers (name, uen, email, phone, address, payment_terms, delivery_days)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, suppliers)

    cur.execute("SELECT id, name FROM suppliers")
    supplier_ids = {row["name"]: row["id"] for row in cur.fetchall()}

    today = date.today().isoformat()

    ingredients = [
        ("Pasta Linguine", "Dry Goods", supplier_ids["Tong Seng Produce"], None,
         "12kg bag", 12000, "g", 30.90, 100, today),
        ("Diced Tomatoes", "Pantry", supplier_ids["Tong Seng Produce"], None,
         "2.55kg tin", 2550, "g", 7.19, 100, today),
        ("Streaky Bacon", "Meat", supplier_ids["Huber's Butchery"], None,
         "2kg pack", 2000, "g", 26.16, 50, today),
        ("Shredded Mozzarella", "Dairy", supplier_ids["Phoon Huat"], None,
         "5kg ctn", 5000, "g", 51.78, 20, today),
        ("Cooking Cream (Millac Gold)", "Dairy", supplier_ids["Phoon Huat"], None,
         "12L ctn", 12000, "ml", 53.41, 50, today),
    ]
    cur.executemany("""
        INSERT INTO ingredients
            (name, category, primary_supplier_id, backup_supplier_id,
             purchase_size_label, purchase_qty, base_unit, purchase_price,
             recipe_unit_qty, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ingredients)

    conn.commit()
    conn.close()
