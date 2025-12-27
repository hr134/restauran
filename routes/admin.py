from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from services.auth import role_required
from services.email import send_email, format_order_body
from extensions import db, cache
from models.models import User, MenuItem, Order, Reservation, StaffShift, Rating, ReportLog, Employee, EmployeeRequest, Attendance
import os
import json
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@admin_bp.route('/')
@role_required('admin')
def index():
    items = MenuItem.query.order_by(MenuItem.id.desc()).all()
    # orders = Order.query.order_by(Order.created_at.desc()).all() # Optimization: limit or paginate in future
    orders = Order.query.order_by(Order.created_at.desc()).all()
    reservations = Reservation.query.order_by(Reservation.created_at.desc()).all()

    # Parse JSON items
    for o in orders:
        try:
            o.items_parsed = json.loads(o.items)
        except:
            o.items_parsed = []

    total_sales = db.session.query(db.func.sum(Order.total)).scalar() or 0
    
    # --- Live Operations Widget Logic ---
    from datetime import date
    
    # 1. Active Staff (Present today)
    # Join with User and Employee to get details
    active_attendance = db.session.query(Attendance, User, Employee)\
        .join(Employee, Attendance.employee_id == Employee.id)\
        .join(User, Employee.user_id == User.id)\
        .filter(Attendance.date == date.today(), Attendance.status == 'present')\
        .all()
    
    active_staff_count = len(active_attendance)
    active_staff_list = [{
        'name': u.full_name,
        'username': u.username,
        'role': e.position,
        'image': u.profile_image,
        'check_in': a.created_at.strftime('%I:%M %p') if a.created_at else 'N/A'
    } for a, u, e in active_attendance]
    
    # 2. Kitchen Status (Pending Orders)
    pending_orders_count = Order.query.filter(Order.status.in_(['Placed', 'Pending'])).count()
    
    kitchen_status = 'Normal'
    kitchen_status_color = 'success'
    if pending_orders_count >= 10:
        kitchen_status = 'Overload'
        kitchen_status_color = 'danger'
    elif pending_orders_count >= 5:
        kitchen_status = 'Busy'
        kitchen_status_color = 'warning'
        
    return render_template('admin/index.html', 
                           items=items, 
                           orders=orders, 
                           reservations=reservations, 
                           total_sales=total_sales,
                           active_staff_count=active_staff_count,
                           active_staff_list=active_staff_list,
                           kitchen_status=kitchen_status,
                           kitchen_status_color=kitchen_status_color,
                           pending_orders_count=pending_orders_count)

# -------------------------
# Menu Management
# -------------------------
@admin_bp.route('/menu/add', methods=['GET', 'POST'])
@role_required('admin')
def add_menu():
    if request.method == 'POST':
        name = request.form['name'].strip()
        price = float(request.form.get('price') or 0)
        category = request.form.get('category')
        ingredients = request.form.get('ingredients')
        availability = True if request.form.get('availability') else False
        stock_quantity = int(request.form.get('stock_quantity') or 0)
        low_stock_threshold = int(request.form.get('low_stock_threshold') or 5)

        # handle image upload
        file = request.files.get('image')
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

        mi = MenuItem(
            name=name,
            price=price,
            category=category,
            ingredients=ingredients,
            availability=availability,
            image=filename,
            stock_quantity=stock_quantity,
            low_stock_threshold=low_stock_threshold
        )
        db.session.add(mi); db.session.commit()
        cache.clear() # Clear cache so users see new item immediately
        flash('Menu item added.', 'success')
        return redirect(url_for('admin.index'))
    return render_template('admin/add_menu.html')


@admin_bp.route('/menu/edit/<int:item_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_menu(item_id):
    mi = MenuItem.query.get_or_404(item_id)
    if request.method == 'POST':
        mi.name = request.form['name'].strip()
        mi.price = float(request.form.get('price') or 0)
        mi.category = request.form.get('category')
        mi.ingredients = request.form.get('ingredients')
        mi.availability = True if request.form.get('availability') else False
        mi.stock_quantity = int(request.form.get('stock_quantity') or 0)
        mi.low_stock_threshold = int(request.form.get('low_stock_threshold') or 5)

        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            mi.image = filename

        db.session.commit()
        cache.clear() # Clear cache so update appears immediately
        flash('Menu item updated.', 'success')
        return redirect(url_for('admin.index'))
    return render_template('admin/edit_menu.html', item=mi)


@admin_bp.route('/menu/delete/<int:item_id>')
@role_required('admin')
def delete_menu(item_id):
    mi = MenuItem.query.get_or_404(item_id)
    # Optionally remove image file
    if mi.image:
        try:
            os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], mi.image))
        except:
            pass
    db.session.delete(mi); db.session.commit()
    cache.clear() # Clear cache
    flash('Menu item deleted.', 'success')
    return redirect(url_for('admin.index'))

# -------------------------
# Sales & Reporting
# -------------------------
@admin_bp.route('/sales')
@role_required('admin')
def sales_report():
    orders = Order.query.all()
    total_sales = db.session.query(db.func.sum(Order.total)).scalar() or 0
    
    # Calculate popular dishes
    dish_counts = {}
    for o in orders:
        try:
            items = json.loads(o.items)
            for item in items:
                name = item.get('name')
                qty = item.get('qty', 0)
                if name:
                    dish_counts[name] = dish_counts.get(name, 0) + qty
        except:
            continue
            
    popular = []
    for k, v in dish_counts.items():
        item = MenuItem.query.filter_by(name=k).first()
        avg = item.get_average_rating() if item else 0
        popular.append({
            'name': k, 
            'count': v, 
            'avg_rating': avg
        })
    
    popular = sorted(popular, key=lambda x: x['count'], reverse=True)
    
    return render_template('admin/sales.html', total_sales=total_sales, popular=popular)

# -------------------------
# User Management
# -------------------------
@admin_bp.route('/users')
@role_required('admin')
def users():
    users = User.query.order_by(User.id.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/admins')
@role_required('admin')
def admins():
    admins = User.query.filter_by(role='admin').order_by(User.id.desc()).all()
    # Also support old is_admin flag if needed, but lets try to rely on role.
    # The SRS plan says we moved to role enum.
    # However existing data might just use is_admin?
    # Actually User model has `role` column now.
    # The admin logic in routes/admin.html needs `admins` list.
    
    # We fetch users who are NOT admin for the "Promote" functionality
    other_users = User.query.filter(User.role != 'admin').order_by(User.username).all()
    return render_template('admin/admins.html', admins=admins, users=other_users)

# -------------------------
@admin_bp.route('/orders')
@role_required('admin')
def orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    for o in orders:
        try:
            o.items_parsed = json.loads(o.items)
        except:
            o.items_parsed = []
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/orders/data')
@role_required('admin')
def orders_data():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    orders_json = []
    for o in orders:
        try:
            items = json.loads(o.items)
        except:
            items = []
        orders_json.append({
            'id': o.id,
            'unique_order_number': o.unique_order_number,
            'status': o.status,
            'total': o.total,
            'customer': o.user.full_name if o.user else 'Guest',
            'username': o.user.username if o.user else 'guest',
            'created_at': o.created_at.strftime('%Y-%m-%d %H:%M'),
            'items': items
        })
    return jsonify({'orders': orders_json})

@admin_bp.route('/order/delete/<int:order_id>', methods=['POST', 'GET'])
@role_required('admin')
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    user = User.query.get(order.user_id)
    
    email_status = False
    if user and user.email:
        details = format_order_body(order)
        # Using print/send_email from services
        # We need to ensure message format is correct
        email_status = send_email(f"Order #{order.unique_order_number} Canceled", user.email,
                    f"Hello {user.full_name},\n\nYour order #{order.unique_order_number} has been CANCELED/DELETED by the admin.\n\n{details}\n\nIf you have already paid, a refund will be processed shortly.\n\nRegards,\nRestaurant Team")

    db.session.delete(order)
    db.session.commit()
    
    msg = 'Order has been deleted.'
    msg = 'Order has been deleted.'
    if not email_status and user and user.email:
        msg += f' (Note: Could not send email to {user.email})'
        
    flash(msg, 'success' if email_status else 'warning')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'message': msg,
            'email': user.email if user else None,
            'email_status': email_status
        })
    return redirect(request.referrer or url_for('admin.index'))


@admin_bp.route('/order/confirm/<int:order_id>')
@role_required('admin')
def confirm_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.status = 'Confirmed'
    db.session.commit()
    
    email_status = False
    user = User.query.get(order.user_id)
    if user and user.email:
        details = format_order_body(order)
        email_status = send_email(f"Order #{order.unique_order_number} Confirmed", user.email, 
                   f"Hello {user.full_name},\n\nYour order #{order.unique_order_number} has been confirmed. We are starting to prepare it!\n\n{details}\n\nRegards,\nRestaurant Team")

    msg = 'Order confirmed.'
    msg = 'Order confirmed.'
    if not email_status and user and user.email:
        msg += f' (Note: Could not send email to {user.email})'

    flash(msg, 'success' if email_status or not user or not user.email else 'warning')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'message': msg,
            'email': user.email if user else None,
            'email_status': email_status
        })
    return redirect(request.referrer or url_for('admin.index'))


@admin_bp.route('/order/<int:order_id>')
@role_required('admin')
def get_order(order_id):
    order = Order.query.get_or_404(order_id)
    try:
        items = json.loads(order.items)
    except:
        items = []
    
    user = User.query.get(order.user_id)
    return jsonify({
        'id': order.id,
        'unique_order_number': order.unique_order_number,
        'total': order.total,
        'status': order.status,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
        'customer': user.full_name if user else 'Unknown',
        'username': user.username if user else 'anon',
        'phone': order.phone,
        'address_street': order.address_street,
        'address_city': order.address_city,
        'address_district': order.address_district,
        'items': items
    })

# -------------------------
# Reservation Management
# -------------------------
@admin_bp.route('/reservations')
@role_required('admin')
def reservations():
    reservations = Reservation.query.order_by(Reservation.created_at.desc()).all()
    return render_template('admin/reservations.html', reservations=reservations)

@admin_bp.route('/reservations/data')
@role_required('admin')
def reservations_data():
    reservations = Reservation.query.order_by(Reservation.date.desc(), Reservation.time.desc()).all()
    res_json = [{
        'id': r.id,
        'unique_reservation_number': r.unique_reservation_number,
        'table_no': r.table_no,
        'username': r.user.username if r.user else 'guest',
        'full_name': r.user.full_name if r.user else 'Guest',
        'guests': r.guests,
        'duration': r.duration,
        'date': r.date,
        'time': r.time,
        'status': r.status
    } for r in reservations]
    return jsonify({'reservations': res_json})


@admin_bp.route('/reservation/cancel/<int:res_id>')
@role_required('admin')
def cancel_reservation(res_id):
    res = Reservation.query.get_or_404(res_id)
    res.status = 'Canceled'
    db.session.commit()

    msg = 'Reservation has been canceled.'
    user = User.query.get(res.user_id)
    email_status = False
    if user and user.email:
        email_status = send_email("Reservation Canceled", user.email,
                   f"Hello {user.full_name},\n\nYour reservation for Table {res.table_no} on {res.date} at {res.time} has been CANCELED by the admin.\n\nRegards,\nRestaurant Team")

    if not email_status and user and user.email:
        msg += f' (Note: Could not send email to {user.email})'

    flash(msg, 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'message': msg,
            'email': user.email if user else None,
            'email_status': email_status
        })
    return redirect(request.referrer or url_for('admin.index'))


@admin_bp.route('/reservation/confirm/<int:res_id>')
@role_required('admin')
def confirm_reservation(res_id):
    res = Reservation.query.get_or_404(res_id)
    res.status = 'Confirmed'
    db.session.commit()

    msg = 'Reservation confirmed.'
    user = User.query.get(res.user_id)
    email_status = False
    if user and user.email:
        email_status = send_email("Reservation Confirmed", user.email,
                   f"Hello {user.full_name},\n\nYour reservation for Table {res.table_no} on {res.date} at {res.time} has been CONFIRMED.\n\nWe look forward to hosting you!\n\nRegards,\nRestaurant Team")
        if email_status:
            msg += f' Notification sent to {user.email}.'
        elif email_status == 'pending':
            msg += f' Notification queued for {user.email}.'
        else:
            msg += f' (Note: Could not send email to {user.email})'

    flash(msg, 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'message': msg,
            'email': user.email if user else None,
            'email_status': email_status
        })
    return redirect(request.referrer or url_for('admin.index'))


@admin_bp.route('/reservation/remove/<int:res_id>')
@role_required('admin')
def remove_reservation(res_id):
    res = Reservation.query.get_or_404(res_id)
    user = User.query.get(res.user_id)
    
    email_status = False
    if user and user.email:
        email_status = send_email("Reservation Removed", user.email,
                   f"Hello {user.full_name},\n\nYour reservation record for Table {res.table_no} on {res.date} at {res.time} has been removed from our system.\n\nRegards,\nRestaurant Team")

    db.session.delete(res)
    db.session.commit()
    
    msg = 'Reservation removed.'
    if not email_status and user and user.email:
        msg += f' (Note: Could not send notification to {user.email})'

    flash(msg, 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'message': msg,
            'email': user.email if user else None,
            'email_status': email_status
        })
    return redirect(request.referrer or url_for('admin.index'))


# -------------------------
# Admin User API Routes
# -------------------------

@admin_bp.route('/user/<username>')
@role_required('admin')
def get_user(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    return jsonify({
        'username': user.username,
        'email': user.email,
        'full_name': user.full_name,
        'phone': user.phone,
        'address_street': user.address_street,
        'address_city': user.address_city,
        'address_district': user.address_district,
        'profile_image': user.profile_image,
        'email_verified': user.email_verified,
        'role': user.role
    })

@admin_bp.route('/user/<username>/update', methods=['POST'])
@role_required('admin')
def update_user(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    data = request.json
    user.email = data.get('email')
    user.full_name = data.get('full_name')
    user.phone = data.get('phone')
    user.address_street = data.get('address_street')
    user.address_city = data.get('address_city')
    # Can also update role
    if data.get('role'):
         user.role = data.get('role')
         # Sync employee status if applicable
         if user.role != 'customer':
             employee = Employee.query.filter_by(user_id=user.id).first()
             if employee:
                 employee.status = 'active'
         
    db.session.commit()

    email_status = False
    if user.email:
        email_status = send_email("Profile Updated by Admin", user.email, 
                   f"Hello {user.username},\n\nYour profile details have been updated by an administrator.\n\nRegards,\nRestaurant Team")

    return jsonify({
        'success': True,
        'email': user.email,
        'email_status': email_status
    })

@admin_bp.route('/user/<username>/delete', methods=['POST'])
@role_required('admin')
def delete_user_api(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    
    if user.id == session.get('user_id'):
        return jsonify({
            'success': False,
            'message': 'You cannot delete your own account while logged in.'
        }), 400
        
    if user.username == 'admin':
        return jsonify({
            'success': False,
            'message': 'System account "admin" is protected and cannot be deleted.'
        }), 400

    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            return jsonify({
                'success': False,
                'message': 'This is the last administrator account. You cannot delete it.'
            }), 400

    email = user.email
    db.session.delete(user)
    db.session.commit()

    email_status = False
    if email:
        email_status = send_email("Account Deleted", email, 
                   f"Hello {username},\n\nYour account has been deleted by an administrator. \n\nRegards,\nRestaurant Team")

    return jsonify({
        'success': True,
        'email': email,
        'email_status': email_status
    })

@admin_bp.route('/user/<username>/promote', methods=['POST'])
@role_required('admin')
def promote_user_api(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    if user.role == 'admin':
        return jsonify({'success': False, 'message': 'User is already an administrator.'}), 400
    
    user.role = 'admin'
    
    # Sync employee status
    employee = Employee.query.filter_by(user_id=user.id).first()
    if employee:
        employee.status = 'active'
        
    db.session.commit()
    
    email_status = False
    if user.email:
        email_status = send_email("Role Upgraded - Administrator", user.email, 
                   f"Hello {user.username},\n\nCongratulations! Your account has been promoted to Administrator. You now have full access to the Finedine Management Panel.\n\nRegards,\nFinedine Team")
        
    return jsonify({
        'success': True,
        'message': f'@{user.username} has been promoted to Administrator.',
        'email': user.email,
        'email_status': email_status
    })

@admin_bp.route('/user/<username>/demote', methods=['POST'])
@role_required('admin')
def demote_user_api(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    
    if user.id == session.get('user_id'):
        return jsonify({
            'success': False,
            'message': 'You cannot demote your own account. Use logout if you wish to leave.'
        }), 400

    if user.username == 'admin':
        return jsonify({
            'success': False,
            'message': 'System account "admin" is protected and cannot be demoted.'
        }), 400

    if user.role != 'admin':
        return jsonify({'success': False, 'message': 'User is not an administrator.'}), 400
    
    user.role = 'customer'
    db.session.commit()
    
    email_status = False
    if user.email:
        email_status = send_email("Account Status Update", user.email, 
                   f"Hello {user.username},\n\nYour account role has been changed to Regular User. You no longer have access to the Management Panel.\n\nRegards,\nFinedine Team")
        
    return jsonify({
        'success': True,
        'message': f'@{user.username} has been demoted to Regular User.',
        'email': user.email,
        'email_status': email_status
    })

@admin_bp.route('/user/<username>/promote-manager', methods=['POST'])
@role_required('admin')
def promote_manager_api(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    if user.role == 'manager':
        return jsonify({'success': False, 'message': 'User is already a manager.'}), 400
    
    user.role = 'manager'
    
    # Sync employee status
    employee = Employee.query.filter_by(user_id=user.id).first()
    if employee:
        employee.status = 'active'
        
    db.session.commit()
    
    email_status = False
    if user.email:
        email_status = send_email("Role Upgraded - Manager", user.email, 
                   f"Hello {user.username},\n\nCongratulations! Your account has been promoted to Manager. You now have access to the ERP features.\n\nRegards,\nFinedine Team")
        
    return jsonify({
        'success': True,
        'message': f'@{user.username} has been promoted to Manager.',
        'email': user.email,
        'email_status': email_status
    })

@admin_bp.route('/user/<username>/demote-manager', methods=['POST'])
@role_required('admin')
def demote_manager_api(username):
    user = User.query.filter_by(username=username.lower()).first_or_404()
    
    if user.role != 'manager':
        return jsonify({'success': False, 'message': 'User is not a manager.'}), 400
    
    user.role = 'customer'
    db.session.commit()
    
    email_status = False
    if user.email:
        email_status = send_email("Account Status Update", user.email, 
                   f"Hello {user.username},\n\nYour account role has been changed to Regular User. You no longer have access to ERP features.\n\nRegards,\nFinedine Team")
        
    return jsonify({
        'success': True,
        'message': f'@{user.username} has been demoted to Regular User.',
        'email': user.email,
        'email_status': email_status
    })



# -------------------------
# Inventory Management
# -------------------------
@admin_bp.route('/inventory')
@role_required('admin')
def inventory():
    items = MenuItem.query.order_by(MenuItem.category, MenuItem.name).all()
    return render_template('admin/inventory.html', items=items)

@admin_bp.route('/inventory/update/<int:item_id>', methods=['POST'])
@role_required('admin')
def update_stock(item_id):
    mi = MenuItem.query.get_or_404(item_id)
    try:
        mi.stock_quantity = int(request.form.get('stock_quantity', 0))
        mi.low_stock_threshold = int(request.form.get('low_stock_threshold', 5))
        db.session.commit()
        flash(f'Stock updated for {mi.name}.', 'success')
    except Exception as e:
        flash(f'Error updating stock: {str(e)}', 'danger')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 400
        
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'message': f'Stock updated for {mi.name}.'})
    return redirect(url_for('admin.inventory'))


# -------------------------
# Staff Shift Management
# -------------------------
@admin_bp.route('/shifts', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def shifts():
    # Only show staff (kitchen, waiter, cashier, admin)
    staff_users = User.query.filter(User.role != 'customer').all()
    all_shifts = StaffShift.query.order_by(StaffShift.shift_start.desc()).all()
    
    if session.get('role') == 'manager':
        # Managers view only
        return render_template('manager/shifts.html', staff=staff_users, shifts=all_shifts)
        
    return render_template('admin/shifts.html', staff=staff_users, shifts=all_shifts)

@admin_bp.route('/shifts/data')
@role_required('admin')
def shifts_data():
    all_shifts = StaffShift.query.order_by(StaffShift.shift_start.desc()).all()
    shifts_json = [{
        'id': s.id,
        'username': s.staff.username,
        'role': s.staff.role,
        'start': s.shift_start.strftime('%Y-%m-%d %H:%M'),
        'end': s.shift_end.strftime('%Y-%m-%d %H:%M')
    } for s in all_shifts]
    return jsonify({'shifts': shifts_json})

@admin_bp.route('/shifts/add', methods=['POST'])
@role_required('admin')
def add_shift():
    user_id = request.form.get('user_id')
    start_str = request.form.get('shift_start')
    end_str = request.form.get('shift_end')
    
    try:
        start_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
        end_dt = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')
        
        shift = StaffShift(user_id=user_id, shift_start=start_dt, shift_end=end_dt)
        db.session.add(shift)
        db.session.commit()
        flash('Staff shift added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding shift: {str(e)}', 'danger')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 400
        
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'message': 'Staff shift added successfully.'})
    return redirect(url_for('admin.shifts'))

@admin_bp.route('/shifts/delete/<int:shift_id>')
@role_required('admin')
def delete_shift(shift_id):
    shift = StaffShift.query.get_or_404(shift_id)
    db.session.delete(shift)
    db.session.commit()
    flash('Shift deleted.', 'success')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'message': 'Shift deleted successfully.'})
    return redirect(url_for('admin.shifts'))
@admin_bp.route('/employee-requests')
@role_required('admin')
def employee_requests():
    """List all pending employee requests"""
    requests = EmployeeRequest.query.order_by(EmployeeRequest.created_at.desc()).all()
    return render_template('admin/employee_requests.html', requests=requests)

@admin_bp.route('/employee-request/<int:req_id>/approve', methods=['POST'])
@role_required('admin')
def approve_employee_request(req_id):
    """Approve promotion or status update request"""
    req = EmployeeRequest.query.get_or_404(req_id)
    admin_notes = request.form.get('admin_notes', '')
    
    try:
        user = req.user
        if req.request_type == 'promotion':
            # Update user role only if hire date reached
            hire_date = req.hire_date or datetime.now().date()
            if hire_date <= datetime.now().date():
                 user.role = req.requested_role or 'waiter'
            
            # Create employee record
            employee = Employee(
                user_id=user.id,
                position=req.position,
                department=req.department,
                salary=req.salary,
                hire_date=hire_date,
                status='active'
            )
            db.session.add(employee)
            msg = f"Approved promotion for @{user.username} to {user.role}."
            
        elif req.request_type == 'status_update':
            # Update existing employee record
            employee = Employee.query.filter_by(user_id=user.id).first()
            if employee:
                employee.status = req.requested_status
                # If terminated, reset user role to customer
                if req.requested_status == 'terminated':
                    user.role = 'customer'
                msg = f"Approved status change for @{user.username} to {req.requested_status}."
            else:
                return jsonify({'success': False, 'message': 'Employee record not found.'}), 404

        req.status = 'approved'
        req.admin_notes = admin_notes
        db.session.commit()
        
        # Notify user (if email service is functional)
        if user.email:
            send_email("Employee Request Approved", user.email, 
                       f"Hello {user.username},\n\nYour recent employee-related request ({req.request_type}) has been APPROVED by an admin.\n\nNotes: {admin_notes or 'None'}\n\nRegards,\nFinedine Team")

        flash(msg, 'success')
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/employee-request/<int:req_id>/reject', methods=['POST'])
@role_required('admin')
def reject_employee_request(req_id):
    """Reject promotion or status update request"""
    req = EmployeeRequest.query.get_or_404(req_id)
    admin_notes = request.form.get('admin_notes', '')
    
    try:
        req.status = 'rejected'
        req.admin_notes = admin_notes
        db.session.commit()
        
        user = req.user
        if user.email:
            send_email("Employee Request Rejected", user.email, 
                       f"Hello {user.username},\n\nYour recent employee-related request ({req.request_type}) has been REJECTED by an admin.\n\nReason: {admin_notes or 'No reason provided'}\n\nRegards,\nFinedine Team")

        msg = f"Rejected request for @{user.username}."
        flash(msg, 'warning')
        return jsonify({'success': True, 'message': msg})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
