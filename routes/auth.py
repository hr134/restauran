from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.models import User
from extensions import db
from services.email import send_email
import random
import secrets
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        role = 'customer' # Default role
        # Could have admin/staff registration page or use internal admin panel
        
        if not username or not password:
            flash('Provide username and password.', 'danger')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('auth.register'))
            
        u = User(username=username, password=generate_password_hash(password), role=role)
        db.session.add(u); db.session.commit()
        
        # Generate member_id: 75 + random(10,99) + id
        u.member_id = f"75{random.randint(10, 99)}{u.id}"
        db.session.commit()
        
        flash('Registered! Please login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid credentials.', 'danger')
            return redirect(url_for('auth.login'))
            
        # Check for deferred role activation
        from models.models import Employee
        from datetime import date
        employee_record = Employee.query.filter_by(user_id=user.id).first()
        
        if employee_record and employee_record.hire_date and employee_record.hire_date <= date.today():
             target_role = employee_record.position.lower()
             # If role doesn't match position (and isn't admin overriding it, though usually they match)
             if user.role != target_role:
                 user.role = target_role
                 db.session.commit()
                 flash(f'Welcome aboard! Your profile has been updated to {target_role.capitalize()}.', 'info')
            
        session.permanent = True  # Use PERMANENT_SESSION_LIFETIME (7 days)
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = str(getattr(user.role, 'name', user.role))
        session['is_admin'] = (session['role'] == 'admin')
        
        flash('Logged in successfully.', 'success')
        return redirect(url_for('main.index'))
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        flash('A password reset link has been sent to your email if the account exists.', 'success')
        
        if email and '@' in email:
            user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
            if user:
                token = secrets.token_urlsafe(32)
                user.reset_token = token
                user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=30)
                db.session.commit()
                
                reset_url = url_for('auth.reset_password', token=token, _external=True)
                email_body = f"""Hello {user.full_name or user.username},

You requested to reset your password. Click the link below to reset it:

{reset_url}

This link will expire in 30 minutes.

If you didn't request this, please ignore this email.

Regards,
Restaurant Team"""
                
                send_email("Password Reset Request", user.email, email_body)
        
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    
    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password:
            flash('Password is required.', 'danger')
            return render_template('reset_password.html', token=token)
        
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)
        
        user.password = generate_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        
        flash('Password reset successful! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', token=token)
