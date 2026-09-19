from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import os
from dotenv import load_dotenv

load_dotenv()


def create_app():
    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )

    app.secret_key = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key-in-production-32chars",
    )

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800

    # Local demo: SESSION_COOKIE_SECURE=0
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    )

    app.config["JSON_SORT_KEYS"] = False

    # Render / reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url.startswith(("redis://", "rediss://")):
        storage_uri = redis_url
    else:
        storage_uri = "memory://"

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["60 per minute", "1000 per hour"],
        storage_uri=storage_uri,
        strategy="fixed-window",
    )
    app.limiter = limiter

    # Main + API
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Pricing
    try:
        from app.pricing import pricing_bp
        app.register_blueprint(pricing_bp)
    except ImportError:
        app.logger.warning("Pricing module chưa được load.")

    # Transaction
    try:
        from app.transaction import transaction_bp
        app.register_blueprint(transaction_bp)
    except ImportError:
        app.logger.warning("Transaction module chưa được load.")

    @app.context_processor
    def inject_app_info():
        return {
            "app_name": "Anti-Bot Pro + Pricing",
            "environment": os.environ.get("PRICING_ENVIRONMENT", "demo"),
        }

    return app
