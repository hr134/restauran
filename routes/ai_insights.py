from flask import Blueprint, render_template, jsonify, request
from ai_features import predict_sales, get_top_products, get_sales_trend, get_stock_recommendations, get_customer_insights

ai_insights_bp = Blueprint('ai_insights', __name__, url_prefix='/ai-insights')

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

@ai_insights_bp.route('/')
@admin_required
def index():
    """AI insights dashboard"""
    # Get AI predictions and insights
    predictions = predict_sales()
    top_products = get_top_products(limit=10)
    trend_data = get_sales_trend(days=30)
    stock_recommendations = get_stock_recommendations()
    customer_insights = get_customer_insights()
    
    from flask import session
    template_folder = 'admin' if session.get('role') == 'admin' else 'manager'
    return render_template(f'{template_folder}/ai_insights.html',
                         predictions=predictions,
                         top_products=top_products,
                         trend_data=trend_data,
                         stock_recommendations=stock_recommendations,
                         customer_insights=customer_insights)

@ai_insights_bp.route('/api/predictions')
@admin_required
def api_predictions():
    """API endpoint for sales predictions"""
    predictions = predict_sales()
    return jsonify(predictions)

@ai_insights_bp.route('/api/top-products')
@admin_required
def api_top_products():
    """API endpoint for top products"""
    limit = int(request.args.get('limit', 5))
    top_products = get_top_products(limit=limit)
    return jsonify(top_products)

@ai_insights_bp.route('/api/stock-recommendations')
@admin_required
def api_stock_recommendations():
    """API endpoint for stock recommendations"""
    recommendations = get_stock_recommendations()
    return jsonify(recommendations)

@ai_insights_bp.route('/api/customer-insights')
@admin_required
def api_customer_insights():
    """API endpoint for customer insights"""
    insights = get_customer_insights()
    return jsonify(insights)
