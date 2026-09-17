```python
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import os
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# APPLICATION FACTORY
# ============================================================

def create_app():

    # --------------------------------------------------------
    # Project root
    #
    # /opt/render/project/src/
    # ├── app/
    # │   └── __init__.py
    # ├── templates/
    # ├── static/
    # ├── utils/
    # └── run.py
    # --------------------------------------------------------

    BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    # ========================================================
    # CREATE FLASK APPLICATION
    # ========================================================

    app = Flask(
        __name__,
        template_folder=os.path.join(
            BASE_DIR,
            "templates"
        ),
        static_folder=os.path.join(
            BASE_DIR,
            "static"
        )
    )

    # ========================================================
    # SECRET KEY
    # ========================================================

    app.secret_key = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key-in-production-32chars"
    )

    # ========================================================
    # SESSION SECURITY
    # ========================================================

    app.config["SESSION_COOKIE_HTTPONLY"] = True

    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.config["PERMANENT_SESSION_LIFETIME"] = 1800

    # Chỉ bật Secure khi chạy HTTPS.
    #
    # Render production chạy HTTPS nên có thể bật.
    # Local HTTP sẽ không bị lỗi nếu biến này được cấu hình
    # đúng theo môi trường.

    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get(
            "SESSION_COOKIE_SECURE",
            "1"
        ) == "1"
    )

    # ========================================================
    # JSON CONFIGURATION
    # ========================================================

    app.config["JSON_SORT_KEYS"] = False

    # ========================================================
    # FLASK-LIMITER
    # ========================================================
    #
    # Ưu tiên Redis nếu REDIS_URL thực sự là:
    #
    # redis://...
    #
    # hoặc:
    #
    # rediss://...
    #
    # Nếu REDIS_URL bị cấu hình sai hoặc không tồn tại,
    # tự động fallback về memory://
    #
    # Điều này tránh lỗi:
    #
    # ConfigurationError:
    # unknown storage scheme
    #
    # ========================================================

    redis_url = os.environ.get(
        "REDIS_URL",
        ""
    ).strip()

    if redis_url.startswith(
        (
            "redis://",
            "rediss://"
        )
    ):
        storage_uri = redis_url
    else:
        storage_uri = "memory://"

    # ========================================================
    # CREATE RATE LIMITER
    # ========================================================

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,

        # Default protection
        default_limits=[
            "60 per minute",
            "1000 per hour"
        ],

        # Redis hoặc memory fallback
        storage_uri=storage_uri,

        # Fixed window strategy
        strategy="fixed-window"
    )

    # Cho phép các module khác truy cập limiter
    app.limiter = limiter

    # ========================================================
    # REGISTER MAIN / API BLUEPRINTS
    # ========================================================

    from app.routes import (
        main_bp,
        api_bp
    )

    app.register_blueprint(
        main_bp
    )

    app.register_blueprint(
        api_bp,
        url_prefix="/api"
    )

    # ========================================================
    # REGISTER PRICING BLUEPRINT
    # ========================================================
    #
    # Pricing API:
    #
    # POST /api/pricing/quote
    #
    # GET:
    #
    # /api/pricing/health
    #
    # ========================================================

    try:

        from app.pricing import pricing_bp

        app.register_blueprint(
            pricing_bp
        )

    except ImportError:

        # Cho phép hệ thống vẫn chạy nếu pricing.py
        # chưa được tạo hoặc đang trong quá trình triển khai.
        #
        # Khi pricing.py đã tồn tại, blueprint sẽ được
        # đăng ký bình thường.

        app.logger.warning(
            "Pricing module chưa được load."
        )

    # ========================================================
    # APPLICATION HEALTH INFORMATION
    # ========================================================

    @app.context_processor
    def inject_app_info():

        return {
            "app_name": "Anti-Bot Pro",
            "environment": os.environ.get(
                "PRICING_ENVIRONMENT",
                "production"
            )
        }

    # ========================================================
    # RETURN APPLICATION
    # ========================================================

    return app
```
