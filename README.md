# Social Media Bot (Desktop Prototype)

This is a lightweight desktop prototype that helps generate engagement-focused social media posts while avoiding promotional messaging (no discounts, promos, or coupon wording).

What you get
- A small Tkinter desktop UI (`app.py`) to generate and preview posts
- A rule-based post generator that filters promotional language (`generator.py`)
- Local scheduling demo (`scheduler.py`) and connector stubs (`connectors/`)
- A Facebook connector with dry-run support (`connectors/facebook_connector.py`)
- Unit tests in `tests/`

Full setup & run steps (Windows PowerShell)

1) Clone the repo (if not already) and open a PowerShell terminal in the project root.

2) Create and activate a virtual environment:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

3) Install dependencies:

```powershell
pip install -r requirements.txt
```

4) Run unit tests to confirm everything is OK:

```powershell
# run all tests in the tests/ folder
python -m unittest discover -s tests -p "test_*.py" -v
```

5) Run the desktop app:

```powershell
python app.py
```

Using the Facebook connector (dry-run vs live)

The `FacebookConnector` supports a dry-run mode by default so you can test without posting to Facebook.

- Dry-run example (PowerShell one-liner):

```powershell
python -c "from connectors.facebook_connector import FacebookConnector; print(FacebookConnector(dry_run=True).post('Hello dry run'))"
```

- To post for real, set these environment variables in PowerShell (example):

```powershell
$env:FB_PAGE_ID = 'your_page_id'
$env:FB_ACCESS_TOKEN = 'your_page_access_token'
# run the real post
python -c "from connectors.facebook_connector import FacebookConnector; print(FacebookConnector(dry_run=False).post('Hello live test (no promos)'))"
```

Important notes about Facebook/Meta posting
- You must create and configure a Meta App and obtain a Page access token with the proper scopes (for posting, typically `pages_manage_posts` and related permissions). Follow Meta Graph API docs for creating long-lived tokens.
- Test with `dry_run=True` until you've confirmed permissions and behavior.
- Respect rate limits and platform terms. Do not post spammy content.

Security & secrets
- Never commit tokens or secrets to source control.
- Prefer using environment variables or a local secrets manager.
- For production, implement secure token storage and refresh logic; consider an OAuth flow for user accounts.

Customizing the generator
- `generator.py` contains templates, insights, and a `PROMO_WORDS` list. Edit templates or `PROMO_WORDS` to change tone or allowed content.

Next steps and extensions
- Wire the UI to post via the real `FacebookConnector` with a switch for dry-run vs live.
- Add persistence for scheduled posts (SQLite/Postgres) and a retry queue.
- Add an LLM-based content generator with guardrails to avoid promotional language (requires API key for an LLM provider).

If you want, I can implement one of the next steps for you (OAuth flow, persistent scheduling, or LLM generator). Tell me which and I will implement it.
# Social Media Bot (Desktop Prototype)

This is a lightweight desktop prototype that helps generate engagement-focused social media posts without offering promotions or discounts.

Features
- Tkinter-based desktop UI to generate and preview posts
- Rule-based post generator that avoids promotional language (discounts/promos)
- Save drafts, export to CSV, and schedule posts locally
- Stubs for social media connectors (placeholders for API integration)

What this is NOT
- This prototype does not ship posts to real platforms out of the box. Connectors are stubs so you can add platform API keys and logic.

Getting started (Windows)
1. Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python app.py
```

Extending for real platforms
- Add API keys (use environment variables or a .env file) and implement the posting functions in `connectors/`.
- Ensure you follow each platform's API terms and rate limits.

Notes
- The generator intentionally filters out words like "discount", "sale", "promo", and similar to avoid promotional messaging.
