from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

def get_dhaka_time():
    return datetime.now(pytz.timezone('Asia/Dhaka'))
import uuid
from extensions import db

# User model with role-based access control
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    member_id = db.Column(db.String(20), unique=True)  # Custom ID
    email = db.Column(db.String(200), unique=True)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    address_district = db.Column(db.String(100))
    address_city = db.Column(db.String(100))
    address_street = db.Column(db.String(200))
    profile_image = db.Column(db.String(200))  # image filename
    # Password reset fields
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    # Role based access control
    role = db.Column(db.Enum('admin', 'manager', 'cashier', 'waiter', 'chef', 'customer', name='user_roles'), default='customer')
    # Email verification
    email_verified = db.Column(db.Boolean, default=False)
    email_verification_code = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=get_dhaka_time)
    # Relationships
    orders = db.relationship('Order', backref='user', lazy=True)
    reservations = db.relationship('Reservation', backref='user', lazy=True)
    ratings = db.relationship('Rating', backref='user', lazy=True)
    staff_shifts = db.relationship('StaffShift', backref='user', lazy=True)
    staff_shifts = db.relationship('StaffShift', backref='user', lazy=True)

    @property
    def is_complete(self):
        required_fields = [self.full_name, self.phone, self.address_district, self.address_city, self.address_street]
        return all(field and field.strip() for field in required_fields)

class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    category = db.Column(db.String(100), nullable=True)
    ingredients = db.Column(db.String(400), nullable=True)
    availability = db.Column(db.Boolean, default=True)
    image = db.Column(db.String(300), nullable=True)
    # Inventory fields
    stock_quantity = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=5)
    # Relationships
    ratings = db.relationship('Rating', backref='menu_item', lazy=True, cascade="all, delete-orphan")

    def get_average_rating(self):
        if not self.ratings:
            return 0
        return round(sum(r.score for r in self.ratings) / len(self.ratings), 1)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    unique_order_number = db.Column(db.String(12), unique=True, nullable=False, default=lambda: str(uuid.uuid4().hex[:12]).upper())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.Column(db.Text, nullable=False)  # JSON string of items
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Placed')
    payment_status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(20), nullable=True)
    discount = db.Column(db.Float, default=0.0)
    order_type = db.Column(db.Enum('dine_in', 'takeaway', name='order_type'), default='dine_in')
    phone = db.Column(db.String(50), nullable=False)
    address_district = db.Column(db.String(100), nullable=False)
    address_city = db.Column(db.String(100), nullable=False)
    address_street = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=get_dhaka_time)
    items_parsed = db.Column(db.PickleType)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_reservation_number = db.Column(db.String(12), unique=True, nullable=False, default=lambda: str(uuid.uuid4().hex[:12]).upper())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    time = db.Column(db.String(50), nullable=False)  # Start time (HH:MM)
    duration = db.Column(db.Integer, nullable=False)  # Duration in hours
    guests = db.Column(db.Integer, nullable=False)
    table_no = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=get_dhaka_time)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    score = db.Column(db.Integer, nullable=False)  # 1-5
    created_at = db.Column(db.DateTime, default=get_dhaka_time)


class StaffShift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shift_start = db.Column(db.DateTime, nullable=False)
    shift_end = db.Column(db.DateTime, nullable=False)


class ReportLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_type = db.Column(db.String(50), nullable=False)
    generated_at = db.Column(db.DateTime, default=get_dhaka_time)
    report_metadata = db.Column(db.Text, nullable=True)  # JSON string with extra info


# ERP Models for Analytics and Management

class SaleItem(db.Model):
    """Track individual items within orders for detailed analytics"""
    __tablename__ = 'sale_item'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey('menu_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False)  # Price at time of sale
    created_at = db.Column(db.DateTime, default=get_dhaka_time)
    
    # Relationships
    order = db.relationship('Order', backref=db.backref('sale_items', lazy=True, cascade='all, delete-orphan'))
    menu_item = db.relationship('MenuItem', backref=db.backref('sale_items', lazy=True))


class Employee(db.Model):
    """Employee management with HR data"""
    __tablename__ = 'employee'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    position = db.Column(db.String(100), nullable=False)  # Chef, Waiter, Cashier, Manager, etc.
    department = db.Column(db.String(100))  # Kitchen, Service, Management, etc.
    salary = db.Column(db.Float)
    hire_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, on_leave, terminated
    created_at = db.Column(db.DateTime, default=get_dhaka_time)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('employee_record', uselist=False, lazy=True))
    attendance_records = db.relationship('Attendance', backref='employee', lazy=True, cascade='all, delete-orphan')
    
    def total_days_worked(self):
        """Calculate total days worked based on attendance"""
        return len([a for a in self.attendance_records if a.status == 'present'])


class EmployeeRequest(db.Model):
    """Pending requests for employee promotions or status changes (Leave/Termination)"""
    __tablename__ = 'employee_request'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_type = db.Column(db.String(20), nullable=False) # 'promotion' or 'status_update'
    requested_role = db.Column(db.String(20)) # for promotions
    requested_status = db.Column(db.String(20)) # for on_leave, terminated
    salary = db.Column(db.Float)
    position = db.Column(db.String(100))
    department = db.Column(db.String(100))
    hire_date = db.Column(db.Date)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, approved, rejected
    admin_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_dhaka_time)

    # Specific relationships to avoid ambiguity
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('received_requests', lazy=True))
    requested_by = db.relationship('User', foreign_keys=[requested_by_id], backref=db.backref('made_requests', lazy=True))


class Attendance(db.Model):
    """Employee attendance tracking"""
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # present, absent, leave, half_day
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_dhaka_time)
    
    # Unique constraint to prevent duplicate attendance for same day
    __table_args__ = (db.UniqueConstraint('employee_id', 'date', name='_employee_date_uc'),)

