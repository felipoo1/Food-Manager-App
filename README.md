# Cafe Manager — v0.1 (Master Stock List + Suppliers)

This is the first real, working slice of your cafe management app.
It is NOT a mockup — this is the actual database and actual screens.

## What's working right now
- **Master Stock List** — view ingredients grouped by category, with live
  calculated cost per recipe unit, and a form to add new ingredients.
- **Suppliers** — view supplier details and which ingredients link to them
  (as Primary or Backup), and a form to add new suppliers.
- Your real starter data (Pasta Linguine, Diced Tomatoes, Streaky Bacon,
  Shredded Mozzarella, Cooking Cream, and the 3 suppliers we discussed) is
  pre-loaded automatically the first time you run it.

## What's NOT built yet (coming in the next steps)
- Recipes (Prep / Dish / Beverage) and food cost % calculations
- Team task dashboard with PIN logins
- Invoice photo scanning

## How to run this on your own computer

You'll need Python installed (free, from python.org — version 3.10 or
newer). Once installed:

1. Open a terminal (Mac: Terminal app, Windows: Command Prompt) and
   navigate into this folder. For example:
   ```
   cd path/to/cafe_app
   ```
2. Install the two required packages (one-time setup):
   ```
   pip install -r requirements.txt
   ```
3. Start the app:
   ```
   streamlit run app.py
   ```
4. Your browser will open automatically to a local web address
   (something like `http://localhost:8501`) showing the app.

Every time you want to use the app again later, you only need to repeat
step 3 — step 2 is one-time only.

## Where your data is stored

Your data is stored in a real, persistent Postgres database hosted on
**Supabase** (a free database hosting service) — not in a local file
inside this folder anymore. This means your data survives app restarts
and redeploys, unlike the original local-file setup.

The app connects using a single secret, `SUPABASE_DB_URL`, set under
your Streamlit app's Settings → Secrets. See the setup guide for how
to get this connection string from your Supabase project.

## A note on running this without installing anything

If you'd rather not install Python on your own computer at all, this
same app can be hosted for free on a service called Streamlit Community
Cloud, which runs it on the internet and gives you a link to open from
any device. We can set that up together when you're ready — just say so.
