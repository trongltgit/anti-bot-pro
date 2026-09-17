from functools import wraps
from flask import current_app


def custom_rate_limit(limit_string: str):
    """
    Decorator rate limit tùy chỉnh.
    Cách dùng: @custom_rate_limit("10 per minute")
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Lấy limiter từ app context
            limiter = getattr(current_app, "limiter", None)
            if limiter is None:
                return f(*args, **kwargs)
            # Áp dụng limit
            return limiter.limit(limit_string)(f)(*args, **kwargs)
        return wrapped
    return decorator
