"""
Anti-Bot Pro + Pricing + Transaction
====================================

Entry point cho Flask application.

Chạy local:
    python app.py

Production (Render / Gunicorn):
    gunicorn app:app
"""

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    # Local demo: tắt Secure cookie để chạy HTTP
    if debug or os.environ.get("SESSION_COOKIE_SECURE", "0") != "1":
        app.config["SESSION_COOKIE_SECURE"] = False
    app.run(host="0.0.0.0", port=port, debug=debug)
