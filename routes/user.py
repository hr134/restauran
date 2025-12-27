from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from extensions import db
from models.models import User, Order
from services.email import send_email
import os
import random
from werkzeug.utils import secure_filename
import json

user_bp = Blueprint('user', __name__)

@user_bp.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@user_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        email = request.form.get('email', '').strip()
        address_district = request.form.get('district')
        address_city = request.form.get('city')
        address_street = request.form.get('street')

        # Check if email is already taken by another user
        if email:
            existing_user = User.query.filter(db.func.lower(User.email) == email.lower(), User.id != user.id).first()
            if existing_user:
                flash("This email address is already associated with another account.", "danger")
                return render_template('edit_profile.html', user=user)

            # Check if email is being changed
            if user.email != email:
                user.email = email
                user.email_verified = False # Reset verification status
            
        user.full_name = full_name
        user.phone = phone
        user.address_district = address_district
        user.address_city = address_city
        user.address_street = address_street

        # Image upload
        img = request.files.get('profile_image')
        if img and img.filename:
            filename = secure_filename(img.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            img.save(filepath)
            user.profile_image = filename

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('user.profile'))

    return render_template('edit_profile.html', user=user)

@user_bp.route('/my-orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user = User.query.get(session['user_id'])
    my_orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    
    # Parse items JSON for display
    for o in my_orders:
        try:
             o.items_parsed = json.loads(o.items)
        except:
             o.items_parsed = []
             
    return render_template('orders.html', orders=my_orders)


@user_bp.route('/api/send-verification-code', methods=['POST'])
def api_send_verification_code():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    user = User.query.get(session['user_id'])
    
    data = request.json or {}
    email_to_verify = data.get('email', user.email or '').strip()

    if not email_to_verify or '@' not in email_to_verify:
        return jsonify({'success': False, 'message': 'Valid email address is required.'}), 400

    # check if email taken by another user
    existing = User.query.filter(User.email == email_to_verify, User.id != user.id).first()
    if existing:
        return jsonify({'success': False, 'message': 'This email is already used by another account.'}), 400
    
    # Generate 4-digit code
    code = str(random.randint(1000, 9999))
    user.email_verification_code = code
    db.session.commit()
    
    # Send email
    subject = "Finedine - Email Verification Code"
    body = f"Hello {user.full_name or user.username},\n\nYour 4-digit verification code is: {code}\n\nPlease enter this code in your profile to verify your email.\n\nRegards,\nRestaurant Team"
    
    email_status = send_email(subject, email_to_verify, body)
    
    if email_status:
        return jsonify({'success': True, 'message': f'Verification code sent to {email_to_verify}.'})
    else:
        return jsonify({'success': False, 'message': 'Failed to send verification email. Please try again later.'})

@user_bp.route('/api/verify-email-code', methods=['POST'])
def api_verify_email_code():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Authentication required'}), 401
    
    data = request.json
    code = data.get('code')
    new_email = data.get('email') 
    
    if not code:
        return jsonify({'success': False, 'message': 'Code is required'}), 400
    
    user = User.query.get(session['user_id'])
    
    if user.email_verification_code and user.email_verification_code == str(code):
        # Code matched. Update email if provided.
        if new_email and new_email != user.email:
             # Double check uniqueness
            existing = User.query.filter(User.email == new_email, User.id != user.id).first()
            if existing:
                return jsonify({'success': False, 'message': 'Email already taken by another user.'}), 400
            user.email = new_email
            
        user.email_verified = True
        user.email_verification_code = None # Clear code
        db.session.commit()
        return jsonify({'success': True, 'message': 'Email verified and updated successfully!'})
    else:
        return jsonify({'success': False, 'message': 'Invalid verification code.'})
