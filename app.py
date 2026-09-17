"""
Anti-Bot Pro - Entry point
Chạy local: python app.py
Production (Render): gunicorn app:app
"""

from flask import Flask
import os

app = Flask(__name__)


@app.route("/")
def index():
    return "Anti-Bot Pro is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )
