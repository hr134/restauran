from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models.models import User, Reservation
from datetime import datetime, timedelta

reservations_bp = Blueprint('reservations', __name__)

def check_table_availability(date, time, duration=2, table_no=None):
    """
    Checks if a table is available.
    Returns (bool, message)
    """
    try:
        # 1. Parse DateTime
        req_start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        req_end = req_start + timedelta(hours=duration)
        now = datetime.now()
    except ValueError:
        return False, "Invalid date/time format. Use YYYY-MM-DD and HH:MM."

    # 2. Check Past Date
    if req_start < now:
        return False, "You cannot book a table in the past."

    # 3. Check Opening Hours (11:00 to 23:00)
    if req_start.hour < 11:
        return False, "We are closed. Opening hours are 11:00 AM - 11:00 PM."
    
    if req_start.hour >= 22:
        return False, "Our last seating is at 10:00 PM."

    # 4. Check Conflicts in DB
    if table_no and table_no != "Any":
        conflict = Reservation.query.filter_by(date=date, table_no=table_no).all()
        for r in conflict:
            existing_start = datetime.strptime(f"{r.date} {r.time}", "%Y-%m-%d %H:%M")
            existing_end = existing_start + timedelta(hours=r.duration)

            # Check Overlap
            if req_start < existing_end and req_end > existing_start:
                return False, f"Table {table_no} is already booked at that time."

    return True, "Available"

@reservations_bp.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if 'user_id' not in session:
        flash('Please login to make a reservation.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])

    # Profile check
    if not user.is_complete:
        flash('Please complete your profile before reserving a table.', 'warning')
        return redirect(url_for('user.edit_profile'))

    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        duration = int(request.form['duration'])
        guests = int(request.form['guests'])
        table_no = request.form['table_no']

        is_valid, msg = check_table_availability(date, time, duration, table_no)
        
        if not is_valid:
            flash(msg, 'danger')
            return redirect(url_for('reservations.reserve'))

        new_res = Reservation(
            user_id=user.id,
            date=date,
            time=time,
            duration=duration,
            guests=guests,
            table_no=table_no,
            status="Pending"
        )

        db.session.add(new_res)
        db.session.commit()

        flash("Reservation successful!", 'success')
        return redirect(url_for('reservations.my_reservations'))

    return render_template('reserve.html')

@reservations_bp.route('/')
def my_reservations():
    if 'user_id' not in session:
        flash('Please login.')
        return redirect(url_for('auth.login'))
    res = Reservation.query.filter_by(user_id=session['user_id']).order_by(Reservation.created_at.desc()).all()
    return render_template('reservations.html', reservations=res)

@reservations_bp.route('/reservation/cancel/<int:res_id>')
def cancel_reservation(res_id):
    if 'user_id' not in session:
        flash('Please login first.', 'danger')
        return redirect(url_for('auth.login'))

    r = Reservation.query.get(res_id)

    if not r or r.user_id != session['user_id']:
        flash('Reservation not found.', 'danger')
        return redirect(url_for('reservations.my_reservations'))

    r.status = 'Canceled'
    db.session.commit()

    flash('Reservation has been canceled successfully.', 'success')
    return redirect(url_for('reservations.my_reservations'))
