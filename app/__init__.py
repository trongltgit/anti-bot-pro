from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__, 
                template_folder="../templates",
                static_folder="../static")
    
    app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production-32chars")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 1800  # 30 minutes

    # Rate Limiter - ưu tiên Redis, fallback memory
    redis_url = os.environ.get("REDIS_URL")
    storage_uri = redis_url if redis_url else "memory://"

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["60 per minute", "1000 per hour"],
        storage_uri=storage_uri,
        strategy="fixed-window"
    )

    app.limiter = limiter

    # Register blueprints
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
