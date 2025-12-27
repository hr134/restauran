from functools import wraps
from flask import session, redirect, url_for, flash

def role_required(*roles):
    """Decorator to enforce role‑based access control.
    Usage: @role_required('admin', 'cashier')
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_role = session.get('role')
            if not user_role or user_role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('auth.login'))
            return fn(*args, **kwargs)
        return wrapper
    return decorator
