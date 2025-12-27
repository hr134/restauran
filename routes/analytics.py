from flask import Blueprint, render_template, request, jsonify, make_response
from models.models import db, Order, SaleItem, MenuItem, User
from datetime import datetime, timedelta
from sqlalchemy import func
import csv
from io import StringIO

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

def admin_required(f):
    """Decorator to require admin or manager role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import session, flash, redirect, url_for
        if session.get('role') not in ['admin', 'manager']:
            flash('Access denied. Manager privileges required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@analytics_bp.route('/dashboard')
@admin_required
def dashboard():
    """Main analytics dashboard with sales trends and statistics"""
    from ai_features import get_sales_trend, get_top_products
    
    # Get date range from query params
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get orders in date range
    orders = Order.query.filter(Order.created_at >= start_date).all()
    
    # Calculate statistics
    total_revenue = sum(order.total for order in orders)
    total_orders = len(orders)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    
    # Today's statistics
    today = datetime.utcnow().date()
    today_orders = Order.query.filter(func.date(Order.created_at) == today).all()
    today_revenue = sum(order.total for order in today_orders)
    today_orders_count = len(today_orders)
    
    # Get trend data
    trend_result = get_sales_trend(days)
    trend_data = trend_result.get('trend_data', [])
    
    # Get top products
    top_products_result = get_top_products(limit=5)
    top_products = top_products_result.get('products', [])
    
    # Payment method breakdown
    payment_methods = db.session.query(
        Order.payment_method,
        func.count(Order.id).label('count'),
        func.sum(Order.total).label('total')
    ).filter(Order.created_at >= start_date).group_by(Order.payment_method).all()
    
    from flask import session
    template_folder = 'admin' if session.get('role') == 'admin' else 'manager'
    return render_template(f'{template_folder}/analytics_dashboard.html',
                         total_revenue=total_revenue,
                         total_orders=total_orders,
                         avg_order_value=avg_order_value,
                         today_revenue=today_revenue,
                         today_orders_count=today_orders_count,
                         trend_data=trend_data,
                         top_products=top_products,
                         payment_methods=payment_methods,
                         days=days)

@analytics_bp.route('/sales-report')
@admin_required
def sales_report():
    """Detailed sales report with filtering"""
    # Get date range from query params
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)
    
    orders = Order.query.filter(Order.created_at >= start_date).order_by(Order.created_at.desc()).all()
    
    total_revenue = sum(order.total for order in orders)
    total_orders = len(orders)
    
    # Top selling items
    top_items = db.session.query(
        MenuItem.name,
        func.sum(SaleItem.quantity).label('total_quantity'),
        func.sum(SaleItem.quantity * SaleItem.price_at_sale).label('total_revenue')
    ).join(SaleItem).join(Order).filter(
        Order.created_at >= start_date
    ).group_by(MenuItem.id).order_by(func.sum(SaleItem.quantity).desc()).limit(10).all()
    
    from flask import session
    template_folder = 'admin' if session.get('role') == 'admin' else 'manager'
    return render_template(f'{template_folder}/sales_report.html',
                         orders=orders,
                         total_revenue=total_revenue,
                         total_orders=total_orders,
                         top_items=top_items,
                         days=days)

@analytics_bp.route('/export-csv')
@admin_required
def export_csv():
    """Export sales data to CSV"""
    days = int(request.args.get('days', 30))
    start_date = datetime.utcnow() - timedelta(days=days)
    
    orders = Order.query.filter(Order.created_at >= start_date).all()
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Order ID', 'Date', 'Customer', 'Total Amount', 'Payment Method', 'Status'])
    
    for order in orders:
        customer = User.query.get(order.user_id)
        customer_name = customer.full_name or customer.username if customer else 'Unknown'
        writer.writerow([
            order.unique_order_number,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            customer_name,
            f'৳{order.total:.2f}',
            order.payment_method or 'N/A',
            order.status
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=sales_report_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@analytics_bp.route('/api/revenue-chart')
@admin_required
def revenue_chart_api():
    """API endpoint for revenue chart data"""
    days = int(request.args.get('days', 7))
    
    chart_data = []
    labels = []
    
    for i in range(days-1, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        day_orders = Order.query.filter(func.date(Order.created_at) == date).all()
        revenue = sum(order.total for order in day_orders)
        
        chart_data.append(revenue)
        labels.append(date.strftime('%m/%d'))
    
    return jsonify({
        'labels': labels,
        'data': chart_data
    })
