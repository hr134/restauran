from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.models import db, Employee, Attendance, User, EmployeeRequest
from datetime import datetime, date

employees_bp = Blueprint('employees', __name__, url_prefix='/employees')

def admin_required(f):
    """Decorator to require admin or manager role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import session
        if session.get('role') not in ['admin', 'manager']:
            flash('Access denied. Manager privileges required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@employees_bp.route('/')
@admin_required
def index():
    """List all employees and pending requests"""
    from flask import session
    employees = Employee.query.all()
    
    # Get pending requests based on role
    if session.get('role') == 'admin':
        pending_requests = EmployeeRequest.query.filter_by(status='pending').all()
    else:
        pending_requests = EmployeeRequest.query.filter_by(requested_by_id=session.get('user_id'), status='pending').all()
        
    template_folder = 'admin' if session.get('role') == 'admin' else 'manager'
    return render_template(f'{template_folder}/employee_management.html', 
                         employees=employees, 
                         pending_requests=pending_requests,
                         now=datetime.now)

@employees_bp.route('/users-search')
@admin_required
def users_search():
    """Search users for employee assignment"""
    query = request.args.get('q', '').lower()
    if not query:
        return {"users": []}
    
    # Find users matching query who are NOT already employees
    users = User.query.filter(
        (User.username.like(f'%{query}%')) | 
        (User.full_name.like(f'%{query}%')) |
        (User.member_id.like(f'%{query}%'))
    ).all()
    
    # Filter out existing employees
    employee_user_ids = [e.user_id for e in Employee.query.all()]
    available_users = [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name or u.username,
            "role": u.role,
            "member_id": u.member_id
        } 
        for u in users if u.id not in employee_user_ids
    ]
    
    return {"users": available_users}

@employees_bp.route('/add', methods=['POST'])
@admin_required
def add_employee():
    """Add new employee or request promotion if manager"""
    from flask import session
    try:
        user_id = request.form.get('user_id')
        position = request.form.get('position')
        department = request.form.get('department')
        salary = float(request.form.get('salary', 0))
        hire_date_str = request.form.get('hire_date')
        
        # Convert hire_date string to date object
        hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
        
        # Check if employee record already exists for this user
        existing = Employee.query.filter_by(user_id=user_id).first()
        if existing:
            flash('Employee record already exists for this user', 'warning')
            return redirect(url_for('employees.index'))

        if session.get('role') == 'manager':
            # Create request instead of direct add
            req = EmployeeRequest(
                user_id=user_id,
                request_type='promotion',
                requested_role='waiter',  # Default or let manager choose if we add it
                position=position,
                department=department,
                salary=salary,
                hire_date=hire_date,
                requested_by_id=session.get('user_id')
            )
            db.session.add(req)
            db.session.commit()
            flash('Employee promotion request submitted for Admin approval.', 'success')
            return redirect(url_for('employees.index'))
        
        # Admin can add directly
        employee = Employee(
            user_id=user_id,
            position=position,
            department=department,
            salary=salary,
            hire_date=hire_date,
            status='active'
        )
        
        # Automatically update user role to match position ONLY if hire date reached
        user = User.query.get(user_id)
        if user and hire_date <= date.today():
            user.role = position.lower()
            db.session.add(user) # Explicitly add modified user to session
            
        db.session.add(employee)
        db.session.commit()
        
        flash(f'Employee added successfully!', 'success')
        return redirect(url_for('employees.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('employees.index'))

@employees_bp.route('/edit/<int:id>', methods=['POST'])
@admin_required
def edit_employee(id):
    """Edit employee details or request status change if manager"""
    from flask import session
    try:
        employee = Employee.query.get_or_404(id)
        new_status = request.form.get('status', 'active')
        
        if session.get('role') == 'manager' and new_status != employee.status:
            # Create status update request
            req = EmployeeRequest(
                user_id=employee.user_id,
                request_type='status_update',
                requested_status=new_status,
                position=employee.position,
                department=employee.department,
                salary=employee.salary,
                requested_by_id=session.get('user_id'),
                admin_notes=f"Manager requested status change from {employee.status} to {new_status}"
            )
            db.session.add(req)
            db.session.commit()
            flash('Status change request submitted for Admin approval.', 'success')
            return redirect(url_for('employees.index'))

        # If manager but NO status change, we might allow editing other fields or block entirely
        # For now, let's allow admins to edit everything and managers only to request status changes
        if session.get('role') == 'manager':
            # In this simple implementation, managers can only request status changes
            # If they didn't change status, just return with a message
            flash('Managers can only request status changes. Other details must be updated by an Admin.', 'info')
            return redirect(url_for('employees.index'))

        # Admin logic
        employee.position = request.form.get('position')
        
        # --- SAFEGUARD: Prevent Self-Demotion ---
        if employee.user_id == session.get('user_id'):
            # If current user is Admin, ensure they aren't changing their position to something else
            # (which would auto-demote them due to our logic)
            if session.get('role') == 'admin' and employee.position.lower() != 'admin':
                flash("You cannot demote yourself from Administrator. Create another admin first or use the Users panel.", "danger")
                return redirect(url_for('employees.index'))
        # ----------------------------------------
        
        # Automatically update user role to match position
        if employee.user:
            employee.user.role = employee.position.lower()
            db.session.add(employee.user) # Explicitly add modified user to session
            
        employee.department = request.form.get('department')
        employee.salary = float(request.form.get('salary', 0))
        employee.status = new_status
        
        hire_date_str = request.form.get('hire_date')
        if hire_date_str:
            employee.hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
        
        db.session.commit()
        
        flash(f'Employee updated successfully!', 'success')
        return redirect(url_for('employees.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating employee: {str(e)}', 'danger')
        return redirect(url_for('employees.index'))

@employees_bp.route('/delete/<int:id>')
@admin_required
def delete_employee(id):
    """Delete employee record"""
    from flask import session
    try:
        employee = Employee.query.get_or_404(id)
        
        # --- SAFEGUARDS ---
        # 1. Prevent deleting self
        if employee.user_id == session.get('user_id'):
            flash("You cannot delete your own employee record.", "danger")
            return redirect(url_for('employees.index'))

        # 2. Prevent deleting system admin
        if employee.user and employee.user.username == 'admin':
            flash("Cannot delete the system 'admin' account.", "danger")
            return redirect(url_for('employees.index'))

        # 3. Prevent deleting last admin
        if employee.user and employee.user.role == 'admin':
            admin_count = User.query.filter_by(role='admin').count()
            if admin_count <= 1:
                flash("Cannot delete the last Administrator account.", "danger")
                return redirect(url_for('employees.index'))
        # ------------------
        
        # Revert user role to customer
        if employee.user:
            employee.user.role = 'customer'
            db.session.add(employee.user)
        
        db.session.delete(employee)
        db.session.commit()
        
        flash(f'Employee record deleted successfully! Role reverted to Customer.', 'success')
        return redirect(url_for('employees.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {str(e)}', 'danger')
        return redirect(url_for('employees.index'))

@employees_bp.route('/attendance')
@admin_required
def attendance():
    """View and manage attendance"""
    # Get date from query params, default to today
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    employees = Employee.query.filter_by(status='active').all()
    
    # Get attendance records for selected date
    attendance_records = {}
    for emp in employees:
        record = Attendance.query.filter_by(
            employee_id=emp.id,
            date=selected_date
        ).first()
        attendance_records[emp.id] = record
    
    from flask import session
    template_folder = 'admin' if session.get('role') == 'admin' else 'manager'
    return render_template(f'{template_folder}/attendance.html',
                         employees=employees,
                         attendance_records=attendance_records,
                         selected_date=selected_date)

@employees_bp.route('/attendance/mark', methods=['POST'])
@admin_required
def mark_attendance():
    """Mark attendance for an employee"""
    try:
        employee_id = int(request.form.get('employee_id'))
        date_str = request.form.get('date')
        status = request.form.get('status')
        notes = request.form.get('notes', '')
        
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if attendance already exists
        existing = Attendance.query.filter_by(
            employee_id=employee_id,
            date=attendance_date
        ).first()
        
        if existing:
            # Update existing record
            existing.status = status
            existing.notes = notes
        else:
            # Create new record
            attendance = Attendance(
                employee_id=employee_id,
                date=attendance_date,
                status=status,
                notes=notes
            )
            db.session.add(attendance)
        
        db.session.commit()
        
        flash('Attendance marked successfully!', 'success')
        return redirect(url_for('employees.attendance', date=date_str))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking attendance: {str(e)}', 'danger')
        return redirect(url_for('employees.attendance'))

@employees_bp.route('/staff-list')
@admin_required
def staff_list():
    """Get list of staff users for employee assignment"""
    staff_users = User.query.filter(User.role.in_(['chef', 'waiter', 'cashier', 'admin'])).all()
    
    # Get users who don't have employee records yet
    available_staff = []
    for user in staff_users:
        if not hasattr(user, 'employee_record') or user.employee_record is None:
            available_staff.append(user)
    
    return render_template('staff_list.html', staff_users=available_staff)
