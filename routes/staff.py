from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from services.auth import role_required
from extensions import db
from models.models import Order, Reservation, User, MenuItem
import json
from datetime import datetime
import pytz

staff_bp = Blueprint('staff', __name__)

@staff_bp.route('/chef')
@role_required('chef', 'admin')
def chef():
    # Only show orders that are Placed, Confirmed, or Paid (essentially not canceled or delivered)
    active_statuses = ['Placed', 'Confirmed', 'Paid', 'Preparing']
    orders = Order.query.filter(Order.status.in_(active_statuses)).order_by(Order.created_at.asc()).all()
    for o in orders:
        try:
            o.items_parsed = json.loads(o.items)
        except:
            o.items_parsed = []
    return render_template('staff/kitchen.html', orders=orders)

@staff_bp.route('/chef/data')
@role_required('chef', 'admin')
def chef_data():
    active_statuses = ['Placed', 'Confirmed', 'Paid', 'Preparing']
    orders = Order.query.filter(Order.status.in_(active_statuses)).order_by(Order.created_at.asc()).all()
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
            'items': items,
            'created_at': o.created_at.strftime('%H:%M')
        })
    return jsonify({'orders': orders_json})

@staff_bp.route('/waiter')
@role_required('waiter', 'admin')
def waiter():
    # Show pending and confirmed reservations for today
    today = datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%Y-%m-%d')
    reservations = Reservation.query.filter(Reservation.date >= today).order_by(Reservation.time.asc()).all()
    # Also show active orders for dine-in
    orders = Order.query.filter(Order.order_type == 'dine_in', Order.status != 'Delivered').all()
    return render_template('staff/waiter.html', reservations=reservations, orders=orders)

@staff_bp.route('/waiter/data')
@role_required('waiter', 'admin')
def waiter_data():
    today = datetime.now(pytz.timezone('Asia/Dhaka')).strftime('%Y-%m-%d')
    reservations = Reservation.query.filter(Reservation.date >= today).order_by(Reservation.time.asc()).all()
    orders = Order.query.filter(Order.order_type == 'dine_in', Order.status == 'Ready').all()
    
    res_list = [{
        'id': r.id,
        'table_no': r.table_no,
        'guests': r.guests,
        'date': r.date,
        'time': r.time,
        'status': r.status
    } for r in reservations]
    
    order_list = [{
        'id': o.id,
        'unique_order_number': o.unique_order_number,
        'table': o.phone, 
        'phone': o.phone,
        'full_name': o.user.full_name if o.user else 'Guest',
        'status': o.status
    } for o in orders]
    
    return jsonify({'reservations': res_list, 'orders': order_list})

@staff_bp.route('/order/status/<int:order_id>', methods=['POST'])
@role_required('chef', 'waiter', 'admin')
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status:
        order.status = new_status
        db.session.commit()
        msg = f'Order #{order.unique_order_number} status updated to {new_status}.'
        flash(msg, 'success')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'message': msg})
    
    return redirect(request.referrer or url_for('staff.chef'))

@staff_bp.route('/reservation/status/<int:res_id>', methods=['POST'])
@role_required('waiter', 'admin')
def update_reservation_status(res_id):
    res = Reservation.query.get_or_404(res_id)
    new_status = request.form.get('status')
    if new_status:
        res.status = new_status
        db.session.commit()
        msg = f'Reservation #{res.unique_reservation_number} updated to {new_status}.'
        flash(msg, 'success')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'message': msg})
    
    return redirect(request.referrer or url_for('staff.waiter'))
