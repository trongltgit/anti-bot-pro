```python
"""
Anti-Bot Pro
============

Entry point cho Flask application.

Chạy local:
    python app.py

Production trên Render:
    gunicorn app:app
"""

import os
from flask import Flask, jsonify


def create_app():
    """
    Khởi tạo Flask application.

    Tách phần tạo app thành factory để sau này có thể
    bổ sung các module Anti-Bot mà không phải thay đổi
    Start Command trên Render.
    """

    app = Flask(__name__)

    # ---------------------------------------------------------
    # CẤU HÌNH
    # ---------------------------------------------------------
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "anti-bot-pro-dev-key"
    )

    # ---------------------------------------------------------
    # HEALTH CHECK
    # ---------------------------------------------------------
    @app.route("/")
    def index():
        return jsonify({
            "application": "Anti-Bot Pro",
            "status": "running",
            "service": "Flask",
            "environment": os.environ.get("FLASK_ENV", "production")
        })

    @app.route("/health")
    def health():
        return jsonify({
            "status": "healthy"
        })

    # ---------------------------------------------------------
    # ANTI-BOT STATUS
    # ---------------------------------------------------------
    @app.route("/api/anti-bot/status")
    def anti_bot_status():
        return jsonify({
            "application": "Anti-Bot Pro",
            "status": "active",
            "protection": True
        })

    return app


# =============================================================
# GUNICORN ENTRY POINT
# =============================================================
# Render Start Command:
#
#     gunicorn app:app
#
app = create_app()


# =============================================================
# LOCAL RUN
# =============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )
```
