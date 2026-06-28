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
import psycopg2.pool
from datetime import date, timedelta


# =========================================================
# Connection pooling
# ---------------------------------------------------------
# Opening a brand new connection to Supabase for every single query (the
# original approach) requires a fresh network handshake each time, which is
# slow over the internet. A connection pool keeps a small set of connections
# open and ready, so "get_connection()" just borrows one instead of
# reconnecting from scratch -- this is what was making actions like removing
# an ingredient feel slow.
# =========================================================

@st.cache_resource
def _get_pool():
    return psycopg2.pool.ThreadedConnectionPool(1, 10, st.secrets["SUPABASE_DB_URL"])


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
    def __init__(self, pg_conn, pool):
        self._conn = pg_conn
        self._pool = pool
        self._returned = False

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
        # Instead of truly closing the TCP connection, return it to the pool
        # so the next get_connection() call can reuse it immediately.
        if not self._returned:
            self._pool.putconn(self._conn)
            self._returned = True


@st.cache_data(ttl=30)
def get_cached_ingredients_basic():
    """
    A lightweight, cached version of 'all ingredients (id, name, unit)' --
    used for dropdowns that don't need to be byte-fresh on every single
    click. Cuts down on repeated round-trips to Supabase, which is what was
    making actions like adding/removing a recipe line feel slow. Cache
    clears automatically after 30 seconds, or immediately after any
    ingredient is added/edited/removed (see calls to .clear() in app.py).
    """
    conn = get_connection()
    rows = conn.execute("SELECT id, name, base_unit FROM ingredients ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_connection():
    """Borrows a connection from the pool (instead of opening a new one each time)."""
    pool = _get_pool()
    pg_conn = pool.getconn()
    return _ConnWrapper(pg_conn, pool)


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
            current_stock_qty REAL,  -- running balance, in base_unit. NULL = never initialized
            min_stock_qty REAL,      -- low-stock alert threshold, in base_unit. NULL = no alert set
            FOREIGN KEY (primary_supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (backup_supplier_id) REFERENCES suppliers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipe_categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,        -- 'Prep', 'Dish', or 'Beverage' -- which tab this category lives under
            image_url TEXT,            -- public URL in Supabase Storage, or NULL to use a placeholder icon
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            category_id INTEGER,
            yield_qty REAL,
            yield_unit TEXT,
            selling_price REAL,
            FOREIGN KEY (category_id) REFERENCES recipe_categories(id)
        )
    """)

    # Migration safety net: adds category_id to recipes if this database was
    # created before recipe_categories existed. Safe to run every time.
    def _ensure_column(table, column, coltype):
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? AND column_name = ?",
            (table, column)
        )
        if not cur.fetchone():
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

    _ensure_column("recipes", "category_id", "INTEGER")
    _ensure_column("recipes", "tags", "TEXT")
    _ensure_column("recipes", "portions", "REAL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipe_conversions (
            id SERIAL PRIMARY KEY,
            recipe_id INTEGER NOT NULL,
            from_qty REAL NOT NULL,
            from_unit TEXT NOT NULL,
            to_qty REAL NOT NULL,
            to_unit TEXT NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            supplier_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',  -- 'draft', 'sent', or 'error'
            channel TEXT,                          -- 'whatsapp' or 'email', once chosen
            supplier_note TEXT,                    -- included in the message sent to the supplier
            internal_note TEXT,                    -- for your own team only, never sent
            delivery_date TEXT,                     -- requested delivery date, included in the message
            created_by TEXT,
            created_at TEXT,
            sent_at TEXT,
            error_message TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    """)

    _ensure_column("orders", "supplier_note", "TEXT")
    _ensure_column("orders", "internal_note", "TEXT")
    _ensure_column("orders", "delivery_date", "TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_lines (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            ingredient_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            kind TEXT NOT NULL,        -- 'info' or 'error'
            message TEXT NOT NULL,
            order_id INTEGER,
            created_at TEXT,
            created_by TEXT,
            is_read INTEGER DEFAULT 0, -- 0 = unread (still counts in the bell), 1 = read
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    _ensure_column("notifications", "is_read", "INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_sync_log (
            id SERIAL PRIMARY KEY,
            email_message_id TEXT UNIQUE,  -- prevents the same email ever being processed twice
            processed_at TEXT,
            processed_by TEXT,
            items_matched INTEGER,
            items_unmatched INTEGER,
            unmatched_names TEXT  -- comma-separated, for the Owner to review
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
            expected_qty_before REAL,  -- the running balance the system expected, before this count
            variance REAL,             -- quantity_counted - expected_qty_before
            is_flagged INTEGER DEFAULT 0, -- 1 if |variance| exceeds tolerance (1kg/1L/1 unit)
            FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
        )
    """)

    _ensure_column("stock_takes", "expected_qty_before", "REAL")
    _ensure_column("stock_takes", "variance", "REAL")
    _ensure_column("stock_takes", "is_flagged", "INTEGER DEFAULT 0")
    _ensure_column("ingredients", "current_stock_qty", "REAL")
    _ensure_column("ingredients", "min_stock_qty", "REAL")

    conn.commit()
    conn.close()


def upload_category_image(file_bytes, file_name, content_type):
    """
    Uploads an image to Supabase Storage (bucket: recipe-images) and returns
    its public URL, or None if the upload failed. Requires SUPABASE_URL and
    SUPABASE_SERVICE_KEY to be set in Streamlit secrets.
    """
    import requests
    import time
    import re

    project_url = st.secrets["SUPABASE_URL"].rstrip("/")
    api_key = st.secrets["SUPABASE_SERVICE_KEY"]
    bucket = "recipe-images"

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file_name)
    path = f"{int(time.time())}_{safe_name}"

    upload_url = f"{project_url}/storage/v1/object/{bucket}/{path}"
    response = requests.post(
        upload_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        data=file_bytes,
        timeout=30,
    )

    if response.status_code in (200, 201):
        return f"{project_url}/storage/v1/object/public/{bucket}/{path}"
    return None


def get_latest_stock_take_qty(ingredient_id, conn=None):
    """
    Returns the most recently recorded stock take quantity for an ingredient
    (in its base unit), or None if it's never been counted. Used to give a
    helpful starting point for the 'In Stock' reference field when ordering.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    row = conn.execute(
        "SELECT quantity_counted FROM stock_takes WHERE ingredient_id = ? ORDER BY count_date DESC, id DESC LIMIT 1",
        (ingredient_id,)
    ).fetchone()
    if owns_conn:
        conn.close()
    return row["quantity_counted"] if row else None


def get_variance_tolerance(base_unit):
    """
    Returns the acceptable variance (in base_unit) between what the system
    expected and what staff actually counted during a Stock Take, before
    it gets flagged for review. Matches the agreed tolerance: ±1kg for
    weight-based ingredients, ±1L for liquids, ±1 unit for countable items.
    """
    tolerance_map = {"g": 1000, "ml": 1000, "each": 1}
    return tolerance_map.get(base_unit, 1)


def get_order_unit(base_unit):
    """
    Maps an ingredient's storage base_unit (g/ml/each) to a friendlier
    ordering unit (Kg/L/Unit), so staff order in sensible quantities like
    "5 Kg" instead of "5000 g". Returns (display_unit_label, factor), where:
        base_unit_quantity_stored = entered_order_quantity * factor
    """
    mapping = {
        "g": ("Kg", 1000),
        "ml": ("L", 1000),
        "each": ("Unit", 1),
    }
    return mapping.get(base_unit, (base_unit, 1))


def build_order_message(order_id, conn=None):
    """
    Builds the plain-text order message for a given order: supplier name,
    then each line as "Ingredient — quantity Kg/L/Unit", plus the supplier
    note if one was added (the internal note is deliberately NOT included
    here, since it's for your own team only).
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (order["supplier_id"],)).fetchone()
    lines = conn.execute("""
        SELECT ol.quantity, i.name, i.base_unit
        FROM order_lines ol
        JOIN ingredients i ON ol.ingredient_id = i.id
        WHERE ol.order_id = ?
        ORDER BY i.name
    """, (order_id,)).fetchall()

    if owns_conn:
        conn.close()

    message_parts = [f"New order for {supplier['name']}:", ""]
    if order["delivery_date"]:
        message_parts.append(f"Requested delivery date: {order['delivery_date']}")
        message_parts.append("")
    for line in lines:
        display_unit, factor = get_order_unit(line["base_unit"])
        display_qty = line["quantity"] / factor
        message_parts.append(f"- {line['name']} — {display_qty:g} {display_unit}")
    if order["supplier_note"]:
        message_parts.append("")
        message_parts.append(f"Note: {order['supplier_note']}")
    message_parts.append("")
    message_parts.append("Thank you!")
    return "\n".join(message_parts)


def build_whatsapp_link(phone, message):
    """
    Builds a wa.me 'click to chat' link with the message pre-filled.
    This opens WhatsApp with the message ready to review and send --
    it does NOT send automatically, since true automated WhatsApp sending
    requires Meta's paid Business API and business verification.
    Returns None if no usable phone number is given.
    """
    import urllib.parse
    if not phone:
        return None
    digits_only = "".join(ch for ch in phone if ch.isdigit())
    if not digits_only:
        return None
    encoded_message = urllib.parse.quote(message)
    return f"https://wa.me/{digits_only}?text={encoded_message}"


def send_order_email(to_email, subject, message):
    """
    Actually sends an email via Gmail's SMTP server, using an App Password
    (not your real Gmail password -- a special password generated specifically
    for this purpose, which is what Google requires for non-Google apps to
    send mail through a Gmail account).

    Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD in Streamlit secrets.
    Returns (success: bool, error_message: str or None).
    """
    import smtplib
    from email.mime.text import MIMEText

    if "GMAIL_ADDRESS" not in st.secrets or "GMAIL_APP_PASSWORD" not in st.secrets:
        return False, "Email sending isn't set up yet (missing GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets)."

    sender = st.secrets["GMAIL_ADDRESS"]
    app_password = st.secrets["GMAIL_APP_PASSWORD"]

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(sender, app_password)
            server.sendmail(sender, [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def build_mailto_link(email, subject, message):
    """
    Builds a mailto: link with subject and body pre-filled. Opens the
    person's own email client with the message ready to review and send.
    Returns None if no email address is given.
    """
    import urllib.parse
    if not email:
        return None
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(message)
    return f"mailto:{email}?subject={encoded_subject}&body={encoded_body}"


def add_notification(kind, message, order_id=None, created_by=None, conn=None):
    """Logs an entry to the shared notification feed (visible to everyone via the bell icon)."""
    from datetime import datetime
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %-I:%M %p")
    conn.execute(
        "INSERT INTO notifications (kind, message, order_id, created_at, created_by) VALUES (?, ?, ?, ?, ?)",
        (kind, message, order_id, timestamp, created_by)
    )
    conn.commit()
    if owns_conn:
        conn.close()


def mark_all_notifications_read():
    """
    Marks every notification as read, so they stop counting toward the bell
    icon's badge. Called the moment someone opens the notifications panel --
    only genuinely NEW notifications (created since the last time anyone
    viewed the panel) should show up as an active alert.
    """
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
    conn.commit()
    conn.close()


def parse_pos_sales_file(file_bytes):
    """
    Parses a POS 'Itemised Sales Report' .xls file and returns a combined,
    aggregated list of [{"name": ..., "quantity_sold": ...}, ...] from BOTH
    the 'Product' and 'Modifier' sheets, since both represent things that
    consume ingredient stock (a whole dish, or an add-on like extra spinach).

    The real header row in this report format is the 3rd row of each sheet
    (the first two rows are a title and a date-range summary), so those are
    skipped. The same item can appear on multiple rows (e.g. sold via
    "Self Order", "Pick Up", and "Dine In" separately) -- these are summed
    together since what matters for stock deduction is the total sold.
    """
    import io
    import pandas as pd
    from collections import defaultdict

    totals = defaultdict(float)

    for sheet_name, name_column in [("Product", "Product Name"), ("Modifier", "Modifier Name")]:
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, skiprows=2, engine="xlrd")
        except Exception:
            continue  # sheet might not exist in some report variants -- skip gracefully

        if name_column not in df.columns or "Total Quantity Sold" not in df.columns:
            continue

        for _, row in df.iterrows():
            item_name = row.get(name_column)
            qty = row.get("Total Quantity Sold")
            if pd.isna(item_name) or pd.isna(qty):
                continue
            totals[str(item_name).strip()] += float(qty)

    return [{"name": k, "quantity_sold": v} for k, v in totals.items()]


def get_or_create_unmapped_category(conn=None):
    """
    Returns the id of a special 'Unmapped POS Items' Dish category, creating
    it if it doesn't exist yet. Every placeholder recipe auto-created from
    an unmatched sales item gets filed here, so they're all in one obvious
    place for the Owner to flesh out (or rename/re-map) later.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM recipe_categories WHERE name = ? AND type = 'Dish'", ("Unmapped POS Items",)
    ).fetchone()
    if existing:
        category_id = existing["id"]
    else:
        conn.execute(
            "INSERT INTO recipe_categories (name, type, created_at) VALUES (?, 'Dish', ?)",
            ("Unmapped POS Items", date.today().isoformat())
        )
        category_id = conn.execute(
            "SELECT id FROM recipe_categories WHERE name = ? AND type = 'Dish'", ("Unmapped POS Items",)
        ).fetchone()["id"]
        conn.commit()
    if owns_conn:
        conn.close()
    return category_id


def create_placeholder_recipe(pos_name, conn=None):
    """
    Creates a bare placeholder Recipe for a POS item that didn't match
    anything -- so it's visible and trackable in the Recipes page instead of
    silently disappearing. It starts with no ingredients/cost, but its name
    means the NEXT time this same item is sold, it'll match itself directly.
    Strips common POS prefixes (modifier "+", promo "[TAG]") for a cleaner name.
    Returns the new recipe's id.
    """
    import re
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    clean_name = re.sub(r"^\[.*?\]\s*", "", pos_name)  # strip a leading "[STUDENTMEAL] " style tag
    clean_name = re.sub(r"^\+\s*", "", clean_name)      # strip a leading "+ " modifier marker
    clean_name = clean_name.strip() or pos_name

    category_id = get_or_create_unmapped_category(conn)
    conn.execute(
        "INSERT INTO recipes (name, type, category_id) VALUES (?, 'Dish', ?)",
        (clean_name, category_id)
    )
    new_id = conn.execute("SELECT id FROM recipes WHERE name = ? AND category_id = ? ORDER BY id DESC LIMIT 1", (clean_name, category_id)).fetchone()["id"]

    if owns_conn:
        conn.commit()
        conn.close()
    return new_id


def apply_sales_deductions(confirmed_items, unmatched_pos_names, email_message_id, processed_by):
    """
    Takes the Owner-confirmed list of matched sales items and actually
    deducts stock. confirmed_items is a list of dicts each with at least
    "match_type" ("recipe" or "ingredient"), "match_id", and "quantity_sold".

    For a matched Recipe: walks its full ingredient breakdown (including
    nested Preps) via accumulate_recipe_ingredient_usage.
    For a matched Ingredient directly (e.g. a "+Bacon" modifier add-on):
    treats quantity_sold as that many of the ingredient's own recipe-portion
    size, the same convention used everywhere else in the app.

    Only deducts from ingredients that have already been stock-counted at
    least once (current_stock_qty is not NULL) -- there's nothing sensible
    to deduct from an uninitialized balance.

    unmatched_pos_names: items that didn't match anything at all. Rather
    than being silently skipped, each gets a placeholder Recipe created
    (filed under "Unmapped POS Items") so it's visible and trackable, and
    so the SAME item will match itself automatically next time it's sold.

    Returns a summary dict.
    """
    conn = get_connection()
    usage = {}

    for item in confirmed_items:
        if item["match_type"] == "recipe":
            accumulate_recipe_ingredient_usage(item["match_id"], item["quantity_sold"], usage, conn)
        elif item["match_type"] == "ingredient":
            ing = conn.execute("SELECT * FROM ingredients WHERE id = ?", (item["match_id"],)).fetchone()
            if ing and ing["recipe_unit_qty"]:
                usage[item["match_id"]] = usage.get(item["match_id"], 0.0) + item["quantity_sold"] * ing["recipe_unit_qty"]

    skipped_uninitialized = []
    low_stock_alerts = []

    for ingredient_id, qty_used in usage.items():
        ing = conn.execute("SELECT * FROM ingredients WHERE id = ?", (ingredient_id,)).fetchone()
        if ing["current_stock_qty"] is None:
            skipped_uninitialized.append(ing["name"])
            continue
        new_qty = ing["current_stock_qty"] - qty_used
        conn.execute("UPDATE ingredients SET current_stock_qty = ? WHERE id = ?", (new_qty, ingredient_id))
        if ing["min_stock_qty"] is not None and new_qty < ing["min_stock_qty"]:
            low_stock_alerts.append((ing["name"], new_qty, ing["min_stock_qty"], ing["base_unit"]))

    created_placeholders = []
    for pos_name in unmatched_pos_names:
        create_placeholder_recipe(pos_name, conn)
        created_placeholders.append(pos_name)

    matched_count = len(confirmed_items)
    conn.execute(
        "INSERT INTO sales_sync_log (email_message_id, processed_at, processed_by, items_matched, items_unmatched, unmatched_names) VALUES (?, ?, ?, ?, ?, ?)",
        (email_message_id, date.today().isoformat(), processed_by, matched_count, len(created_placeholders),
         ", ".join(created_placeholders) if created_placeholders else None)
    )

    if created_placeholders:
        add_notification(
            "info",
            f"Sales sync created {len(created_placeholders)} new placeholder recipe(s) for items that didn't match anything: "
            f"{', '.join(created_placeholders)}. Find them under Recipes → Dish → 'Unmapped POS Items' and add ingredients so future sales deduct stock correctly.",
            created_by=processed_by, conn=conn
        )
    if low_stock_alerts:
        for name, new_qty, min_qty, base_unit in low_stock_alerts:
            display_unit, factor = get_order_unit(base_unit)
            add_notification(
                "error",
                f"Low stock: {name} is now at {new_qty / factor:g} {display_unit} (alert set below {min_qty / factor:g} {display_unit}).",
                created_by=processed_by, conn=conn
            )
    if skipped_uninitialized:
        add_notification(
            "info",
            f"Sales sync skipped deducting {len(skipped_uninitialized)} ingredient(s) that have never been stock-counted yet: {', '.join(skipped_uninitialized)}. Do an initial Stock Take for these.",
            created_by=processed_by, conn=conn
        )

    conn.commit()
    conn.close()

    return {
        "ingredients_deducted": len(usage) - len(skipped_uninitialized),
        "skipped_uninitialized": skipped_uninitialized,
        "low_stock_alerts": low_stock_alerts,
        "created_placeholders": created_placeholders,
    }


def fetch_latest_pos_sales_email():
    """
    Connects to the POS sales report email account via IMAP and returns the
    most recent email that has an .xls attachment.
    Requires POS_GMAIL_ADDRESS and POS_GMAIL_APP_PASSWORD in Streamlit secrets
    (the same App Password mechanism used for order emails, just for this
    second account).
    Returns (result_dict, error_message). result_dict is None if nothing
    found or something went wrong; error_message explains why.
    """
    import imaplib
    import email as email_lib

    if "POS_GMAIL_ADDRESS" not in st.secrets or "POS_GMAIL_APP_PASSWORD" not in st.secrets:
        return None, "Email retrieval isn't set up yet (missing POS_GMAIL_ADDRESS / POS_GMAIL_APP_PASSWORD secrets)."

    address = st.secrets["POS_GMAIL_ADDRESS"]
    app_password = st.secrets["POS_GMAIL_APP_PASSWORD"]

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.login(address, app_password)
        imap.select("INBOX")

        status, message_numbers = imap.search(None, "ALL")
        if status != "OK" or not message_numbers[0]:
            imap.logout()
            return None, "No emails found in this inbox."

        ids = message_numbers[0].split()
        # Check the most recent emails first (newest last in IMAP's list), looking for one with an .xls attachment
        for msg_id in reversed(ids[-20:]):
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw_email = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw_email)
            message_id_header = msg.get("Message-ID") or f"no-id-{msg_id.decode()}"

            for part in msg.walk():
                filename = part.get_filename()
                if filename and filename.lower().endswith(".xls"):
                    file_bytes = part.get_payload(decode=True)
                    imap.logout()
                    return {"message_id": message_id_header, "filename": filename, "file_bytes": file_bytes}, None

        imap.logout()
        return None, "No recent email with an .xls attachment was found in the last 20 messages."
    except Exception as e:
        return None, str(e)


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


def match_sales_items_to_recipes_and_ingredients(parsed_items, conn=None):
    """
    For each {name, quantity_sold} parsed from a POS sales report, finds the
    best match among BOTH existing Recipes and Ingredients.

    Testing against a real POS export showed that matching against Recipes
    alone gets modifier add-ons wrong -- e.g. "+ Bacon" matched to the
    "Bacon Aglio" dish instead of the plain Bacon ingredient, and "Spinach"
    (an add-on) had no match at all since there's no "Spinach" recipe.
    Including ingredient names in the matching pool fixes both cases.

    Returns a list of dicts ready for a review screen:
        {"pos_name", "quantity_sold", "match_type" ("recipe"/"ingredient"/None),
         "match_id", "match_name", "score"}
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    recipes = conn.execute("SELECT id, name FROM recipes").fetchall()
    ingredients = conn.execute("SELECT id, name FROM ingredients").fetchall()
    if owns_conn:
        conn.close()

    name_to_recipe = {r["name"]: r["id"] for r in recipes}
    name_to_ingredient = {i["name"]: i["id"] for i in ingredients}
    combined_names = list(name_to_recipe.keys()) + list(name_to_ingredient.keys())

    results = []
    for item in parsed_items:
        match_name, score = find_best_match(item["name"], combined_names)
        match_type, match_id = None, None
        if match_name:
            if match_name in name_to_recipe:
                match_type, match_id = "recipe", name_to_recipe[match_name]
            elif match_name in name_to_ingredient:
                match_type, match_id = "ingredient", name_to_ingredient[match_name]
        results.append({
            "pos_name": item["name"], "quantity_sold": item["quantity_sold"],
            "match_type": match_type, "match_id": match_id, "match_name": match_name, "score": score
        })
    return results


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


def convert_to_base_unit(recipe_id, quantity, chosen_unit, base_unit, conn=None):
    """
    Converts a quantity entered in an alternate unit (defined via this
    recipe's Conversions, e.g. "1 Shot = 30 ml") into the recipe's base
    yield_unit, so the costing engine -- which always works in the base
    unit -- doesn't need to know about conversions at all.
    If chosen_unit already IS the base unit, returns quantity unchanged.
    """
    if chosen_unit == base_unit:
        return quantity
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recipe_conversions WHERE recipe_id = ? AND from_unit = ?",
        (recipe_id, chosen_unit)
    ).fetchone()
    if owns_conn:
        conn.close()
    if row and row["from_qty"]:
        ratio = row["to_qty"] / row["from_qty"]
        return quantity * ratio
    return quantity


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


def accumulate_recipe_ingredient_usage(recipe_id, multiplier, usage_dict, conn=None, _visited=None):
    """
    Recursively walks a recipe's lines (handling nested Prep sub-recipes,
    using the exact same recursion pattern as compute_recipe_cost) and adds
    up how much of each underlying ingredient gets used, scaled by
    `multiplier` (e.g. how many of this recipe were sold today).
    Accumulates directly into usage_dict: {ingredient_id: qty_in_base_unit}.
    Used by the POS sales sync to figure out how much stock to deduct.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    if _visited is None:
        _visited = set()

    if recipe_id in _visited:
        if owns_conn:
            conn.close()
        return usage_dict
    _visited.add(recipe_id)

    lines = conn.execute("SELECT * FROM recipe_lines WHERE parent_recipe_id = ?", (recipe_id,)).fetchall()

    for line in lines:
        if line["ingredient_id"] is not None:
            usage_dict[line["ingredient_id"]] = usage_dict.get(line["ingredient_id"], 0.0) + line["quantity"] * multiplier
        elif line["sub_recipe_id"] is not None:
            sub_recipe = conn.execute("SELECT * FROM recipes WHERE id = ?", (line["sub_recipe_id"],)).fetchone()
            if sub_recipe and sub_recipe["yield_qty"]:
                sub_multiplier = multiplier * (line["quantity"] / sub_recipe["yield_qty"])
                accumulate_recipe_ingredient_usage(line["sub_recipe_id"], sub_multiplier, usage_dict, conn, _visited)

    if owns_conn:
        conn.close()
    return usage_dict


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


def get_task_completions_batch(tasks, conn=None):
    """
    Same logic as get_task_completion, but for a whole list of tasks at once
    using a SINGLE database query instead of one query per task. This is
    what the Tasks page uses to render the weekly list -- with N tasks, the
    old approach made N round-trips to the database just to check who'd
    completed what; this makes one.
    Returns {task_id: (is_done, completed_by, completed_at, log_id)}.
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    task_ids = [t["id"] for t in tasks]
    if not task_ids:
        if owns_conn:
            conn.close()
        return {}

    placeholders = ",".join("?" * len(task_ids))
    all_logs = conn.execute(
        f"SELECT * FROM task_log WHERE task_id IN ({placeholders}) ORDER BY id DESC",
        task_ids
    ).fetchall()

    if owns_conn:
        conn.close()

    # Group log rows by task_id, newest first (since we ordered by id DESC)
    logs_by_task = {}
    for row in all_logs:
        logs_by_task.setdefault(row["task_id"], []).append(row)

    current_week = get_week_start()
    results = {}
    for t in tasks:
        rows_for_task = logs_by_task.get(t["id"], [])
        match = None
        if t["recurrence"] == "weekly":
            for row in rows_for_task:
                if row["week_start_date"] == current_week:
                    match = row
                    break  # first match is the newest, since list is id DESC
        else:
            if rows_for_task:
                match = rows_for_task[0]

        if match and not match["reverted"]:
            results[t["id"]] = (True, match["completed_by"], match["completed_at"], match["id"])
        else:
            results[t["id"]] = (False, None, None, None)

    return results


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


def export_all_tables_to_excel():
    """
    Builds a single Excel workbook with one sheet per table, covering the
    entire database. Returns the file as bytes, ready for a download button.
    This also doubles as a real backup of your data, independent of whatever
    Supabase's own backup settings are doing.
    """
    import io
    import pandas as pd

    tables = [
        "suppliers", "ingredients", "recipe_categories", "recipes",
        "recipe_lines", "recipe_conversions", "staff", "task_definitions",
        "task_log", "stock_takes", "invoice_log",
    ]

    conn = get_connection()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for table in tables:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
            # Excel sheet names can't exceed 31 characters
            sheet_name = table[:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    conn.close()

    output.seek(0)
    return output.getvalue()


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
