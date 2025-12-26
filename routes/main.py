from flask import Blueprint, render_template, request, jsonify, session
from models.models import MenuItem, Rating, Order, Reservation, EmployeeRequest
from extensions import db, cache

main_bp = Blueprint('main', __name__)

@main_bp.route('/api/dashboard/stats')
def dashboard_stats():
    # 1. Pending Orders
    orders_count = Order.query.filter(Order.status.in_(['Placed', 'Pending'])).count()
    
    # 2. Pending Reservations
    reservations_count = Reservation.query.filter_by(status='Pending').count()
    
    # 3. Out of Stock (Availability=False or Stock=0)
    out_of_stock_count = MenuItem.query.filter(
        db.or_(MenuItem.availability == False, MenuItem.stock_quantity <= 0)
    ).count()
    
    # 4. Pending Employee Requests
    employee_requests_count = EmployeeRequest.query.filter_by(status='pending').count()
    
    # 5. Manager: Absent/On Leave Today
    from datetime import date
    from models.models import Attendance
    absent_leave_count = Attendance.query.filter(
        Attendance.date == date.today(),
        Attendance.status.in_(['absent', 'leave', 'on_leave']) 
    ).count()
    
    return jsonify({
        'orders_count': orders_count,
        'reservations_count': reservations_count,
        'out_of_stock_count': out_of_stock_count,
        'employee_requests_count': employee_requests_count,
        'absent_leave_count': absent_leave_count
    })


def make_cache_key():
    """Create a cache key that includes the user identity to prevent shared caching between users."""
    user_id = session.get('user_id', 'anon')
    return f"{request.path}:{user_id}:{request.query_string.decode('utf-8')}"

def has_flash_messages():
    """Check if there are any flash messages in the session."""
    return '_flashes' in session

@main_bp.route('/')
@cache.cached(timeout=300, key_prefix=make_cache_key, unless=has_flash_messages)
def index():
    # Only available items on homepage, eager load ratings
    items = MenuItem.query.options(db.joinedload(MenuItem.ratings)).filter_by(availability=True).all()
    # Optimized category fetch
    cat_query = db.session.query(MenuItem.category).distinct().all()
    categories = sorted([c[0] or 'Uncategorized' for c in cat_query])

    return render_template('index.html', items=items, categories=categories)

@main_bp.route('/menu')
@cache.cached(timeout=300, key_prefix=make_cache_key, unless=has_flash_messages)
def menu():
    q = request.args.get('q', '').strip()
    cat = request.args.get('category', '').strip()
    query = MenuItem.query.options(db.joinedload(MenuItem.ratings))
    
    # Filter by name if search provided
    if q:
        query = query.filter(MenuItem.name.ilike(f'%{q}%'))
    
    # Filter by category
    if cat:
        query = query.filter_by(category=cat)
        
    items = query.all()
    
    # Optimized category fetch
    cat_query = db.session.query(MenuItem.category).distinct().all()
    categories = sorted([c[0] or 'Uncategorized' for c in cat_query])
    
    return render_template('menu.html', items=items, categories=categories, q=q, cat=cat)

@main_bp.route("/api/rate", methods=["POST"])
def rate_item():
    data = request.get_json()
    item_id = data.get("item_id")
    score = data.get("score")
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"success": False, "message": "Please log in to rate dishes."}), 401

    if not item_id or not score:
        return jsonify({"success": False, "message": "Missing item_id or score."}), 400

    try:
        score = int(score)
        if not (1 <= score <= 5):
            return jsonify({"success": False, "message": "Score must be between 1 and 5."}), 400
    except ValueError:
        return jsonify({"success": False, "message": "Score must be an integer."}), 400

    item = MenuItem.query.get(item_id)
    if not item:
        return jsonify({"success": False, "message": "Item not found."}), 404

    # Save new rating
    new_rating = Rating(
        item_id=item_id,
        user_id=user_id,
        score=score
    )
    db.session.add(new_rating)
    db.session.commit()

    return jsonify({
        "success": True, 
        "message": "Thank you for your rating!",
        "average": item.get_average_rating()
    })
