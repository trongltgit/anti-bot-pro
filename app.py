"""
Entry point cho Gunicorn / local.

Render Start Command (khuyến nghị):
    gunicorn app:app

Hoặc:
    gunicorn run:app
"""

import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    if debug or os.environ.get("SESSION_COOKIE_SECURE", "0") != "1":
        app.config["SESSION_COOKIE_SECURE"] = False
    app.run(host="0.0.0.0", port=port, debug=debug)
