import os
import re
import json
import io
import uuid
import difflib
import random
import requests
import threading
import time
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_from_directory, send_file, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from xhtml2pdf import pisa
from dotenv import load_dotenv
from flask_mail import Mail, Message  # Import Flask-Mail
from flask_wtf.csrf import CSRFProtect

import openai
from openai import OpenAI

from bkash_config import BKASH

load_dotenv()

# Set your OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI()

# -------------------------
# Config
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-default-key-fallback')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Email Config
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_DEBUG'] = True # Enable verbose SMTP logs

mail = Mail(app)

# Helper functions send_email and format_order_body moved to services.email
from services.email import send_email, format_order_body


# -------------------------
# Config (Already done above)
# -------------------------

from extensions import db, mail, migrate, cache, compress

# -------------------------
# Config (Already done above)
# -------------------------

db.init_app(app)
csrf = CSRFProtect(app)
mail.init_app(app)
migrate.init_app(app, db)
cache.init_app(app)
compress.init_app(app)
from routes.auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/auth')

# ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']



from routes.admin import admin_bp
from routes.main import main_bp
from routes.cart import cart_bp
from routes.orders import orders_bp
from routes.user import user_bp
from routes.reservations import reservations_bp
from routes.chatbot import chatbot_bp
from routes.staff import staff_bp
# ERP Blueprints
from routes.analytics import analytics_bp
from routes.ai_insights import ai_insights_bp
from routes.crm import crm_bp
from routes.employees import employees_bp

app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(main_bp)
app.register_blueprint(cart_bp, url_prefix='/cart')
app.register_blueprint(orders_bp, url_prefix='/orders')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(reservations_bp, url_prefix='/reservations')
app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
app.register_blueprint(staff_bp, url_prefix='/staff')
# Register ERP blueprints
app.register_blueprint(analytics_bp)
app.register_blueprint(ai_insights_bp)
app.register_blueprint(crm_bp)
app.register_blueprint(employees_bp)


@app.before_request
def refresh_user_session():
    """
    Ensure the session is always in sync with the database.
    This handles immediate role updates (e.g. admin promotion/demotion)
    and ensuring deleted users are logged out.
    """
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            # Sync role and username from DB to Session
            session['role'] = user.role
            session['is_admin'] = (user.role == 'admin')
            session['username'] = user.username
        else:
            # User deleted from DB but still has cookie -> Logout them
            session.clear()


# -------------------------
# Models
# -------------------------
# Import models from the new package
from models.models import User, MenuItem, Order, Reservation, Rating, StaffShift, ReportLog


def is_profile_complete(user):
    if not user:
        return False

    required_fields = [
        user.full_name,
        user.email,
        user.phone,
        user.address_district,
        user.address_city,
        user.address_street
    ]

    # All fields must be non-empty, non-None, non-whitespace
    for field in required_fields:
        if not field or str(field).strip() == "":
            return False

    return True




# Models are imported from models.models


# -------------------------
# Create default admin & DB
# -------------------------

def create_admin_if_not_exists():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('adminpass'), role='admin')
        db.session.add(admin)
        db.session.commit()


# Run DB setup once, when the app starts
with app.app_context():
    db.create_all()
    create_admin_if_not_exists()


@app.context_processor
def inject_global_data():
    cart = session.get('cart', {})
    count = sum(cart.values()) if isinstance(cart, dict) else 0

    # Cached best rated item (5 minutes)
    @cache.cached(timeout=300, key_prefix='best_rated_item_context')
    def get_best_rated_item():
        # Eager load ratings to avoid N+1
        all_items = MenuItem.query.options(db.joinedload(MenuItem.ratings)).all()
        best_item = None
        max_avg = 0
        
        for it in all_items:
            # Calculate in-memory with pre-fetched ratings (no new queries)
            ratings = it.ratings
            if not ratings:
                avg = 0
            else:
                avg = round(sum(r.score for r in ratings) / len(ratings), 1)

            if avg > max_avg:
                max_avg = avg
                best_item = it
        return best_item

    return dict(cart_count=count, best_rated_item=get_best_rated_item())


# -------------------------
# Keep-Alive System for Render
# -------------------------
@app.route('/health')
def health_check():
    """Simple health check endpoint for keep-alive pings"""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now().isoformat(),
        'message': 'Site is active'
    }), 200


def keep_alive_worker():
    """
    Background worker that pings the site every 14 minutes
    to prevent Render from putting it to sleep after 15 minutes of inactivity
    """
    # Wait 2 minutes after startup before first ping
    time.sleep(120)
    
    while True:
        try:
            # Get the site URL from environment or use localhost as fallback
            site_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')
            ping_url = f"{site_url}/health"
            
            # Make the ping request
            response = requests.get(ping_url, timeout=10)
            
            if response.status_code == 200:
                print(f"[Keep-Alive] ✓ Ping successful at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"[Keep-Alive] ⚠ Ping returned status {response.status_code}")
                
        except Exception as e:
            print(f"[Keep-Alive] ✗ Ping failed: {str(e)}")
        
        # Wait 14 minutes before next ping (840 seconds)
        time.sleep(840)


# Start keep-alive thread only in production (when RENDER_EXTERNAL_URL is set)
if os.environ.get('RENDER_EXTERNAL_URL'):
    keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
    keep_alive_thread.start()
    print("[Keep-Alive] Background worker started - site will ping itself every 14 minutes")


# -------------------------
# Error Handlers
# -------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# -------------------------
# Run server
# -------------------------
if __name__ == '__main__':
    # If you change models and need a fresh DB: delete restaurant.db manually then restart.
    with app.app_context():
        db.create_all()
        create_admin_if_not_exists()
    app.run(debug=True)
